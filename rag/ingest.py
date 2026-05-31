import os
import csv
import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_CSV = ROOT / 'wiki_text_pulito.csv'
OUT_DIR = ROOT / 'rag_index'
OUT_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 1000


def chunk_text(text, max_chars=CHUNK_SIZE):
    text = text.replace('\n', ' ').strip()
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end].strip())
        start = end
    return chunks


def read_csv_rows(csv_path):
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def build_embeddings_and_index(model_name='all-MiniLM-L6-v2'):
    print('Loading CSV:', DATA_CSV)
    rows = read_csv_rows(DATA_CSV)
    docs = []
    for r in rows:
        # heuristics: prefer a column named 'text' or 'paragraph', otherwise join all text-like fields
        text = r.get('text') or r.get('paragraph') or r.get('description') or ''
        if not text:
            # fallback: join all fields
            text = ' '.join([v for v in r.values() if v])
        city = r.get('city') or r.get('citta') or r.get('city_name') or ''
        source = r.get('source') or ''
        for chunk in chunk_text(text):
            docs.append({'text': chunk, 'city': city, 'source': source})

    print(f'Prepared {len(docs)} text chunks')
    model = SentenceTransformer(model_name)
    texts = [d['text'] for d in docs]
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    # normalize embeddings for cosine similarity via inner product
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, str(OUT_DIR / 'index.faiss'))
    # save docs metadata
    with open(OUT_DIR / 'docs.json', 'w', encoding='utf-8') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

    print('Saved index and docs to', OUT_DIR)
    return len(docs)


if __name__ == '__main__':
    build_embeddings_and_index()
