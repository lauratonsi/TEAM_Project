
## Model download helper

To download a GGML model locally, run:

```bash
./scripts/download_model.sh <MODEL_URL> /absolute/path/to/ELABORAZIONE/models/your-model.ggml
```

Example (replace with a valid URL you are authorized to download from):

```bash
./scripts/download_model.sh https://example.com/path/to/ggml-alpaca-7b-q4.bin
```

After download, set `LOCAL_LLM_MODEL_PATH` in your `.env` or environment and restart the API.
# Minimal internal RAG backend

This scaffold adds a minimal internal Retrieval-Augmented Generation backend using:
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

Default simulated RAG

This service can run in a lightweight simulated RAG mode without any external model. It retrieves the top matching chunks from the local index and then generates a concise answer using local heuristics.

Use the URL parameter `simulated_rag=true` to enable it:

```bash
curl "http://127.0.0.1:8000/query?q=Che%20posti%20consigli%20a%20Roma&simulated_rag=true"
```

The response includes both a generated answer and the source chunks it relied on.

Optional real LLM synthesis

Optional: if you set `OPENAI_API_KEY` in the environment and call `/query?use_llm=true`, the service will synthesize an answer with the configured OpenAI model.

Local LLM (no API keys)

This scaffold supports running a local LLM instead of using external APIs. Steps:

1. Install `llama-cpp-python` (already in `requirements.txt`).
2. Download a compatible model (GGML format) and place it somewhere on the server, e.g. `/models/your-model.ggml`.
3. Set the environment variable `LOCAL_LLM_MODEL_PATH` to the model path.
4. Call the API with `use_local_llm=true`, for example:

```bash
curl "http://127.0.0.1:8000/query?q=Che%20posti%20consigli%20a%20Roma&use_local_llm=true"
```

Notes:
- Local models can be large (GBs) and may require CPU/GPU resources.
- If no local model is configured, the API will return an error telling you to set `LOCAL_LLM_MODEL_PATH`.
