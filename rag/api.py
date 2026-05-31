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


def simulated_rag_answer(query: str, results: list[dict], max_sentences: int = 3) -> str:
    if not results:
        return ''
    tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
    # Prefer the chunk with the most exact query-term matches for the simulated answer.
    scored_results = []
    for r in results:
        text_lower = r.get('text', '').lower()
        score = 0
        for t in tokens:
            if re.search(rf"\b{re.escape(t)}\b", text_lower):
                score += 1
        scored_results.append((score, r))
    if scored_results:
        best_score, best_result = max(scored_results, key=lambda x: x[0])
        if best_score > 0:
            results = [best_result]
    matches = []
    for r in results:
        text = r.get('text', '').replace('\n', ' ').strip()
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for s in sentences:
            if not s:
                continue
            lower = s.lower()
            score = sum(1 for t in tokens if t in lower)
            if score > 0:
                matches.append((score, len(s), s.strip()))
    if not matches:
        return results[0].get('text', '')[:600]
    matches.sort(key=lambda x: (-x[0], x[1]))
    selected = []
    seen = set()
    for _, _, sentence in matches:
        if len(selected) >= max_sentences:
            break
        if sentence in seen:
            continue
        selected.append(sentence)
        seen.add(sentence)
    return ' '.join(selected)


@app.post('/ingest')
def run_ingest():
    count = ingest.build_embeddings_and_index()
    return {'status': 'ok', 'chunks_indexed': count}


@app.get('/query')
def query(q: str = Query(..., description='Query text'), k: int = 5, use_llm: bool = False, use_local_llm: bool = False, simulated_rag: bool = False):
    results = vectorstore.search(q, k=k)
    if simulated_rag:
        answer = simulated_rag_answer(q, results)
        return {'answer': answer, 'sources': results}

    # local LLM option (no API key)
    if use_local_llm:
        model_path = os.getenv('LOCAL_LLM_MODEL_PATH')
        if not model_path:
            return {'error': 'LOCAL_LLM_MODEL_PATH not set', 'sources': results}
        try:
            from llama_cpp import Llama
            llama = Llama(model_path=model_path)
            context = '\n\n'.join([f"Source {i+1}: {r['text']}" for i, r in enumerate(results)])
            prompt = f"You are an assistant. Use the following sources to answer the question:\n\n{context}\n\nQuestion: {q}\n\nAnswer concisely and cite source numbers."
            resp = llama.create(prompt=prompt, max_tokens=512, stop=None)
            # llama_cpp returns 'choices' with 'text'
            answer = resp['choices'][0]['text'] if 'choices' in resp and resp['choices'] else resp.get('text', '')
            return {'answer': answer, 'sources': results}
        except Exception as e:
            return {'error': f'local LLM error: {e}', 'sources': results}

    # optionally call OpenAI to synthesize an answer
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
