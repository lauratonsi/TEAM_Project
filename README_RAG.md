# Minimal internal RAG backend

This scaffold provides a lightweight Retrieval-Augmented Generation backend using:
- `sentence-transformers` for embeddings
- `faiss` for vector similarity search
- `FastAPI` for a small query/ingest API

Quick start

1. Create / activate your virtualenv and install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Build the index from `wiki_text_pulito.csv`:

```bash
python -m rag.ingest
```

3. Run the API server:

```bash
python -m rag.api
```

4. Query the index:

GET http://127.0.0.1:8000/query?q=your+question

Simulated RAG mode

This service can run in a lightweight simulated RAG mode without any external model. It retrieves the top matching chunks from the local index and then generates a concise answer using local heuristics.

Use the URL parameter `simulated_rag=true` to enable it:

```bash
curl "http://127.0.0.1:8000/query?q=Che%20posti%20consigli%20a%20Roma&simulated_rag=true"
```

The response includes both a generated answer and the source chunks it relied on.

Optional OpenAI synthesis

If you set `OPENAI_API_KEY` in the environment and call `/query?use_llm=true`, the service will optionally synthesize an answer with the configured OpenAI model.

```bash
curl "http://127.0.0.1:8000/query?q=Che%20posti%20consigli%20a%20Roma&use_llm=true"
```

Notes:
- This version is optimized for local retrieval and simulated RAG, without requiring heavy GGML model downloads.
- The local OpenAI path is optional and only works if `OPENAI_API_KEY` is configured.
