# Virtual Analyst — il motore di domande e risposte

Il **Virtual Analyst** è l'assistente che, nel sito, risponde a domande scritte in linguaggio naturale
(italiano o inglese) sulle 30 capitali europee del dataset — per esempio *«bar a Dublino»*,
*«discoteche nelle città fuori dall'euro»* o *«città con appeal sopra 60»*.

Tecnicamente è un sistema **RAG** (*Retrieval-Augmented Generation*): invece di "sapere" le risposte,
**va a cercarle** nei nostri dati e poi le presenta. L'idea di fondo è semplice:

> 1. l'utente fa una domanda;
> 2. il sistema **recupera** dai 30 file XML i pezzi di testo più pertinenti;
> 3. li **mostra** in modo ordinato e leggibile.

Niente "allucinazioni": l'analista non inventa, riporta solo ciò che è nel dataset.

---

## Come fa a trovare la risposta giusta

Trovare "i pezzi di testo più pertinenti" è il cuore del sistema. Lo fa combinando **due modi di cercare**,
perché da soli ciascuno ha un punto debole:

| Modo di cercare | Cosa fa | Limite se usato da solo |
|-----------------|---------|--------------------------|
| **Per significato** (*semantico*) | Capisce il *senso* della domanda, anche se usa parole diverse da quelle nel testo (es. "dove dormire" ≈ "hotel") | A volte è "troppo creativo" e prende risultati vagamente affini |
| **Per parole chiave** (*lessicale*) | Cerca le parole esatte della domanda nel testo | Non capisce i sinonimi |

Il Virtual Analyst li usa **entrambi** e poi **fonde le due classifiche** in un'unica graduatoria
(la tecnica si chiama *Reciprocal Rank Fusion*): un risultato che piace a tutti e due i metodi finisce in cima.

---

## La novità: cercare anche tra i "metadati"

Cercare nel testo libero funziona bene per le domande discorsive, ma fa fatica con le domande **precise**.
Esempio: *«discoteche nelle città che non usano l'euro»*. Cercando queste parole nel testo si rischia di
sbagliare città.

La soluzione è sfruttare i **metadati** che abbiamo già iniettato in ogni file: etichette nette e affidabili
come la **macro-regione** (Nord/Sud/Ovest/Est Europa), la **valuta**, il **tipo di locale** (bar / pub /
discoteca) e i punteggi numerici (appeal, sicurezza, green…).

L'analogia è quella dei **filtri di un sito di e-commerce**: prima spunti "taglia M" e "colore blu"
(restringi il campo a colpo sicuro), *poi* sfogli i prodotti rimasti. Allo stesso modo l'analista:

> **prima filtra** le città con i metadati (es. *valuta ≠ euro* **e** *tipo = discoteca*), <br>
> **poi cerca** nel testo solo dentro quel sottoinsieme.

Il vantaggio è triplo:

- **Precisione**: i filtri sono esatti, non "indovinati" dal testo.
- **Niente confusione tra categorie**: un pub e una discoteca si distinguono dall'etichetta, non dal contesto.
- **Numeri garantiti**: coordinate, appeal e indicatori vengono restituiti **identici** a come sono nel dato —
  un computer è pessimo a "leggere" numeri dentro un paragrafo, qui non deve farlo.

Questo è il punto in cui i due argomenti del corso — la **RAG** e il **Web of Data** (i metadati Schema.org) —
si **fondono**: la stessa informazione che descrive le città per i motori di ricerca serve anche a rispondere
meglio alle domande.

### Esempi di domande che sfruttano i filtri

| Domanda | Cosa filtra |
|---------|-------------|
| *attractions in northern europe* | solo città del **Nord Europa** |
| *nightclubs in non-euro cities* | solo **discoteche** in città **fuori dall'euro** |
| *pubs in eastern europe* | solo **pub** dell'**Est Europa** |
| *cities with appeal over 60* | solo città con **appeal ≥ 60** |

I filtri si **sommano** (es. *eurozona* **e** *green sopra 70*). Se la domanda nomina una sola città
(es. *«hotel ad Amsterdam»*), l'analista salta i filtri e risponde direttamente su quella città.

---

## I due "motori": uno in locale, uno nel browser

Qui c'è un dettaglio importante per capire **cosa gira davvero** sul sito pubblicato.

- **Motore completo (in locale).** È la versione di riferimento: un piccolo server Python (FastAPI) con gli
  indici di ricerca veri (FAISS + BM25). Si avvia sul proprio computer ed è ciò che documentiamo qui sotto in
  dettaglio.
- **Motore leggero (nel browser).** Il sito è pubblicato su **GitHub Pages**, che ospita **solo file statici**:
  non può eseguire un server Python. Perciò, quando la pagina non riesce a contattare il server locale, usa
  una versione **che gira interamente nel browser** sui dati già inclusi nella pagina.

I due motori usano **la stessa logica di filtraggio per metadati**: la versione del browser è quella che i
visitatori del sito usano davvero, e funziona senza alcun server.

---

## Dettagli tecnici (approfondimento)

> Questa sezione è per chi vuole guardare "sotto il cofano": le sezioni precedenti bastano per capire il sistema.

