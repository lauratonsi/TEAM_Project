import os
import httpx
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import re

from . import ingest, vectorstore

app = FastAPI(title='Minimal RAG Service')

load_dotenv()

OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2')

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
    'rome': 'ROME',
    'londra': 'LONDON',
    'london': 'LONDON',
    'parigi': 'PARIS',
    'paris': 'PARIS',
    'bruxelles': 'BRUSSELS',
    'brussels': 'BRUSSELS',
    'praga': 'PRAGUE',
    'prague': 'PRAGUE',
    'copenaghen': 'COPENHAGEN',
    'copenhagen': 'COPENHAGEN',
    'dublino': 'DUBLIN',
    'dublin': 'DUBLIN',
    'lussemburgo': 'LUXEMBOURG',
    'luxembourg': 'LUXEMBOURG',
    'zagabria': 'ZAGREB',
    'zagreb': 'ZAGREB',
    'amsterdam': 'AMSTERDAM',
    'vienna': 'VIENNA',
    'budapest': 'BUDAPEST',
    'sofia': 'SOFIA',
    'oslo': 'OSLO',
    'tallinn': 'TALLINN',
    'talinn': 'TALLINN',
    'lisbona': 'LISBON',
    'lisbon': 'LISBON',
    'nicosia': 'NICOSIA',
    'vilnius': 'VILNIUS',
    'reykjavik': 'REYKJAVIK',
    'bratislava': 'BRATISLAVA',
    # Previously missing capitals
    'atene': 'ATHENS',
    'athens': 'ATHENS',
    'berlino': 'BERLIN',
    'berlin': 'BERLIN',
    'bucarest': 'BUCHAREST',
    'bucharest': 'BUCHAREST',
    'helsinki': 'HELSINKI',
    'lubiana': 'LJUBLJANA',
    'ljubljana': 'LJUBLJANA',
    'madrid': 'MADRID',
    'riga': 'RIGA',
    'stoccolma': 'STOCKHOLM',
    'stockholm': 'STOCKHOLM',
    'valletta': 'VALLETTA',
    'la valletta': 'VALLETTA',
    'varsavia': 'WARSAW',
    'warsaw': 'WARSAW',
}

CITY_LOOKUP = {k.lower(): v for k, v in CITY_ALIASES.items()}
CITY_PATTERN = re.compile(
    r"\b(" + r"|".join(sorted(map(re.escape, CITY_LOOKUP.keys()), key=len, reverse=True)) + r")\b",
    re.I,
)

# Intent keyword sets
_INTENT_KEYWORDS = {
    'transport': {'aeroporto', 'aeroporti', 'bus', 'tram', 'metro', 'treno', 'taxi', 'trasporto', 'trasporti',
                  'transport', 'gira', 'girare', 'muoversi', 'spostarsi', 'mobilità', 'raggiungere', 'arrivare',
                  'arrivo', 'partenza', 'stazione', 'fermata', 'volo', 'volare'},
    'hotel': {'hotel', 'hostel', 'alloggio', 'albergo', 'b&b', 'ostello', 'accommodation', 'dormire', 'pernottare'},
    'attractions': {'museo', 'musei', 'monumento', 'monumenti', 'piazza', 'attrazioni', 'vedere', 'visitare',
                    'colosseo', 'vaticano', 'chiesa', 'palazzo', 'parco', 'tour', 'turismo', 'fare', 'cosa'},
    'safety': {'sicurezza', 'sicuro', 'pericolo', 'criminalità', 'pericoloso', 'rischio', 'rischioso'},
}


def extract_city(text: str) -> str:
    match = CITY_PATTERN.search(text or '')
    return CITY_LOOKUP[match.group(1).lower()] if match else ''


