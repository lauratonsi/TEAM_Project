# EuroCity Strategic Intelligence
## Progetto TEAM — Text Extraction Analysis and Manipulation

**Laurea Magistrale in Governance e Politiche dell'Innovazione Digitale**  
Università di Bologna — Docente: Angelo Di Iorio — A.A. 2024/2025

---

## Descrizione del Progetto

EuroCity è una pipeline ETL (Extract, Transform, Load) che analizza **30 capitali europee**
estraendo, pulendo e trasformando dati da dump MediaWiki (Wikivoyage) in formato XML.
L'output finale è una dashboard HTML navigabile con statistiche comparative, mappa interattiva
e documentazione integrata del processo.

**Appeal Score** (indice composito):
`Safety × 0.4 + Green Score × 0.4 + (100 − Costo della vita) × 0.2`

---

## Struttura del Progetto

```
ELABORAZIONE/
├── original_source/          # Dump Wikivoyage (MediaWiki XML) per 30 capitali
├── xml_dataset/              # Output: 30 file XML validati rispetto al DTD
├── city_report.dtd           # DTD per la validazione dei file XML
├── city_indices.json         # Indici: safety, green score, costo della vita
├── wiki_text_pulito.csv      # Trasporti, hotel, distretti estratti da Wikivoyage
├── attrazione_descrizione_fixed.csv  # Attrazioni con coordinate geografiche
├── city_descriptions.json    # Sintesi strategiche in italiano (generate con AI)
├── extract_wiki_info.py      # Script 1: preparazione dataset
├── final_processor.py        # Script 2: elaborazione principale → XML
├── deploy_dashboard.py       # Script 3: generazione HTML
├── index.html                # Dashboard navigabile (output principale)
├── report.html               # Report statistiche + documentazione pipeline
├── style.css                 # Foglio di stile applicato a tutti i documenti HTML
└── mappa_attrazioni.html     # Mappa Leaflet.js con tutte le attrazioni
```

---

## Come Eseguire la Pipeline

### Prerequisiti
```bash
pip install lxml pandas
```

### Esecuzione completa
```bash
# Passo 1 – Generazione XML validati
python final_processor.py

# Passo 2 – Generazione HTML (index.html + report.html)
python deploy_dashboard.py
```

> `extract_wiki_info.py` è lo script di preparazione iniziale (richiede `mwparserfromhell`, `spacy`,
> opzionalmente Google Cloud Language API). I file CSV/JSON prodotti sono già inclusi nel repository,
> quindi non è necessario rieseguirlo.

---

## Fase di Preparazione del Dataset

### Fonti dei Dati

| Fonte | File | Contenuto |
|-------|------|-----------|
| Wikivoyage (MediaWiki XML) | `original_source/*.xml` | Testi, trasporti, hotel, distretti |
| Dataset pubblici (Numbeo, EIU) | `city_indices.json` | Safety, green score, costo della vita |
| Wikimedia Commons | `landmark_image` in XML | Immagini simbolo (URL stabili via Special:FilePath) |
| Generato con AI | `city_descriptions.json` | Sintesi strategiche in italiano |

### Struttura dei Dump Wikivoyage

I file in `original_source/` sono dump MediaWiki XML con namespace
`http://www.mediawiki.org/xml/export-0.11/`. Ogni file contiene più `<page>`:
- la pagina principale della città (es. `<title>London</title>`)
- le pagine dei distretti (es. `<title>Amsterdam/Canal District</title>`)

Per le città più grandi (Amsterdam, Berlino, Roma, Parigi) la pagina principale
non esiste nel dump: la pipeline usa la prima sotto-pagina disponibile.

---

## Schema DTD

```xml
<!ELEMENT city_report (metadata, indicators, transport, accommodation,
                        highlights, districts?, description,
                        wiki_intro?, landmark_image?)>
<!ATTLIST city_report appeal_score CDATA #REQUIRED>

<!ELEMENT metadata (title, name_it, flag)>
<!ELEMENT indicators (hotel_count, hotel_price, safety, environment,
                       cost_index, economic_accessibility)>
<!ELEMENT transport (#PCDATA)>
<!ELEMENT accommodation (hotel*)>
<!ELEMENT hotel (name, price)>
<!ELEMENT highlights (attraction*)>
<!ELEMENT attraction (name, description)>
<!ATTLIST attraction lat CDATA #REQUIRED lon CDATA #REQUIRED>
<!ELEMENT districts (district*)>
<!ELEMENT district (name, description)>
<!ELEMENT description (#PCDATA)>
<!ELEMENT wiki_intro (#PCDATA)>
<!ELEMENT landmark_image (#PCDATA)>
```

Tutti i 30 file XML superano la validazione DTD eseguita a runtime
con `lxml.etree.DTD`.

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
2. Prima pagina con titolo `Città/XYZ` (sotto-distretto)
3. Prima pagina contenente il nome della città

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
Ogni card HTML include annotazioni microdata generate dallo script:
```html
<article itemscope itemtype="https://schema.org/City">
  <span itemprop="name">Roma</span>
  ...
</article>
```

---

## Utilizzo di Strumenti AI

L'utilizzo di AI è dichiarato come richiesto dalle linee guida del progetto.

### Claude Code (Anthropic — claude-sonnet-4-6)
Utilizzato per assistenza allo sviluppo della pipeline:
- Debugging del problema di selezione della pagina principale nei dump multi-pagina
- Scrittura della funzione `advanced_wiki_cleaner()` per la pulizia Wikitext
- Risoluzione della gestione accent-insensitive per Reykjavík
- Correzione del bug nell'estrazione distretti in `deploy_dashboard.py`
- Override distretti per Luxembourg (dati CSV errati: siti Mullerthal) e Stockholm
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
| `report.html` | Statistiche estratte + documentazione pipeline |
| `style.css` | Foglio di stile applicato a tutti i documenti HTML |
| `mappa_attrazioni.html` | Mappa Leaflet con 300 attrazioni geolocalizzate |

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
