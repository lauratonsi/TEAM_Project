import json
import re
from pathlib import Path
from lxml import etree
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
XML_DIR = ROOT / 'data' / 'xml_dataset'
OUT_DIR = ROOT / 'rag_index'
OUT_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def chunk_text(text, max_chars=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = text.replace('\n', ' ').strip()
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ''
    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_chars:
            current = (current + ' ' + sent).strip() if current else sent
        else:
            if current:
                chunks.append(current)
            if len(sent) > max_chars:
                for i in range(0, len(sent), max_chars - overlap):
                    chunks.append(sent[i:i + max_chars].strip())
                current = sent[max(0, len(sent) - overlap):]
            else:
                current = sent
    if current:
        chunks.append(current)
    if overlap and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:].strip()
            overlapped.append((tail + ' ' + chunks[i]).strip() if tail else chunks[i])
        return overlapped
    return chunks


def build_embeddings_and_index(model_name='all-MiniLM-L6-v2'):
    if not XML_DIR.exists():
        raise FileNotFoundError(f'XML directory not found: {XML_DIR}')

    xml_files = sorted(XML_DIR.glob('*.xml'))
    print(f'Loading {len(xml_files)} XML files from {XML_DIR}')

    docs = []

    for xml_file in xml_files:
        try:
            tree = etree.parse(str(xml_file))
            root = tree.getroot()
        except Exception as e:
            print(f'  ⚠️  Skipping {xml_file.name}: {e}')
            continue

        city = (root.findtext('metadata/title') or xml_file.stem).upper()

        def add(text, section):
            if not text or not text.strip():
                return
            for chunk in chunk_text(text.strip()):
                docs.append({
                    'text': f'[{city}] {chunk}',
                    'city': city,
                    'section': section,
                    'source': xml_file.name,
                })

        # Transport
        add(root.findtext('transport'), 'transport')

        # Hotels
        hotels = root.xpath('.//accommodation/hotel')
        if hotels:
            hotel_parts = [
                f"{h.findtext('name')} ({h.findtext('price') or 'N/D'})"
                for h in hotels if h.findtext('name')
            ]
            if hotel_parts:
                add('Hotel e alloggi: ' + '; '.join(hotel_parts), 'hotels')

        # Districts — one chunk per district (long descriptions get split)
        for district in root.xpath('.//districts/district'):
            name = district.findtext('name') or ''
            desc = district.findtext('description') or ''
            if name:
                add(f'Quartiere {name}: {desc}', 'districts')

        # Strategic description (Italian summary)
        add(root.findtext('description'), 'description')

        # Wiki intro (often long — will be chunked)
        add(root.findtext('wiki_intro'), 'wiki_intro')

        # Attractions
        attractions = root.xpath('.//highlights/attraction')
        if attractions:
            parts = [
                f"{a.findtext('name')}: {a.findtext('description')}"
                for a in attractions if a.findtext('name')
            ]
            if parts:
                add('Attrazioni: ' + '; '.join(parts), 'attractions')

        # Nightlife
        venues = root.xpath('.//nightlife/venue')
        if venues:
            venue_parts = [
                f"{v.findtext('name')} ({v.findtext('category') or 'bar'})"
                for v in venues if v.findtext('name')
            ]
            if venue_parts:
                add('Bar e locali notturni: ' + '; '.join(venue_parts), 'nightlife')

    print(f'Prepared {len(docs)} text chunks from {len(xml_files)} cities')

    model = SentenceTransformer(model_name)
    texts = [d['text'] for d in docs]
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, str(OUT_DIR / 'index.faiss'))
    with open(OUT_DIR / 'docs.json', 'w', encoding='utf-8') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

    print(f'Saved index and docs to {OUT_DIR}')
    return len(docs)


if __name__ == '__main__':
    build_embeddings_and_index()