### Architettura

```
data/xml_dataset/*.xml  →  rag/ingest.py  →  rag_index/
                                                  ├── index.faiss   (indice vettoriale, 384 dim)
                                                  └── docs.json     (452 frammenti + metadati)
                                                       ↓
                                              rag/vectorstore.py    (ricerca + fusione + pre-filtro)
                                                       ↓
                                              rag/api.py            (server FastAPI, 127.0.0.1:8000)
```

- `ingest.py` legge i 30 XML e li spezza in **452 frammenti** (*chunk*) tematici — trasporti, hotel,
  quartieri (uno per quartiere), attrazioni, descrizione, intro wiki (testo lungo → più chunk) e vita
  notturna — ciascuno prefissato col nome della città. I campi a *content-model misto*
  (`transport`/`description`/`wiki_intro`) vengono letti col testo **completo** (`itertext`, non `findtext`,
  che si fermerebbe al primo markup inline).
- `vectorstore.py` tiene un indice **FAISS** (ricerca per significato, modello `all-MiniLM-L6-v2`, 384
  dimensioni) e un indice **BM25Okapi** (ricerca per parole chiave), e li fonde con **Reciprocal Rank Fusion**.
- `api.py` espone il server, riconosce l'intento della domanda e applica il pre-filtro per metadati.

### Da dove vengono i frammenti

| Sezione | Contenuto |
|---------|-----------|
| `transport` | Mobilità urbana e aeroportuale |
| `hotels` | Strutture ricettive con prezzi |
| `districts` | Un frammento per quartiere |
| `description` | Sintesi strategica in italiano |
| `wiki_intro` | Panoramica Wikivoyage (29/30 città, testo lungo → più chunk) |
| `attractions` | Attrazioni con coordinate |
| `nightlife` | Locali notturni (bar/pub/discoteca) |

### Cosa contiene ogni frammento

Oltre al testo, `ingest.py` allega a ogni frammento i **metadati strutturati** presi dall'XML, così la ricerca
può filtrare su valori esatti invece di cercarli nel testo:

```json
{
  "text": "[BERLIN] Bar e locali notturni: …",
  "city": "BERLIN", "section": "nightlife", "source": "Berlin.xml",
  "meta": { "appeal": 63.2, "currency": "EUR", "region": "western",
            "safety": 72.5, "green": 78.0, "cost": 85.0, "economy": 15.0, "price": 157.25 },
  "categories": ["bar", "pub", "nightclub"]
}
```

- `meta.region` ← attributo `@region` (geoscheme UN M49) · `meta.currency` ← `@currency` (assente ⇒ `"EUR"`)
- gli indicatori numerici vengono dagli attributi degli `<indicators>`
- `categories` (solo sui frammenti `nightlife`) elenca i tipi di locale presenti (`@category`)

### Le dimensioni di filtro riconosciute

| Dimensione | Sorgente | Esempio | Filtro |
|------------|----------|---------|--------|
| Macro-regione | `meta.region` (UN M49) | "attractions in northern europe" | `region = northern` |
| Valuta | `meta.currency` | "nightclubs in non-euro cities" | `currency ≠ EUR` |
| Categoria locale | `categories` | "pubs in eastern europe" | `category = pub` |
| Soglie numeriche | `meta.appeal/safety/green/price` | "cities with appeal over 60" | `appeal ≥ 60` |

Il server (`parse_filters` in `api.py`) ricava questi filtri dalla domanda e li passa alla ricerca; la risposta
`/query` include il campo `filters` con le dimensioni applicate, così si vede sempre *cosa* è stato filtrato.
La stessa logica è replicata nel motore del browser (`metadataQuery()`, generato da `scripts/deploy_dashboard.py`).

### Avvio (motore completo, in locale)

```bash
pip install -r requirements.txt                    # 1. dipendenze
python -m rag.ingest                               # 2. costruisce l'indice dai 30 XML
uvicorn rag.api:app --host 127.0.0.1 --port 8000   # 3. avvia il server
```

### Endpoint

| Metodo | Path | Parametri |
|--------|------|-----------|
| `GET` | `/query` | `q` (domanda), `k` (n. risultati, default 5), `simulated_rag=true` |
| `POST` | `/ingest` | — (ricostruisce l'indice) |
| `GET` | `/health` | — |

`/query` analizza `q` con `parse_filters()` e restituisce nel risultato il campo `filters` con le dimensioni di
metadati applicate (es. `{"region": "northern", "category": "pub"}`).

### Limiti noti

- Alcune città non hanno dati hotel (Budapest, Londra, Parigi, Oslo, Madrid…) perché assenti nelle sorgenti Wikivoyage.
- La sezione `wiki_intro` manca solo per **Luxembourg** (il cui dump non contiene una pagina-città principale né una sotto-pagina `/Understand`); le altre 29 capitali la includono.
- La sintesi delle risposte testuali è **euristica** (estrae le frasi più pertinenti), non generativa: senza un modello come Ollama/OpenAI attivo si usa la modalità `simulated_rag`.
- Conosce solo i 30 capoluoghi del dataset e non dati successivi ai dump Wikivoyage scaricati a mano.
