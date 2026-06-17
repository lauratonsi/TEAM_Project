# EuroCity Strategic Intelligence
## Progetto TEAM — Text Extraction Analysis and Manipulation

**Laurea Magistrale in Governance e Politiche dell'Innovazione Digitale**  
Università di Bologna — Docente: Angelo Di Iorio — A.A. 2024/2025

---

## Descrizione del Progetto

EuroCity è una pipeline ETL (Extract, Transform, Load) che analizza **30 capitali europee**
estraendo, pulendo e trasformando dati da dump Wikivoyage (scaricati manualmente) in formato XML.
L'output finale è una dashboard HTML navigabile con statistiche comparative, mappa interattiva
e documentazione integrata del processo.

**Appeal Score** (indice composito):
`Safety × 0.4 + Green Score × 0.4 + (100 − Costo della vita) × 0.2`

---

## Struttura del Progetto

```
ELABORAZIONE/
├── data/
│   ├── original_source/                 # Dump Wikivoyage (MediaWiki XML) scaricati a mano
│   ├── xml_dataset/                     # Output: 30 file XML validati rispetto al DTD
│   ├── city_report.dtd                  # DTD per la validazione dei file XML
│   ├── city_indices.json                # Indici: safety, green score, costo della vita
│   ├── currency_rates.json              # Valute locali + tassi indicativi (capitali non-euro)
│   ├── geo_regions.json                 # Macro-regione per capitale (geoscheme UN M49) + fonte
│   ├── nightlife.json                   # Locali notturni geolocalizzati (Overpass / OSM)
│   ├── wiki_text_pulito.csv             # Trasporti, hotel, distretti estratti da Wikivoyage
│   ├── attrazione_descrizione_fixed.csv # Attrazioni con coordinate geografiche
│   ├── city_descriptions.json           # Sintesi strategiche in italiano (generate con AI)
│   └── transport_patches.json           # Patch trasporti per città con CSV mancante
├── scripts/
│   ├── extract_wiki_info.py             # Preparazione dataset (dump → CSV/JSON)
│   ├── final_processor.py               # Elaborazione principale → XML (validazione in scrittura)
│   ├── deploy_dashboard.py              # Generazione HTML/CSS (ri-validazione in lettura)
│   ├── validate.py                      # Validatore DTD standalone (DOM + DTD)
│   ├── check_microdata.py               # Verifica round-trip dei microdata (libreria `microdata`)
│   └── …                                # download_images, fetch_nightlife, map, …
├── pages/
│   ├── cities/*.html                    # 30 pagine città (una per file XML)
│   ├── report.html                      # Report statistiche + documentazione pipeline
│   └── mappa_attrazioni.html            # Mappa Leaflet con attrazioni e locali
├── rag/                                 # Virtual Analyst: ingest, vectorstore, API (BM25 + FAISS)
├── index.html                           # Dashboard navigabile (output principale)
└── stile.css                            # Foglio di stile unico per tutti i documenti HTML
```

---

## Architettura della Pipeline

Cinque componenti Python. La pipeline trasforma i dump MediaWiki in file XML conformi al DTD
(con **content-model misto**), li valida, genera l'HTML annotato con **microdata** e indicizza
i contenuti per le query in linguaggio naturale.

| # | Componente | Ruolo |
|---|-----------|-------|
| 1 | `extract_wiki_info.py` | Preparazione: dump Wikivoyage → CSV/JSON (mwparserfromhell, spaCy) |
| 2 | `final_processor.py` | Costruzione XML (content-model misto + `<source_url>`) e **validazione DTD in scrittura** |
| 3 | `deploy_dashboard.py` | **Ri-validazione DTD in lettura** + generazione HTML/CSS con microdata annidati (`itemid` ← documento) |
| 4 | `validate.py` | **Validatore DTD standalone**: DOM + `etree.DTD().validate()`, isolato dal resto |
| 5 | `rag/` | Indicizzazione FAISS + BM25 e Virtual Analyst per query in linguaggio naturale |

