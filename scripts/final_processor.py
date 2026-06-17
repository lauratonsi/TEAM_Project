import os
import json
import re
from pathlib import Path
import pandas as pd
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent

# --- CONFIGURAZIONE ---
ORIGINAL_XML_DIR = str(ROOT / 'data' / 'original_source')
INPUT_JSON_INDICES = str(ROOT / 'data' / 'city_indices.json')
INPUT_CSV_WIKI = str(ROOT / 'data' / 'wiki_text_pulito.csv')
INPUT_CSV_ATTR = str(ROOT / 'data' / 'attrazione_descrizione_fixed.csv')
INPUT_JSON_DESC = str(ROOT / 'data' / 'city_descriptions.json')
INPUT_JSON_NIGHTLIFE = str(ROOT / 'data' / 'nightlife.json')
INPUT_JSON_TRANSPORT_PATCHES = str(ROOT / 'data' / 'transport_patches.json')
DTD_FILE = str(ROOT / 'data' / 'city_report.dtd')
OUTPUT_DIR = str(ROOT / 'data' / 'xml_dataset')

MW_NS = 'http://www.mediawiki.org/xml/export-0.11/'

CITY_MAP = {
    "London": {"it": "London", "flag": "🇬🇧"}, "Prague": {"it": "Prague", "flag": "🇨🇿"},
    "Copenhagen": {"it": "Copenhagen", "flag": "🇩🇰"}, "Warsaw": {"it": "Warsaw", "flag": "🇵🇱"},
    "Bucharest": {"it": "Bucharest", "flag": "🇷🇴"}, "Stockholm": {"it": "Stockholm", "flag": "🇸🇪"},
    "Athens": {"it": "Athens", "flag": "🇬🇷"}, "Berlin": {"it": "Berlin", "flag": "🇩🇪"},
    "Brussels": {"it": "Brussels", "flag": "🇧🇪"}, "Dublin": {"it": "Dublin", "flag": "🇮🇪"},
    "Lisbon": {"it": "Lisbon", "flag": "🇵🇹"}, "Ljubljana": {"it": "Ljubljana", "flag": "🇸🇮"},
    "Luxembourg": {"it": "Luxembourg", "flag": "🇱🇺"}, "Paris": {"it": "Paris", "flag": "🇫🇷"},
    "Rome": {"it": "Rome", "flag": "🇮🇹"}, "Valletta": {"it": "Valletta", "flag": "🇲🇹"},
    "Zagreb": {"it": "Zagreb", "flag": "🇭🇷"}, "Amsterdam": {"it": "Amsterdam", "flag": "🇳🇱"},
    "Vienna": {"it": "Vienna", "flag": "🇦🇹"}, "Madrid": {"it": "Madrid", "flag": "🇪🇸"},
    "Helsinki": {"it": "Helsinki", "flag": "🇫🇮"}, "Oslo": {"it": "Oslo", "flag": "🇳🇴"},
    "Bratislava": {"it": "Bratislava", "flag": "🇸🇰"}, "Budapest": {"it": "Budapest", "flag": "🇭🇺"},
    "Reykjavik": {"it": "Reykjavík", "flag": "🇮🇸"}, "Sofia": {"it": "Sofia", "flag": "🇧🇬"},
    "Tallinn": {"it": "Tallinn", "flag": "🇪🇪"}, "Riga": {"it": "Riga", "flag": "🇱🇻"},
    "Vilnius": {"it": "Vilnius", "flag": "🇱🇹"}, "Nicosia": {"it": "Nicosia", "flag": "🇨🇾"},
}

