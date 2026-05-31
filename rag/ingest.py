import csv
import json
import re
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_CSV = ROOT / 'wiki_text_pulito.csv'
OUT_DIR = ROOT / 'rag_index'
OUT_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def chunk_text(text, max_chars=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = text.replace('\n', ' ').strip()
    if len(text) <= max_chars:
        return [text]
    # split on sentence boundaries first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ''
    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_chars:
            current = (current + ' ' + sent).strip() if current else sent
        else:
            if current:
                chunks.append(current)
            # if a single sentence exceeds max_chars, split it hard
            if len(sent) > max_chars:
                for i in range(0, len(sent), max_chars - overlap):
                    chunks.append(sent[i:i + max_chars].strip())
                current = sent[max(0, len(sent) - overlap):]
            else:
                current = sent
    if current:
        chunks.append(current)
    # add overlap: prepend tail of previous chunk to each chunk
    if overlap and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:].strip()
            overlapped.append((tail + ' ' + chunks[i]).strip() if tail else chunks[i])
        return overlapped
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
        # use actual CSV columns; fall back gracefully if schema differs
        city = r.get('City') or r.get('city') or r.get('citta') or r.get('city_name') or ''
        source = r.get('source') or ''
        parts = [
            r.get('Transport_Text') or '',
            r.get('Districts') or '',
            r.get('Hotels_Extracted') or '',
            r.get('text') or r.get('paragraph') or r.get('description') or '',
        ]
        text = ' '.join(p for p in parts if p).strip()
        if not text:
            text = ' '.join(v for v in r.values() if v)
        for chunk in chunk_text(text):
            # prefix city name so BM25 and keyword matching benefit from it
            prefixed = f"[{city}] {chunk}" if city else chunk
            docs.append({'text': prefixed, 'city': city, 'source': source})

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
