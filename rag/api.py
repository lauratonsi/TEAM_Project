import os
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import re

from . import ingest, vectorstore

app = FastAPI(title='Minimal RAG Service')

# load .env if present
load_dotenv()

# Allow cross-origin requests from the frontend. In production, restrict this to your domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    q: str
    k: Optional[int] = 5
    use_llm: Optional[bool] = False


CITY_ALIASES = {
    'roma': 'ROME',
    'londra': 'LONDON',
    'parigi': 'PARIS',
    'bruxelles': 'BRUSSELS',
    'castel': 'PRAGUE',
    'praga': 'PRAGUE',
    'copenaghen': 'COPENHAGEN',
    'dublino': 'DUBLIN',
    'lussemburgo': 'LUXEMBOURG',
    'zagabria': 'ZAGREB',
    'nijmegen': 'AMSTERDAM',
    'vienna': 'VIENNA',
    'budapest': 'BUDAPEST',
    'sofia': 'SOFIA',
    'oslo': 'OSLO',
    'talinn': 'TALLINN',
    'porto': 'OOSTENDA',
    'lisbona': 'LISBON',
    'nicosia': 'NICOSIA',
    'vilnius': 'VILNIUS',
    'reykjavik': 'REYKJAVIK',
    'bratislava': 'BRATISLAVA',
}

CITY_LOOKUP = {
    **{k.lower(): v for k, v in CITY_ALIASES.items()},
    **{v.lower(): v for v in set(CITY_ALIASES.values())},
}
CITY_PATTERN = re.compile(r"\b(" + r"|".join(sorted(map(re.escape, CITY_LOOKUP.keys()), key=len, reverse=True)) + r")\b", re.I)


def extract_city(text: str) -> str:
    text = (text or '').strip()
    if not text:
        return ''
    first_token = text.split(None, 1)[0]
    if first_token.isalpha() and len(first_token) <= 20:
        return first_token.upper()
    match = CITY_PATTERN.search(text)
    if match:
        return CITY_LOOKUP[match.group(1).lower()]
    return ''


def find_query_city(query: str) -> str:
    query_lower = query.lower()
    for token, city in CITY_LOOKUP.items():
        if re.search(rf"\b{re.escape(token)}\b", query_lower):
            return city
    return ''


def simulated_rag_answer(query: str, results: list[dict], max_sentences: int = 3) -> tuple[str, list[dict]]:
    if not results:
        return '', []
    tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
    topic_keywords = {
        'aeroporto': 4,
        'alloggio': 3,
        'hotel': 4,
        'hostel': 3,
        'b&b': 3,
        'bus': 2,
        'tram': 2,
        'metro': 2,
        'tren': 2,
        'sicurezza': 3,
        'sicuro': 3,
        'verde': 2,
        'parco': 2,
        'centro': 2,
        'attrazion': 2,
        'museo': 2,
        'ristor': 2,
        'ristorante': 2,
        'cibo': 2,
        'costo': 2,
        'budget': 2,
        'spesa': 2,
        'trasporto': 3,
        'trasporti': 3,
        'aeroporti': 3,
        'taxi': 2,
    }
    query_city = find_query_city(query)
    if query_city:
        city_results = [r for r in results if extract_city(r.get('text', '')) == query_city]
        if not city_results:
            _, all_docs = vectorstore.load_index()
            city_results = [d for d in all_docs if extract_city(d.get('text', '')) == query_city]
        if city_results:
            results = city_results
    scored_results = []
    for r in results:
        text_lower = r.get('text', '').lower()
        score = 0
        if query_city and query_city.lower() in text_lower:
            score += 5
        if extract_city(r.get('text', '')) == query_city:
            score += 3
        for t in tokens:
            if re.search(rf"\b{re.escape(t)}\b", text_lower):
                score += 2
        for keyword, weight in topic_keywords.items():
            if keyword in text_lower:
                score += weight
        score += min(3, float(r.get('score', 0)) * 10)
        scored_results.append((score, r))
    scored_results.sort(key=lambda item: (-item[0], -item[1].get('score', 0)))
    top_results = [item[1] for item in scored_results[:5]] if scored_results else results[:5]

    accommodation_terms = {'hotel', 'hostel', 'alloggio', 'albergo', 'b&b'}
    wants_accommodation = any(term in tokens for term in accommodation_terms)
    if query_city and wants_accommodation:
        city_docs = [r for r in top_results if extract_city(r.get('text', '')) == query_city]
        if city_docs and not any(any(term in r.get('text', '').lower() for term in accommodation_terms) for r in city_docs):
            return f"Ho trovato informazioni locali su {query_city}, ma il dataset non contiene dettagli specifici sugli hotel per quella città.", top_results

    matches = []
    for r in top_results:
        text = r.get('text', '').replace('\n', ' ').strip()
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            if not sentence:
                continue
            sentence_lower = sentence.lower()
            sentence_score = 0
            if query_city and query_city.lower() in sentence_lower:
                sentence_score += 2
            sentence_score += sum(2 for t in tokens if re.search(rf"\b{re.escape(t)}\b", sentence_lower))
            sentence_score += sum(weight for keyword, weight in topic_keywords.items() if keyword in sentence_lower)
            if sentence_score > 0:
                matches.append((sentence_score, len(sentence), sentence.strip()))
    if matches:
        matches.sort(key=lambda item: (-item[0], item[1]))
        selected = []
        seen = set()
        for _, _, sentence in matches:
            if len(selected) >= max_sentences:
                break
            if sentence in seen:
                continue
            selected.append(sentence)
            seen.add(sentence)
        header = f"Informazioni utili{(' su ' + query_city) if query_city else ''}: "
        return header + ' '.join(selected), top_results

    best_doc = top_results[0]
    best_text = best_doc.get('text', '').replace('\n', ' ').strip()
    excerpt = best_text[:450].rstrip()
    return f"Ecco un estratto utile{(' su ' + query_city) if query_city else ''}: {excerpt}", top_results


@app.post('/ingest')
def run_ingest():
    count = ingest.build_embeddings_and_index()
    return {'status': 'ok', 'chunks_indexed': count}


@app.get('/query')
def query(q: str = Query(..., description='Query text'), k: int = 5, use_llm: bool = False, simulated_rag: bool = False):
    if simulated_rag:
        internal_results = vectorstore.search(q, k=max(k, 50))
        answer, sources = simulated_rag_answer(q, internal_results)
        return {'answer': answer, 'sources': sources[:k]}
    results = vectorstore.search(q, k=k)

    if use_llm and os.getenv('OPENAI_API_KEY'):
        try:
            import openai
            openai.api_key = os.getenv('OPENAI_API_KEY')
            model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
            context = '\n\n'.join([f"Source {i+1}: {r['text']}" for i, r in enumerate(results)])
            prompt = f"You are an assistant. Use the following sources to answer the question:\n\n{context}\n\nQuestion: {q}\n\nAnswer concisely and cite source numbers."
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=512,
                temperature=0.2,
            )
            answer = resp['choices'][0]['message']['content']
            return {'answer': answer, 'sources': results}
        except Exception as e:
            return {'error': str(e), 'sources': results}
    return {'query': q, 'results': results}


@app.get('/health')
def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    uvicorn.run('rag.api:app', host='127.0.0.1', port=8000, reload=True)