La validazione DTD avviene quindi in **tre punti** (scrittura, lettura, script standalone),
tutti con `lxml.etree.DTD`.

---

## Come Eseguire la Pipeline

### Prerequisiti
```bash
pip install lxml pandas
```

### Esecuzione completa
```bash
# Passo 1 – Generazione XML validati
python scripts/final_processor.py

# Passo 2 – Generazione HTML (index.html, pagine città, report.html, mappa)
python scripts/deploy_dashboard.py
```

### Validazione DTD — script standalone

Oltre alla validazione integrata nella pipeline, è disponibile uno **script dedicato e
indipendente** che valida la directory XML rispetto al DTD, modellato sui laboratori del
corso (`lab_castles_validation.py`):

```bash
python scripts/validate.py             # valida data/xml_dataset/
python scripts/validate.py <altra_dir> # valida un'altra directory
```

Per ogni file lo script: (1) costruisce il **DOM** con `etree.parse()` — intercettando i
documenti *mal formati*; (2) lo valida con `etree.DTD(...).validate()` — distinguendo i
*non validi*; (3) ispeziona il DOM (radice, n. elementi, attrazioni). Restituisce codice
di uscita `0` solo se tutti i file sono validi. Output:

```
📄 DTD     : data/city_report.dtd
📂 Sorgente: data/xml_dataset
  ✅ amsterdam.xml   VALIDO   [root=<city_report> · 112 elementi · 10 attractions · appeal=63.2]
  …
📋 Risultato: 30/30 validi · 0 non validi · 0 malformati
```

> `extract_wiki_info.py` è lo script di preparazione iniziale (richiede `mwparserfromhell`, `spacy`,
> opzionalmente Google Cloud Language API). I file CSV/JSON prodotti sono già inclusi nel repository,
> quindi non è necessario rieseguirlo.

---

## Fase di Preparazione del Dataset

### Fonti dei Dati