# Landmark images — scaricate in locale con download_images.py (Wikimedia Commons, licenza libera)
LANDMARK_IMAGES = {
    "Amsterdam":  "assets/images/amsterdam.jpg",
    "Athens":     "assets/images/athens.jpg",
    "Berlin":     "assets/images/berlin.jpg",
    "Bratislava": "assets/images/bratislava.jpg",
    "Brussels":   "assets/images/brussels.jpg",
    "Bucharest":  "assets/images/bucharest.jpg",
    "Budapest":   "assets/images/budapest.jpg",
    "Copenhagen": "assets/images/copenhagen.jpg",
    "Dublin":     "assets/images/dublin.jpg",
    "Helsinki":   "assets/images/helsinki.jpg",
    "Lisbon":     "assets/images/lisbon.jpg",
    "Ljubljana":  "assets/images/ljubljana.jpg",
    "London":     "assets/images/london.jpg",
    "Luxembourg": "assets/images/luxembourg.jpg",
    "Madrid":     "assets/images/madrid.jpg",
    "Nicosia":    "assets/images/nicosia.jpg",
    "Oslo":       "assets/images/oslo.jpg",
    "Paris":      "assets/images/paris.jpg",
    "Prague":     "assets/images/prague.jpg",
    "Reykjavik":  "assets/images/reykjavik.jpg",
    "Riga":       "assets/images/riga.jpg",
    "Rome":       "assets/images/rome.jpg",
    "Sofia":      "assets/images/sofia.jpg",
    "Stockholm":  "assets/images/stockholm.jpg",
    "Tallinn":    "assets/images/tallinn.jpg",
    "Valletta":   "assets/images/valletta.jpg",
    "Vienna":     "assets/images/vienna.jpg",
    "Vilnius":    "assets/images/vilnius.jpg",
    "Warsaw":     "assets/images/warsaw.jpg",
    "Zagreb":     "assets/images/zagreb.jpg",
}

# Patch transport for cities where CSV extraction failed
with open(INPUT_JSON_TRANSPORT_PATCHES, encoding='utf-8') as _f:
    TRANSPORT_PATCH = json.load(_f)

# Valuta locale: solo per le capitali fuori dall'area euro. Il codice ISO viene
# scritto come attributo opzionale `currency` sul root (DTD: #IMPLIED); le città
# euro non hanno l'attributo. I tassi vivono in currency_rates.json e li usa il sito.
INPUT_JSON_CURRENCY = str(ROOT / 'data' / 'currency_rates.json')
with open(INPUT_JSON_CURRENCY, encoding='utf-8') as _f:
    CITY_CURRENCY = json.load(_f).get('cities', {})

# Macro-regione geografica (UN M49): scritta come attributo ENUMERATO obbligatorio
# `region` sul root (DTD: (northern|western|southern|eastern) #REQUIRED). La mappa
# e la sua fonte vivono in geo_regions.json; il sito la usa come filtro di navigazione.
INPUT_JSON_REGION = str(ROOT / 'data' / 'geo_regions.json')
with open(INPUT_JSON_REGION, encoding='utf-8') as _f:
    CITY_REGION = json.load(_f).get('cities', {})

# District names that are clearly noise (not real city districts)
_NOISE_DISTRICTS = {
    'visitor info', 'visitor info:', 'buses', 'bus', 'trams', 'tram',
    'green line', 'world heritage site', 'world heritage', 'laibach', 'reval',
    'tourist information', 'tourist information:', 'to and from the airport:',
    'il-belt', 'to and from the airport',
    # Luxembourg - these are Mullerthal nature sites, not Luxembourg City districts
    'mullerthal', 'schéissendëmpel', 'hohllay', 'beaufort castles',
    # Stockholm County municipalities (not Stockholm city districts)
    'stockholm county', 'norrtälje', 'sigtuna', 'norrort',
    'stockholm archipelago', 'södertörn', 'södertälje',
}

# Per-city district overrides (when CSV data is completely wrong)
_DISTRICT_OVERRIDES = {
    # Luxembourg City actual quarters
    "Luxembourg": [
        ("Ville-Haute", "The historic and political centre of the city, home to the Grand Ducal Palace."),
        ("Grund", "A picturesque medieval district along the Alzette river, known for its bistros."),
        ("Kirchberg", "The European quarter, seat of EU institutions and the MUDAM museum."),
        ("Clausen", "A residential district along the Alzette, famous for its breweries."),
        ("Limpertsberg", "A leafy, upscale neighbourhood with the university and quality shops."),
    ],
    # Stockholm city districts (instead of county municipalities)
    "Stockholm": [
        ("Gamla Stan", "The medieval old town on its own island, the historic heart of Stockholm."),
        ("Södermalm", "The hip and creative district with cafés, markets and panoramic views."),
        ("Östermalm", "The elegant neighbourhood with the Östermalm Market Hall and embassies."),
        ("Norrmalm", "The commercial and cultural hub, home to the central railway station."),
        ("Kungsholmen", "An island district featuring City Hall (Stadshuset) and quiet residential areas."),
    ],
}


def clean_xml_text(text):
    if not text or str(text).lower() == 'nan':
        return ""
    return str(text).strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _plain(text):
    """Raw text (stripped, nan-safe) WITHOUT entity escaping: lxml escapes by itself."""
    if not text or str(text).lower() == 'nan':
        return ""
    return str(text).strip()


