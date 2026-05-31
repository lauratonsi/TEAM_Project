import json
from pathlib import Path
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'rag_index'

_model = None


def get_model(name='all-MiniLM-L6-v2'):
    global _model
    if _model is None:
        _model = SentenceTransformer(name)
    return _model


def load_index():
    idx_path = OUT_DIR / 'index.faiss'
    docs_path = OUT_DIR / 'docs.json'
    if not idx_path.exists() or not docs_path.exists():
        raise FileNotFoundError('Index or docs not found. Run ingest first.')
    index = faiss.read_index(str(idx_path))
    with open(docs_path, encoding='utf-8') as f:
        docs = json.load(f)
    return index, docs


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