| Fonte | File | Contenuto |
|-------|------|-----------|
| Wikivoyage (MediaWiki XML, download manuale) | `original_source/*.xml` | Testi, trasporti, hotel, distretti |
| Dataset pubblici (Numbeo, EIU) | `city_indices.json` | Safety, green score, costo della vita |
| OpenStreetMap (Overpass API) | `nightlife.json` | 240 locali notturni geolocalizzati (bar/pub/nightclub) |
| Tassi di cambio indicativi (snapshot 2026-01) | `currency_rates.json` | Valuta locale ISO 4217 + tasso EUR→locale delle 10 capitali non-euro |
| [UN M49 geoscheme](https://unstats.un.org/unsd/methodology/m49/) (UN Statistics Division) | `geo_regions.json` | Macro-regione (Northern/Western/Southern/Eastern) di ogni capitale + nota su Cipro |
| Wikimedia Commons | `landmark_image` in XML | Immagini simbolo (URL stabili via Special:FilePath) |
| Generato con AI | `city_descriptions.json` | Sintesi strategiche in italiano |

### Struttura dei Dump Wikivoyage

I file in `original_source/` sono dump MediaWiki XML con namespace
`http://www.mediawiki.org/xml/export-0.11/`. Ogni file contiene più `<page>`:
- la pagina principale della città (es. `<title>London</title>`)
- le pagine dei distretti (es. `<title>Amsterdam/Canal District</title>`)

Per le città più grandi (Amsterdam, Berlino, Roma, Parigi) la pagina principale
non esiste nel dump: in questi casi la sezione Wiki Archive viene omessa (mostrare
testo di un distretto come intro della città sarebbe fuorviante).

---

## Schema DTD

```xml
<!ELEMENT city_report (metadata, indicators, transport, accommodation,
                        highlights, districts?, description,
                        wiki_intro?, landmark_image?, nightlife?)>
<!ATTLIST city_report appeal_score CDATA                                     #REQUIRED
                      currency     CDATA                                     #IMPLIED   <!-- valuta locale (ISO 4217), solo capitali non-euro -->
                      region       (northern | western | southern | eastern) #REQUIRED> <!-- macro-regione UN M49 (enumerato) -->

<!ELEMENT metadata (title, name_it, flag, source_url)>
<!ELEMENT source_url (#PCDATA)>            <!-- URI canonico → itemid microdata -->
<!ELEMENT indicators (hotel_count, hotel_price, safety, environment,
                       cost_index, economic_accessibility)>
<!ELEMENT transport (#PCDATA | b | i | link)*>   <!-- content-model misto -->
<!ELEMENT accommodation (hotel*)>
<!ELEMENT hotel (name, price)>
<!ELEMENT highlights (attraction*)>
<!ELEMENT attraction (name, description)>
<!ATTLIST attraction lat CDATA #REQUIRED lon CDATA #REQUIRED>
<!ELEMENT districts (district*)>
<!ELEMENT district (name, description)>
<!ELEMENT description (#PCDATA | b | i | link)*>  <!-- content-model misto -->
<!ELEMENT wiki_intro (#PCDATA | b | i | link)*>   <!-- content-model misto -->
<!ELEMENT landmark_image (#PCDATA)>
<!-- Elementi inline per il content-model misto -->
<!ELEMENT b (#PCDATA)>
<!ELEMENT i (#PCDATA)>
<!ELEMENT link (#PCDATA)>
<!ATTLIST link href CDATA #REQUIRED>
<!ELEMENT nightlife (venue*)>
<!ELEMENT venue (name)>
<!ATTLIST venue lat CDATA #REQUIRED lon CDATA #REQUIRED
                category (bar | pub | nightclub) #REQUIRED>   <!-- attributo enumerato -->
```

### Riepilogo degli elementi

| Elemento | Content model | Attributi | Cardinalità / Note |
|----------|---------------|-----------|--------------------|
| `city_report` | `metadata, indicators, transport, accommodation, highlights, districts?, description, wiki_intro?, landmark_image?, nightlife?` | `appeal_score` *(REQ)*, `currency` *(IMPL)*, `region` **enum** *(REQ)* | **radice** |
| `metadata` | `title, name_it, flag, source_url` | — | 1 |
| `title` / `name_it` / `flag` | `#PCDATA` | — | nome EN / nome IT / emoji bandiera |
| `source_url` | `#PCDATA` | — | URI canonico → `itemid` microdata |
| `indicators` | `hotel_count, hotel_price, safety, environment, cost_index, economic_accessibility` | — | 1 |
| `hotel_count` / `hotel_price` | `#PCDATA` | — | numerici (testo) |
| `safety` | `EMPTY` | `index_score` *(REQ)* | indice 0–100 |
| `environment` | `EMPTY` | `green_score` *(REQ)* | indice 0–100 |
| `cost_index` | `EMPTY` | `value` *(REQ)* | costo della vita |
| `economic_accessibility` | `EMPTY` | `score` *(REQ)* | 100 − costo |
| `transport` | `(#PCDATA \| b \| i \| link)*` | — | **content-model misto** |
| `accommodation` | `hotel*` | — | può essere vuoto (12 città senza hotel) |
| `hotel` | `name, price` | — | 0+ |
| `price` | `#PCDATA` | — | €/notte |
| `highlights` | `attraction*` | — | — |
| `attraction` | `name, description` | `lat` *(REQ)*, `lon` *(REQ)* | geolocalizzata su mappa |
| `districts` | `district*` | — | **opzionale** (19/30) |
| `district` | `name, description` | — | 0+ |
| `name` | `#PCDATA` | — | condiviso (hotel/attraction/district/venue) |
| `description` | `(#PCDATA \| b \| i \| link)*` | — | **misto**; condiviso (città/attraction/district) |
| `wiki_intro` | `(#PCDATA \| b \| i \| link)*` | — | **opzionale**, misto (29/30) |
| `landmark_image` | `#PCDATA` | — | opzionale, URL immagine |
| `b` / `i` | `#PCDATA` | — | inline (grassetto / corsivo) |
| `link` | `#PCDATA` | `href` *(REQ)* | inline (collegamento) |
| `nightlife` | `venue*` | — | **opzionale** |
| `venue` | `name` | `lat` *(REQ)*, `lon` *(REQ)*, `category` *(REQ)* | geolocalizzata; `category` **enumerato** `(bar \| pub \| nightclub)` |

*(REQ) = `#REQUIRED`; (IMPL) = `#IMPLIED` (opzionale); `?` = opzionale; `*` = zero o più; gli elementi `EMPTY` portano il dato in un attributo.*

**Valuta locale (attributo opzionale).** L'attributo `currency` del root è `#IMPLIED`: è **assente** per le
città dell'area euro e **presente** (codice ISO 4217, es. `SEK`, `GBP`) solo per le 10 capitali che usano
un'altra valuta. Il sito lo legge via XPath (`string(/city_report/@currency)`) e mostra, accanto al prezzo
in euro, l'equivalente locale indicativo letto da `currency_rates.json`.

**Macro-regione (attributo enumerato obbligatorio).** L'attributo `region` del root è **enumerato** e
`#REQUIRED`: ogni capitale appartiene a una e una sola area tra `northern | western | southern | eastern`.
La classificazione segue il **geoscheme UN M49** (UN Statistics Division); la mappa capitale→regione e la sua
fonte vivono in [`data/geo_regions.json`](data/geo_regions.json). Unica eccezione documentata: **Cipro**
(Nicosia), che M49 colloca in *Asia occidentale*, è assegnata a `southern` in quanto Stato membro UE
all'estremo sud-est dell'Unione. Il dato è scritto da `final_processor.py` e riletto via XPath
(`string(/city_report/@region)`) da `deploy_dashboard.py`, che lo usa come **filtro per area** nell'`index.html`.
Essendo enumerato, un valore fuori vocabolario (es. `region="central"`) fa **fallire** la validazione DTD —
verificabile sostituendolo in un file e rilanciando `validate.py`.

**Prezzo: stima sintetica, non osservata.** L'elemento `<hotel_price>` **non** è estratto dalle voci
alloggio di Wikivoyage: è derivato dall'indice Numbeo del costo della vita con `hotel_price = cost_of_living × 1.85`.
È un proxy in euro pensato per il **confronto tra città**, non un prezzo di mercato. I prezzi dei singoli
`<hotel>` sono invece testo grezzo verbatim da Wikivoyage (formati eterogenei).

**Content-model misto.** I campi `transport`, `description` e `wiki_intro` non sono solo
testo: contengono markup inline (`<b>`, `<i>`, `<link href>`) interlacciato al testo —
il content-model misto richiesto dal progetto (es. `<b>Roma</b> ... (<i>Trastevere</i>)`).

**Scelte di obbligatorietà.** Gli attributi geografici di `attraction` e `venue` sono
`#REQUIRED` perché entrambi gli elementi sono posizionati sulla mappa (senza coordinate non
sarebbero collocabili); `hotel`, che compare solo in elenco, non ha coordinate. Gli elementi
`districts?`, `wiki_intro?`, `landmark_image?` e `nightlife?` sono opzionali perché il dato
non è sempre disponibile nelle fonti; `accommodation` è invece sempre presente ma con
`hotel*` (zero o più), così le città senza hotel restano valide.

**Validazione.** Tutti i 30 file XML superano la validazione DTD, eseguita con
`lxml.etree.DTD` in **tre punti**: in scrittura (`final_processor.py`), in lettura
(`deploy_dashboard.py`, che distingue documenti *mal formati* da *non validi* e mostra
il contatore `30/30 DTD-valid` nell'`index.html`) e tramite lo **script standalone**
[`validate.py`](scripts/validate.py) (vedi sopra), che costruisce il DOM e lo valida
in modo isolato dal resto della pipeline.

**Analisi critica della validazione.** Nel rispetto delle linee guida del Progetto TEAM la
validazione strutturale è affidata a un **DTD**, scelta ottima per il **content-model misto**
delle sezioni narrative (trasporti, introduzioni) e per i vincoli **enumerati** (`venue/@category`,
`city_report/@region`), in cui il DTD è pienamente espressivo. Tuttavia, data l'abbondanza di dati puramente
strutturati e numerici nel dataset (coordinate `lat`/`lon`, indici di sicurezza, green score,
prezzi), il DTD mostra limiti di **espressività**: può validarli solo come stringhe generiche
(`CDATA` / `#PCDATA`). In uno scenario di produzione, per garantire la robustezza dei *tipi di
dato* prima ancora del parsing in Python, sarebbe tecnicamente più appropriato affiancare o
sostituire il DTD con **Relax NG** o **XML Schema**, che offrono meccanismi di verifica molto più
raffinati per i dati strutturati.

---

## Tecniche di Parsing Adottate

### 1. Parsing MediaWiki XML (lxml)
Il namespace MediaWiki viene gestito esplicitamente:
```python
MW_NS = 'http://www.mediawiki.org/xml/export-0.11/'
ns = {'mw': MW_NS}
pages = tree.findall('.//mw:page', ns)
```

### 2. Selezione della Pagina Principale
Algoritmo a priorità decrescente per trovare il testo intro corretto:
1. Pagina con titolo esatto uguale al nome della città
2. Pagina `Città/Understand` (sezione intro Wikivoyage)
3. Se nessuna delle due esiste (città suddivise solo in distretti), wiki_intro rimane vuoto

La comparazione è **accent-insensitive** tramite:
```python
unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
```
Necessario per `Reykjavík` ≠ `Reykjavik`.

### 3. Pulizia del Wikitext (regex)
Il testo Wikitext viene pulito con sequenze di `re.sub()`:
```python
# Template (5 passate per nested): {{...}} → ""
# Link con testo: [[link|testo]] → "testo"
# Link semplici: [[link]] → "link"
# URL con testo: [http://url testo] → "testo"
# Header sezione: == Titolo == → ""
# Hatnote: :For other places... → ""
# Bold/italic: '''testo''' → "testo"
# Tag HTML: <tag> → ""
```

### 4. Estrazione Distretti
La colonna `Districts` del CSV (prodotta nella fase di preparazione)
fornisce i nomi pipe-separated. I nomi vengono filtrati per rimuovere
rumore (etichette di navigazione, toponomastica storica, categorie errate).
Per ogni distretto si cerca la sotto-pagina corrispondente nel dump XML
e si estrae il testo introduttivo come descrizione.

### 5. Microdata Schema.org
Ogni documento HTML è annotato con microdata Schema.org generati dallo script, con
struttura **annidata** (come il pattern `Place > Review > Person` visto a lezione):
```html
<main itemscope itemtype="https://schema.org/City"
      itemid="https://en.wikivoyage.org/wiki/Rome">
  <meta itemprop="name" content="Roma">
  <!-- URI canonico (Wikivoyage = fonte dei documenti), reso come link visibile -->
  <a itemprop="url" href="https://en.wikivoyage.org/wiki/Rome">en.wikivoyage.org/wiki/Rome</a>
  ...
  <tr itemprop="containsPlace" itemscope itemtype="https://schema.org/TouristAttraction">
    <span itemprop="name">Colosseum</span>
    <div itemprop="geo" itemscope itemtype="https://schema.org/GeoCoordinates">
      <meta itemprop="latitude" content="41.89">
      <meta itemprop="longitude" content="12.49">
    </div>
  </tr>
</main>
```

**Identità (itemid ↔ documento).** L'`itemid` non è arbitrario: è l'URI canonico letto
dall'elemento `<source_url>` del file XML. Gli identificatori nel sito **corrispondono
esattamente** a quelli nei documenti, come nell'esempio dei castelli del corso
(`itemid` dell'HTML ↔ `id` del file XML).

**Quantificazione** (conteggio a runtime, ri-scansionando l'HTML generato — sezione
`#microdata` di `report.html`; verificato con la libreria `microdata.get_items()` del corso):

| Metrica | Valore |
|---------|--------|
| Item tipizzati (`itemscope`) | **1.378** |
| Proprietà (`itemprop`) | **3.924** |
| Identificatori (`itemid`) | 60 |
| **Attributi microdata totali** | **≈ 6.740** |

| Tipo Schema.org | Item | | Tipo Schema.org | Item |
|-----------------|------|---|-----------------|------|
| `GeoCoordinates` | 570 | | `Hotel` | 88 |
| `TouristAttraction` | 300 | | `City` | 60 |
| `BarOrPub` | 227 | | `AggregateRating` | 30 |
| `PropertyValue` | 90 | | `NightClub` | 13 |

Oltre alla gerarchia `City > containsPlace`, ogni `City` porta un **`AggregateRating`** (l'Appeal Score, con
`ratingValue` 0–100) e i sotto-indici come **`PropertyValue`** (`additionalProperty`: Safety, Green, Economic
Accessibility) — la forma corretta dato che un `Place` ammette un solo `aggregateRating`. La categoria enumerata
del XML (`bar|pub|nightclub`) è mappata sulla classe più specifica (`BarOrPub` / `NightClub`).

---

## HTML Semantico e Accessibilità

> *Teoria (slide del corso):* «HTML è il linguaggio base del Web. Deve essere usato in modo
> **semantico**, evitando tag procedurali deprecati come `<font>` e preferendo una chiara
> organizzazione logica. Gli elementi si dividono in quelli **di blocco** (che vanno a capo) e
> **inline** (come `<em>`, `<strong>` o il generico `<span>`), che si inseriscono nel flusso
> del testo senza spezzarlo.»

Tutto l'HTML prodotto applica questo principio.

**1. Niente tag procedurali deprecati.** Sulle 33 pagine: zero `<font>`/`<center>`/`<strike>`
e zero attributi presentazionali (`align`, `bgcolor`…). La presentazione è interamente in
`stile.css`.

**2. Organizzazione logica con elementi di blocco semantici** — non `<div>` generici:
`<header>`, `<nav>`, `<main>` (uno per pagina), `<section>`/`<article>`, `<footer>`, con
gerarchia `h1→h2→h3`.

**3. Inline semantici.** Il vocabolario inline del content-model misto (`b`/`i`/`link` nel XML)
è mappato da `inline_to_html()` ai tag **semantici** `b→<strong>`, `i→<em>`, `link→<a>` (l'enfasi
porta significato: nome città, termine straniero); `<span>` per i frammenti senza semantica. I
`<b>` residui sono enfasi puramente visiva — in HTML5 `<b>` non è deprecato ma ridefinito come
"testo stilisticamente distinto senza importanza".

**4. La "traduzione" del semantico: l'accessibilità.** L'HTML semantico è invisibile all'occhio
ma si traduce nell'**albero di accessibilità**: gli elementi semantici generano i **landmark
ARIA** (`<header>`→banner, `<nav>`→navigation, `<main>`→main, `<footer>`→contentinfo) tra cui uno
screen reader può saltare. Per renderli usabili sono stati aggiunti:
- **skip link** "Salta al contenuto" (visibile solo al focus da tastiera);
- **`aria-label`** sulle `<nav>` duplicate (Principale / Tra le città / Sezioni del report);
- **`aria-current="page"`** sul link attivo; `lang` sul documento e `alt` su tutte le 60 immagini.

Verifica: DevTools → scheda *Accessibility* (mostra i landmark etichettati), o la navigazione
per landmark di uno screen reader.

**Target tattili (tap-target).** Un audit **Lighthouse** (accessibilità **96/100**) ha segnalato
marker Leaflet con area cliccabile inferiore a **24×24 px** o sovrapposti (es. Stoccolma, Oslo,
Roma). Correzioni: marker di locali/attrazioni portati a **32×32 px** e marker delle capitali
**raggruppati** con `L.markerClusterGroup`, così gli overlap a zoom basso si fondono in un unico
bersaglio cliccabile (e si riaprono allo zoom).

**Albero di accessibilità (`index.html`).** È la struttura che uno screen reader «vede» — solo
ruoli e nomi accessibili, non lo stile:

```
document  "EuroCity Strategic Intelligence"            [lang="en"]
├─ link        "Salta al contenuto"                    (skip-link, visibile al focus)
├─ banner                                              ‹header›
│  └─ navigation  "Navigazione principale"             ‹nav›  → Home · Report · Map
├─ heading h1  "30 European capitals, one intelligence."
├─ region      "How the data is built"                 ‹section[aria-label]›
│  └─ heading h2  "How the data is built"
├─ main        "Griglia delle capitali"                ‹main#city-grid›
│  ├─ article → heading h2 "Amsterdam"  + link
│  ├─ article → heading h2 "Athens"     + link
│  └─ …  (30 article, una card per capitale)
├─ contentinfo                                         ‹footer›  → link "Report & Documentation"
├─ button      "Back to top"
└─ dialog      "Virtual Analyst"                       ‹div[role="dialog"]›  ← widget flottante
     button "Ask the analyst" · textbox · button "Ask" · button "Close the analyst"
```

**5. Il sito come riflesso diretto dei documenti.** Ogni dato del XML è reso **visibile** nella
pagina, non solo scaricabile. L'URI canonico (`<source_url>`) è un **link cliccabile** su ogni
pagina città e coincide con l'`itemid` dei microdata: lo stesso identificatore vive nel
documento, nel link visibile e nell'annotazione machine-readable. Il download del file XML è
un'aggiunta, non l'unico accesso ai dati.

| Principio (slide) | Costrutto HTML | Effetto reale |
|-------------------|----------------|---------------|
| No tag procedurali | 0 `<font>`; stile in CSS | separazione contenuto/presentazione |
| Organizzazione logica (blocco) | `header/nav/main/section/footer` | landmark ARIA + document outline |
| Inline semantico (em/strong) | `<strong>/<em>/<span>` | enfasi pronunciata dagli screen reader |
| Web come grafo di risorse | `<a itemprop="url" href=URI>` | URI documento = link = itemid microdata |

---

## Uso di XPath

La fase di **lettura/estrazione** dei documenti si basa su XPath, a due livelli.

### 1. XPath completo — metodo `.xpath()` (motore XPath di lxml)

| File | Espressione | Costrutto XPath |
|------|-------------|-----------------|
| `deploy_dashboard.py` | `root.xpath("string(.//safety/@index_score)")` | funzione `string()` + **asse attributo** `@` |
| `deploy_dashboard.py` | `root.xpath(".//hotel")`, `.//attraction`, `.//district`, `.//venue` | asse discendente `//` |
| `extract_wiki_info.py` | `xpath("//mw:page", namespaces=ns)`, `xpath("string(.//mw:text)")` | `//` + **namespace** + `string()` |
| `built_dataset.py` | `xpath("string(//*[local-name()='text'])")` | **predicato** `[local-name()=…]` |
| `rag/ingest.py` | `.//accommodation/hotel`, `.//highlights/attraction`, `.//nightlife/venue` | path relativi |

L'esempio più completo è `string(.//safety/@index_score)`: combina **path discendente**,
**asse attributo** e **funzione XPath** in un'unica espressione.

### 2. ElementPath — `.find()` / `.findall()` / `.findtext()`

Sottoinsieme di XPath di ElementTree/lxml, usato pervasivamente per navigare il DOM
(es. `final_processor.py`: `tree.findall('.//mw:page', ns)`; `validate.py`:
`root.findall('.//attraction')`; `deploy_dashboard.py`: `root.findtext(".//title")`).

> **Nota sui due tipi di accesso agli attributi.** Gli attributi enumerati/obbligatori
> (`@index_score`, `@category`, `@lat`/`@lon`) si leggono con l'asse attributo XPath
> (`string(.../@attr)`) o con `element.get('attr')`; gli elementi figli con `findtext()`.

---

## Utilizzo di Strumenti AI

L'utilizzo di AI è dichiarato come richiesto dalle linee guida del progetto.

### Claude Code (Anthropic)
Utilizzato per assistenza allo sviluppo della pipeline:
- Debugging del problema di selezione della pagina principale nei dump multi-pagina
- Scrittura della funzione `advanced_wiki_cleaner()` per la pulizia Wikitext
- Risoluzione della gestione accent-insensitive per Reykjavík
- Correzione del bug nell'estrazione distretti in `deploy_dashboard.py`
- Override distretti per Luxembourg (dati CSV errati: siti Mullerthal) e Stockholm
- Introduzione del content-model misto e della ri-validazione DTD in lettura
- Espansione dei microdata Schema.org (`AggregateRating`, `PropertyValue`, `BarOrPub`/`NightClub`, `Hotel`) e script `check_microdata.py` per il round-trip
- Gestione della valuta locale (`currency_rates.json`, attributo `currency`, nota sulle capitali non-euro) e correzione della provenienza del prezzo (stima sintetica, non estratta)
- Iniezione della macro-regione geografica negli XML (`geo_regions.json`, attributo enumerato `region` da geoscheme UN M49) come dimensione di filtro/navigazione nell'index
- Trasformazione del Virtual Analyst in widget flottante presente su ogni pagina
- Generazione di `report.html` e del presente `README.md`

**Prompt rappresentativo usato con Claude Code:**
> "Analizza il progetto e il parsing. Nel codice HTML ci sono ancora diversi problemi:
> l'estrazione del testo dai file .xml non è veramente riuscita, molte città non hanno
> ancora i distretti/li hanno errati, ci sono alcuni errori nelle bandiere."

### AI per i Contenuti del Dataset
Le sintesi strategiche in `city_descriptions.json` sono state generate con Claude (Anthropic):

> *Prompt tipo:* "Genera una descrizione strategica in italiano (max 2 frasi) di [CITTÀ]
> come capitale europea, focalizzandoti su: innovazione urbana, sostenibilità, sicurezza,
> accessibilità economica. Tono: analitico, da report istituzionale."

---

## Output Prodotti

| File | Descrizione |
|------|-------------|
| `xml_dataset/*.xml` | 30 file XML, uno per capitale, validati DTD |
| `index.html` | Dashboard navigabile con griglia di card, mappa e Virtual Analyst |
| `pages/cities/*.html` | 30 pagine città (una per XML), con microdata, mappa e nota valuta per le città non-euro |
| `pages/report.html` | Statistiche estratte + documentazione pipeline |
| `pages/mappa_attrazioni.html` | Mappa Leaflet con attrazioni e locali notturni geolocalizzati |
| `stile.css` | Foglio di stile unico, applicato a tutti i documenti HTML (con cache-busting `?v=hash`) |

Il **Virtual Analyst** (RAG: BM25 + FAISS) è un **widget chat flottante** presente su `index.html` e su ogni
pagina città: segue lo scroll e resta accessibile in qualsiasi momento della navigazione.

---

## Statistiche del Dataset

| Indicatore | Valore |
|------------|--------|
| Capitali analizzate | 30 |
| File XML generati e validati | 30 |
| Strutture ricettive catalogate | 370 |
| Attrazioni geolocalizzate | 300 |
| Città con distretti estratti | 19/30 |
| Appeal Score medio | 61.3 |
| Safety Index medio | 66.0 |
| Green Score medio | 71.8 |

---

*Progetto TEAM — Università di Bologna — A.A. 2024/2025*