def _append_text(parent, last_child, text):
    """Append plain text to parent.text (no children yet) or to last_child.tail."""
    if not text:
        return
    if last_child is None:
        parent.text = (parent.text or "") + text
    else:
        last_child.tail = (last_child.tail or "") + text


def build_mixed_content(parent, raw_text, bold_terms=None):
    """Populate `parent` with mixed content: plain text interleaved with inline
    <b>/<i>/<link> children. Realises the *content-model misto* taught in the course
    (cfr. notebook 01.xmljson: <p><b>Bologna</b> ... <a href>...</a>).

    Rules (deterministic):
      - http(s) URL          -> <link href="URL">URL</link>
      - occurrence of a city name (bold_terms) -> <b>...</b>
      - parenthesised native proper name, e.g. (Stadshuset) -> (<i>Stadshuset</i>)
    `raw_text` must be UNescaped: lxml handles escaping on serialization.
    """
    raw_text = _plain(raw_text)
    if not raw_text:
        return
    bold_terms = [t for t in (bold_terms or []) if t]

    alternatives = [r'(?P<url>https?://[^\s<>"\)]+)']
    if bold_terms:
        alt = "|".join(re.escape(t) for t in sorted(set(bold_terms), key=len, reverse=True))
        alternatives.append(r'(?P<bold>\b(?:' + alt + r')\b)')
    alternatives.append(r'\((?P<ital>[A-ZÅÄÖØ][\wÅÄÖØåäöø-]+)\)')
    pattern = re.compile("|".join(alternatives))

    last_child = None
    pos = 0
    for m in pattern.finditer(raw_text):
        _append_text(parent, last_child, raw_text[pos:m.start()])
        kind = m.lastgroup
        if kind == 'url':
            child = etree.SubElement(parent, "link")
            child.set("href", m.group('url'))
            child.text = m.group('url')
        elif kind == 'bold':
            child = etree.SubElement(parent, "b")
            child.text = m.group('bold')
        else:  # parenthesised native name -> keep parens, italicise inside
            _append_text(parent, last_child, "(")
            child = etree.SubElement(parent, "i")
            child.text = m.group('ital')
            child.tail = ")"
        last_child = child
        pos = m.end()
    _append_text(parent, last_child, raw_text[pos:])


