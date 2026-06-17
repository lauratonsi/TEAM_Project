# RAG — Virtual Analyst backend

Sistema RAG (Retrieval-Augmented Generation) interno per query in linguaggio naturale sulle 30 capitali europee del dataset.

## Architettura

```
data/xml_dataset/*.xml  →  rag/ingest.py  →  rag_index/
                                                  ├── index.faiss   (384-dim, IndexFlatIP)
                                                  └── docs.json     (336 chunk + metadati strutturati)
                                                       ↓
                                              rag/vectorstore.py    (FAISS + BM25Okapi, RRF + pre-filtro metadati)
                                                       ↓
                                              rag/api.py            (FastAPI, 127.0.0.1:8000)
```

> **Due layer di esecuzione.** Questa RAG FastAPI è la **reference implementation** eseguibile in locale.
> Il sito pubblicato su **GitHub Pages** è statico e non può ospitarla: ogni pagina tenta `fetch` verso
> `127.0.0.1:8000` e, fallendo, ricade su un **motore metadata-filtered client-side** (in `clientSideAnswer()`,
> generato da `scripts/deploy_dashboard.py`) che gira interamente nel browser sui dati già embeddati. I due
> layer condividono la stessa logica di filtraggio per metadati descritta sotto.

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

**336 chunk totali** (30 città × ~11 chunk medi), prefissati con `[CITY]`.

### Metadati strutturati per chunk

Oltre al testo, `ingest.py` allega a **ogni** chunk i metadati strutturati iniettati nell'XML, così che il
retrieval possa filtrare per dimensioni esatte invece di cercarle nel testo libero:

```json
{
  "text": "[BERLIN] Bar e locali notturni: …",
  "city": "BERLIN", "section": "nightlife", "source": "Berlin.xml",
  "meta": { "appeal": 63.2, "currency": "EUR", "region": "western",
            "safety": 72.5, "green": 78.0, "cost": 85.0, "economy": 15.0, "price": 157.25 },
  "categories": ["bar", "pub", "nightclub"]
}
```

- `meta.region` ← `@region` (UN M49) · `meta.currency` ← `@currency` (assente ⇒ `"EUR"`) · `meta.appeal` ← `@appeal_score`
- indicatori numerici (`safety`/`green`/`cost`/`economy`/`price`) dagli attributi degli `<indicators>`
- `categories` (solo sui chunk `nightlife`) ← valori distinti di `venue/@category`

## Retrieval ibrido

1. **Pre-filtro per metadati** (`parse_filters` in `api.py` → `filters` passati a `hybrid_search`): la query è
   analizzata per dimensioni strutturate — macro-regione, valuta, categoria locale, soglie numeriche — e il
   set di candidati è ristretto ai chunk il cui `meta` soddisfa i vincoli **prima** della ricerca semantica.
2. **FAISS** (cosine similarity, `all-MiniLM-L6-v2`, 384 dim) → top-k candidati (entro il sottoinsieme filtrato)
3. **BM25Okapi** → top-k candidati per keyword match (entro il sottoinsieme filtrato)
4. **Reciprocal Rank Fusion** (α=0.5, k=60) → score fuso
5. **Rilevamento intento** (transport / hotel / attractions / safety / districts / nightlife / general) → boost +8 ai chunk della sezione corrispondente

### Metadata-filtered retrieval — dimensioni riconosciute

| Dimensione | Sorgente metadato | Esempi di query | Filtro applicato |
|------------|-------------------|-----------------|------------------|
| Macro-regione | `meta.region` (UN M49) | "attractions in northern europe" | `region = northern` |
| Valuta | `meta.currency` | "nightclubs in non-euro cities" | `currency ≠ EUR` |
| Categoria locale | `categories` (`@category`) | "pubs in eastern europe" | `category = pub` |
| Soglie numeriche | `meta.appeal/safety/green/price` | "cities with appeal over 60" | `appeal ≥ 60` |

I vincoli si combinano in **AND** (es. *eurozone + green > 70*). La risposta `/query` include il campo
`filters` con le dimensioni effettivamente applicate (trasparenza). La stessa logica è replicata nel motore
client-side del sito (`metadataQuery()`), che restituisce in più i **valori garantiti** verbatim dai metadati
(coordinate `GeoCoordinates`, appeal `AggregateRating`, indicatori) senza alcun LLM e senza allucinazioni.

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

`/query` analizza automaticamente `q` con `parse_filters()` e restituisce nel payload il campo `filters` con le
dimensioni di metadati applicate al retrieval (es. `{"region": "northern", "category": "pub"}`).

## Limiti noti

- Alcune città mancano di dati hotel (Budapest, Londra, Parigi, Oslo, Madrid…) perché assenti nelle sorgenti Wikivoyage
- La sezione `wiki_intro` è assente per città con solo sub-pagine distrettuali (Amsterdam, Berlino, Bruxelles, Copenaghen, Helsinki, Lisbona, Parigi, Roma)
- La sintesi delle risposte è euristica (estrazione frasi), non generativa; se Ollama/OpenAI non è in esecuzione viene usata la modalità `simulated_rag`
- Non conosce eventi o dati successivi ai dump Wikivoyage scaricati manualmente