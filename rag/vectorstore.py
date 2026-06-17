import json
import re
from pathlib import Path
from typing import Optional
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'rag_index'

_model = None
_index = None
_docs = None
_bm25 = None


def get_model(name='all-MiniLM-L6-v2'):
    global _model
    if _model is None:
        _model = SentenceTransformer(name)
    return _model


def _tokenize(text: str) -> list[str]:
    return re.findall(r'\w+', text.lower())


def load_index():
    global _index, _docs, _bm25
    if _index is not None:
        return _index, _docs
    idx_path = OUT_DIR / 'index.faiss'
    docs_path = OUT_DIR / 'docs.json'
    if not idx_path.exists() or not docs_path.exists():
        raise FileNotFoundError('Index or docs not found. Run ingest first.')
    _index = faiss.read_index(str(idx_path))
    with open(docs_path, encoding='utf-8') as f:
        _docs = json.load(f)
    _bm25 = BM25Okapi([_tokenize(d['text']) for d in _docs])
    return _index, _docs


def search(query, k=5, model_name='all-MiniLM-L6-v2'):
    index, docs = load_index()
    model = get_model(model_name)
    q_emb = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(q_emb)
    D, I = index.search(q_emb, k)
    results = []
    for score, idx in zip(D[0], I[0]):
        if idx < 0:
            continue
        item = docs[idx].copy()
        item['score'] = float(score)
        results.append(item)
    return results


def _passes(doc: dict, filters: dict) -> bool:
    """True if a chunk's structured metadata satisfies all filter dimensions."""
    meta = doc.get('meta', {})
    if 'region' in filters and meta.get('region') != filters['region']:
        return False
    if 'currency' in filters:
        is_eur = meta.get('currency') == 'EUR'
        if filters['currency'] == 'eur' and not is_eur:
            return False
        if filters['currency'] == 'other' and is_eur:
            return False
    if 'category' in filters:
        cats = doc.get('categories')
        if not cats or filters['category'] not in cats:
            return False
    for key in ('appeal', 'safety', 'green', 'price'):
        if key in filters:
            mv = meta.get(key)
            if mv is None:
                return False
            op, val = filters[key]['op'], filters[key]['val']
            if op == '>=' and not (mv >= val):
                return False
            if op == '<=' and not (mv <= val):
                return False
    return True


def hybrid_search(query: str, k: int = 5, alpha: float = 0.5, model_name: str = 'all-MiniLM-L6-v2',
                  filters: Optional[dict] = None) -> list[dict]:
    """Reciprocal Rank Fusion of vector search and BM25, with optional metadata pre-filter.

    When ``filters`` is given, the candidate set is restricted to chunks whose injected
    structured metadata (region / currency / category / numeric indicators) satisfies the
    constraints BEFORE fusion — i.e. semantic search runs only inside the matching subset.
    """
    index, docs = load_index()
    model = get_model(model_name)
    candidate_k = min(max(k * 4, 20), len(docs))

    # --- metadata pre-filter (allowed index set) ---
    allowed = None
    if filters:
        allowed = {i for i, d in enumerate(docs) if _passes(d, filters)}
        if not allowed:
            return []
        # with a filter active the eligible pool is small → consider every allowed doc
        candidate_k = len(docs)

    # --- vector search ---
    q_emb = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(q_emb)
    D, I = index.search(q_emb, candidate_k)
    vec_hits = {int(idx): float(score) for score, idx in zip(D[0], I[0])
                if idx >= 0 and (allowed is None or int(idx) in allowed)}

    # --- BM25 search ---
    bm25_scores = _bm25.get_scores(_tokenize(query))
    bm25_pool = range(len(docs)) if allowed is None else allowed
    bm25_ranked = sorted(bm25_pool, key=lambda i: bm25_scores[i], reverse=True)[:candidate_k]

    # --- Reciprocal Rank Fusion (RRF, k=60) ---
    rrf: dict[int, float] = {}
    for rank, idx in enumerate(sorted(vec_hits, key=lambda i: -vec_hits[i])):
        rrf[idx] = rrf.get(idx, 0) + alpha / (rank + 60)
    for rank, idx in enumerate(bm25_ranked):
        rrf[idx] = rrf.get(idx, 0) + (1 - alpha) / (rank + 60)

    top_k = sorted(rrf, key=lambda i: -rrf[i])[:k]
    results = []
    for idx in top_k:
        item = docs[idx].copy()
        item['score'] = vec_hits.get(idx, 0.0)
        item['rrf_score'] = rrf[idx]
        results.append(item)
    return results