def advanced_wiki_cleaner(raw_text):
    """Clean Wikivoyage/Wikipedia wikitext into plain prose."""
    if not raw_text or str(raw_text).lower() == 'nan':
        return ""
    text = str(raw_text)
    # Remove templates (5 passes for nested ones)
    for _ in range(5):
        text = re.sub(r'\{\{[^{}]*?\}\}', '', text, flags=re.DOTALL)
    # Remove wiki tables
    text = re.sub(r'\{\|.*?\|\}', '', text, flags=re.DOTALL)
    # Remove file/image links
    text = re.sub(r'\[\[(File|Image|Categoria|Category):.*?\]\]', '', text,
                  flags=re.IGNORECASE | re.DOTALL)
    # [[link|display text]] → display text
    text = re.sub(r'\[\[[^|\]]*\|([^\]]+)\]\]', r'\1', text)
    # [[link]] → link text
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    # [http://url display text] → display text
    text = re.sub(r'\[https?://\S+\s+([^\]]*)\]', r'\1', text)
    # [http://url] (bare URL in brackets) → remove
    text = re.sub(r'\[https?://\S+\]', '', text)
    # Remove disambiguation hatnotes (:For other places..., :See also...)
    text = re.sub(r'^:.*\n?', '', text, flags=re.MULTILINE)
    # Remove bold/italic wiki markers
    text = re.sub(r"'{2,}", '', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove section headers (== Header ==)
    text = re.sub(r'=+[^=\n]*=+', '', text)
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', ' ', text)
    text = text.strip()
    text = clean_xml_text(text)

    if len(text) > 3000:
        truncated = text[:3000]
        # prefer cutting at a sentence boundary
        last_dot = max(truncated.rfind('. '), truncated.rfind('! '), truncated.rfind('? '))
        if last_dot > 2000:
            text = truncated[:last_dot + 1]
        else:
            last_space = truncated.rfind(' ')
            text = (truncated[:last_space] + "...") if last_space > 0 else (truncated + "...")
    return text if len(text) > 10 else ""


import unicodedata as _ud


def _ascii_lower(s):
    """Lower-case and strip accents for accent-insensitive comparison."""
    return _ud.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()


def find_orig_file(orig_dir, name):
    """Locate the original XML file, tolerating accent variants (e.g. Reykjavík vs Reykjavik)."""
    direct = os.path.join(orig_dir, f"{name}.xml")
    if os.path.exists(direct):
        return direct
    name_ascii = _ascii_lower(name)
    for fname in os.listdir(orig_dir):
        if fname.lower().endswith('.xml') and _ascii_lower(fname[:-4]) == name_ascii:
            return os.path.join(orig_dir, fname)
    return direct  # will not exist; caller checks


def _get_pages(orig_file):
    """Return list of (title, text) pairs from a Wikivoyage MediaWiki XML dump."""
    ns = {'mw': MW_NS}
    tree = etree.parse(orig_file)
    result = []
    for page in tree.findall('.//mw:page', ns):
        title = page.findtext('mw:title', namespaces=ns) or ""
        text = page.findtext('.//mw:text', namespaces=ns) or ""
        result.append((title, text))
    return result


def get_city_main_text(orig_file, city_name):
    """
    Find city-level intro text from its Wikivoyage dump.

    Priority:
      1. Page whose title matches the city name exactly (accent-insensitive)
      2. "CityName/Understand" sub-page (city-wide intro section)
      3. Empty string — cities with only district sub-pages return nothing
         (showing a district page as a city intro is misleading)
    """
    if not os.path.exists(orig_file):
        return ""
    pages = _get_pages(orig_file)
    city_ascii = _ascii_lower(city_name)

    # Priority 1: accent-insensitive exact title match
    for title, text in pages:
        if _ascii_lower(title) == city_ascii:
            return text

    # Priority 2: "CityName/Understand" — Wikivoyage intro section
    for title, text in pages:
        if _ascii_lower(title) == city_ascii + "/understand":
            return text

    return ""


def get_subpage_texts(orig_file, city_name):
    """
    Return {normalised_district_key: wiki_text} for all sub-pages of a city.
    Keys have any "CityName/" prefix stripped and are lower-cased.
    Uses accent-insensitive prefix stripping so Reykjavik matches Reykjavík/.
    """
    if not os.path.exists(orig_file):
        return {}
    pages = _get_pages(orig_file)
    city_ascii = _ascii_lower(city_name)
    prefix_ascii = city_ascii + "/"
    result = {}
    for title, text in pages:
        title_ascii = _ascii_lower(title)
        if title_ascii.startswith(prefix_ascii):
            key = title[len(city_name) + 1:]  # strip prefix by character count
        else:
            key = title
        result[key.lower()] = text
    return result


def clean_district_names(raw_str, city_name):
    """
    Parse pipe-separated district names from the CSV Districts column.
    Strips any "CityName/" prefix and removes known noise entries.
    Returns at most 5 clean district names.
    """
    if not raw_str or str(raw_str).lower() == 'nan':
        return []
    prefix = f"{city_name}/"
    seen = set()
    result = []
    for part in str(raw_str).split('|'):
        d = part.strip()
        if d.startswith(prefix):
            d = d[len(prefix):]
        d = d.strip()
        if not d or len(d) < 3:
            continue
        if d.lower() in _NOISE_DISTRICTS:
            continue
        if d.endswith(':'):          # header labels like "Visitor info:"
            continue
        if d.lower() not in seen:
            seen.add(d.lower())
            result.append(d)
    return result[:5]


def get_district_description(district_name, subpage_texts):
    """
    Try to find a wiki intro for a district by fuzzy-matching its name
    against the available sub-page texts.
    """
    d_lower = district_name.lower()
    # Exact key match
    if d_lower in subpage_texts:
        return advanced_wiki_cleaner(subpage_texts[d_lower])
    # Partial match: district name contained in a page key or vice-versa
    words = [w for w in d_lower.split() if len(w) > 3]
    for key, text in subpage_texts.items():
        if d_lower in key or key in d_lower or any(w in key for w in words):
            cleaned = advanced_wiki_cleaner(text)
            if cleaned:
                return cleaned
    return ""


def _row_get(row, key, default=''):
    """Get a value from either a pandas Series row or an empty fallback dict."""
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        val = row[key]
        return val if pd.notna(val) else default
    except (KeyError, TypeError):
        return default


def parse_hotels(hotel_str):
    hotels = []
    if not hotel_str or str(hotel_str).lower() == 'nan':
        return hotels
    for p in hotel_str.split('|'):
        match = re.search(r'^(.*?)\s*\((.*?)\)$', p.strip())
        if match:
            hotels.append({'n': match.group(1).strip(), 'p': match.group(2).strip()})
        else:
            hotels.append({'n': p.strip(), 'p': 'Prezzo N/D'})
    return hotels


def run_pipeline():
    print("🚀 Avvio pipeline completa: estrazione, pulizia e validazione DTD...")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    try:
        dtd = etree.DTD(open(DTD_FILE, 'rb'))
        df_wiki_raw = pd.read_csv(INPUT_CSV_WIKI)
        # Build a lookup dict keyed by upper-case city name; values are row dicts
        wiki_lookup = {
            row['City'].upper(): row
            for _, row in df_wiki_raw.iterrows()
        }
        df_attr = pd.read_csv(INPUT_CSV_ATTR)
        with open(INPUT_JSON_INDICES, 'r', encoding='utf-8') as f:
            city_entries = json.load(f)['capitali']
        with open(INPUT_JSON_DESC, 'r', encoding='utf-8') as f:
            narratives = json.load(f)
        nightlife_data = {}
        if os.path.exists(INPUT_JSON_NIGHTLIFE):
            with open(INPUT_JSON_NIGHTLIFE, 'r', encoding='utf-8') as f:
                nightlife_data = json.load(f)
    except Exception as e:
        print(f"❌ Errore fatale nel caricamento dei dati: {e}")
        return

    for city_idx in city_entries:
        name = city_idx['city']
        # Only process cities that are in the CITY_MAP
        if name not in CITY_MAP:
            continue
        # Supplementary CSV row (may be absent for some cities like Reykjavik)
        wiki_row = wiki_lookup.get(name.upper(), {})
        orig_file = find_orig_file(ORIGINAL_XML_DIR, name)

        # --- Estrazione testo principale dalla pagina Wikivoyage corretta ---
        full_text = get_city_main_text(orig_file, name)
        subpage_texts = get_subpage_texts(orig_file, name)

        score = round(
            city_idx['safety'] * 0.4
            + city_idx['green_score'] * 0.4
            + (100 - city_idx['cost_of_living']) * 0.2,
            1
        )

        root = etree.Element("city_report", appeal_score=str(score))
        # Valuta locale (solo capitali fuori area euro): attributo opzionale sul root.
        local_currency = CITY_CURRENCY.get(name)
        if local_currency:
            root.set("currency", local_currency)
        # Macro-regione geografica (UN M49): attributo enumerato obbligatorio sul root.
        region = CITY_REGION.get(name)
        if region:
            root.set("region", region)
        else:
            # Senza regione il file non sarebbe valido (attributo #REQUIRED): segnala.
            print(f"⚠️  {name}: regione mancante in geo_regions.json")

        # --- metadata ---
        meta = etree.SubElement(root, "metadata")
        etree.SubElement(meta, "title").text = name
        etree.SubElement(meta, "name_it").text = CITY_MAP.get(name, {}).get("it", name)
        etree.SubElement(meta, "flag").text = CITY_MAP.get(name, {}).get("flag", "🇪🇺")
        # Canonical URI of the city — Wikivoyage, la fonte effettiva dei documenti
        # (mirrored as microdata itemid in the HTML)
        etree.SubElement(meta, "source_url").text = (
            f"https://en.wikivoyage.org/wiki/{name.replace(' ', '_')}"
        )

        # --- indicators ---
        ind = etree.SubElement(root, "indicators")
        hotel_count = _row_get(wiki_row, 'Hotel_Count', 0)
        etree.SubElement(ind, "hotel_count").text = str(hotel_count)
        etree.SubElement(ind, "hotel_price").text = str(round(city_idx['cost_of_living'] * 1.85, 2))
        etree.SubElement(ind, "safety", index_score=str(city_idx['safety']))
        etree.SubElement(ind, "environment", green_score=str(city_idx['green_score']))
        etree.SubElement(ind, "cost_index", value=str(city_idx['cost_of_living']))
        etree.SubElement(ind, "economic_accessibility", score=str(round(100 - city_idx['cost_of_living'], 1)))

        # --- transport (patch takes priority for cities with missing/Italian CSV data) ---
        if name in TRANSPORT_PATCH:
            transport_text = TRANSPORT_PATCH[name]
        else:
            transport_text = str(_row_get(wiki_row, 'Transport_Text', ''))
            if not transport_text or transport_text.lower() == 'nan':
                transport_text = "Public transport information unavailable."
        city_it = CITY_MAP.get(name, {}).get("it", name)
        build_mixed_content(
            etree.SubElement(root, "transport"), transport_text,
            bold_terms=[name, city_it],
        )

        # --- accommodation ---
        acc_node = etree.SubElement(root, "accommodation")
        for h in parse_hotels(str(_row_get(wiki_row, 'Hotels_Extracted', ''))):
            h_node = etree.SubElement(acc_node, "hotel")
            etree.SubElement(h_node, "name").text = clean_xml_text(h['n'])
            etree.SubElement(h_node, "price").text = clean_xml_text(h['p'])

        # --- highlights / attractions ---
        high = etree.SubElement(root, "highlights")
        for _, row in df_attr[df_attr['City'] == name].head(10).iterrows():
            attr = etree.SubElement(high, "attraction",
                                    lat=str(row['Latitude']), lon=str(row['Longitude']))
            etree.SubElement(attr, "name").text = clean_xml_text(row['Attraction'])
            etree.SubElement(attr, "description").text = clean_xml_text(row['Description'])

        # --- districts: per-city overrides > CSV > (no districts) ---
        if name in _DISTRICT_OVERRIDES:
            override_list = _DISTRICT_OVERRIDES[name]
            if override_list:
                dist_tag = etree.SubElement(root, "districts")
                for dname, ddesc in override_list:
                    d_node = etree.SubElement(dist_tag, "district")
                    etree.SubElement(d_node, "name").text = clean_xml_text(dname)
                    etree.SubElement(d_node, "description").text = clean_xml_text(ddesc)
        else:
            csv_districts_raw = str(_row_get(wiki_row, 'Districts', ''))
            district_names = clean_district_names(csv_districts_raw, name)
            if district_names:
                dist_tag = etree.SubElement(root, "districts")
                city_it = CITY_MAP.get(name, {}).get("it", name)
                for dname in district_names:
                    d_node = etree.SubElement(dist_tag, "district")
                    etree.SubElement(d_node, "name").text = clean_xml_text(dname)
                    desc = get_district_description(dname, subpage_texts)
                    if not desc:
                        desc = clean_xml_text(f"Quartiere di {city_it}.")
                    etree.SubElement(d_node, "description").text = desc

        # --- strategic description (Italian narrative, mixed content) ---
        build_mixed_content(
            etree.SubElement(root, "description"),
            narratives.get(name, f"Analisi di {name}."),
            bold_terms=[name, city_it],
        )

        # --- wiki intro from the correct main page (mixed content) ---
        wiki_intro_text = advanced_wiki_cleaner(full_text)
        if wiki_intro_text:
            build_mixed_content(
                etree.SubElement(root, "wiki_intro"), wiki_intro_text,
                bold_terms=[name, city_it],
            )

        # --- landmark image ---
        landmark = LANDMARK_IMAGES.get(name, "")
        if landmark:
            etree.SubElement(root, "landmark_image").text = landmark

        # --- nightlife (from Overpass API, optional) ---
        # Only geolocated venues are kept: lat/lon are #REQUIRED in the DTD because
        # every venue is plotted on the map (no coordinates → not placeable).
        venues = [
            v for v in nightlife_data.get(name, [])
            if str(v.get("lat", "")).strip() and str(v.get("lon", "")).strip()
        ]
        if venues:
            nl_el = etree.SubElement(root, "nightlife")
            for v in venues:
                # category è un attributo enumerato nel DTD: vincola ai valori ammessi
                cat = v["category"] if v["category"] in ("bar", "pub", "nightclub") else "bar"
                venue_el = etree.SubElement(
                    nl_el, "venue",
                    lat=str(v["lat"]),
                    lon=str(v["lon"]),
                    category=cat
                )
                etree.SubElement(venue_el, "name").text = clean_xml_text(v["name"])

        # --- DTD validation and output ---
        if dtd.validate(root):
            tree = etree.ElementTree(root)
            tree.write(
                os.path.join(OUTPUT_DIR, f"{name.lower()}.xml"),
                xml_declaration=True, encoding='UTF-8', pretty_print=True,
                doctype='<!DOCTYPE city_report SYSTEM "../city_report.dtd">'
            )
            print(f"✅ {name} generato correttamente.")
        else:
            errors = dtd.error_log.filter_from_errors()
            print(f"⚠️  Errore DTD su {name}: {errors}")


if __name__ == "__main__":
    run_pipeline()