def detect_intent(query: str) -> str:
    q = query.lower()
    tokens = set(re.findall(r'\w+', q))
    scores = {intent: len(tokens & kw) for intent, kw in _INTENT_KEYWORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else 'general'


def ollama_synthesize(query: str, chunks: list[dict]) -> Optional[str]:
    """Use Ollama to synthesize a natural-language answer from retrieved chunks.
    Returns None if Ollama is unavailable, so the caller can fall back gracefully."""
    if not chunks:
        return None
    context = "\n\n".join(
        f"[{c.get('city', '')} — {c.get('section', '')}]\n{c.get('text', '')}"
        for c in chunks[:5]
    )
    prompt = (
        "Sei un assistente specializzato nelle capitali europee. "
        "Rispondi SOLO in italiano, in modo conciso (max 4 frasi), "
        "usando esclusivamente le informazioni nelle fonti sottostanti. "
        "Se le fonti non contengono la risposta, dillo chiaramente.\n\n"
        f"Fonti:\n{context}\n\n"
        f"Domanda: {query}\n\n"
        "Risposta:"
    )
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=30.0,
        )
        if resp.status_code == 200:
            text = resp.json().get("response", "").strip()
            return text if text else None
    except Exception:
        pass
    return None


_INTENT_WEIGHTS: dict[str, dict[str, int]] = {
    'transport': {'aeroporto': 5, 'aeroporti': 5, 'bus': 4, 'tram': 4, 'metro': 4, 'treno': 4, 'taxi': 3, 'trasporto': 4, 'trasporti': 4},
    'hotel': {'hotel': 5, 'hostel': 4, 'alloggio': 5, 'albergo': 4, 'b&b': 4, 'ostello': 4},
    'attractions': {'museo': 4, 'musei': 4, 'monumento': 4, 'piazza': 3, 'vedere': 5, 'visitare': 5, 'colosseo': 5, 'vaticano': 4},
    'safety': {'sicurezza': 5, 'sicuro': 4, 'pericolo': 4, 'criminalità': 4},
    'general': {'attrazioni': 3, 'costo': 2, 'budget': 2, 'spesa': 2, 'verde': 2, 'parco': 2},
}

_INTENT_SECTION = {
    'transport': 'transport',
    'hotel': 'hotels',
    'attractions': 'attractions',
    'safety': 'description',
    'general': None,
}


def rank_chunks(query: str, results: list[dict], k: int = 5) -> list[dict]:
    """Score and rank chunks by relevance to query. Used by Ollama synthesis path."""
    if not results:
        return []
    tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
    intent = detect_intent(query)
    intent_section = _INTENT_SECTION.get(intent)
    topic_keywords = {**_INTENT_WEIGHTS.get(intent, {}), **_INTENT_WEIGHTS['general']}

    query_city = extract_city(query)
    pool = results
    if query_city:
        city_results = [r for r in results if r.get('city', '').upper() == query_city]
        if not city_results:
            _, all_docs = vectorstore.load_index()
            city_results = [d for d in all_docs if d.get('city', '').upper() == query_city]
        if city_results:
            pool = city_results

    scored = []
    for r in pool:
        text_lower = r.get('text', '').lower()
        score = 0
        if r.get('city', '').upper() == query_city:
            score += 6
        if intent_section and r.get('section') == intent_section:
            score += 8
        for t in tokens:
            if re.search(rf"\b{re.escape(t)}\b", text_lower):
                score += 2
        for keyword, weight in topic_keywords.items():
            if keyword in text_lower:
                score += weight
        score += min(3, float(r.get('rrf_score', r.get('score', 0))) * 10)
        scored.append((score, r))
    scored.sort(key=lambda x: (-x[0], -x[1].get('rrf_score', x[1].get('score', 0))))
    return [r for _, r in scored[:k]]


