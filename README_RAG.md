# RAG — Virtual Analyst backend

Sistema RAG (Retrieval-Augmented Generation) interno per query in linguaggio naturale sulle 30 capitali europee del dataset.

## Architettura

```
data/xml_dataset/*.xml  →  rag/ingest.py  →  rag_index/
                                                  ├── index.faiss   (384-dim, IndexFlatIP)
                                                  └── docs.json     (442 chunk con metadati)
                                                       ↓
                                              rag/vectorstore.py    (FAISS + BM25Okapi, RRF)
                                                       ↓
                                              rag/api.py            (FastAPI, 127.0.0.1:8000)
```

## Dati sorgente

L'indice è costruito direttamente dai **30 file XML validati** in `data/xml_dataset/`.
Ogni città produce chunk tematici separati per sezione:

| Sezione | Contenuto |
|---------|-----------|
| `transport` | Testo mobilità urbana e aeroportuale |
| `hotels` | Lista strutture ricettive con prezzi |
| `districts` | Un chunk per quartiere con descrizione |
| `description` | Sintesi strategica in italiano |
| `wiki_intro` | Panoramica da Wikivoyage (22/30 città; assente per città con solo sub-pagine distrettuali) |
| `attractions` | Lista attrazioni con coordinate |
| `nightlife` | Locali notturni (bar, pub, nightclub) da Overpass API |

**442 chunk totali** (30 città × ~15 chunk medi), prefissati con `[CITY]`.

## Retrieval ibrido

1. **FAISS** (cosine similarity, `all-MiniLM-L6-v2`, 384 dim) → top-k candidati
2. **BM25Okapi** → top-k candidati per keyword match
3. **Reciprocal Rank Fusion** (α=0.5, k=60) → score fuso
4. **Rilevamento intento** (transport / hotel / attractions / safety / districts / nightlife / general) → boost +8 ai chunk della sezione corrispondente

## Avvio

```bash
# 1. Installa dipendenze
pip install -r requirements.txt

# 2. Costruisci l'indice dai file XML
python -m rag.ingest

# 3. Avvia il server API
uvicorn rag.api:app --host 127.0.0.1 --port 8000
```

## Endpoint

| Metodo | Path | Parametri |
|--------|------|-----------|
| `GET` | `/query` | `q` (testo), `k` (int, default 5), `simulated_rag=true` |
| `POST` | `/ingest` | — (ricostruisce l'indice) |
| `GET` | `/health` | — |

## Limiti noti

- Alcune città mancano di dati hotel (Budapest, Londra, Parigi, Oslo, Madrid…) perché assenti nelle sorgenti Wikivoyage
- La sezione `wiki_intro` è assente per città con solo sub-pagine distrettuali (Amsterdam, Berlino, Bruxelles, Copenaghen, Helsinki, Lisbona, Parigi, Roma)
- La sintesi delle risposte è euristica (estrazione frasi), non generativa; se Ollama/OpenAI non è in esecuzione viene usata la modalità `simulated_rag`
- Non conosce eventi o dati successivi ai dump Wikivoyage scaricati manualmente