def simulated_rag_answer(query: str, results: list[dict], max_sentences: int = 3) -> tuple[str, list[dict]]:
    if not results:
        return '', []
    tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
    intent = detect_intent(query)

    topic_keywords = {**_INTENT_WEIGHTS.get(intent, _INTENT_WEIGHTS['general']), **_INTENT_WEIGHTS['general']}

    accommodation_terms = {'hotel', 'hostel', 'alloggio', 'albergo', 'b&b'}
    wants_accommodation = intent == 'hotel' or any(term in tokens for term in accommodation_terms)

    intent_section = _INTENT_SECTION.get(intent)

    query_city = extract_city(query)
    if query_city:
        city_results = [r for r in results if r.get('city', '').upper() == query_city]
        if not city_results:
            _, all_docs = vectorstore.load_index()
            city_results = [d for d in all_docs if d.get('city', '').upper() == query_city]
        if city_results:
            results = city_results

    scored_results = []
    for r in results:
        text_lower = r.get('text', '').lower()
        score = 0
        if r.get('city', '').upper() == query_city:
            score += 6
        if intent_section and r.get('section') == intent_section:
            score += 8
        for t in tokens:
            if re.search(rf"\b{re.escape(t)}\b", text_lower):
                score += 2
        for keyword, weight in topic_keywords.items():
            if keyword in text_lower:
                score += weight
        score += min(3, float(r.get('rrf_score', r.get('score', 0))) * 10)
        scored_results.append((score, r))
    scored_results.sort(key=lambda item: (-item[0], -item[1].get('rrf_score', item[1].get('score', 0))))
    top_results = [item[1] for item in scored_results[:5]] if scored_results else results[:5]

    if query_city and wants_accommodation:
        city_docs = [r for r in top_results if extract_city(r.get('text', '')) == query_city
                     or r.get('city', '').upper() == query_city]
        if city_docs and not any(any(term in r.get('text', '').lower() for term in accommodation_terms) for r in city_docs):
            display_city = query_city.title()
            return f"Ho trovato informazioni locali su {display_city}, ma il dataset non contiene dettagli specifici sugli hotel per quella città.", top_results

    # Se il chunk #1 matcha già la sezione cercata, usalo direttamente (evita sentence mixing)
    if intent_section and top_results and top_results[0].get('section') == intent_section:
        text = top_results[0].get('text', '').replace('\n', ' ').strip()
        text = re.sub(r'^\[[A-Z\s]+\]\s*', '', text)
        excerpt = text[:450].rstrip()
        last_stop = max(excerpt.rfind('.'), excerpt.rfind('!'), excerpt.rfind('?'))
        if last_stop > 80:
            excerpt = excerpt[:last_stop + 1]
        display_city = query_city.title() if query_city else ''
        header = f"Informazioni su {display_city}: " if display_city else ""
        return header + excerpt, top_results

    matches = []
    for r in top_results:
        text = r.get('text', '').replace('\n', ' ').strip()
        text = re.sub(r'^\[[A-Z\s]+\]\s*', '', text)  # strip [CITY] prefix
        normalized = re.sub(r'\s*\|\s*', '. ', text)
        sentences = re.split(r'(?<=[.!?])\s+', normalized)
        for sentence in sentences:
            if not sentence:
                continue
            sentence_lower = sentence.lower()
            sentence_score = 0
            if query_city and query_city.lower() in sentence_lower:
                sentence_score += 2
            sentence_score += sum(2 for t in tokens if re.search(rf"\b{re.escape(t)}\b", sentence_lower))
            sentence_score += sum(weight for keyword, weight in topic_keywords.items() if keyword in sentence_lower)
            if not wants_accommodation and any(term in sentence_lower for term in accommodation_terms):
                continue
            has_topic = any(keyword in sentence_lower for keyword in topic_keywords)
            if sentence_score > 0 and (len(sentence.split()) > 3 or has_topic):
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
        display_city = query_city.title() if query_city else ''
        header = f"Informazioni utili{(' su ' + display_city) if display_city else ''}: "
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
        internal_results = vectorstore.hybrid_search(q, k=max(k, 50))
        top_chunks = rank_chunks(q, internal_results, k=k)
        answer = ollama_synthesize(q, top_chunks)
        if not answer:
            answer, _ = simulated_rag_answer(q, internal_results)
        return {'answer': answer, 'sources': top_chunks}

    results = vectorstore.hybrid_search(q, k=k)

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
    ollama_ok = False
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2.0)
        ollama_ok = r.status_code == 200
    except Exception:
        pass
    return {'status': 'ok', 'ollama': ollama_ok, 'ollama_model': OLLAMA_MODEL}


if __name__ == '__main__':
    uvicorn.run('rag.api:app', host='127.0.0.1', port=8000, reload=True)
