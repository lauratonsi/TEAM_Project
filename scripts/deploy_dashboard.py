import os, json, re, html, glob, hashlib
from pathlib import Path
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent


def count_microdata(paths):
    """Count microdata annotations across the GENERATED HTML files (regex-based, no
    external deps). Used in the report to quantify, verifiably, the injected microdata.
    Cross-checked with the `microdata` library (microdata.get_items) used in the course."""
    import collections
    tot = {'items': 0, 'props': 0, 'ids': 0}
    by_type = collections.Counter()
    by_prop = collections.Counter()
    for p in paths:
        try:
            with open(p, encoding='utf-8') as f:
                src = f.read()
        except OSError:
            continue
        tot['items'] += len(re.findall(r'\bitemscope\b', src))
        tot['ids']   += len(re.findall(r'\bitemid=', src))
        for t in re.findall(r'''itemtype=["']([^"']+)["']''', src):
            by_type[t.rsplit('/', 1)[-1]] += 1
        for pr in re.findall(r'''itemprop=["']([^"']+)["']''', src):
            by_prop[pr] += 1
            tot['props'] += 1
    return tot, by_type, by_prop


def inline_to_html(el):
    """Serialise an element's *mixed content* into an HTML fragment, mapping the
    DTD inline vocabulary (b / i / link) to HTML (b / i / a). Plain text and tails
    are HTML-escaped; the generated tags are literal. Returns '' if `el` is None.

    Needed because findtext() drops child-element text: once description/wiki_intro/
    transport carry inline markup, we must walk the node to keep the full text."""
    if el is None:
        return ""
    parts = [html.escape(el.text)] if el.text else []
    for child in el:
        tag = etree.QName(child).localname
        inner = html.escape(child.text or "")
        if tag == "link":
            href = html.escape(child.get("href", ""), quote=True)
            parts.append(f'<a href="{href}" target="_blank" rel="noopener">{inner}</a>')
        elif tag in ("b", "i"):
            # Map the XML inline vocabulary to *semantic* HTML inline tags
            # (slide del corso: preferire <strong>/<em> ai presentazionali <b>/<i>).
            html_tag = {"b": "strong", "i": "em"}[tag]
            parts.append(f"<{html_tag}>{inner}</{html_tag}>")
        else:
            parts.append(inner)
        if child.tail:
            parts.append(html.escape(child.tail))
    return "".join(parts)


# --- CONFIGURAZIONE ---
XML_DIR = str(ROOT / 'data' / 'xml_dataset')
OUTPUT_HTML = str(ROOT / 'index.html')
REPORT_HTML = str(ROOT / 'pages' / 'report.html')
MAP_FILE = str(ROOT / 'pages' / 'mappa_attrazioni.html')
DTD_FILE = str(ROOT / 'data' / 'city_report.dtd')
CURRENCY_FILE = str(ROOT / 'data' / 'currency_rates.json')

# Cache-busting del foglio di stile: un hash del contenuto di stile.css viene
# accodato come ?v=… ai link CSS, così a ogni modifica del CSS il browser è
# costretto a riscaricarlo (niente più stile vecchio servito dalla cache).
try:
    with open(str(ROOT / 'stile.css'), 'rb') as _css:
        CSS_VER = hashlib.md5(_css.read()).hexdigest()[:8]
except OSError:
    CSS_VER = '1'

# --- VALUTA LOCALE (capitali fuori area euro) ---
# I prezzi del dataset sono SINTETICI e denominati in EUR (hotel_price =
# cost_of_living × 1.85). Per le città non-euro teniamo l'EUR come unità primaria
# (comparabile in tutto il sito) e affianchiamo l'equivalente locale INDICATIVO,
# letto dai tassi di currency_rates.json. La valuta di ciascuna città arriva
# dall'attributo opzionale @currency del documento XML.
with open(CURRENCY_FILE, encoding='utf-8') as _cf:
    _CUR = json.load(_cf)
CURRENCIES = _CUR.get('currencies', {})
CURRENCY_SNAPSHOT = _CUR.get('_meta', {}).get('snapshot', '')

def local_price(eur_value, code):
    """Equivalente locale indicativo di un importo EUR (stringa già formattata,
    es. '1.664 kr'). Ritorna '' per le città in area euro o codici sconosciuti."""
    meta = CURRENCIES.get(code or '')
    if not meta:
        return ''
    try:
        amount = float(eur_value or 0) * meta['per_eur']
    except (TypeError, ValueError):
        return ''
    if amount >= 100:                              # valute "grandi" (HUF, ISK, kr): interi
        n_disp = f"{round(amount):,.0f}".replace(',', '.')
    else:                                          # GBP, BGN: un decimale
        n_disp = f"{round(amount, 1)}"
    return f"{n_disp} {meta['symbol']}"

def currency_meta(code):
    """Metadati valuta (symbol, name_it, …) o None se euro/sconosciuto."""
    return CURRENCIES.get(code or '')

# --- MAPPA: coordinate capitali e palette colori ---
CAPITAL_COORDS = {
    'amsterdam': (52.3676, 4.9041), 'athens': (37.9838, 23.7275),
    'berlin': (52.5200, 13.4050), 'bratislava': (48.1486, 17.1077),
    'brussels': (50.8503, 4.3517), 'bucharest': (44.4268, 26.1025),
    'budapest': (47.4979, 19.0402), 'copenhagen': (55.6761, 12.5683),
    'dublin': (53.3498, -6.2603), 'helsinki': (60.1699, 24.9384),
    'lisbon': (38.7169, -9.1395), 'ljubljana': (46.0569, 14.5058),
    'london': (51.5074, -0.1278), 'luxembourg': (49.6117, 6.1319),
    'madrid': (40.4168, -3.7038), 'nicosia': (35.1856, 33.3823),
    'oslo': (59.9139, 10.7522), 'paris': (48.8566, 2.3522),
    'prague': (50.0755, 14.4378), 'reykjavik': (64.1355, -21.8954),
    'riga': (56.9460, 24.1059), 'rome': (41.9028, 12.4964),
    'sofia': (42.6977, 23.3219), 'stockholm': (59.3293, 18.0686),
    'tallinn': (59.4370, 24.7536), 'valletta': (35.8989, 14.5146),
    'vienna': (48.2082, 16.3738), 'vilnius': (54.6872, 25.2797),
    'warsaw': (52.2297, 21.0122), 'zagreb': (45.8150, 15.9819),
}

# --- REGIONE GEOGRAFICA (geoscheme UN M49) ---
# Dimensione di navigazione: la macro-area di ogni capitale è un dato di prima
# classe scritto nell'XML come attributo enumerato `region` (vedi geo_regions.json
# e final_processor.py). Qui servono solo le ETICHETTE mostrate nei filtri UI;
# i valori arrivano dal documento via XPath string(/city_report/@region).
REGION_LABELS = {
    'northern': '🧭 Northern', 'western': '🌅 Western',
    'southern': '☀️ Southern', 'eastern': '🌄 Eastern',
}
# Nome esteso + codice UN M49 per ciascuna macro-regione: usati nei microdata
# schema.org delle schede città (City containedInPlace → Place → Continent Europe).
REGION_META = {
    'northern': ('Northern Europe', '154'),
    'western':  ('Western Europe',  '155'),
    'southern': ('Southern Europe', '039'),
    'eastern':  ('Eastern Europe',  '151'),
}

CITY_PALETTE = [
    '#E74C3C','#3498DB','#2ECC71','#F39C12','#9B59B6',
    '#1ABC9C','#E67E22','#34495E','#E91E63','#00BCD4',
    '#FF5722','#607D8B','#8BC34A','#FF9800','#673AB7',
    '#795548','#C0392B','#2980B9','#27AE60','#D35400',
    '#8E44AD','#16A085','#2C3E50','#F1C40F','#17A589',
    '#884EA0','#1A5276','#1E8449','#922B21','#1F618D',
]


def _map_js_block(city_data, div_id, city_link_prefix='', with_layer_control=False):
    """Restituisce il blocco <script> Leaflet per il div indicato.
    city_link_prefix: prefisso URL per i link alle pagine città.
    with_layer_control: se True aggiunge un controllo per filtrare i livelli
    (attrazioni / locali / capitali) — usato nella mappa a tutta pagina."""
    sorted_cities = sorted(city_data, key=lambda c: c['city_lower'])
    color_map = {c['city_lower']: CITY_PALETTE[i % len(CITY_PALETTE)]
                 for i, c in enumerate(sorted_cities)}

    map_data = []
    for city in sorted_cities:
        cl = city['city_lower']
        color = color_map[cl]
        coord = CAPITAL_COORDS.get(cl, (None, None))
        valid_attrs = []
        for a in city['attractions']:
            try:
                valid_attrs.append({'n': a['n'] or '', 'd': a['d'] or '',
                                    'lat': float(a['lat']), 'lon': float(a['lon'])})
            except (TypeError, ValueError):
                pass
        valid_venues = []
        for v in city.get('nightlife', []):
            try:
                valid_venues.append({
                    'n': v['n'] or '',
                    'cat': v['cat'] or 'bar',
                    'lat': float(v['lat']),
                    'lon': float(v['lon']),
                })
            except (TypeError, ValueError):
                pass
        map_data.append({
            'cl': cl, 'name': city['name_it'], 'flag': city['flag'],
            'appeal': city['appeal'], 'color': color,
            'link': city_link_prefix + cl + '.html',
            'capLat': coord[0], 'capLon': coord[1],
            'attrs': valid_attrs,
            'venues': valid_venues,
        })

    map_data_json = json.dumps(map_data, ensure_ascii=False)
    # I nomi di variabili JS non possono contenere trattini
    var_id = div_id.replace('-', '_')

    # Stringa non-f-string: le {} di JS non conflittano con Python
    js = (
        "<script>\n"
        "var map_VID=L.map('DID',{center:[52,15],zoom:4});\n"
        "L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',"
        "{attribution:'\\u00a9 OpenStreetMap \\u00a9 CARTO',maxZoom:19}).addTo(map_VID);\n"
        "var attr_VID=L.markerClusterGroup({chunkedLoading:true});\n"
        "var venue_VID=L.markerClusterGroup({chunkedLoading:true});\n"
        # capitali: clustering anche per loro → niente marker sovrapposti a zoom basso
        # (tap-target a11y). A zoom 6+ i cluster si aprono e ogni pillola torna cliccabile.
        "var cap_VID=L.markerClusterGroup({maxClusterRadius:55,showCoverageOnHover:false,spiderfyOnMaxZoom:true,disableClusteringAtZoom:6});\n"
        "var mapData_VID=DATA_JSON;\n"
        "mapData_VID.forEach(function(c){\n"
        "  c.attrs.forEach(function(a){\n"
        "    L.circleMarker([a.lat,a.lon],{radius:9,color:c.color,fillColor:c.color,fillOpacity:0.85,weight:2})\n"
        "    .addTo(attr_VID)\n"
        "    .bindPopup('<div class=\"mp\"><h4 style=\"color:'+c.color+';margin:0 0 3px\">'+a.n+'</h4>'\n"
        "      +'<small style=\"color:#888\">'+c.flag+' '+c.name+'</small>'\n"
        "      +'<p style=\"margin:6px 0;font-size:.8rem\">'+a.d+'</p>'\n"
        "      +'<a href=\"'+c.link+'\" class=\"pl\">Explore '+c.name+' \\u2192</a></div>')\n"
        "    .bindTooltip(a.n+' ('+c.name+')');\n"
        "  });\n"
        "  var venueIcons={bar:'🍺',pub:'🍺',biergarten:'🍺',nightclub:'🎵'};\n"
        "  (c.venues||[]).forEach(function(v){\n"
        "    var ico=venueIcons[v.cat]||'🍺';\n"
        "    L.marker([v.lat,v.lon],{icon:L.divIcon({\n"
        "      className:'',\n"
        "      html:'<div class=\"venue-mk\">'+ico+'</div>',\n"
        "      iconSize:[32,32],iconAnchor:[16,16]\n"
        "    })})\n"
        "    .addTo(venue_VID)\n"
        "    .bindPopup('<div class=\"mp\"><h4 style=\"margin:0 0 3px\">'+ico+' '+v.n+'</h4>'\n"
        "      +'<small style=\"color:#888\">'+c.flag+' '+c.name+'</small>'\n"
        "      +'<p style=\"margin:6px 0;font-size:.8rem;color:#64748b\">'+v.cat+'</p>'\n"
        "      +'<a href=\"'+c.link+'\" class=\"pl\">Explore '+c.name+' \\u2192</a></div>')\n"
        "    .bindTooltip(v.n+' ('+c.name+')');\n"
        "  });\n"
        "  if(c.capLat!==null){\n"
        "    L.marker([c.capLat,c.capLon],{icon:L.divIcon({\n"
        "      className:'',\n"
        "      html:'<div class=\"cap-mk\" style=\"background:'+c.color+'\">'+'<span>'+c.flag+'</span><b>'+c.appeal+'</b></div>',\n"
        "      iconSize:[70,28],iconAnchor:[35,14]\n"
        "    })}).addTo(cap_VID)\n"
        "    .bindPopup('<div class=\"mp\"><b>'+c.flag+' '+c.name+'</b>'\n"
        "      +'<br>Appeal: <b>'+c.appeal+'</b>'\n"
        "      +'<br><a href=\"'+c.link+'\" class=\"pl\">Explore '+c.name+' \\u2192</a></div>');\n"
        "  }\n"
        "});\n"
        "map_VID.addLayer(attr_VID);map_VID.addLayer(venue_VID);map_VID.addLayer(cap_VID);\n"
        + ("L.control.layers(null,{'\\ud83d\\udccd Attrazioni':attr_VID,"
           "'\\ud83c\\udf7a Bar e locali':venue_VID,"
           "'\\ud83c\\udfc1 Capitali':cap_VID},{collapsed:false}).addTo(map_VID);\n"
           if with_layer_control else "")
        + "</script>"
    ).replace('VID', var_id).replace('DID', div_id).replace('DATA_JSON', map_data_json)

    return js


def generate_map(city_data):
    """Genera pages/mappa_attrazioni.html: mappa Leaflet navigabile con header, legenda
    e controllo dei livelli (attrazioni / locali / capitali)."""
    map_js = _map_js_block(city_data, 'map', 'cities/', with_layer_control=True)
    n_attr = sum(len(c['attractions']) for c in city_data)
    n_ven  = sum(len(c['nightlife']) for c in city_data)
    map_html = (
        "<!DOCTYPE html>\n<html lang='en'><head>\n"
        "<meta charset='UTF-8'>\n"
        "<title>Mappa — EuroCity</title>\n"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
        f"<link rel='stylesheet' href='../stile.css?v={CSS_VER}'>\n"
        "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css'>\n"
        "<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css'>\n"
        "<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css'>\n"
        "<style>\n"
        "html,body{height:100%;margin:0}\n"
        "body{display:flex;flex-direction:column;font-family:Inter,sans-serif}\n"
        ".map-wrap{position:relative;flex:1 1 auto;min-height:0}\n"
        "#map{position:absolute;inset:0}\n"
        ".cap-mk{display:flex;align-items:center;gap:4px;padding:4px 9px;border-radius:20px;"
        "font-weight:800;font-size:.72rem;color:#fff;box-shadow:0 2px 8px rgba(0,0,0,.35);white-space:nowrap}\n"
        ".venue-mk{font-size:20px;line-height:32px;width:32px;text-align:center;filter:drop-shadow(0 1px 3px rgba(0,0,0,.35))}\n"
        ".mp{min-width:190px;max-width:260px}\n"
        ".mp h4{font-size:.9rem;margin:0 0 2px}\n"
        ".pl{display:inline-block;margin-top:7px;color:#E74C3C;font-weight:700;font-size:.78rem;text-decoration:none}\n"
        ".pl:hover{text-decoration:underline}\n"
        ".map-legend{position:absolute;left:12px;bottom:18px;z-index:1000;background:#fff;"
        "border:1px solid var(--slate-200);border-radius:12px;padding:12px 14px;font-size:.78rem;"
        "box-shadow:0 4px 14px rgba(0,0,0,.12);max-width:230px}\n"
        ".map-legend h4{margin:0 0 8px;font-size:.8rem;color:var(--primary-dark)}\n"
        ".map-legend div{display:flex;align-items:center;gap:8px;margin:5px 0;color:var(--slate-800)}\n"
        ".lg-dot{width:13px;height:13px;border-radius:50%;background:#E74C3C;border:2px solid #C0392B;flex:none}\n"
        ".map-intro{position:absolute;left:12px;top:12px;z-index:1000;background:rgba(255,255,255,.94);"
        "border-radius:12px;padding:10px 14px;font-size:.8rem;box-shadow:0 4px 14px rgba(0,0,0,.12);max-width:260px}\n"
        ".map-intro b{color:var(--accent)}\n"
        "@media(max-width:600px){.map-legend{display:none}}\n"
        "</style>\n"
        "</head><body>\n"
        "<a href='#map' class='skip-link'>Salta alla mappa</a>\n"
        "<header class='topbar'>\n"
        "  <div class='topbar-inner'>\n"
        "    <a href='../index.html' class='topbar-logo'>EuroCity <b>SI</b></a>\n"
        "    <nav class='topbar-nav' aria-label='Navigazione principale'>\n"
        "      <a href='../index.html'>\U0001f3e0 Home</a>\n"
        "      <a href='mappa_attrazioni.html' class='active' aria-current='page'>\U0001f5fa️ Map</a>\n"
        "      <a href='report.html'>\U0001f4ca Report</a>\n"
        "    </nav>\n"
        "  </div>\n"
        "</header>\n"
        "<main class='map-wrap' aria-label='Mappa interattiva delle attrazioni e dei locali'>\n"
        "  <div id='map'></div>\n"
        "  <div class='map-intro'>\U0001f5fa️ <b>" + str(len(city_data)) + " capitali</b> · "
        + str(n_attr) + " attrazioni · " + str(n_ven) + " locali.<br>"
        "Usa il pannello in alto a destra per filtrare i livelli.</div>\n"
        "  <div class='map-legend'>\n"
        "    <h4>Legenda</h4>\n"
        "    <div><span class='lg-dot'></span> Attrazione turistica<br><small style='color:#94a3b8'>(colore = città)</small></div>\n"
        "    <div><span>\U0001f37a</span> Bar / Pub</div>\n"
        "    <div><span>\U0001f3b5</span> Nightclub</div>\n"
        "    <div><span class='cap-mk' style='background:#334155'>\U0001f3f3 99</span> Capitale (Appeal)</div>\n"
        "  </div>\n"
        "</main>\n"
        "<script src='https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js'></script>\n"
        "<script src='https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.js'></script>\n"
        + map_js + "\n</body></html>"
    )
    os.makedirs(os.path.dirname(MAP_FILE), exist_ok=True)
    with open(MAP_FILE, 'w', encoding='utf-8') as f:
        f.write(map_html)
    print(f"🗺️  Mappa rigenerata: {MAP_FILE}")


def _fv(x):
    try: return float(x or 0)
    except: return 0.0

def _pct(val, maxv=100):
    try: return round(min(100, max(0, float(val or 0) / maxv * 100)))
    except: return 0

def _price(val):
    """Formatta prezzo: 157.25 → '157' (arrotondato all'euro intero)."""
    try: return str(round(float(val or 0)))
    except: return str(val)


# ─────────────────────────────────────────────────────────────────────────────
# VIRTUAL ANALYST — widget flottante riusabile su tutte le pagine
# Markup (launcher + popup) e script sono fattorizzati qui così da iniettare
# l'identico chatbot su index e su ogni scheda città. NB: la LOGICA di query
# (runQuery / clientSideAnswer) è invariata; si aggiunge solo il toggle apri/chiudi.
# ─────────────────────────────────────────────────────────────────────────────
def analyst_widget_html():
    """Launcher flottante + pannello popup dell'analista (HTML statico)."""
    return """
<!-- ═══ FLOATING VIRTUAL ANALYST ════════════════════════════════════════ -->
<button id="va-launcher" class="va-launcher" aria-label="Open the Virtual Analyst" aria-expanded="false">
    <span class="va-launcher-ico">🤖</span>
    <span class="va-launcher-txt">Ask the analyst</span>
</button>
<div id="va-widget" class="va-widget" role="dialog" aria-label="Virtual Analyst" aria-modal="false" hidden>
    <div class="analyst-panel va-panel">
        <div class="analyst-header">
            <div class="analyst-icon">🤖</div>
            <div class="va-head-txt">
                <p class="analyst-title">Virtual Analyst</p>
                <p class="analyst-sub">RAG · BM25 + FAISS · metadata-filtered</p>
            </div>
            <button id="va-close" class="va-close" aria-label="Close the analyst">✕</button>
        </div>
        <div class="analyst-input-row">
            <input type="text" id="chat-input" class="analyst-input"
                   placeholder="e.g. transport Rome, nightclubs in non-euro cities…">
            <button id="chat-btn" class="analyst-btn">Ask</button>
        </div>
        <div id="chat-output" class="analyst-output">
            System ready — ask in English or Italian, or click an example below.
        </div>
        <p class="analyst-hint" style="margin:8px 0 4px;font-size:0.78rem;color:var(--slate-500)">
            💬 You can ask in <b>English or Italian</b> — try a single city, or filter by
            region · currency · category · numeric threshold.
        </p>
        <div class="analyst-chips">
            <button class="chip" data-q="transport Rome">🚇 transport Rome</button>
            <button class="chip" data-q="hotels Amsterdam">🏨 hotels Amsterdam</button>
            <button class="chip" data-q="museums Athens">🏛️ museums Athens</button>
            <button class="chip" data-q="bars in Dublin">🍺 bars Dublin</button>
            <button class="chip" data-q="safety Vienna">🛡️ safety Vienna</button>
            <button class="chip" data-q="districts Prague">🏘️ districts Prague</button>
            <button class="chip" data-q="nightclubs in non-euro cities">🎵 nightclubs · non-euro</button>
            <button class="chip" data-q="attractions in northern europe">🗺️ attractions · north</button>
            <button class="chip" data-q="pubs in eastern europe">🍻 pubs · east</button>
            <button class="chip" data-q="cities with appeal over 60">⭐ appeal &gt; 60</button>
            <button class="chip" data-q="greenest cities">🌱 greenest cities</button>
            <button class="chip" data-q="most affordable cities">💰 most affordable</button>
        </div>
        <details class="analyst-details">
            <summary>How does it work?</summary>
            <p>
                Ask a question and the analyst <b>looks up the answer</b> in the 30 city files — it never
                makes things up. It searches in two ways at once: by <b>meaning</b> (so "where to sleep"
                also finds hotels) and by <b>exact keywords</b>, then merges the two rankings.
            </p>
            <p>
                For precise questions it also uses the <b>metadata</b> built into every city — region,
                currency and venue type — like the <b>filters on a shopping site</b>: it first narrows the
                cities down (e.g. <i>non-euro</i> + <i>nightclub</i>), then searches inside them. Numbers
                (coordinates, appeal score, indicators) come <b>straight from the data</b>, so they are always exact.
            </p>
            <p style="font-size:0.8rem; color:var(--slate-500); margin:8px 0 0;">
                💡 On this published site the analyst runs <b>entirely in your browser</b>, no server needed.
                It only knows the 30 capitals in the dataset; some lack hotel data because they are absent
                from the Wikivoyage sources.
            </p>
        </details>
    </div>
</div>
"""


def analyst_script(city_data):
    """Script dell'analista (logica di query INVARIATA) + toggle del widget flottante."""
    return f"""<script>
const cityData = {json.dumps(city_data)};

/* chat query — tenta il server RAG locale, poi fallback client-side */
const RAG_API = 'http://127.0.0.1:8000';

async function runQuery() {{
    const q = document.getElementById('chat-input').value.trim();
    const out = document.getElementById('chat-output');
    if (!q) return;
    out.innerHTML = '<span style="color:#64748b;font-size:.9rem">⏳ Searching...</span>';
    try {{
        const ctrl = new AbortController();
        const tid = setTimeout(() => ctrl.abort(), 5000);
        const resp = await fetch(
            RAG_API + '/query?q=' + encodeURIComponent(q) + '&simulated_rag=true&k=5',
            {{signal: ctrl.signal}}
        );
        clearTimeout(tid);
        if (resp.ok) {{
            const data = await resp.json();
            let html = '<p style="margin:0">' + (data.answer || '') + '</p>';
            if (data.sources && data.sources.length) {{
                html += '<details style="margin-top:8px"><summary style="cursor:pointer;color:#64748b;font-size:.82rem">📚 Sources (' + data.sources.length + ')</summary>' +
                    '<ul style="margin:4px 0;padding-left:18px;font-size:.82rem;color:#64748b">' +
                    data.sources.slice(0,3).map(s => '<li>[' + s.city + '] <em>' + s.section + '</em></li>').join('') +
                    '</ul></details>';
            }}
            out.innerHTML = html;
            return;
        }}
    }} catch(e) {{ /* server non disponibile — usa fallback client-side */ }}
    clientSideAnswer(q.toLowerCase());
}}

/* ── METADATA-FILTERED query (structured): region / currency / category / numeric thresholds.
      Sfrutta i metadati strutturati già iniettati (@region UN M49, @currency, @category, lat/lon)
      per filtri esatti + valori numerici garantiti, senza alcun backend. ── */
const REGION_NAMES = {{northern:'Northern Europe', southern:'Southern Europe', western:'Western Europe', eastern:'Eastern Europe'}};
const REGION_KW = {{
    northern: /(northern|north europe|nord|nordic|scandinav|baltic)/,
    southern: /(southern|south europe|sud|mediterran|meridional)/,
    western:  /(western|west europe|ovest|occidental)/,
    eastern:  /(eastern|east europe|est europ|orientale|balkan)/
}};
function mThresh(q, kw) {{
    var over  = new RegExp('(' + kw + ')[^0-9]{{0,18}}(over|above|more than|greater than|higher than|at least|>|più di|piu di|sopra|oltre) *([0-9]+)');
    var und   = new RegExp('(' + kw + ')[^0-9]{{0,18}}(under|below|less than|lower than|cheaper than|at most|<|meno di|sotto) *([0-9]+)');
    var overR = new RegExp('(over|above|more than|greater than|higher than|at least|>) *([0-9]+)[^0-9]{{0,14}}(' + kw + ')');
    var undR  = new RegExp('(under|below|less than|cheaper than|at most|<) *([0-9]+)[^0-9]{{0,14}}(' + kw + ')');
    var m;
    if ((m = q.match(over)))  return {{op:'>=', val:+m[3]}};
    if ((m = q.match(und)))   return {{op:'<=', val:+m[3]}};
    if ((m = q.match(overR))) return {{op:'>=', val:+m[2]}};
    if ((m = q.match(undR)))  return {{op:'<=', val:+m[2]}};
    return null;
}}
function mCmp(v, t){{ return t.op === '>=' ? v >= t.val : v <= t.val; }}
function mCoord(v){{ return (v.lat && v.lon) ? ' <a href="https://www.google.com/maps?q=' + v.lat + ',' + v.lon + '" target="_blank" style="font-size:.75em;color:#3498db">📍 ' + (+v.lat).toFixed(4) + ', ' + (+v.lon).toFixed(4) + '</a>' : ''; }}
function metadataQuery(q) {{
    var region = null;
    for (var rk in REGION_KW) {{ if (REGION_KW[rk].test(q)) {{ region = rk; break; }} }}
    var currency = null;
    if (/non[ -]?euro|outside (the )?euro|outside the eurozone|fuori.{{0,8}}euro|senza euro|don't use the euro|do not use the euro|not use the euro/.test(q)) currency = 'other';
    else if (/eurozone|euro area|euro zone|area euro|in the euro\\b|uses? the euro/.test(q)) currency = 'eur';
    var cat = null;
    if (/nightclub|night club|discotec|clubbing/.test(q)) cat = 'nightclub';
    else if (/\\bpubs?\\b/.test(q)) cat = 'pub';
    else if (/\\bbars?\\b/.test(q)) cat = 'bar';
    var tA = mThresh(q, 'appeal');
    var tS = mThresh(q, 'safety|safe|secure');
    var tG = mThresh(q, 'green|eco|sustainab');
    var tB = mThresh(q, 'budget|price|cost|night');
    var hasFilter = region || currency || cat || tA || tS || tG || tB;
    if (!hasFilter) return null;
    var conds = [];
    if (region)             conds.push(function(c){{ return c.region === region; }});
    if (currency==='other') conds.push(function(c){{ return c.currency !== ''; }});
    if (currency==='eur')   conds.push(function(c){{ return c.currency === ''; }});
    if (tA) conds.push(function(c){{ return mCmp(+c.appeal, tA); }});
    if (tS) conds.push(function(c){{ return mCmp(+c.safety, tS); }});
    if (tG) conds.push(function(c){{ return mCmp(+c.green,  tG); }});
    if (tB) conds.push(function(c){{ return mCmp(+c.price,  tB); }});
    var cities = cityData.filter(function(c){{ return conds.every(function(fn){{ return fn(c); }}); }});
    var desc = [];
    if (region) desc.push(REGION_NAMES[region]);
    if (currency==='other') desc.push('non-euro');
    if (currency==='eur')   desc.push('eurozone');
    if (tA) desc.push('appeal ' + tA.op + ' ' + tA.val);
    if (tS) desc.push('safety ' + tS.op + ' ' + tS.val);
    if (tG) desc.push('green ' + tG.op + ' ' + tG.val);
    if (tB) desc.push('budget ' + tB.op + ' ' + tB.val + '€');
    var dtxt = desc.join(' · ');
    var entity = null;
    if (cat || /nightlife|where to drink|locali|drinking/.test(q)) entity = 'nightlife';
    else if (/attraction|museum|sight|landmark|monument|things to do|to see|to visit/.test(q)) entity = 'attractions';
    else if (/hotel|accommodation|stay|sleep|hostel|lodg/.test(q)) entity = 'hotels';
    if (!cities.length) return '<b>🔎 ' + (dtxt || 'filter') + '</b><p style="margin:6px 0">No cities match these criteria.</p>';
    if (entity === 'nightlife') {{
        var total = 0, blocks = [];
        cities.forEach(function(c){{
            var vs = (c.nightlife||[]).filter(function(v){{ return !cat || v.cat === cat; }});
            if (!vs.length) return;
            total += vs.length;
            var items = vs.slice(0,6).map(function(v){{ return '<li>' + (v.cat==='nightclub'?'🎵':(v.cat==='pub'?'🍻':'🍺')) + ' ' + v.n + ' <span style="color:#94a3b8;font-size:.8em">(' + v.cat + ')</span>' + mCoord(v) + '</li>'; }}).join('');
            if (vs.length > 6) items += '<li style="color:#94a3b8">…+' + (vs.length-6) + ' more</li>';
            blocks.push('<li style="margin-top:4px">' + c.flag + ' <b>' + c.name_it + '</b> <span style="color:#64748b">(' + vs.length + ')</span><ul style="margin:2px 0 4px;padding-left:16px">' + items + '</ul></li>');
        }});
        if (!total) return '<b>🍺 ' + (cat||'venues') + ' · ' + dtxt + '</b><p style="margin:6px 0">No matching venues.</p>';
        var label = cat ? cat + 's' : 'venues';
        return '<b>🍺 ' + total + ' ' + label + (dtxt ? ' — ' + dtxt : '') + '</b><ul style="margin:6px 0;padding-left:18px">' + blocks.join('') + '</ul>';
    }}
    if (entity === 'attractions') {{
        var totalA = 0, blocksA = [];
        cities.forEach(function(c){{
            var as = c.attractions || [];
            if (!as.length) return;
            totalA += as.length;
            var items = as.slice(0,4).map(function(a){{ return '<li><b>' + a.n + '</b>' + mCoord(a) + '</li>'; }}).join('');
            if (as.length > 4) items += '<li style="color:#94a3b8">…+' + (as.length-4) + ' more</li>';
            blocksA.push('<li style="margin-top:4px">' + c.flag + ' <b>' + c.name_it + '</b> <span style="color:#64748b">(' + as.length + ')</span><ul style="margin:2px 0 4px;padding-left:16px">' + items + '</ul></li>');
        }});
        return '<b>🗺️ ' + totalA + ' attractions' + (dtxt ? ' — ' + dtxt : '') + '</b><ul style="margin:6px 0;padding-left:18px">' + blocksA.join('') + '</ul>';
    }}
    if (entity === 'hotels') {{
        var blocksH = [];
        cities.forEach(function(c){{
            var hs = c.hotels || [];
            if (!hs.length) return;
            var items = hs.slice(0,4).map(function(h){{ return '<li><b>' + h.n + '</b> <span style="color:#64748b">(' + (h.p||'N/D') + ')</span></li>'; }}).join('');
            blocksH.push('<li style="margin-top:4px">' + c.flag + ' <b>' + c.name_it + '</b><ul style="margin:2px 0 4px;padding-left:16px">' + items + '</ul></li>');
        }});
        if (!blocksH.length) return '<b>🏨 ' + dtxt + '</b><p style="margin:6px 0">No hotel data for matching cities.</p>';
        return '<b>🏨 Hotels' + (dtxt ? ' — ' + dtxt : '') + '</b><ul style="margin:6px 0;padding-left:18px">' + blocksH.join('') + '</ul>';
    }}
    var sorted = cities.slice().sort(function(a,b){{ return (+b.appeal) - (+a.appeal); }});
    var li = sorted.map(function(c){{
        var bits = ['⭐ ' + c.appeal];
        if (tS) bits.push('🛡️ ' + c.safety);
        if (tG) bits.push('🌱 ' + c.green);
        if (tB) bits.push('💰 ' + Math.round(c.price) + '€');
        bits.push(c.currency ? c.currency : 'EUR');
        return '<li>' + c.flag + ' <b>' + c.name_it + '</b> <span style="color:#64748b;font-size:.85em">' + bits.join(' · ') + '</span></li>';
    }}).join('');
    return '<b>🌍 ' + cities.length + ' cities' + (dtxt ? ' — ' + dtxt : '') + '</b><ol style="margin:6px 0;padding-left:18px">' + li + '</ol>';
}}

function clientSideAnswer(q) {{
    const out = document.getElementById('chat-output');
    let res = '❓ City not found. Try: <em>safety Vienna</em>, <em>hotels Rome</em>, <em>bars Berlin</em>, <em>nightclubs in non-euro cities</em>.';
    var hasCity = cityData.some(function(c){{ return q.includes(c.name_it.toLowerCase()) || q.includes((c.name_en||'').toLowerCase()); }});
    if (!hasCity) {{ var mq = metadataQuery(q); if (mq) {{ out.innerHTML = mq; return; }} }}
    cityData.forEach(function(c) {{
        if (q.includes(c.name_it.toLowerCase()) || q.includes((c.name_en || '').toLowerCase())) {{
            if (/hotel|alloggio|dorm|ostello|stay|accommodation|sleep|lodg/.test(q)) {{
                var li = c.hotels.map(h => '<li><b>' + h.n + '</b> <span style="color:#64748b">(' + h.p + ')</span></li>').join('');
                res = '<b>🏨 Accommodation — ' + c.flag + ' ' + c.name_it + '</b><ul style="margin:6px 0;padding-left:18px">' + (li || '<li>No data in dataset</li>') + '</ul>';
            }} else if (/trasport|muoversi|aeroporto|arriv|transport|airport|metro|subway|bus|train|tram|get.to|getting/.test(q)) {{
                res = '<b>🚇 Transport — ' + c.flag + ' ' + c.name_it + '</b><p style="margin:6px 0">' + c.transport + '</p>';
            }} else if (/distrett|quartier|zona|district|neighborhood|area|quarter/.test(q)) {{
                var dn = c.districts.map(d => d.n).join(', ');
                res = '<b>🏘️ Districts — ' + c.flag + ' ' + c.name_it + '</b><p style="margin:6px 0">' + (dn || 'No district data available.') + '</p>';
            }} else if (/attrazione|visitare|vedere|turismo|museo|sight|museum|visit|attraction|landmark|tour/.test(q)) {{
                var al = c.attractions.slice(0,5).map(a => '<li><b>' + a.n + '</b> — <span style="color:#64748b;font-size:.88em">' + a.d + '</span> <a href="https://www.google.com/maps?q=' + a.lat + ',' + a.lon + '" target="_blank" style="font-size:.75em;color:#3498db">📍</a></li>').join('');
                res = '<b>🗺️ Attractions — ' + c.flag + ' ' + c.name_it + '</b><ul style="margin:6px 0;padding-left:18px">' + al + '</ul>';
            }} else if (/bar|pub|drink|beer|nightlife|bere|birra|club|nightclub|aperitivo/.test(q)) {{
                if (!c.nightlife || !c.nightlife.length) {{
                    res = '<b>' + c.flag + ' ' + c.name_it + '</b>: no nightlife data available.';
                }} else {{
                    var nl = c.nightlife.map(v => '<li>' + (v.cat==='nightclub'?'🎵':'🍺') + ' <b>' + v.n + '</b> <span style="color:#94a3b8;font-size:.82em">(' + v.cat + ')</span> <a href="https://www.google.com/maps?q=' + v.lat + ',' + v.lon + '" target="_blank" style="font-size:.75em;color:#3498db">📍</a></li>').join('');
                    res = '<b>🍺 Where to Drink — ' + c.flag + ' ' + c.name_it + '</b><ul style="margin:6px 0;padding-left:18px">' + nl + '</ul>';
                }}
            }} else if (/sicur|safety|pericol|crime|safe|danger/.test(q)) {{
                res = '<b>🛡️ ' + c.flag + ' ' + c.name_it + '</b> — Safety Index: <b>' + c.safety + '</b> · Appeal: <b>' + c.appeal + '</b>';
            }} else if (/verde|green|sustainab|ecolog/.test(q)) {{
                res = '<b>🌱 ' + c.flag + ' ' + c.name_it + '</b> — Green Score: <b>' + c.green + '</b>';
            }} else if (/cost|budget|price|cheap|expens|afford/.test(q)) {{
                res = '<b>💰 ' + c.flag + ' ' + c.name_it + '</b> — Budget: <b>' + Math.round(c.price) + '€/night</b> · Cost of living: <b>' + c.economy + '</b>';
            }} else {{
                res = '<b>' + c.flag + ' ' + c.name_it + '</b><div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:6px 0;font-size:.87em"><span>⭐ Appeal: <b>' + c.appeal + '</b></span><span>🛡️ Safety: <b>' + c.safety + '</b></span><span>🌱 Green: <b>' + c.green + '</b></span><span>💰 Budget: <b>' + Math.round(c.price) + '€</b></span></div>';
            }}
        }}
    }});
    /* global queries without city name */
    if (res.startsWith('❓')) {{
        if (/sicur|safe/.test(q)) {{
            var top = cityData.slice().sort((a,b) => b.safety-a.safety).slice(0,5);
            res = '<b>🛡️ Top 5 Safest Cities</b><ol style="padding-left:18px;margin:6px 0">' + top.map(c => '<li>' + c.flag + ' ' + c.name_it + ' — ' + c.safety + '</li>').join('') + '</ol>';
        }} else if (/verde|green|ecolog|sustainab/.test(q)) {{
            var top = cityData.slice().sort((a,b) => b.green-a.green).slice(0,5);
            res = '<b>🌱 Top 5 Greenest Cities</b><ol style="padding-left:18px;margin:6px 0">' + top.map(c => '<li>' + c.flag + ' ' + c.name_it + ' — ' + c.green + '</li>').join('') + '</ol>';
        }} else if (/econom|cheap|afford|basso|budget/.test(q)) {{
            var top = cityData.slice().sort((a,b) => a.price-b.price).slice(0,5);
            res = '<b>💰 Top 5 Most Affordable</b><ol style="padding-left:18px;margin:6px 0">' + top.map(c => '<li>' + c.flag + ' ' + c.name_it + ' — ' + Math.round(c.price) + '€/night</li>').join('') + '</ol>';
        }} else if (/appeal|best|top|ranking/.test(q)) {{
            var top = cityData.slice().sort((a,b) => b.appeal-a.appeal).slice(0,5);
            res = '<b>⭐ Top 5 by Appeal Score</b><ol style="padding-left:18px;margin:6px 0">' + top.map(c => '<li>' + c.flag + ' ' + c.name_it + ' — ' + c.appeal + '</li>').join('') + '</ol>';
        }} else if (/confronta|compare|vs/.test(q)) {{
            res = 'To compare two cities type: <em>"compare Rome and Paris"</em> or <em>"Rome vs Berlin"</em>.';
        }}
    }}
    out.innerHTML = res;
}}
document.getElementById('chat-btn').onclick = runQuery;
document.getElementById('chat-input').addEventListener('keydown', function(e) {{ if (e.key === 'Enter') runQuery(); }});
document.querySelectorAll('.chip').forEach(function(chip) {{
    chip.onclick = function() {{
        document.getElementById('chat-input').value = chip.dataset.q;
        runQuery();
    }};
}});

/* toggle del widget flottante (presentazione, non logica di query) */
(function() {{
    var launcher = document.getElementById('va-launcher');
    var widget   = document.getElementById('va-widget');
    var closeBtn = document.getElementById('va-close');
    if (!launcher || !widget) return;
    function openVA()  {{ widget.hidden = false; launcher.setAttribute('aria-expanded', 'true');
                          launcher.classList.add('is-open'); document.getElementById('chat-input').focus(); }}
    function closeVA() {{ widget.hidden = true;  launcher.setAttribute('aria-expanded', 'false');
                          launcher.classList.remove('is-open'); }}
    launcher.onclick = function() {{ widget.hidden ? openVA() : closeVA(); }};
    if (closeBtn) closeBtn.onclick = closeVA;
    document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape' && !widget.hidden) closeVA(); }});
}})();
</script>"""


def deploy():
    print("🚀 Generazione Dashboard: Reintegro Attrazioni + Griglia 3x2...")

    city_data = []
    cards_html = ""

    if not os.path.exists(XML_DIR): 
        print(f"Errore: Cartella {XML_DIR} non trovata.")
        return

    # Carica il DTD una sola volta per validare la directory di input (cfr.
    # lab_castles_files: parse -> well-formed, dtd.validate -> valid).
    dtd = etree.DTD(open(DTD_FILE, 'rb'))
    validation = {'valid': 0, 'invalid': 0, 'malformed': 0, 'errors': []}

    files = sorted([f for f in os.listdir(XML_DIR) if f.endswith('.xml')])
    for filename in files:
        try:
            city_lower = filename.replace('.xml', '')
            # etree.parse solleva un'eccezione se il documento NON è ben formato
            tree = etree.parse(os.path.join(XML_DIR, filename))
            root = tree.getroot()

            # Validazione rispetto al DTD (validità, non solo buona forma)
            if dtd.validate(tree):
                validation['valid'] += 1
            else:
                validation['invalid'] += 1
                err = dtd.error_log.filter_from_errors()
                validation['errors'].append(f"{filename}: {err}")
                print(f"⚠️  {filename}: NON valido rispetto al DTD → {err}")

            # 1. Estrazione dati strutturati
            city_obj = {
                'name_en': root.findtext(".//title"),
                'name_it': root.findtext(".//name_it") or root.findtext(".//title"),
                'flag': root.findtext(".//flag") or "🇪🇺",
                # Canonical URI read FROM the document → microdata itemid (correspondence)
                'uri': root.findtext(".//source_url") or "",
                # @ sull'attributo obbligatorio del root via XPath: string(/city_report/@appeal_score)
                'appeal': root.xpath("string(/city_report/@appeal_score)").strip() or "0",
                # @currency: attributo opzionale del root (assente = area euro)
                'currency': root.xpath("string(/city_report/@currency)").strip(),
                # @region: attributo enumerato obbligatorio (UN M49) → filtro per area
                'region': root.xpath("string(/city_report/@region)").strip(),
                'price': root.findtext(".//hotel_price", "0"),
                'safety': root.xpath("string(.//safety/@index_score)") or "0",
                'green': root.xpath("string(.//environment/@green_score)") or "0",
                'hotel_count': root.findtext(".//hotel_count", "0"),
                'economy': root.xpath("string(.//economic_accessibility/@score)") or "0",
                # Mixed-content fields: serialise inline markup (b/i/link) to HTML
                'transport': inline_to_html(root.find("transport")) or "Transport data unavailable.",
                'story_it': inline_to_html(root.find("description")) or "Strategic summary unavailable.",
                'wiki_intro': inline_to_html(root.find("wiki_intro")),
                'hotels': [{'n': h.findtext("name"), 'p': h.findtext("price")} for h in root.xpath(".//hotel")],
                'attractions': [{'n': a.findtext("name"), 'd': a.findtext("description"), 'lat': a.get("lat"), 'lon': a.get("lon")} for a in root.xpath(".//attraction")],
                'districts': [
                    {'n': d.findtext('name', ''), 'd': d.findtext('description', '')}
                    for d in root.xpath(".//district")
                ],
                'nightlife': [
                    {'n': v.findtext('name', ''), 'cat': v.get('category', 'bar'), 'lat': v.get('lat', ''), 'lon': v.get('lon', '')}
                    for v in root.xpath(".//venue")
                ],
                'landmark_image': root.findtext("landmark_image") or "",
                'city_lower': city_lower,
            }
            city_data.append(city_obj)

            # Card compatta per index: solo immagine + stats + CTA
            img_src = city_obj.get('landmark_image', '')
            n_attr = len(city_obj['attractions'])
            # Dimensioni extra per i filtri/ordinamento dell'index
            cur_bucket = 'eur' if not city_obj['currency'] else 'other'
            region_code = city_obj['region']
            s_pct = _pct(city_obj['safety'])
            g_pct = _pct(city_obj['green'])
            p_pct = _pct(city_obj['price'], 2.5)   # max €250
            e_pct = _pct(city_obj['economy'])
            cards_html += f"""
            <article class="city-card" data-slug="{city_lower}" data-safety="{city_obj['safety']}" data-green="{city_obj['green']}" data-price="{city_obj['price']}" data-appeal="{city_obj['appeal']}" data-economy="{city_obj['economy']}" data-attractions="{n_attr}" data-venues="{city_obj['hotel_count']}" data-currency="{cur_bucket}" data-region="{region_code}" data-name="{city_obj['name_it'].lower()}" itemscope itemtype="https://schema.org/City" itemid="{city_obj['uri']}">
                <div class="landmark-img-wrap">
                    <img src="{img_src}" alt="{city_obj['name_it']} Landmark" class="landmark-img" loading="lazy">
                    <div class="city-card-overlay">
                        <h2 class="city-title-overlay">
                            <span>{city_obj['flag']}</span>
                            <a href="pages/cities/{city_lower}.html" itemprop="name" class="city-overlay-link">{city_obj['name_it']}</a>
                        </h2>
                        <div class="city-score-badge">{city_obj['appeal']}<small> score</small></div>
                    </div>
                </div>
                <div class="city-card-body">
                    <div class="stats-box">
                        <div class="stat-item">
                            <span class="stat-label">Budget/night</span>
                            <span class="stat-val">{_price(city_obj['price'])}€</span>
                            <div class="score-bar-wrap"><div class="score-bar-fill amber" style="width:{p_pct}%"></div></div>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Safety</span>
                            <span class="stat-val">{city_obj['safety']}</span>
                            <div class="score-bar-wrap"><div class="score-bar-fill green" style="width:{s_pct}%"></div></div>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Green</span>
                            <span class="stat-val" style="color:var(--green-500)">{city_obj['green']}</span>
                            <div class="score-bar-wrap"><div class="score-bar-fill green" style="width:{g_pct}%"></div></div>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Venues</span>
                            <span class="stat-val" style="color:var(--blue-500)">{city_obj['hotel_count']}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Cost of living</span>
                            <span class="stat-val">{city_obj['economy']}</span>
                            <div class="score-bar-wrap"><div class="score-bar-fill blue" style="width:{e_pct}%"></div></div>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Attractions</span>
                            <span class="stat-val">{n_attr}</span>
                        </div>
                    </div>
                    <a href="pages/cities/{city_lower}.html" class="card-cta">Explore {city_obj['name_it']} →</a>
                </div>
            </article>"""
        except etree.XMLSyntaxError as e:
            # Documento mal formato: scartato dalla pipeline (cfr. "BAD FORM")
            validation['malformed'] += 1
            validation['errors'].append(f"{filename}: malformato — {e}")
            print(f"❌ {filename}: documento MAL FORMATO → {e}")
        except Exception as e:
            print(f"⚠️ Errore su {filename}: {e}")

    print(f"📋 Validazione DTD: {validation['valid']} validi, "
          f"{validation['invalid']} non validi, {validation['malformed']} malformati "
          f"(su {len(files)} file)")

    # Mappa inline: pre-calcolata fuori dall'f-string per evitare conflitti {}
    inline_map_js = _map_js_block(city_data, 'map-inline', 'pages/cities/')

    n_attractions = sum(len(c['attractions']) for c in city_data)
    n_hotels      = sum(len(c['hotels'])      for c in city_data)

    # Il secondo blocco <script> è una stringa NON f-string: usare { e } singoli (non {{ }})
    js_block = """<script>
/* back-to-top */
const btt = document.getElementById('back-to-top');
window.addEventListener('scroll', function() {
    btt.classList.toggle('visible', window.scrollY > 400);
});
btt.onclick = function() { window.scrollTo({top: 0, behavior: 'smooth'}); };

/* ───── Toolbar: faceted filter (search + profile/region/currency) + sort ───── */
(function() {
    var grid = document.getElementById('city-grid');
    if (!grid) return;
    var cards   = Array.prototype.slice.call(grid.querySelectorAll('.city-card'));
    var search  = document.getElementById('city-search');
    var sortSel = document.getElementById('city-sort');
    var countEl = document.getElementById('ft-count');
    var resetBtn= document.getElementById('ft-reset');
    var chips   = Array.prototype.slice.call(document.querySelectorAll('.filter-btn[data-dim]'));
    var total   = cards.length;
    var num     = function(c, attr) { return parseFloat(c.dataset[attr] || 0); };

    function activeVals(dim) {
        return chips.filter(function(c) {
            return c.dataset.dim === dim && c.getAttribute('aria-pressed') === 'true';
        }).map(function(c) { return c.dataset.val; });
    }

    function matches(card) {
        var q = (search.value || '').trim().toLowerCase();
        if (q && (card.dataset.name || '').indexOf(q) === -1) return false;
        // Profile: ogni soglia attiva è un vincolo AND
        var prof = activeVals('profile');
        for (var i = 0; i < prof.length; i++) {
            if (prof[i] === 'safety' && num(card, 'safety') < 70)  return false;
            if (prof[i] === 'green'  && num(card, 'green')  < 70)  return false;
            if (prof[i] === 'budget' && num(card, 'price')  > 120) return false;
        }
        // Region / Currency: OR all'interno del gruppo, AND fra gruppi
        var reg = activeVals('region');
        if (reg.length && reg.indexOf(card.dataset.region) === -1) return false;
        var cur = activeVals('currency');
        if (cur.length && cur.indexOf(card.dataset.currency) === -1) return false;
        return true;
    }

    function sortCards() {
        var key = sortSel.value;
        var sorted = cards.slice().sort(function(a, b) {
            switch (key) {
                case 'safety':      return num(b,'safety') - num(a,'safety');
                case 'green':       return num(b,'green') - num(a,'green');
                case 'price-asc':   return num(a,'price') - num(b,'price');
                case 'price-desc':  return num(b,'price') - num(a,'price');
                case 'attractions': return num(b,'attractions') - num(a,'attractions');
                case 'venues':      return num(b,'venues') - num(a,'venues');
                case 'name':        return (a.dataset.name||'').localeCompare(b.dataset.name||'');
                default:            return num(b,'appeal') - num(a,'appeal');
            }
        });
        sorted.forEach(function(c) { grid.appendChild(c); });
        return sorted;
    }

    function apply() {
        var sorted = sortCards();
        var shown = 0, order = [];
        sorted.forEach(function(c) {
            var ok = matches(c);
            c.style.display = ok ? '' : 'none';
            if (ok) { shown++; order.push(c.dataset.slug); }
        });
        countEl.textContent = 'Showing ' + shown + ' of ' + total + ' capitals';
        // Memorizza l'ordine corrente delle capitali VISIBILI: le schede città lo
        // useranno per una navigazione prev/next coerente col filtro scelto qui.
        // Doppio storage: sessionStorage (semantica corretta, http) + localStorage
        // (fallback affidabile quando il sito è aperto da file:// e session non è condiviso).
        try {
            var payload = JSON.stringify(order);
            sessionStorage.setItem('eurocity_nav', payload);
            localStorage.setItem('eurocity_nav', payload);
        } catch (e) {}
    }

    // Region e Currency sono a selezione SINGOLA (una città sta in una sola area /
    // usa una sola valuta): cliccare un'opzione deseleziona le altre dello stesso
    // gruppo. Profile resta multiplo: le soglie si combinano in AND (safe + green + …).
    var SINGLE = { region: true, currency: true };
    chips.forEach(function(chip) {
        chip.addEventListener('click', function() {
            var on = chip.getAttribute('aria-pressed') === 'true';
            if (SINGLE[chip.dataset.dim] && !on) {
                chips.forEach(function(c) {
                    if (c.dataset.dim === chip.dataset.dim && c !== chip) {
                        c.setAttribute('aria-pressed', 'false');
                        c.classList.remove('active');
                    }
                });
            }
            chip.setAttribute('aria-pressed', on ? 'false' : 'true');
            chip.classList.toggle('active', !on);
            apply();
        });
    });
    search.addEventListener('input', apply);
    sortSel.addEventListener('change', apply);
    resetBtn.addEventListener('click', function() {
        chips.forEach(function(c) { c.setAttribute('aria-pressed','false'); c.classList.remove('active'); });
        search.value = '';
        sortSel.value = 'appeal';
        apply();
    });
    apply();
})();

/* card entrance animation */
document.body.classList.add('js-loaded');
var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(e) {
        if (e.isIntersecting) { e.target.classList.add('visible'); observer.unobserve(e.target); }
    });
}, {rootMargin: '0px 0px -50px 0px'});
document.querySelectorAll('.city-card').forEach(function(c) { observer.observe(c); });
</script>"""

    # Virtual Analyst flottante (stesso markup/logica su index e schede città)
    analyst_widget = analyst_widget_html()
    analyst_js = analyst_script(city_data)

    # Chip dei filtri "Regione" generati dalla mappatura geografica
    region_chips = "\n        ".join(
        f'<button class="filter-btn" data-dim="region" data-val="{code}" '
        f'aria-pressed="false">{label}</button>'
        for code, label in REGION_LABELS.items()
    )

    # Template finale HTML
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="stile.css?v={CSS_VER}">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css">
    <title>EuroCity Strategic Intelligence</title>
</head>
<body>
<a href="#city-grid" class="skip-link">Salta al contenuto</a>

<!-- ═══ TOPBAR STICKY ══════════════════════════════════════════════════ -->
<header class="topbar">
    <div class="topbar-inner">
        <span class="topbar-logo">EuroCity <b>SI</b></span>
        <nav class="topbar-nav" aria-label="Navigazione principale">
            <a href="#" class="active" aria-current="page">🏠 Home</a>
            <a href="pages/mappa_attrazioni.html">🗺️ Map</a>
            <a href="pages/report.html">📊 Report</a>
        </nav>
    </div>
</header>

<!-- ═══ HERO ════════════════════════════════════════════════════════════ -->
<section class="hero">
    <div class="hero-content">
        <h1 class="hero-title">30 European capitals,<br>one intelligence.</h1>
        <p class="hero-sub">
            EuroCity turns free-text travel guides into structured, queryable data. For each EU
            capital, the pipeline <b>extracts</b> transport, attractions, districts and venues from
            the <b>Wikivoyage</b> dumps, <b>combines</b> them with international indices for safety,
            sustainability and cost, and <b>writes one DTD-validated XML file</b> per city. Every
            page, ranking and map you see below is rendered straight from those XML documents — the
            site is a <b>direct reflection</b> of the data, not a hand-written brochure.
        </p>
        <div class="hero-stats">
            <div class="hero-stat"><span class="hs-num">{len(city_data)}</span><span class="hs-lbl">capitals</span></div>
            <div class="hero-stat"><span class="hs-num">{n_attractions}</span><span class="hs-lbl">attractions</span></div>
            <div class="hero-stat"><span class="hs-num">{n_hotels}</span><span class="hs-lbl">venues</span></div>
            <div class="hero-stat" title="File XML validati rispetto a city_report.dtd (lxml.etree.DTD)">
                <span class="hs-num">{validation['valid']}/{len(files)}</span>
                <span class="hs-lbl">✅ DTD-valid XML</span>
            </div>
        </div>
    </div>
</section>

<!-- ═══ DATA PROVENANCE — how the numbers are built ════════════════════ -->
<section class="provenance-band" aria-label="How the data is built">
  <div class="prov-inner">
    <p class="prov-eyebrow">The pipeline</p>
    <h2 class="prov-heading">How the data is built</h2>
    <p class="prov-lead">Every page, ranking and map is generated from validated XML — not hand-written.</p>

    <ol class="prov-flow">
        <li class="prov-node">
            <span class="prov-step">1</span>
            <span class="prov-ico">📂</span>
            <b>Wikivoyage</b>
            <small>MediaWiki dumps parsed into clean text: transport, attractions, districts, venues.</small>
        </li>
        <li class="prov-node">
            <span class="prov-step">2</span>
            <span class="prov-ico">📄</span>
            <b>XML + DTD</b>
            <small>One validated file per city: mixed content, geo-coordinates, Schema.org microdata.</small>
        </li>
        <li class="prov-node">
            <span class="prov-step">3</span>
            <span class="prov-ico">📊</span>
            <b>Indices</b>
            <small>Safety, Green and Cost of living merged in from international sources.</small>
        </li>
        <li class="prov-node">
            <span class="prov-step">4</span>
            <span class="prov-ico">🌐</span>
            <b>This site</b>
            <small>Pages, rankings and map generated directly from the XML.</small>
        </li>
    </ol>

    <div class="prov-formula" role="img"
         aria-label="Appeal Score equals 40% safety, 40% green, 20% affordability">
        <span class="prov-formula-lbl">Appeal&nbsp;Score</span>
        <span class="prov-eq">=</span>
        <span class="prov-seg prov-safety">Safety <i>×0.4</i></span>
        <span class="prov-plus">+</span>
        <span class="prov-seg prov-green">Green <i>×0.4</i></span>
        <span class="prov-plus">+</span>
        <span class="prov-seg prov-cost">Affordability <i>×0.2</i></span>
        <a class="prov-formula-link" href="pages/report.html#statistiche">see how →</a>
    </div>
  </div>
</section>

<!-- Virtual Analyst: ora è un widget flottante, iniettato a fine pagina -->

<!-- ═══ MAPPA INLINE ════════════════════════════════════════════════════ -->
<div id="map-inline"></div>

<!-- ═══ TOOLBAR FILTRI + ORDINAMENTO ════════════════════════════════════ -->
<section class="filter-toolbar" id="filter-toolbar" aria-label="Filtra e ordina le capitali">
    <div class="ft-row ft-main">
        <div class="ft-search">
            <label for="city-search" class="ft-sr">Search a capital by name</label>
            <input type="search" id="city-search" placeholder="🔍 Search a capital…" autocomplete="off">
        </div>
        <div class="ft-sort">
            <label for="city-sort">Sort by</label>
            <select id="city-sort">
                <option value="appeal">⭐ Appeal score</option>
                <option value="safety">🛡️ Safest first</option>
                <option value="green">🌱 Greenest first</option>
                <option value="price-asc">💰 Cheapest first</option>
                <option value="price-desc">💎 Priciest first</option>
                <option value="attractions">🏛️ Most attractions</option>
                <option value="venues">🍺 Most venues</option>
                <option value="name">🔤 A–Z</option>
            </select>
        </div>
    </div>
    <div class="ft-facets">
        <div class="ft-group" role="group" aria-label="Profilo">
            <span class="ft-glabel">Profile</span>
            <div class="ft-chips">
                <button class="filter-btn" data-dim="profile" data-val="safety" aria-pressed="false">🛡️ Safe ≥ 70</button>
                <button class="filter-btn" data-dim="profile" data-val="green" aria-pressed="false">🌱 Green ≥ 70</button>
                <button class="filter-btn" data-dim="profile" data-val="budget" aria-pressed="false">💰 ≤ €120/night</button>
            </div>
        </div>
        <div class="ft-group" role="group" aria-label="Regione">
            <span class="ft-glabel">Region</span>
            <div class="ft-chips">
                {region_chips}
            </div>
        </div>
        <div class="ft-group" role="group" aria-label="Valuta">
            <span class="ft-glabel">Currency</span>
            <div class="ft-chips">
                <button class="filter-btn" data-dim="currency" data-val="eur" aria-pressed="false">💶 Eurozone</button>
                <button class="filter-btn" data-dim="currency" data-val="other" aria-pressed="false">💱 Non-euro</button>
            </div>
        </div>
    </div>
    <div class="ft-row ft-meta">
        <span class="ft-count" id="ft-count" aria-live="polite">Showing {len(city_data)} of {len(city_data)} capitals</span>
        <button class="ft-reset" id="ft-reset" type="button">✕ Reset filters</button>
    </div>
</section>
<main class="container" id="city-grid" aria-label="Griglia delle capitali">{cards_html}</main>

<button id="back-to-top" title="Back to top">↑</button>

<footer class="site-footer">
    Progetto TEAM — Laurea Magistrale in Governance e Politiche dell'Innovazione Digitale ·
    Università di Bologna A.A. 2024/2025
    <br>
    <a href="pages/report.html">📊 Report &amp; Documentation</a>
</footer>

{analyst_widget}
{analyst_js}
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.js"></script>
""" + inline_map_js + "\n" + js_block + "\n</body></html>"

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(full_html)
    print(f"✅ Dashboard generata correttamente con {len(city_data)} città.")

    generate_city_pages(city_data)
    generate_report(city_data, validation)   # dopo le pagine: conta i microdata reali generati
    generate_map(city_data)


def generate_city_pages(city_data):
    """Generate one HTML file per city: {city_lower}.html with full content, microdata, XML download link."""
    print("📄 Generazione pagine individuali per città...")
    cities = sorted(city_data, key=lambda c: c['city_lower'])
    n = len(cities)

    # Virtual Analyst flottante: identico markup/logica dell'index, su ogni scheda
    analyst_widget = analyst_widget_html()
    analyst_js = analyst_script(city_data)

    # Mappa slug → {bandiera, nome} per le etichette prev/next dinamiche (identica su ogni scheda)
    nav_cities_map = "{" + ",".join(
        f'{json.dumps(c["city_lower"])}:{{"f":{json.dumps(c["flag"])},"n":{json.dumps(c["name_it"])}}}'
        for c in cities
    ) + "}"
    # Script (parentesi normali: è una stringa Python, NON una f-string) iniettato in
    # ogni scheda. Rende prev/next coerenti col filtro+ordinamento scelto sull'index,
    # leggendo l'ordine salvato in sessionStorage; se assente o la città è stata
    # filtrata fuori, lascia i vicini statici (alfabetici) già presenti nell'HTML.
    nav_rewrite_js = """<script>
(function() {
  var nav = document.querySelector('.city-nav');
  if (!nav) return;
  var CITIES = __NAV_MAP__;
  var current = nav.dataset.slug, order, raw = null;
  try { raw = sessionStorage.getItem('eurocity_nav') || localStorage.getItem('eurocity_nav'); } catch (e) {}
  try { order = JSON.parse(raw || 'null'); } catch (e) { order = null; }
  if (!Array.isArray(order)) return;
  var idx = order.indexOf(current);
  if (idx === -1 || order.length < 2) return;   // arrivo diretto o città filtrata fuori → statico
  var prev = order[(idx - 1 + order.length) % order.length];
  var next = order[(idx + 1) % order.length];
  var links = nav.querySelectorAll('a');
  if (links[0] && CITIES[prev]) { links[0].setAttribute('href', prev + '.html'); links[0].textContent = '\\u2190 ' + CITIES[prev].f + ' ' + CITIES[prev].n; }
  if (links[1] && CITIES[next]) { links[1].setAttribute('href', next + '.html'); links[1].textContent = CITIES[next].f + ' ' + CITIES[next].n + ' \\u2192'; }
  if (order.length < __TOTAL__) {
    nav.setAttribute('data-filtered', 'true');
    nav.setAttribute('title', 'Navigazione tra le ' + order.length + ' capitali filtrate');
  }
})();
</script>""".replace('__NAV_MAP__', nav_cities_map).replace('__TOTAL__', str(n))

    for i, city in enumerate(cities):
        prev_city = cities[(i - 1) % n]
        next_city = cities[(i + 1) % n]
        cl = city['city_lower']

        # --- Microdata: geo from first attraction ---
        geo_html = ""
        if city['attractions']:
            a0 = city['attractions'][0]
            geo_html = (
                f"<div itemprop='geo' itemscope itemtype='https://schema.org/GeoCoordinates'>"
                f"<meta itemprop='latitude' content='{a0['lat']}'>"
                f"<meta itemprop='longitude' content='{a0['lon']}'>"
                f"</div>"
            )

        # --- Indicatori come microdata (schema.org) ---
        # Appeal Score (composito) → AggregateRating con ratingValue 0–100.
        # Safety / Green / Economic Accessibility → additionalProperty/PropertyValue
        # (la forma corretta per metriche multiple: Place ammette UN solo aggregateRating).
        rating_html = (
            f"<div itemprop='aggregateRating' itemscope itemtype='https://schema.org/AggregateRating'>"
            f"<meta itemprop='ratingValue' content='{city['appeal']}'>"
            f"<meta itemprop='bestRating' content='100'>"
            f"<meta itemprop='worstRating' content='0'>"
            f"<meta itemprop='ratingCount' content='1'>"
            f"</div>"
            + "".join(
                f"<div itemprop='additionalProperty' itemscope itemtype='https://schema.org/PropertyValue'>"
                f"<meta itemprop='name' content='{label}'>"
                f"<meta itemprop='value' content='{val}'>"
                f"</div>"
                for label, val in (
                    ('Safety Index', city['safety']),
                    ('Green Score', city['green']),
                    ('Economic Accessibility', city['economy']),
                )
            )
        )

        # --- Region come microdata: containment geografico VERSO L'ALTO ---
        # City containedInPlace → Place (macro-regione, id UN M49) containedInPlace
        # → Continent "Europe" (sameAs Wikidata). Specchio di containsPlace, derivato
        # dall'attributo @region del documento XML.
        region_md_html = ""
        _rmeta = REGION_META.get(city['region'])
        if _rmeta:
            _rname, _m49 = _rmeta
            region_md_html = (
                f"<div itemprop='containedInPlace' itemscope itemtype='https://schema.org/Place'>"
                f"<meta itemprop='name' content='{_rname}'>"
                f"<div itemprop='identifier' itemscope itemtype='https://schema.org/PropertyValue'>"
                f"<meta itemprop='propertyID' content='UN M49'>"
                f"<meta itemprop='value' content='{_m49}'>"
                f"</div>"
                f"<div itemprop='containedInPlace' itemscope itemtype='https://schema.org/Continent'>"
                f"<meta itemprop='name' content='Europe'>"
                f"<link itemprop='sameAs' href='https://www.wikidata.org/wiki/Q46'>"
                f"</div>"
                f"</div>"
            )

        # --- Landmark image ---
        lm_html = ""
        if city['landmark_image']:
            img_url = city['landmark_image']
            if not img_url.startswith('http'):
                img_url = '../../' + img_url.lstrip('/')
            lm_html = (
                f"<div style='border-radius:20px; overflow:hidden; height:280px; margin-bottom:30px;'>"
                f"<img itemprop='image' src='{img_url}' alt='{city['name_it']} Landmark' "
                f"style='width:100%; height:100%; object-fit:cover;'></div>"
            )

        # --- Valuta locale (solo capitali fuori area euro) ---
        # L'euro resta l'unità primaria (il prezzo è una stima sintetica in EUR);
        # affianchiamo l'equivalente locale indicativo e una nota esplicativa.
        cmeta = currency_meta(city['currency'])
        budget_local = local_price(city['price'], city['currency'])
        budget_local_sub = (
            f"<span class='stat-local'>≈ {budget_local}</span>" if budget_local else ""
        )
        if cmeta:
            currency_note_html = (
                f"<div class='currency-note'>"
                f"<span class='cur-ico'>🪙</span>"
                f"<div><b>{city['name_it']}</b> does not use the euro: the local currency is the "
                f"<b>{cmeta['name_en']}</b> ({city['currency']}, {cmeta['symbol']}). "
                f"Prices on this site are a <b>synthetic estimate in euros</b> (for cross-city comparison); "
                f"the local equivalent (<b>≈ {budget_local}</b> per night) is indicative, "
                f"at {CURRENCY_SNAPSHOT} reference rates.</div>"
                f"</div>"
            )
        else:
            currency_note_html = ""

        # --- Stats box ---
        _s = _pct(city['safety']); _g = _pct(city['green'])
        _p = _pct(city['price'], 2.5); _e = _pct(city['economy'])
        _a = _pct(city['appeal'])
        stats_html = f"""
        <div class='stats-box'>
            <div class='stat-item'>
                <span class='stat-label'>Appeal</span>
                <span class='stat-val' style='color:var(--accent)'>{city['appeal']}</span>
                <div class='score-bar-wrap'><div class='score-bar-fill red' style='width:{_a}%'></div></div>
            </div>
            <div class='stat-item'>
                <span class='stat-label'>Budget</span>
                <span class='stat-val'>{city['price']}€</span>{budget_local_sub}
                <div class='score-bar-wrap'><div class='score-bar-fill amber' style='width:{_p}%'></div></div>
            </div>
            <div class='stat-item'>
                <span class='stat-label'>Safety</span>
                <span class='stat-val'>{city['safety']}</span>
                <div class='score-bar-wrap'><div class='score-bar-fill green' style='width:{_s}%'></div></div>
            </div>
            <div class='stat-item'>
                <span class='stat-label'>Green</span>
                <span class='stat-val' style='color:var(--green-500)'>{city['green']}</span>
                <div class='score-bar-wrap'><div class='score-bar-fill green' style='width:{_g}%'></div></div>
            </div>
            <div class='stat-item'>
                <span class='stat-label'>Venues</span>
                <span class='stat-val' style='color:var(--blue-500)'>{city['hotel_count']}</span>
            </div>
            <div class='stat-item'>
                <span class='stat-label'>Cost of living</span>
                <span class='stat-val'>{city['economy']}</span>
                <div class='score-bar-wrap'><div class='score-bar-fill blue' style='width:{_e}%'></div></div>
            </div>
        </div>"""

        # --- Hotels (microdata schema.org/Hotel: name + priceRange) ---
        hotel_li = "".join([
            f"<li itemprop='containsPlace' itemscope itemtype='https://schema.org/Hotel'>"
            f"<b itemprop='name'>{h['n']}</b> "
            f"<small>(<span itemprop='priceRange'>{h['p']}</span>)</small></li>"
            for h in city['hotels']])
        hotel_html = (
            f"<div class='info-block hotel-block'><span class='block-title'>🏨 Where to Stay</span>"
            f"<ul style='margin:0; padding-left:15px;'>{hotel_li}</ul></div>"
        ) if hotel_li else ""

        # --- Transport (strip inline AI-source marker before display) ---
        import re as _re
        transport_display = _re.sub(r'\s*\(Source: AI-generated[^)]*\)', '', city['transport']).strip()
        transport_html = (
            f"<div class='info-block transport-block'>"
            f"<span class='block-title'>🚇 Urban Transport</span>"
            f"<p style='margin:0;'>{transport_display}</p></div>"
        )

        # --- Districts ---
        dist_li = "".join([
            f"<li><b>{d['n']}</b>" + (f": {d['d'][:200]}..." if len(d['d']) > 200 else (f": {d['d']}" if d['d'] else "")) + "</li>"
            for d in city['districts']
        ])
        districts_html = (
            f"<div class='info-block district-block'><span class='block-title'>🏙️ Districts</span>"
            f"<ul style='margin:0; padding-left:15px;'>{dist_li}</ul></div>"
        ) if dist_li else ""

        # --- Nightlife ---
        # Mapping dell'attributo XML enumerato (bar|pub|nightclub) sulla classe schema.org
        # più specifica: NightClub per le discoteche, BarOrPub per bar e pub.
        def _venue_schema(cat):
            return 'NightClub' if cat == 'nightclub' else 'BarOrPub'
        night_li = "".join([
            f"<li itemprop='containsPlace' itemscope itemtype='https://schema.org/{_venue_schema(v['cat'])}'>"
            f"<a itemprop='name' href='https://www.google.com/maps?q={v['lat']},{v['lon']}' target='_blank'>{v['n']}</a>"
            f" <span style='color:#94a3b8; font-size:0.82rem;'>({v['cat']})</span>"
            f"<div itemprop='geo' itemscope itemtype='https://schema.org/GeoCoordinates'>"
            f"<meta itemprop='latitude' content='{v['lat']}'>"
            f"<meta itemprop='longitude' content='{v['lon']}'></div></li>"
            for v in city['nightlife']
        ])
        nightlife_html = (
            f"<div id='nightlife' class='info-block nightlife-block'>"
            f"<span class='block-title'>🍺 Where to Drink</span>"
            f"<ul style='margin:0; padding-left:15px;'>{night_li}</ul></div>"
        ) if night_li else ""

        # --- Descriptions ---
        desc_html = f"""
        <div class='city-desc'>
            <div class='desc-section' style='border-left:3px solid var(--blue-500); padding-left:15px; background:#f0f9ff;'>
                <span class='source-tag'>🎯 Strategic Summary</span>
                <p style='font-weight:600; margin:0;' itemprop='description'>{city['story_it']}</p>
            </div>
            {'<div class="desc-section"><span class="source-tag">📂 Wiki Archive</span><p style="font-size:0.85rem; margin:0;">' + city['wiki_intro'] + '</p></div>' if city['wiki_intro'] else ''}
        </div>"""

        # --- Attractions with microdata (tabular layout) ---
        attr_rows = ""
        for idx, a in enumerate(city['attractions'], 1):
            attr_rows += (
                f"<tr itemprop='containsPlace' itemscope itemtype='https://schema.org/TouristAttraction'>"
                f"<td class='atn'>{idx}</td>"
                f"<td class='atn-name'><span itemprop='name'>{a['n']}</span>"
                f"<div itemprop='geo' itemscope itemtype='https://schema.org/GeoCoordinates'>"
                f"<meta itemprop='latitude' content='{a['lat']}'>"
                f"<meta itemprop='longitude' content='{a['lon']}'></div></td>"
                f"<td class='atn-desc'><span itemprop='description'>{a['d']}</span></td>"
                f"<td class='atn-map'>"
                f"<a href='https://www.google.com/maps?q={a['lat']},{a['lon']}' target='_blank' class='maps-link'>📍</a>"
                f"</td></tr>"
            )
        attractions_html = (
            "<div class='attractions'>"
            "<span class='block-title'>Strategic Sights &amp; Coordinates</span>"
            "<table class='attr-table'>"
            "<thead><tr><th>#</th><th>Attraction</th><th>Description</th><th></th></tr></thead>"
            f"<tbody>{attr_rows}</tbody>"
            "</table></div>"
        )

        # --- City map data ---
        import json as _json, math as _math
        city_lat, city_lon = CAPITAL_COORDS.get(cl, (48.8566, 2.3522))

        def _map_dist_km(lat2, lon2):
            R = 6371
            dlat = _math.radians(float(lat2) - city_lat)
            dlon = _math.radians(float(lon2) - city_lon)
            a = (_math.sin(dlat/2)**2 +
                 _math.cos(_math.radians(city_lat)) * _math.cos(_math.radians(float(lat2))) *
                 _math.sin(dlon/2)**2)
            return R * 2 * _math.asin(_math.sqrt(a))

        MAX_MAP_KM = 15
        map_attrs_js = _json.dumps([
            {'lat': float(a['lat']), 'lon': float(a['lon']), 'n': a['n'], 'd': a.get('d', '')}
            for a in city['attractions']
            if a.get('lat') and a.get('lon')
            and _map_dist_km(a['lat'], a['lon']) <= MAX_MAP_KM
        ])
        map_venues_js = _json.dumps([
            {'lat': float(v['lat']), 'lon': float(v['lon']), 'n': v['n'], 'cat': v.get('cat', 'bar')}
            for v in city['nightlife']
            if v.get('lat') and v.get('lon')
            and _map_dist_km(v['lat'], v['lon']) <= MAX_MAP_KM
        ])

        page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="../../stile.css?v={CSS_VER}">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <title>{city['name_it']} — EuroCity Strategic Intelligence</title>
</head>
<body>
<a href="#main" class="skip-link">Salta al contenuto</a>
<header class="topbar">
    <div class="topbar-inner">
        <a href="../../index.html" class="topbar-logo">EuroCity <b>SI</b></a>
        <nav class="topbar-nav" aria-label="Navigazione principale">
            <a href="../../index.html">🏠 Home</a>
            <a href="../../pages/mappa_attrazioni.html">🗺️ Map</a>
            <a href="../../pages/report.html">📊 Report</a>
        </nav>
    </div>
</header>
<nav class="city-nav" data-slug="{cl}" aria-label="Navigazione tra le città">
    <a href="{prev_city['city_lower']}.html">← {prev_city['flag']} {prev_city['name_it']}</a>
    <span class="city-nav-title">{city['flag']} {city['name_it']}</span>
    <a href="{next_city['city_lower']}.html">{next_city['flag']} {next_city['name_it']} →</a>
</nav>
<main id="main" class="city-detail" itemscope itemtype="https://schema.org/City" itemid="{city['uri']}">
    <meta itemprop="name" content="{city['name_it']}">
    {rating_html}
    {region_md_html}
    {geo_html}
    {lm_html}
    <h1 class="city-title" style="margin-bottom:25px;">{city['flag']} {city['name_it']}</h1>
    {stats_html}
    {currency_note_html}
    {transport_html}
    {hotel_html}
    {districts_html}
    {nightlife_html}
    {desc_html}
    {attractions_html}
    <div class="info-block" style="padding:0;overflow:hidden;border-radius:16px;">
        <span class="block-title" style="display:block;padding:14px 18px;">🗺️ City Map</span>
        <div id="city-map" style="height:380px;width:100%;"></div>
    </div>
    <div class="download-block">
        <p style="color:var(--slate-500); font-size:0.85rem; margin-bottom:12px;">Structured data source (DTD-validated XML — <code>city_report.dtd</code>):</p>
        <a href="../../data/xml_dataset/{cl}.xml" download class="download-link">📥 Download XML source</a>
        <p style="color:var(--slate-500); font-size:0.85rem; margin:14px 0 0;">URI canonico del documento (elemento <code>&lt;source_url&gt;</code>, usato anche come <code>itemid</code> microdata):</p>
        <a href="{city['uri']}" itemprop="url" target="_blank" rel="noopener" class="source-link">🔗 {city['uri'].replace('https://', '').replace('http://', '')}</a>
    </div>
</main>
<footer style="text-align:center; padding:40px; color:var(--slate-500); font-size:0.82rem;">
    Progetto TEAM — Laurea Magistrale in Governance e Politiche dell'Innovazione Digitale<br>
    Università di Bologna — A.A. 2024/2025
</footer>
<button id="back-to-top" title="Back to top">↑</button>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
(function(){{
  var map = L.map('city-map');
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}{{r}}.png',
    {{attribution:'&copy; OpenStreetMap &copy; CARTO',maxZoom:19}}).addTo(map);
  var mkIcon=function(e){{return L.divIcon({{className:'',html:'<div style="font-size:21px;line-height:32px;width:32px;text-align:center;filter:drop-shadow(0 1px 3px rgba(0,0,0,.4))">'+e+'</div>',iconSize:[32,32],iconAnchor:[16,16]}});}};
  var venueIco={{bar:'🍺',pub:'🍺',biergarten:'🍺',nightclub:'🎵'}};
  var attrs={map_attrs_js};
  var venues={map_venues_js};
  var allMkrs=[];
  attrs.forEach(function(a){{
    var m=L.marker([a.lat,a.lon],{{icon:mkIcon('📍')}}).addTo(map);
    m.bindTooltip(a.n);
    if(a.d)m.bindPopup('<div class="mp"><h4 style="margin:0 0 4px">📍 '+a.n+'</h4><p style="margin:0;font-size:.82rem;color:#334155">'+a.d+'</p></div>');
    allMkrs.push(m);
  }});
  venues.forEach(function(v){{
    var ico=venueIco[v.cat]||'🍺';
    var m=L.marker([v.lat,v.lon],{{icon:mkIcon(ico)}}).addTo(map);
    m.bindTooltip(v.n);
    m.bindPopup('<div class="mp"><h4 style="margin:0 0 4px">'+ico+' '+v.n+'</h4><p style="margin:0 0 6px;font-size:.82rem;color:#64748b">'+v.cat+'</p>'
      +'<a href="https://www.google.com/maps?q='+v.lat+','+v.lon+'" target="_blank" class="pl" style="margin-right:10px">📍 Maps</a>'
      +'<a href="#nightlife" class="pl">🍺 Where to Drink ↓</a></div>');
    allMkrs.push(m);
  }});
  if(allMkrs.length>0){{
    map.fitBounds(L.featureGroup(allMkrs).getBounds().pad(0.2));
  }}else{{
    map.setView([{city_lat},{city_lon}],13);
  }}
}})();
var btt = document.getElementById('back-to-top');
window.addEventListener('scroll', function() {{
    btt.classList.toggle('visible', window.scrollY > 400);
}});
btt.onclick = function() {{ window.scrollTo({{top: 0, behavior: 'smooth'}}); }};
</script>
{analyst_widget}
{analyst_js}
{nav_rewrite_js}
</body>
</html>"""

        with open(ROOT / 'pages' / 'cities' / f"{cl}.html", 'w', encoding='utf-8') as f:
            f.write(page_html)

    print(f"✅ Generate {n} pagine HTML individuali.")


def generate_report(city_data, validation):
    """Generate report.html: statistics extracted from XML files + pipeline documentation.
    `validation` is the DTD-validation summary computed in deploy() (valid/invalid/malformed)."""
    print("📊 Generazione report.html...")
    val_total = validation['valid'] + validation['invalid'] + validation['malformed']

    def fv(x):
        # casting resiliente: .strip() per i ritorni a capo accidentali (cfr. teoria del corso)
        try: return float(str(x).strip())
        except: return 0.0

    # --- Statistics extracted from XML data ---
    by_appeal  = sorted(city_data, key=lambda c: fv(c['appeal']),  reverse=True)
    by_safety  = sorted(city_data, key=lambda c: fv(c['safety']),  reverse=True)
    by_green   = sorted(city_data, key=lambda c: fv(c['green']),   reverse=True)
    by_cost    = sorted(city_data, key=lambda c: fv(c['price']))  # ascending = cheapest first

    total_cities      = len(city_data)
    total_hotels      = sum(int(c['hotel_count']) for c in city_data if str(c['hotel_count']).isdigit())
    total_attractions = sum(len(c['attractions']) for c in city_data)
    cities_with_dist  = sum(1 for c in city_data if c['districts'])

    # --- XPath con PREDICATO per valore di attributo: //venue[@category="..."] ---
    # Rilegge i documenti XML e conta i locali per categoria usando un predicato vero,
    # l'esempio-bandiera del prof; resiliente ai file mal formati (try/except, continua).
    venue_by_cat = {'pub': 0, 'bar': 0, 'nightclub': 0}
    for _xf in sorted(glob.glob(os.path.join(XML_DIR, '*.xml'))):
        try:
            _root = etree.parse(_xf).getroot()
        except etree.XMLSyntaxError:
            continue
        for _cat in venue_by_cat:
            venue_by_cat[_cat] += len(_root.xpath(f'.//venue[@category="{_cat}"]'))
    total_venues = sum(venue_by_cat.values())

    # --- Microdata: conteggio REALE sui file HTML appena generati (index + pagine città) ---
    md_files = [str(OUTPUT_HTML)] + sorted(
        str(p) for p in (ROOT / 'pages' / 'cities').glob('*.html'))
    md_tot, md_types, md_props = count_microdata(md_files)
    md_attrs_total = md_tot['items'] * 2 + md_tot['props'] + md_tot['ids']  # itemscope+itemtype+itemprop+itemid
    md_type_rows = "".join(
        f"<tr><td style='padding:6px 10px'><code>schema.org/{t}</code></td>"
        f"<td style='padding:6px 10px;text-align:right'><b>{n}</b></td></tr>"
        for t, n in md_types.most_common())
    md_prop_chips = " · ".join(
        f"<code>{p}</code>&nbsp;{n}" for p, n in md_props.most_common())
    avg_appeal = round(sum(fv(c['appeal'])  for c in city_data) / total_cities, 1)
    avg_safety = round(sum(fv(c['safety'])  for c in city_data) / total_cities, 1)
    avg_green  = round(sum(fv(c['green'])   for c in city_data) / total_cities, 1)

    def ranking_chart(cities, key, unit="", color="var(--accent)", invert=False, n=5):
        """Riga-grafico (CSS Grid) per ogni città: posizione · nome · barra · valore.
        La barra è normalizzata sul massimo del dataset per quell'indicatore; con
        `invert=True` (prezzo) più corta = più cara, così la barra più lunga è sempre
        la 'migliore'. Podio (1-3) marcato con medaglie."""
        medals = {1: '🥇', 2: '🥈', 3: '🥉'}
        vals = [fv(c[key]) for c in city_data]
        vmax, vmin = (max(vals) if vals else 1), (min(vals) if vals else 0)
        rows = ""
        for i, c in enumerate(cities[:n], 1):
            v = fv(c[key])
            if invert:
                pct = round((vmax - v) / (vmax - vmin) * 100) if vmax > vmin else 100
            else:
                pct = round(v / vmax * 100) if vmax else 0
            pct = max(6, min(100, pct))          # pavimento: anche la barra minima resta visibile
            pos = medals.get(i, str(i))
            val_disp = str(int(round(v))) if unit == '€' else c[key]   # prezzi: euro interi
            rows += (
                f"<div class='rk-row'>"
                f"<span class='rk-pos'>{pos}</span>"
                f"<span class='rk-name'>{c['flag']} {c['name_it']}</span>"
                f"<span class='rk-track'><span class='rk-fill' style='width:{pct}%;background:{color}'></span></span>"
                f"<span class='rk-val'>{val_disp}{unit}</span>"
                f"</div>"
            )
        return rows

    def stat_card(label, value, color="var(--accent)"):
        return (
            f"<div class='rstat-card'>"
            f"<span class='rstat-val' style='color:{color}'>{value}</span>"
            f"<span class='rstat-label'>{label}</span>"
            f"</div>"
        )

    # Read DTD for display
    dtd_content = ""
    if os.path.exists(DTD_FILE):
        with open(DTD_FILE, encoding='utf-8') as f:
            dtd_content = f.read().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    summary_cards = (
        stat_card("Capitals Analysed", total_cities)
        + stat_card("Accommodation Venues", total_hotels, "var(--blue-500)")
        + stat_card("Attractions Catalogued", total_attractions, "var(--green-500)")
        + stat_card("Cities with Districts", f"{cities_with_dist}/{total_cities}", "#8b5cf6")
        + stat_card("Avg Appeal", avg_appeal, "var(--accent)")
        + stat_card("Avg Safety", avg_safety, "var(--blue-500)")
        + stat_card("Avg Green Score", avg_green, "var(--green-500)")
        + stat_card("Validated XML Files", total_cities, "#D97706")
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="../stile.css?v={CSS_VER}">
  <title>Report &amp; Documentation — EuroCity</title>
  <style>
    .report-nav {{
      max-width: 950px; margin: 0 auto 0; padding: 18px 20px;
      display: flex; gap: 12px; flex-wrap: wrap;
    }}
    .report-nav a {{
      background: var(--slate-100); color: var(--slate-800);
      padding: 7px 18px; border-radius: 20px; text-decoration: none;
      font-size: 0.82rem; font-weight: 700; border: 1px solid var(--slate-200);
      transition: 0.2s;
    }}
    .report-nav a:hover {{ background: var(--accent-dark); color: white; }}
    .report-section {{
      max-width: 950px; margin: 36px auto; background: white;
      border-radius: 20px; padding: 40px 44px;
      border: 1px solid var(--slate-200);
      box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }}
    .report-section h2 {{
      font-size: 1.35rem; font-weight: 800; margin: 0 0 24px;
      padding-bottom: 12px; border-bottom: 3px solid var(--accent);
      color: var(--primary-dark);
    }}
    .report-section h3 {{
      font-size: 1rem; font-weight: 800; color: var(--slate-800);
      margin: 24px 0 10px;
    }}
    .rstat-grid {{
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
      margin-bottom: 32px;
    }}
    .rstat-card {{
      background: var(--slate-50); border: 1px solid var(--slate-100);
      border-radius: 14px; padding: 18px 12px; text-align: center;
      display: flex; flex-direction: column; gap: 4px;
    }}
    .rstat-val {{ font-size: 1.8rem; font-weight: 800; }}
    .rstat-label {{
      font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
      color: var(--slate-500); letter-spacing: 0.06em;
    }}
    .rank-table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    .rank-table td {{ padding: 8px 6px; vertical-align: middle; }}
    .rank-table tr:not(:last-child) {{ border-bottom: 1px solid var(--slate-100); }}
    /* --- Classifiche: grafici a barre in CSS Grid --- */
    .rank-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 18px; margin-bottom: 10px;
    }}
    .rank-card {{
      background: var(--slate-50); border: 1px solid var(--slate-100);
      border-left: 4px solid var(--accent); border-radius: 14px; padding: 16px 18px;
    }}
    .rk-appeal {{ border-left-color: var(--accent); }}
    .rk-safety {{ border-left-color: var(--blue-500); }}
    .rk-green  {{ border-left-color: var(--green-500); }}
    .rk-price  {{ border-left-color: #f59e0b; }}
    .rk-head {{ display: flex; align-items: center; gap: 9px; margin-bottom: 14px; }}
    .rk-head h3 {{ margin: 0; font-size: 0.98rem; }}
    .rk-ico {{ font-size: 1.15rem; line-height: 1; }}
    .rk-tag {{
      margin-left: auto; font-size: 0.64rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.05em; color: var(--slate-500); background: #fff;
      border: 1px solid var(--slate-200); border-radius: 6px; padding: 2px 8px;
    }}
    .rk-chart {{ display: flex; flex-direction: column; gap: 9px; }}
    .rk-row {{
      display: grid;
      grid-template-columns: 26px minmax(84px, 130px) 1fr auto;
      align-items: center; gap: 10px; font-size: 0.86rem;
    }}
    .rk-pos {{ text-align: center; font-weight: 800; color: var(--slate-500); }}
    .rk-name {{
      font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    .rk-track {{
      height: 10px; background: var(--slate-200); border-radius: 6px; overflow: hidden;
    }}
    .rk-fill {{ display: block; height: 100%; border-radius: 6px; min-width: 4px; }}
    .rk-val {{ font-weight: 800; font-variant-numeric: tabular-nums; white-space: nowrap; }}
    .pipeline-steps {{
      display: flex; flex-direction: column; gap: 0;
      position: relative; margin: 8px 0 0;
    }}
    .pipeline-step {{
      display: flex; gap: 20px; align-items: flex-start;
      padding: 18px 0; position: relative;
    }}
    .pipeline-step:not(:last-child)::after {{
      content: ''; position: absolute; left: 20px; top: 56px;
      width: 2px; height: calc(100% - 20px);
      background: var(--slate-200);
    }}
    .step-num {{
      min-width: 40px; height: 40px; background: var(--accent);
      color: white; border-radius: 50%; display: flex;
      align-items: center; justify-content: center;
      font-weight: 800; font-size: 0.95rem; z-index: 1;
    }}
    .step-body p {{ margin: 4px 0 0; font-size: 0.9rem; color: var(--slate-500); }}
    code {{
      background: var(--slate-100); color: var(--slate-800); padding: 2px 6px; border-radius: 4px;
      font-family: monospace; font-size: 0.85em;
    }}
    pre {{
      background: #0f172a; color: #e2e8f0; padding: 20px 24px;
      border-radius: 12px; overflow-x: auto; font-size: 0.82rem;
      line-height: 1.6; margin: 0;
    }}
    .technique-grid {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
    }}
    .technique-card {{
      background: var(--slate-50); border: 1px solid var(--slate-200);
      border-radius: 14px; padding: 20px;
    }}
    .technique-card h3 {{
      margin: 0 0 8px; font-size: 0.9rem; color: var(--accent-dark);
      font-weight: 800;
    }}
    .technique-card p {{
      margin: 0; font-size: 0.87rem; color: var(--slate-500);
      line-height: 1.5;
    }}
    .ai-badge {{
      display: inline-block; background: #f0fdf4; color: #166534;
      border: 1px solid #bbf7d0; border-radius: 8px;
      padding: 3px 10px; font-size: 0.78rem; font-weight: 700;
      margin-bottom: 8px;
    }}
    /* --- Provenienza degli indicatori --- */
    .prov-table {{
      width: 100%; border-collapse: collapse; font-size: 0.86rem;
      margin: 0 0 10px; background: var(--slate-50);
      border: 1px solid var(--slate-100); border-radius: 12px; overflow: hidden;
    }}
    .prov-table th {{
      text-align: left; padding: 10px 12px; background: var(--slate-100);
      font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;
      color: var(--slate-500);
    }}
    .prov-table td {{
      padding: 10px 12px; vertical-align: top; border-top: 1px solid var(--slate-100);
    }}
    .prov-table td:first-child {{ font-weight: 700; white-space: nowrap; }}
    .prov-src {{
      display: inline-block; font-size: 0.72rem; font-weight: 700;
      border-radius: 6px; padding: 2px 8px; white-space: nowrap;
    }}
    .src-derived {{ background: #fef3c7; color: #92400e; }}
    .src-indices {{ background: #dbeafe; color: #1e40af; }}
    .src-wiki    {{ background: #dcfce7; color: #166534; }}
    /* --- Formula Appeal Score --- */
    .appeal-formula {{
      display: flex; border-radius: 10px; overflow: hidden;
      font-size: 0.82rem; font-weight: 700; color: white; margin: 10px 0 6px;
      box-shadow: 0 2px 8px rgba(0,0,0,.08);
    }}
    .appeal-seg {{
      padding: 14px 10px; text-align: center; line-height: 1.3;
    }}
    .appeal-seg small {{ display: block; font-weight: 500; opacity: 0.85; font-size: 0.72rem; }}
    .seg-safety {{ background: var(--accent);     flex: 40; }}
    .seg-green  {{ background: var(--green-500);   flex: 40; }}
    .seg-cost   {{ background: #f59e0b;            flex: 20; }}
    @media (max-width: 768px) {{
      .rstat-grid {{ grid-template-columns: 1fr 1fr; }}
      .rank-grid, .technique-grid {{ grid-template-columns: 1fr; }}
      .report-section {{ padding: 24px 20px; }}
      .prov-table {{ font-size: 0.78rem; }}
    }}
  </style>
</head>
<body>
<a href="#main" class="skip-link">Salta al contenuto</a>
<header class="topbar">
  <div class="topbar-inner">
    <a href="../index.html" class="topbar-logo">EuroCity <b>SI</b></a>
    <nav class="topbar-nav" aria-label="Navigazione principale">
      <a href="../index.html">🏠 Home</a>
      <a href="mappa_attrazioni.html">🗺️ Map</a>
      <a href="report.html" class="active" aria-current="page">📊 Report</a>
    </nav>
  </div>
</header>
<div style="background:linear-gradient(135deg,#0F172A 0%,#1a2e4a 60%,#1e3a58 100%);
            color:white; padding:40px 24px 50px; text-align:center; border-bottom:4px solid var(--accent);">
  <h1 style="font-size:clamp(1.5rem,3vw,2.4rem);font-weight:800;margin:0 0 8px;letter-spacing:-0.03em;">
    Report &amp; Documentation</h1>
  <p style="opacity:0.7;font-size:1rem;margin:0;">
    Statistics extracted algorithmically · TEAM Pipeline · UniBo A.Y. 2024/2025</p>
</div>

<nav class="report-nav" aria-label="Sezioni del report">
  <a href="#statistiche">📊 Statistics</a>
  <a href="#ranking">🏆 Rankings</a>
  <a href="#architettura">⚙️ Architecture</a>
  <a href="#dtd">📄 DTD Schema</a>
  <a href="#parsing">🔬 Parsing Techniques</a>
  <a href="#xpath">🧭 XPath</a>
  <a href="#microdata">🏷️ Microdata</a>
  <a href="#semantica">♿ HTML &amp; Accessibilità</a>
  <a href="#rag">🔎 Virtual Analyst (RAG)</a>
  <a href="#ai">🤖 AI Usage</a>
  <a href="#team">👥 Team</a>
</nav>

<main id="main" aria-label="Contenuto del report">
<!-- ===== STATISTICHE ===== -->
<section class="report-section" id="statistiche">
  <h2>📊 Statistiche Comparative — Dati Estratti dai File XML</h2>
  <p style="margin-top:0; color:var(--slate-500); font-size:0.92rem;">
    Nessun numero in questa pagina è scritto a mano: ognuno è <b>calcolato a runtime</b> rileggendo
    i {total_cities} file <code>data/xml_dataset/*.xml</code> già validati contro il DTD. Il report
    è quindi il <b>riflesso diretto</b> dei documenti — se cambia un XML, cambia la statistica.
  </p>
  <div class="rstat-grid">
    {summary_cards}
  </div>

  <h3 style="margin:6px 0 6px;">🔍 Da dove viene ogni numero — provenienza degli indicatori</h3>
  <p style="font-size:0.9rem; color:var(--slate-500); margin:0 0 14px;">
    In ogni XML confluiscono due famiglie di dati: i <b>contenuti testuali</b> estratti
    algoritmicamente dai dump <b>Wikivoyage</b> (trasporti, attrazioni, distretti, locali) e gli
    <b>indici numerici</b> presi da <code>city_indices.json</code> (fonti internazionali). L'unico
    valore <i>derivato</i> dalla pipeline è l'<b>Appeal Score</b>, ricalcolato dai tre indici.
  </p>
  <table class="prov-table">
    <thead>
      <tr><th>Indicatore</th><th>Fonte</th><th>Come si ottiene</th><th style="text-align:right">Scala</th></tr>
    </thead>
    <tbody>
      <tr>
        <td>Appeal Score</td>
        <td><span class="prov-src src-derived">🧮 Derivato</span></td>
        <td>Ricalcolato: <code>Safety×0.4 + Green×0.4 + (100−Costo)×0.2</code>; salvato come attributo <code>appeal_score</code> di <code>&lt;city_report&gt;</code>.</td>
        <td style="text-align:right">0–100</td>
      </tr>
      <tr>
        <td>Indice di Sicurezza</td>
        <td><span class="prov-src src-indices">📊 city_indices.json</span></td>
        <td>Numbeo Safety Index 2024; letto da <code>&lt;safety index_score="…"&gt;</code>.</td>
        <td style="text-align:right">0–100</td>
      </tr>
      <tr>
        <td>Green Score</td>
        <td><span class="prov-src src-indices">📊 city_indices.json</span></td>
        <td>EU Green Capital Award / EEA; letto da <code>&lt;environment green_score="…"&gt;</code>.</td>
        <td style="text-align:right">0–100</td>
      </tr>
      <tr>
        <td>Accessibilità economica</td>
        <td><span class="prov-src src-indices">📊 city_indices.json</span></td>
        <td>Numbeo Cost of Living 2024; letto da <code>&lt;economic_accessibility score="…"&gt;</code>.</td>
        <td style="text-align:right">0–100</td>
      </tr>
      <tr>
        <td>Budget alloggio</td>
        <td><span class="prov-src src-derived">🧮 Derivato</span> <span class="prov-src src-indices">📊 city_indices.json</span></td>
        <td><b>Stima sintetica</b>, non un prezzo osservato: <code>&lt;hotel_price&gt; = cost_of_living × 1.85</code>
            (proxy in euro del costo della vita Numbeo). Serve a confrontare le città, non a prenotare.</td>
        <td style="text-align:right">€/notte</td>
      </tr>
      <tr>
        <td>Valuta locale</td>
        <td><span class="prov-src src-indices">📊 currency_rates.json</span></td>
        <td>Codice ISO nell'attributo opzionale <code>&lt;city_report&nbsp;currency="…"&gt;</code> (solo capitali fuori
            area euro); l'equivalente locale mostrato è una conversione <b>indicativa</b> a tassi di riferimento.</td>
        <td style="text-align:right">ISO 4217</td>
      </tr>
      <tr>
        <td>Macro-regione</td>
        <td><span class="prov-src src-indices">📊 geo_regions.json</span></td>
        <td>Attributo <b>enumerato obbligatorio</b> <code>&lt;city_report&nbsp;region="…"&gt;</code> secondo il geoscheme
            <b>UN&nbsp;M49</b> (Northern/Western/Southern/Eastern). Cipro, classificato da M49 in Asia occidentale, è
            assegnato a <i>southern</i> come eccezione UE documentata. Usato come filtro per area nell'index.</td>
        <td style="text-align:right">UN&nbsp;M49</td>
      </tr>
      <tr>
        <td>Attrazioni · Locali · Distretti</td>
        <td><span class="prov-src src-wiki">📂 Wikivoyage</span></td>
        <td>Conteggio diretto degli elementi <code>&lt;attraction&gt;</code> / <code>&lt;venue&gt;</code> / <code>&lt;district&gt;</code> nei documenti.</td>
        <td style="text-align:right">n</td>
      </tr>
    </tbody>
  </table>
  <p style="font-size:0.82rem; color:var(--slate-500); margin:0 0 4px;">
    Le fonti complete con i link a Numbeo, EEA e l'avvertenza accademica sono nella sezione
    <a href="#ai">AI Usage → Fonti degli Indici Numerici</a>.
  </p>

  <h3 style="margin:28px 0 4px;">🧮 Come si calcola l'Appeal Score</h3>
  <p style="font-size:0.9rem; color:var(--slate-500); margin:0 0 6px;">
    È l'unico indice composito: pesa la <b>sicurezza</b> e la <b>sostenibilità</b> al 40% ciascuna e
    l'<b>accessibilità economica</b> al 20% (il costo viene invertito con <code>100−Costo</code>, così
    «più economico = punteggio più alto»). Determina il ranking <a href="#ranking">qui sotto</a>.
  </p>
  <div class="appeal-formula" role="img"
       aria-label="Appeal Score: 40% sicurezza, 40% green, 20% accessibilità economica">
    <div class="appeal-seg seg-safety">Safety<small>peso ×0.4</small></div>
    <div class="appeal-seg seg-green">Green<small>peso ×0.4</small></div>
    <div class="appeal-seg seg-cost">Affordability<small>×0.2 · 100−Costo</small></div>
  </div>
  <p style="font-size:0.82rem; color:var(--slate-500); margin:6px 0 0;">
    Media del dataset: Appeal <b>{avg_appeal}</b> · Safety <b>{avg_safety}</b> · Green <b>{avg_green}</b>
    (calcolate sui {total_cities} file).
  </p>

  <h3 style="margin:28px 0 4px;">🍺 Locali notturni per categoria — estratti con un predicato XPath</h3>
  <p style="font-size:0.9rem; color:var(--slate-500); margin:0 0 8px;">
    Questi conteggi non scorrono l'intera lista filtrando in Python: usano direttamente un
    <b>predicato per valore d'attributo</b>, <code>//venue[@category="…"]</code>, che lascia
    selezionare al motore XPath i soli elementi desiderati (l'attributo <code>category</code> è
    enumerato nel DTD: <code>bar | pub | nightclub</code>).
  </p>
  <div class="rstat-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:8px">
    <div class='rstat-card'><span class='rstat-val' style='color:var(--accent)'>{total_venues}</span><span class='rstat-label'>Locali totali (&lt;venue&gt;)</span></div>
    <div class='rstat-card'><span class='rstat-val' style='color:var(--blue-500)'>{venue_by_cat['bar']}</span><span class='rstat-label'>category="bar"</span></div>
    <div class='rstat-card'><span class='rstat-val' style='color:#8b5cf6'>{venue_by_cat['pub']}</span><span class='rstat-label'>category="pub"</span></div>
    <div class='rstat-card'><span class='rstat-val' style='color:var(--green-500)'>{venue_by_cat['nightclub']}</span><span class='rstat-label'>category="nightclub"</span></div>
  </div>
  <p style="font-size:0.82rem; color:var(--slate-500); margin:0;">
    Dettaglio tecnico del costrutto nella sezione <a href="#xpath">Uso di XPath</a>.
  </p>
</section>

<!-- ===== CLASSIFICHE ===== -->
<section class="report-section" id="ranking">
  <h2>🏆 Classifiche per Indicatore</h2>
  <p style="margin-top:0;color:var(--slate-500);font-size:0.9rem;">
    Top 5 capitali per ogni indicatore. La <b>barra è proporzionale al valore</b>, normalizzata sul
    massimo del dataset; per il prezzo la scala è invertita (<b>barra più lunga = più economica</b>),
    così in ogni grafico la barra più piena è sempre la posizione migliore.
  </p>
  <div class="rank-grid">
    <div class="rank-card rk-appeal">
      <div class="rk-head"><span class="rk-ico">⭐</span><h3>Appeal Score</h3><span class="rk-tag">composito</span></div>
      <div class="rk-chart">{ranking_chart(by_appeal, 'appeal', color='var(--accent)')}</div>
    </div>
    <div class="rank-card rk-safety">
      <div class="rk-head"><span class="rk-ico">🛡️</span><h3>Indice di Sicurezza</h3><span class="rk-tag">0–100</span></div>
      <div class="rk-chart">{ranking_chart(by_safety, 'safety', color='var(--blue-500)')}</div>
    </div>
    <div class="rank-card rk-green">
      <div class="rk-head"><span class="rk-ico">🌱</span><h3>Green Score</h3><span class="rk-tag">sostenibilità</span></div>
      <div class="rk-chart">{ranking_chart(by_green, 'green', color='var(--green-500)')}</div>
    </div>
    <div class="rank-card rk-price">
      <div class="rk-head"><span class="rk-ico">💰</span><h3>Più Economiche</h3><span class="rk-tag">€/notte</span></div>
      <div class="rk-chart">{ranking_chart(by_cost, 'price', unit='€', color='#f59e0b', invert=True)}</div>
    </div>
  </div>
</section>

<!-- ===== ARCHITETTURA ===== -->
<section class="report-section" id="architettura">
  <h2>⚙️ Architettura della Pipeline TEAM</h2>
  <p>
    Il progetto è composto da <b>cinque</b> componenti Python. La pipeline trasforma dump
    MediaWiki in file XML conformi al DTD (con <b>content-model misto</b>), li valida, genera
    le pagine HTML navigabili annotate con <b>microdata</b> e indicizza i contenuti in un
    sistema RAG per le query in linguaggio naturale.
  </p>
  <div class="pipeline-steps">
    <div class="pipeline-step">
      <div class="step-num">1</div>
      <div class="step-body">
        <h3 style="margin:0;"><code>extract_wiki_info.py</code> — Preparazione dati</h3>
        <p>
          Analizza i dump Wikivoyage in <code>data/original_source/</code>. Utilizza
          <b>mwparserfromhell</b> e <b>spaCy</b> per estrarre testo strutturato.
          Produce <code>wiki_text_pulito.csv</code> (trasporti, hotel, distretti) e
          <code>attrazione_descrizione_fixed.csv</code> (attrazioni con coordinate geografiche).
          I dati di sicurezza, costo della vita e green score provengono da <code>city_indices.json</code>.
        </p>
      </div>
    </div>
    <div class="pipeline-step">
      <div class="step-num">2</div>
      <div class="step-body">
        <h3 style="margin:0;"><code>final_processor.py</code> — Elaborazione e validazione XML</h3>
        <p>
          Script centrale del progetto. Per ogni capitale individua la pagina principale nel dump,
          pulisce il Wikitext con regex, estrae distretti con descrizioni dalle sotto-pagine, e
          costruisce l'albero XML. I campi <code>transport</code>, <code>description</code> e
          <code>wiki_intro</code> sono generati come <b>content-model misto</b> (testo + markup
          inline <code>&lt;b&gt;/&lt;i&gt;/&lt;link&gt;</code>); ogni documento riceve l'URI
          canonico <code>&lt;source_url&gt;</code>. L'albero viene <b>validato</b> rispetto al DTD
          con <b>lxml.etree.DTD</b> prima della scrittura in <code>data/xml_dataset/</code>.
        </p>
      </div>
    </div>
    <div class="pipeline-step">
      <div class="step-num">3</div>
      <div class="step-body">
        <h3 style="margin:0;"><code>deploy_dashboard.py</code> — Generazione HTML</h3>
        <p>
          Legge la directory dei 30 file XML e li <b>ri-valida in lettura</b> (distinguendo
          documenti <i>mal formati</i> da <i>non validi</i>, con contatore <code>30/30</code>
          nell'<code>index.html</code>). Produce <code>index.html</code>, le 30 pagine città e
          questo <code>report.html</code>, preservando il markup inline del content-model misto.
          Ogni documento è annotato con <b>microdata Schema.org</b> annidati
          (<code>City &gt; containsPlace/TouristAttraction &gt; geo/GeoCoordinates</code>), dove
          l'<code>itemid</code> è l'URI letto dal documento (<code>&lt;source_url&gt;</code>).
          I dati sono anche serializzati come JSON inline per il Virtual Analyst client-side.
        </p>
      </div>
    </div>
    <div class="pipeline-step">
      <div class="step-num">4</div>
      <div class="step-body">
        <h3 style="margin:0;"><code>validate.py</code> — Validazione DTD standalone</h3>
        <p>
          Script <b>indipendente</b> dal resto della pipeline (modellato sui laboratori del corso):
          scorre la directory XML, costruisce il <b>DOM</b> con <code>etree.parse()</code> e lo
          valida con <code>etree.DTD(...).validate()</code>, distinguendo <i>mal formati</i>,
          <i>non validi</i> e <i>validi</i>. Stampa l'esito per file e restituisce codice di uscita
          <code>0</code> solo se tutti i documenti sono validi. Vedi sezione
          <a href="#dtd">Schema DTD</a>.
        </p>
      </div>
    </div>
    <div class="pipeline-step">
      <div class="step-num">5</div>
      <div class="step-body">
        <h3 style="margin:0;"><code>rag/</code> — Sistema RAG per query in linguaggio naturale</h3>
        <p>
          Modulo indipendente (<code>ingest.py</code> + <code>vectorstore.py</code> + <code>api.py</code>):
          indicizza i 30 XML in <b>336 chunk</b> su un indice <b>FAISS</b> + <b>BM25Okapi</b> con
          <b>Reciprocal Rank Fusion</b>, e applica un <b>pre-filtro per metadati</b> (regione / valuta /
          categoria / soglie) prima della ricerca semantica. Documentazione completa nella sezione dedicata
          <a href="#rag">🔎 Virtual Analyst (RAG)</a>.
        </p>
      </div>
    </div>
  </div>
</section>

<!-- ===== DATI AI PATCH ===== -->
<section class="report-section" id="ai-patch">
  <h2>⚠️ Dati Non Reperibili da Wikivoyage — Integrazione AI</h2>
  <p>
    Le seguenti informazioni non erano presenti nei dump Wikivoyage scaricati e sono state
    integrate con testo sintetico generato da AI (Gemini), chiaramente identificato nel dataset:
  </p>
  <table style="width:100%;border-collapse:collapse;font-size:0.88rem;margin-top:12px">
    <thead>
      <tr style="background:var(--slate-50);text-align:left">
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Città</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Sezione</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Motivo</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><b>Parigi</b></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Trasporti urbani</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">Campo <code>Transport_Text</code> assente nel CSV estratto da Wikivoyage</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><b>Bruxelles</b></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Trasporti urbani</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">Testo estratto dal CSV era in italiano (non dalla pagina principale Wikivoyage)</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><b>Lussemburgo</b></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Trasporti urbani</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">Testo estratto dal CSV era in italiano (non dalla pagina principale Wikivoyage)</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><b>Lussemburgo, Stoccolma</b></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Descrizioni distretti</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">Il CSV conteneva dati errati: siti naturali (Mullerthal) per Lussemburgo, comuni della contea per Stoccolma. Override manuali applicati.</td>
      </tr>
      <tr>
        <td style="padding:8px 12px"><b>Tutte le 30 città</b></td>
        <td style="padding:8px 12px">Strategic Summary</td>
        <td style="padding:8px 12px;color:var(--slate-500)">Sintesi strategiche generate con AI (Gemini) tramite prompt strutturati; non estratte da Wikivoyage</td>
      </tr>
    </tbody>
  </table>
  <p style="background:#FEF3C7;border-left:4px solid #F59E0B;padding:12px 16px;border-radius:8px;font-size:0.85rem;margin-top:16px">
    ⚠️ Tutti i testi generati da AI sono identificabili nel dataset dalla presenza della stringa
    <code>(Source: AI-generated — ...)</code> nel campo <code>&lt;transport&gt;</code> del file XML.
  </p>
</section>

<!-- ===== SCHEMA DTD ===== -->
<section class="report-section" id="dtd">
  <h2>📄 Schema DTD — Struttura dei Documenti XML</h2>
  <p>
    Ogni file in <code>xml_dataset/</code> è validato rispetto a <code>city_report.dtd</code>
    prima della scrittura. La validazione è eseguita a runtime con <code>lxml.etree.DTD</code>.
    I file non validi vengono segnalati ma non scritti.
  </p>

  <h3>Script di validazione dedicato — <code>validate.py</code></h3>
  <p>
    Oltre alla validazione integrata nella pipeline, un <b>script Python standalone</b>
    (<code>scripts/validate.py</code>), indipendente dal resto del progetto, costruisce il
    <b>DOM</b> di ogni documento e lo valida rispetto al DTD. Distingue i tre esiti:
    <b>mal formato</b> (<code>etree.parse()</code> solleva <code>XMLSyntaxError</code>),
    <b>non valido</b> (<code>dtd.validate()</code> &rarr; <code>False</code>) e <b>valido</b>.
  </p>
  <pre>from lxml import etree

dtd = etree.DTD(open("data/city_report.dtd", "rb"))   # carica il DTD

for filename in files:                                  # scorre la directory XML
    try:
        tree = etree.parse(path)                        # parsing → DOM (buona forma)
    except etree.XMLSyntaxError:
        ...                                             # documento MAL FORMATO
        continue
    if dtd.validate(tree):                              # validazione del DOM
        ...                                             # VALIDO
    else:
        print(dtd.error_log.filter_from_errors())       # NON VALIDO</pre>
  <p style="background:#ECFDF5;border-left:4px solid #10B981;padding:12px 16px;border-radius:8px;font-size:0.85rem;margin-top:4px">
    ✅ Esecuzione: <code>python scripts/validate.py</code> &rarr;
    <b>{validation['valid']}/{val_total} validi · {validation['invalid']} non validi ·
    {validation['malformed']} malformati</b>. Lo script restituisce codice di uscita
    <code>0</code> solo se tutti i documenti sono validi.
  </p>

  <h3>Struttura ad albero</h3>
  <pre>city_report [@appeal_score, @currency?, @region]
├── metadata
│   ├── title          (nome EN)
│   ├── name_it        (nome IT)
│   └── flag           (emoji bandiera)
├── indicators
│   ├── hotel_count
│   ├── hotel_price
│   ├── safety         [@index_score]
│   ├── environment    [@green_score]
│   ├── cost_index     [@value]
│   └── economic_accessibility [@score]
├── transport          (testo descrittivo)
├── accommodation
│   └── hotel*
│       ├── name
│       └── price
├── highlights
│   └── attraction*    [@lat @lon]
│       ├── name
│       └── description
├── districts?
│   └── district*
│       ├── name
│       └── description
├── description        (sintesi strategica IT)
├── wiki_intro?        (intro da Wikivoyage, ripulita)
└── landmark_image?    (URL immagine simbolo)</pre>
  <h3>Dichiarazione DTD (file sorgente)</h3>
  <pre>{dtd_content}</pre>
</section>

<!-- ===== PARSING ===== -->
<section class="report-section" id="parsing">
  <h2>🔬 Tecniche di Parsing e Pulizia del Testo</h2>
  <div class="technique-grid">
    <div class="technique-card">
      <h3>Parsing MediaWiki XML con lxml</h3>
      <p>
        I dump Wikivoyage sono file XML con namespace
        <code>http://www.mediawiki.org/xml/export-0.11/</code>.
        La libreria <code>lxml.etree</code> li analizza con
        <code>tree.findall('.//mw:page', ns)</code>.
        Ogni dump contiene più pagine: la pagina principale della città
        e le pagine dei singoli distretti (<code>Città/Distretto</code>).
      </p>
    </div>
    <div class="technique-card">
      <h3>Parsing del Wikitext con mwparserfromhell</h3>
      <p>
        All'interno di ogni pagina MediaWiki, il contenuto non è XML ma <b>wikitext</b>
        (la sintassi con <code>{{template}}</code>, <code>[[link]]</code>, <code>== sezioni ==</code>,
        tabelle, ecc.). <b>mwparserfromhell</b> (&ldquo;MediaWiki Parser from Hell&rdquo;) è la
        libreria Python — usata anche dai bot di Wikipedia — che analizza questo wikitext e lo
        trasforma in un <b>albero di nodi</b> tipizzati (template, wikilink, tag, heading…).
        Permette di estrarre e ripulire il testo in modo <b>strutturato e robusto</b> — ad es.
        <code>wikicode.filter_templates()</code> per individuare e rimuovere i template, o
        <code>strip_code()</code> per ottenere il testo leggibile — invece di affidarsi solo a
        fragili espressioni regolari. È impiegata in <code>extract_wiki_info.py</code> nella fase
        di preparazione del dataset.
      </p>
      <p style="margin-top:8px">
        📖 <a href="https://mwparserfromhell.readthedocs.io/" target="_blank" rel="noopener">Documentazione ufficiale di mwparserfromhell</a>
      </p>
    </div>
    <div class="technique-card">
      <h3>Selezione della Pagina Principale</h3>
      <p>
        L'algoritmo cerca nell'ordine: (1) pagina con titolo esatto uguale al nome della
        città; (2) pagina <code>Città/Understand</code> (intro Wikivoyage). Se il dump
        contiene solo pagine di quartiere (es. Amsterdam, Berlino, Parigi, Roma),
        la sezione Wiki Archive viene omessa per evitare di mostrare testo distrettuale
        al posto dell'intro cittadina. La comparazione è <b>accent-insensitive</b>
        tramite <code>unicodedata.normalize('NFKD')</code>, necessario per Reykjavík.
      </p>
    </div>
    <div class="technique-card">
      <h3>Pulizia del Wikitext</h3>
      <p>
        Il testo grezzo in formato Wikitext viene ripulito con sequenze di regex:
        rimozione dei template <code>{{"{{"}}...{{"}}"}}</code> (5 passate per nested),
        link <code>[[...]]</code> → testo visibile,
        link <code>[http://url testo]</code> → solo testo,
        header <code>== ... ==</code>, tag HTML, marcatori bold/italic <code>'''</code>,
        hatnote di disambiguazione (<code>:For other...</code>).
        Il testo finale viene troncato a 400 caratteri.
      </p>
    </div>
    <div class="technique-card">
      <h3>Estrazione dei Distretti</h3>
      <p>
        La colonna <code>Districts</code> del CSV fornisce i nomi dei distretti
        (estratti nella fase 1). I nomi vengono ripuliti da rumore (es. <i>"Visitor info:"</i>,
        <i>"Buses"</i>, toponomastica storica come <i>"Laibach"</i>).
        Per ogni distretto si cerca la sotto-pagina corrispondente nel dump XML
        e se ne estrae il testo introduttivo come descrizione.
        Per Luxembourg e Stockholm sono stati definiti override manuali
        perché il CSV conteneva dati errati (siti naturali, municipalità di contea).
      </p>
    </div>
    <div class="technique-card">
      <h3>Validazione DTD con lxml</h3>
      <p>
        Prima di ogni scrittura, l'albero XML viene validato con
        <code>lxml.etree.DTD(open('city_report.dtd', 'rb')).validate(root)</code>.
        Tutti i {total_cities} file superano la validazione. Gli elementi opzionali
        (<code>districts?</code>, <code>wiki_intro?</code>, <code>landmark_image?</code>)
        non vengono creati se i dati corrispondenti sono assenti.
      </p>
    </div>
    <div class="technique-card">
      <h3>Microdata Schema.org nell'HTML</h3>
      <p>
        Ogni card nella dashboard è annotata con
        <code>itemscope itemtype="https://schema.org/City"</code>
        e <code>itemprop="name"</code> sul nome della città.
        Le annotazioni microdata sono generate direttamente dallo script
        <code>deploy_dashboard.py</code>. 
      </p>
    </div>
    <div class="technique-card">
      <h3>HTML semantico nell'output</h3>
      <p>
        L'HTML prodotto segue il principio dell'<b>HTML semantico</b>: nessun tag procedurale
        deprecato (<code>&lt;font&gt;</code>, <code>&lt;center&gt;</code>) né attributi
        presentazionali (<code>align</code>, <code>bgcolor</code>), e una struttura logica con
        elementi <b>di blocco</b> (<code>&lt;header&gt;</code>, <code>&lt;nav&gt;</code>,
        <code>&lt;main&gt;</code>, <code>&lt;section&gt;</code>, <code>&lt;article&gt;</code>,
        <code>&lt;footer&gt;</code>).
        Per gli elementi <b>inline</b>, il vocabolario del content-model misto (<code>b</code>,
        <code>i</code>, <code>link</code> nel file XML) viene mappato dalla funzione
        <code>inline_to_html()</code> ai tag <b>semantici</b> dell'HTML — <code>b&rarr;&lt;strong&gt;</code>,
        <code>i&rarr;&lt;em&gt;</code>, <code>link&rarr;&lt;a&gt;</code> — e non ai presentazionali
        <code>&lt;b&gt;/&lt;i&gt;</code>, perché in quei punti l'enfasi porta <i>significato</i>
        (nome della città, termine straniero). I rari <code>&lt;b&gt;</code> residui nei template
        sono enfasi puramente visiva (in HTML5 <code>&lt;b&gt;</code> non è deprecato: indica testo
        stilisticamente distinto senza valore semantico).
      </p>
    </div>
    <div class="technique-card">
      <h3>Gestione delle Eccezioni</h3>
      <p>
        Ogni città è elaborata in un blocco <code>try/except</code> indipendente:
        un file corrotto non blocca la pipeline. La funzione <code>find_orig_file()</code>
        usa confronto accent-insensitive per trovare i file sorgente con nomi accentati.
        I dati mancanti nel CSV (es. Paris transport = NaN, Reykjavik non presente)
        vengono gestiti con <code>TRANSPORT_PATCH</code> e iterando su
        <code>city_indices.json</code> anziché sul CSV.
      </p>
    </div>
    <div class="technique-card">
      <h3>Coordinate Geografiche e Mappa</h3>
      <p>
        Le attrazioni hanno attributi <code>@lat</code> e <code>@lon</code> estratti
        dal CSV <code>attrazione_descrizione_fixed.csv</code>. La dashboard genera link
        diretti a Google Maps (<code>?q=lat,lon</code>) e la mappa interattiva
        <code>mappa_attrazioni.html</code> visualizza tutti i punti su Leaflet.js.
      </p>
    </div>
  </div>
</section>

<!-- ===== XPATH ===== -->
<section class="report-section" id="xpath">
  <h2>🧭 Uso di XPath</h2>
  <p>
    La fase di <b>lettura ed estrazione</b> dei documenti XML si basa su <b>XPath</b>, a due
    livelli: il motore XPath completo di lxml (metodo <code>.xpath()</code>) e il suo
    sottoinsieme <i>ElementPath</i> (<code>.find()</code> / <code>.findall()</code> /
    <code>.findtext()</code>).
  </p>

  <h3>1. XPath completo — <code>.xpath()</code></h3>
  <table style="width:100%;border-collapse:collapse;font-size:0.86rem;margin-top:8px">
    <thead>
      <tr style="background:var(--slate-50);text-align:left">
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Script</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Espressione XPath</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Costrutto</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>deploy_dashboard.py</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>string(.//safety/@index_score)</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">funzione <code>string()</code> + <b>asse attributo</b> <code>@</code></td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>deploy_dashboard.py</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>.//hotel</code> · <code>.//attraction</code> · <code>.//venue</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">asse discendente <code>//</code></td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>extract_wiki_info.py</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>//mw:page</code> · <code>string(.//mw:text)</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)"><code>//</code> + <b>namespace</b> + <code>string()</code></td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>deploy_dashboard.py</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>.//venue[@category="pub"]</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)"><b>predicato per valore d'attributo</b> — filtro di precisione</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>deploy_dashboard.py</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>string(/city_report/@appeal_score)</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">path <b>assoluto</b> + <b>asse attributo</b> sull'attributo obbligatorio del root</td>
      </tr>
      <tr>
        <td style="padding:8px 12px"><code>built_dataset.py</code></td>
        <td style="padding:8px 12px"><code>string(//*[local-name()='text'])</code></td>
        <td style="padding:8px 12px;color:var(--slate-500)"><b>predicato con funzione</b> <code>[local-name()=…]</code></td>
      </tr>
    </tbody>
  </table>
  <p style="font-size:0.86rem;margin-top:12px">
    Due esempi mostrano l'intera gamma dei costrutti. <code>string(.//safety/@index_score)</code>
    combina <b>path discendente</b>, <b>asse attributo</b> e <b>funzione XPath</b> per leggere gli
    indici memorizzati come attributi di elementi <code>EMPTY</code>. <code>.//venue[@category="pub"]</code>
    usa invece un <b>predicato</b> (<code>[…]</code>): il filtro per valore d'attributo che lascia
    selezionare al motore XPath i soli locali desiderati — più robusto del filtraggio manuale in
    Python e <b>immune all'ordine</b> degli elementi. Entrambe le espressioni alimentano numeri
    reali nella sezione <a href="#statistiche">Statistiche</a>.
  </p>
  <p style="font-size:0.86rem;margin-top:8px">
    <b>Resilienza nel casting.</b> I valori estratti sono sempre stringhe: la conversione a numero
    (medie di Appeal, Safety, prezzi) passa per una funzione <code>fv()</code> che applica
    <code>float(str(x).strip())</code> dentro un <code>try/except</code>. Così un eventuale valore
    corrotto (es. <code>"dieci"</code>) non manda in crash la pipeline ma viene neutralizzato,
    permettendo di proseguire con gli altri documenti.
  </p>

  <h3>2. ElementPath — <code>find()</code> / <code>findall()</code> / <code>findtext()</code></h3>
  <p style="font-size:0.9rem">
    Sottoinsieme di XPath di ElementTree/lxml, usato pervasivamente per navigare il DOM —
    es. <code>tree.findall('.//mw:page', ns)</code> (<code>final_processor.py</code>),
    <code>root.findall('.//attraction')</code> (<code>validate.py</code>),
    <code>root.findtext(".//title")</code> (<code>deploy_dashboard.py</code>). Gli attributi
    (es. <code>@category</code>, <code>@lat</code>) si leggono invece con
    <code>element.get('attr')</code>.
  </p>
</section>

<!-- ===== MICRODATA ===== -->
<section class="report-section" id="microdata">
  <h2>🏷️ Microdata Schema.org — Quantificazione</h2>
  <p>
    Lo script <code>deploy_dashboard.py</code> annota i documenti HTML con <b>microdata
    Schema.org</b> (vincolo del progetto). Le annotazioni sono generate dallo script e i
    conteggi qui sotto sono calcolati <b>a runtime</b> ri-scansionando i file HTML appena
    prodotti (<code>index.html</code> + {len(md_files) - 1} pagine città), quindi non sono
    valori statici.
  </p>
  <div class="rstat-grid">
    <div class='rstat-card'><span class='rstat-val' style='color:var(--accent)'>{md_tot['items']}</span><span class='rstat-label'>Item tipizzati (itemscope)</span></div>
    <div class='rstat-card'><span class='rstat-val' style='color:var(--blue-500)'>{md_tot['props']}</span><span class='rstat-label'>Proprietà (itemprop)</span></div>
    <div class='rstat-card'><span class='rstat-val' style='color:var(--green-500)'>{md_tot['ids']}</span><span class='rstat-label'>Identificatori (itemid)</span></div>
    <div class='rstat-card'><span class='rstat-val' style='color:#8b5cf6'>{md_attrs_total}</span><span class='rstat-label'>Attributi microdata totali</span></div>
  </div>

  <h3>Item per tipo Schema.org</h3>
  <table class="rank-table" style="max-width:420px">
    <tbody>{md_type_rows}</tbody>
  </table>

  <h3>Proprietà annotate (itemprop)</h3>
  <p style="font-size:0.86rem;color:var(--slate-500);line-height:2">{md_prop_chips}</p>

  <h3>Struttura annidata e identità (itemid ↔ documento)</h3>
  <p style="font-size:0.9rem">
    La gerarchia rispecchia il pattern multi-livello visto a lezione
    (<code>lab_microdata.py</code>): ogni <code>&lt;city&nbsp;report&gt;</code> diventa una
    <code>City</code> che <b>contiene</b> (<code>containsPlace</code>) le entità annidate del
    documento —
    <code>TouristAttraction</code>, <code>Hotel</code> e i locali notturni — ognuna con il proprio
    blocco <code>geo/GeoCoordinates</code> (<code>latitude</code>/<code>longitude</code>), e che a
    sua volta è <b>contenuta</b> (<code>containedInPlace</code>) nella propria macro-regione e nel
    continente:
  </p>
  <pre style="font-size:0.8rem">City [itemid = source_url]
 ├─ containedInPlace → Place "… Europe"  [identifier → PropertyValue "UN M49"]
 │   └─ containedInPlace → Continent "Europe"  (sameAs → wikidata.org/Q46)
 ├─ aggregateRating → AggregateRating   (ratingValue = appeal_score, best/worst 100/0)
 ├─ additionalProperty → PropertyValue  (Safety Index · Green Score · Economic Accessibility)
 ├─ containsPlace → TouristAttraction   (name, description, geo → GeoCoordinates)
 ├─ containsPlace → Hotel               (name, priceRange)
 └─ containsPlace → BarOrPub | NightClub (name, geo → GeoCoordinates)</pre>
  <p style="font-size:0.86rem;color:var(--slate-500)">
    Due scelte semantiche degne di nota: <b>(1)</b> l'attributo XML <b>enumerato</b>
    <code>category</code> (<code>bar | pub | nightclub</code>) viene mappato sulla classe
    Schema.org più specifica — <code>NightClub</code> per le discoteche, <code>BarOrPub</code>
    altrimenti; <b>(2)</b> gli <b>indicatori</b> numerici sono modellati correttamente: l'Appeal
    Score (composito) come <code>AggregateRating</code> — l'unico <code>aggregateRating</code>
    ammesso su un <code>Place</code> — e i tre sotto-indici come <code>PropertyValue</code> via
    <code>additionalProperty</code>, evitando di forzare più <i>rating</i> distinti su una sola
    proprietà; <b>(3)</b> l'attributo XML <code>region</code> (UN&nbsp;M49) diventa la relazione di
    <b>contenimento geografico</b> <code>containedInPlace</code> — speculare a <code>containsPlace</code> —
    risalendo dalla città alla macro-regione (<code>Place</code>, con il codice M49 come
    <code>identifier</code>) fino al <code>Continent</code> "Europe" (<code>sameAs</code> Wikidata).
  </p>
  <p style="font-size:0.9rem">
    Ogni <code>itemid</code> è l'<b>URI canonico letto dal documento XML</b>
    (elemento <code>&lt;source_url&gt;</code>): gli identificatori nel sito
    <b>corrispondono esattamente</b> a quelli nei documenti, come nell'esempio dei castelli
    del corso (<code>itemid</code> ↔ <code>id</code> del file XML).
  </p>
  <p style="font-size:0.86rem;color:var(--slate-500)">
    <b>Verifica round-trip.</b> Lo script standalone <code>scripts/check_microdata.py</code>
    <b>ri-estrae</b> i microdata dalle pagine con la libreria <code>microdata</code>
    (<code>microdata.get_items()</code>, la stessa del laboratorio <code>lab_microdata.py</code>) e
    controlla che: ogni pagina esponga una <code>City</code> top-level; l'<code>itemid</code>
    ri-letto dall'HTML coincida con il <code>&lt;source_url&gt;</code> del relativo XML; gli oggetti
    annidati (<code>TouristAttraction</code>/<code>Hotel</code>/<code>BarOrPub</code>) portino
    <code>GeoCoordinates</code> e l'<code>AggregateRating</code> il suo <code>ratingValue</code>.
    Esito: <b>round-trip coerente su 30/30 pagine</b>, con conteggi per tipo <b>identici</b> a
    quelli del contatore qui sopra — due metodi indipendenti (regex di scrittura ↔ parser di
    rilettura) che concordano.
  </p>
</section>

<!-- ===== HTML SEMANTICO E ACCESSIBILITA ===== -->
<section class="report-section" id="semantica">
  <h2>♿ HTML Semantico e Accessibilità</h2>

  <p style="background:var(--slate-50);border-left:4px solid var(--accent);padding:14px 18px;border-radius:8px;font-size:0.9rem;font-style:italic;color:var(--slate-800)">
    «HTML è il linguaggio base del Web. Deve essere usato in modo <b>semantico</b>, evitando
    tag procedurali deprecati come <code>&lt;font&gt;</code> e preferendo una chiara
    organizzazione logica. Gli elementi si dividono in quelli <b>di blocco</b> (che vanno a
    capo) e <b>inline</b> (come <code>&lt;em&gt;</code>, <code>&lt;strong&gt;</code> o il
    generico <code>&lt;span&gt;</code>), che si inseriscono nel flusso del testo senza
    spezzarlo.» 
    </p>
  <p>
    Tutto l'HTML prodotto da <code>deploy_dashboard.py</code> applica questo principio. Di
    seguito come la teoria si traduce nel codice generato e, soprattutto, in un effetto reale.
  </p>

  <h3>1. Niente tag procedurali deprecati</h3>
  <p style="font-size:0.9rem">
    Sulle 33 pagine generate: <b>zero</b> <code>&lt;font&gt;</code>, <code>&lt;center&gt;</code>,
    <code>&lt;marquee&gt;</code>, <code>&lt;strike&gt;</code> e <b>zero</b> attributi
    presentazionali (<code>align</code>, <code>bgcolor</code>, <code>valign</code>…). La
    presentazione è interamente delegata al foglio di stile <code>stile.css</code>.
  </p>

  <h3>2. Organizzazione logica con elementi di blocco</h3>
  <p style="font-size:0.9rem">
    Ogni pagina è strutturata con elementi di blocco <b>semantici</b> — non <code>&lt;div&gt;</code>
    generici — che descrivono il ruolo del contenuto: <code>&lt;header&gt;</code> (testata),
    <code>&lt;nav&gt;</code> (navigazione), <code>&lt;main&gt;</code> (contenuto principale, uno
    per pagina), <code>&lt;section&gt;</code> / <code>&lt;article&gt;</code> (blocchi tematici),
    <code>&lt;footer&gt;</code> (piè di pagina), con una gerarchia coerente di heading
    <code>h1&rarr;h2&rarr;h3</code>.
  </p>

  <h3>3. Inline semantici (<code>strong</code> / <code>em</code> / <code>span</code>)</h3>
  <p style="font-size:0.9rem">
    Il vocabolario inline del content-model misto nel XML (<code>b</code>, <code>i</code>,
    <code>link</code>) viene mappato dalla funzione <code>inline_to_html()</code> ai tag
    <b>semantici</b> dell'HTML — <code>b&rarr;&lt;strong&gt;</code>, <code>i&rarr;&lt;em&gt;</code>,
    <code>link&rarr;&lt;a&gt;</code> — perché in quei punti l'enfasi porta <i>significato</i>
    (nome città, termine straniero). Il generico <code>&lt;span&gt;</code> è usato per i
    frammenti senza semantica propria (es. valori delle statistiche). I rari <code>&lt;b&gt;</code>
    residui sono enfasi puramente visiva: in HTML5 <code>&lt;b&gt;</code> non è deprecato ma
    ridefinito come «testo stilisticamente distinto senza importanza semantica».
  </p>

  <h3>4. La «traduzione» del semantico: l'accessibilità</h3>
  <p style="font-size:0.9rem">
    L'HTML semantico è volutamente <b>invisibile</b> all'occhio (<code>&lt;strong&gt;</code> si
    vede come un grassetto), ma si <b>traduce</b> in significato leggibile dalle macchine. Il
    canale principale è l'<b>albero di accessibilità</b>: gli elementi semantici generano
    automaticamente dei <b>landmark ARIA</b> — <code>&lt;header&gt;</code>&rarr;<code>banner</code>,
    <code>&lt;nav&gt;</code>&rarr;<code>navigation</code>, <code>&lt;main&gt;</code>&rarr;<code>main</code>,
    <code>&lt;footer&gt;</code>&rarr;<code>contentinfo</code> — tra i quali uno screen reader può
    saltare. Per rendere questa struttura realmente usabile abbiamo aggiunto:
  </p>
  <ul style="font-size:0.9rem; color:var(--slate-500); line-height:1.8;">
    <li><b>Skip link</b> «Salta al contenuto» come primo elemento (visibile solo al focus da tastiera), per bypassare la navigazione;</li>
    <li><b>aria-label</b> sulle <code>&lt;nav&gt;</code> duplicate (Principale / Tra le città / Sezioni del report) così lo screen reader le distingue;</li>
    <li><b>aria-current="page"</b> sul link attivo; <b>lang</b> sul documento e <b>alt</b> su tutte le immagini.</li>
  </ul>
  <p style="font-size:0.86rem;color:var(--slate-500)">
    Verifica: DevTools del browser &rarr; scheda <i>Accessibility</i> (mostra i landmark
    etichettati), oppure la navigazione per landmark di uno screen reader (VoiceOver / NVDA).
  </p>

  <h3>5. Il sito come riflesso diretto dei documenti</h3>
  <p style="font-size:0.9rem">
    Coerentemente con la semantica, ogni dato del documento XML è reso <b>visibile</b> nella
    pagina, non solo scaricabile. In particolare l'URI canonico del documento (elemento
    <code>&lt;source_url&gt;</code>) è ora un <b>link cliccabile</b> in ogni pagina città, e
    coincide con l'<code>itemid</code> dei microdata: <b>lo stesso identificatore</b> vive nel
    documento, nel link visibile e nell'annotazione machine-readable. Il download del file XML
    resta un'aggiunta, non l'unico modo di accedere ai dati.
  </p>

  <h3>Sintesi: principio &rarr; costrutto &rarr; effetto</h3>
  <table style="width:100%;border-collapse:collapse;font-size:0.86rem;margin-top:8px">
    <thead>
      <tr style="background:var(--slate-50);text-align:left">
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Principio (slide)</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Costrutto HTML</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Effetto reale</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">No tag procedurali</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">0 <code>&lt;font&gt;</code>; stile in CSS</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">separazione contenuto/presentazione</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Organizzazione logica (blocco)</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>header/nav/main/section/footer</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">landmark ARIA + document outline</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Inline semantico (em/strong)</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>&lt;strong&gt;/&lt;em&gt;/&lt;span&gt;</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">enfasi pronunciata dagli screen reader</td>
      </tr>
      <tr>
        <td style="padding:8px 12px">Web come grafo di risorse</td>
        <td style="padding:8px 12px"><code>&lt;a itemprop="url" href=URI&gt;</code></td>
        <td style="padding:8px 12px;color:var(--slate-500)">URI documento = link = itemid microdata</td>
      </tr>
    </tbody>
  </table>

  <h3>6. Target tattili (tap-target) sulla mappa</h3>
  <p style="font-size:0.9rem">
    Un audit <b>Lighthouse</b> (accessibilità <b>96/100</b>) ha segnalato che alcuni marker Leaflet
    della mappa (es. Stoccolma, Oslo, Roma) avevano un'area tattile inferiore a <b>24&times;24&nbsp;px</b>
    o parzialmente sovrapposta — un problema per chi naviga da touch o ha difficoltà motorie.
    Interventi correttivi:
  </p>
  <ul style="font-size:0.9rem; color:var(--slate-500); line-height:1.8;">
    <li>marker dei <b>locali</b> e delle <b>attrazioni</b> (pagine città) portati a <b>32&times;32&nbsp;px</b>, ben oltre la soglia di 24;</li>
    <li>i marker delle <b>capitali</b>, che a zoom basso si sovrapponevano, sono ora <b>raggruppati</b> con <code>L.markerClusterGroup</code>: gli overlap si fondono in un unico bersaglio cliccabile e si riaprono allo zoom (≥ 6);</li>
    <li>raggio dei punti-attrazione aumentato per un'area di tocco più comoda.</li>
  </ul>

  <h3>7. Albero di accessibilità — <code>index.html</code></h3>
  <p style="font-size:0.9rem">
    È la struttura che uno screen reader «vede»: solo <b>ruoli</b> e <b>nomi accessibili</b>, non lo
    stile. I landmark (<code>banner / navigation / main / contentinfo</code>) e i heading
    <code>h1&rarr;h2</code> offrono una mappa navigabile della pagina; il widget chat flottante è
    esposto come <code>dialog</code>. Questa è una copia dell'albero reale della home:
  </p>
  <pre style="font-size:0.8rem; background:var(--slate-50); color:var(--slate-800); border:1px solid var(--slate-200); border-radius:8px; padding:14px; overflow:auto; line-height:1.5;">document  "EuroCity Strategic Intelligence"            [lang="en"]
&#9500;&#9472; link        "Salta al contenuto"                    (skip-link, visibile al focus)
&#9500;&#9472; banner                                              &lt;header&gt;
&#9474;  &#9492;&#9472; navigation  "Navigazione principale"             &lt;nav&gt;  &rarr; Home &middot; Report &middot; Map
&#9500;&#9472; heading h1  "30 European capitals, one intelligence."
&#9500;&#9472; region      "How the data is built"                 &lt;section aria-label&gt;
&#9474;  &#9492;&#9472; heading h2  "How the data is built"
&#9500;&#9472; main        "Griglia delle capitali"                &lt;main id="city-grid"&gt;
&#9474;  &#9500;&#9472; article &rarr; heading h2 "Amsterdam"  + link
&#9474;  &#9500;&#9472; article &rarr; heading h2 "Athens"     + link
&#9474;  &#9492;&#9472; &hellip;  (30 article, una card per capitale)
&#9500;&#9472; contentinfo                                         &lt;footer&gt;  &rarr; link "Report &amp; Documentation"
&#9500;&#9472; button      "Back to top"
&#9492;&#9472; dialog      "Virtual Analyst"                       &lt;div role="dialog"&gt;  &larr; widget flottante
     button "Ask the analyst" &middot; textbox &middot; button "Ask" &middot; button "Close the analyst"</pre>
</section>

<!-- ===== RAG / VIRTUAL ANALYST ===== -->
<section class="report-section" id="rag">
  <h2>🔎 Virtual Analyst — l'assistente che risponde alle domande</h2>
  <p>
    Il <b>Virtual Analyst</b> è l'assistente del sito: risponde a domande scritte in linguaggio naturale
    (italiano o inglese) sulle 30 capitali — per esempio <em>«bar a Dublino»</em> o
    <em>«discoteche nelle città fuori dall'euro»</em>. È un sistema <b>RAG</b> (<i>Retrieval-Augmented
    Generation</i>): invece di "sapere" le risposte, <b>le va a cercare</b> nei 30 file XML e le mostra
    in modo ordinato. Non inventa: riporta solo ciò che è nel dataset.
  </p>

  <h3>Come trova la risposta giusta</h3>
  <p>
    Per ogni domanda cerca in <b>due modi complementari</b> allo stesso tempo: <b>per significato</b> (capisce
    il senso anche con parole diverse — «dove dormire» trova gli hotel) e <b>per parole chiave</b> (cerca i
    termini esatti). Poi <b>fonde le due classifiche</b> in un'unica graduatoria: un risultato che convince
    entrambi i metodi finisce in cima.
  </p>

  <h3>La marcia in più: cercare tra i metadati</h3>
  <p>
    La ricerca nel testo va bene per le domande discorsive, ma fa fatica con quelle <b>precise</b>
    (es. <em>«discoteche nelle città che non usano l'euro»</em>). Per questo l'analista sfrutta i <b>metadati</b>
    già iniettati in ogni città — <b>macro-regione</b>, <b>valuta</b>, <b>tipo di locale</b>, punteggi numerici —
    esattamente come i <b>filtri di un sito di e-commerce</b>: prima restringe il campo a colpo sicuro
    (es. <em>valuta ≠ euro</em> <b>e</b> <em>tipo = discoteca</em>), <b>poi</b> cerca nel testo solo dentro
    quel sottoinsieme. È il punto in cui <b>RAG</b> e <b>Web of Data</b> (i microdata Schema.org) si fondono:
    la stessa informazione che descrive le città per i motori di ricerca serve anche a rispondere meglio.
  </p>

  <h3>I tre vantaggi della fusione RAG &times; Web of Data</h3>
  <ul>
    <li><b>Precisione</b>: i filtri su <code>@region</code>, <code>@currency</code>, <code>@category</code> sono esatti — niente più «zuppa di tag» da indovinare nel testo.</li>
    <li><b>Niente confusione tra categorie</b>: un pub e una discoteca si distinguono dall'etichetta tipizzata (<code>BarOrPub</code> / <code>NightClub</code>), non dal contesto della frase.</li>
    <li><b>Numeri garantiti</b>: coordinate (<code>GeoCoordinates</code>), appeal (<code>AggregateRating</code>) e indicatori sono restituiti <b>identici</b> al dato — zero allucinazioni sui numeri.</li>
  </ul>

  <h3>I due "motori": uno in locale, uno nel browser</h3>
  <p>
    La versione completa è un piccolo server <b>Python (FastAPI)</b> con gli indici di ricerca veri: è la
    <i>reference implementation</i>, si avvia sul proprio computer. Ma il sito è pubblicato su
    <b>GitHub Pages</b>, che ospita <b>solo file statici</b> e non può eseguire un server Python: perciò, quando
    non riesce a contattare il server locale, la pagina usa una versione <b>che gira interamente nel browser</b>
    (<code>metadataQuery()</code>) sui dati già inclusi nella pagina. I due motori usano la <b>stessa logica di
    filtraggio</b>: quello del browser è ciò che i visitatori usano davvero, e funziona senza alcun server.
  </p>

  <h3 style="margin-top:24px;color:var(--slate-500)">Dettagli tecnici (approfondimento)</h3>
  <p style="font-size:0.9rem">Le sezioni precedenti bastano per capire il sistema; qui sotto il "sotto il cofano".</p>
  <pre>data/xml_dataset/*.xml  &rarr;  rag/ingest.py  &rarr;  rag_index/  (index.faiss 384-dim &middot; docs.json 336 chunk + meta)
                                              &darr;
                       rag/vectorstore.py   FAISS + BM25Okapi &rarr; Reciprocal Rank Fusion + pre-filtro metadati
                                              &darr;
                       rag/api.py           FastAPI (127.0.0.1:8000) &middot; parse_filters() &middot; rilevamento intento</pre>
  <ul style="font-size:0.9rem">
    <li><b>FAISS</b> <code>IndexFlatIP</code> (384 dim, <code>all-MiniLM-L6-v2</code>) per la ricerca semantica; <b>BM25Okapi</b> per quella lessicale; fusione con <b>Reciprocal Rank Fusion</b> (α=0.5, k=60);</li>
    <li>il <b>rilevamento d'intento</b> (transport / hotel / attractions / safety / districts / nightlife) dà priorità ai chunk della sezione pertinente.</li>
  </ul>
  <p style="font-size:0.9rem;margin-top:12px"><code>ingest.py</code> allega a <b>ogni</b> chunk i metadati strutturati dell'XML, così la ricerca filtra su valori esatti invece di cercarli nel testo:</p>
  <pre>{{
  "text": "[BERLIN] Bar e locali notturni: ...",
  "city": "BERLIN", "section": "nightlife", "source": "Berlin.xml",
  "meta": {{ "appeal": 63.2, "currency": "EUR", "region": "western",
           "safety": 72.5, "green": 78.0, "cost": 85.0, "economy": 15.0, "price": 157.25 }},
  "categories": ["bar", "pub", "nightclub"]
}}</pre>

  <h4 style="margin:12px 0 4px">Dimensioni di filtro riconosciute</h4>
  <table style="width:100%;border-collapse:collapse;font-size:0.88rem;margin-top:8px">
    <thead>
      <tr style="background:var(--slate-50);text-align:left">
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Dimensione</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Sorgente metadato</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Esempio di domanda</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Filtro applicato</th>
      </tr>
    </thead>
    <tbody>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Macro-regione</td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>@region</code> (UN M49)</td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><em>attractions in northern europe</em></td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>region = northern</code></td></tr>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Valuta</td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>@currency</code></td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><em>nightclubs in non-euro cities</em></td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>currency &ne; EUR</code></td></tr>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Categoria locale</td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>@category</code></td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><em>pubs in eastern europe</em></td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>category = pub</code></td></tr>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Soglie numeriche</td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>appeal/safety/green/price</code></td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><em>cities with appeal over 60</em></td><td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>appeal &ge; 60</code></td></tr>
    </tbody>
  </table>
  <p style="margin-top:10px;font-size:0.9rem">
    I vincoli si combinano in <b>AND</b> (es. <em>eurozone + green over 70</em>). Lato server la risposta
    <code>/query</code> include il campo <code>filters</code> con le dimensioni applicate (trasparenza); lato
    client il motore restituisce in più i <b>valori garantiti</b> verbatim dai metadati.
  </p>

  <p style="font-size:0.82rem;color:var(--slate-500);margin:14px 0 0;">
    <b>Limiti noti:</b> alcune città (Londra, Budapest, Parigi…) mancano di dati hotel nelle sorgenti
    Wikivoyage; la sintesi delle risposte testuali è euristica (estrazione di frasi), non generativa.
  </p>
</section>

<!-- ===== AI ===== -->
<section class="report-section" id="ai">
  <h2>🤖 Dichiarazione Utilizzo Strumenti AI</h2>
  <h3>Claude Code (Anthropic) — Assistenza allo Sviluppo</h3>
  <span class="ai-badge">Claude Code / claude-sonnet-4-6</span>
  <p>
    Lo strumento Claude Code è stato utilizzato per:
  </p>
  <ul style="font-size:0.9rem; color:var(--slate-500); line-height:1.8;">
    <li>Debugging della pipeline di parsing (problema selezione pagina principale nei dump Wikivoyage multi-pagina)</li>
    <li>Scrittura della funzione <code>advanced_wiki_cleaner()</code> per la pulizia del Wikitext con regex</li>
    <li>Risoluzione del problema accent-insensitive per Reykjavík (uso di <code>unicodedata.normalize</code>)</li>
    <li>Identificazione e correzione del bug nell'estrazione distretti in <code>deploy_dashboard.py</code> (<code>d.text</code> invece di <code>d.findtext('name')</code>)</li>
    <li>Generazione della griglia di override distretti per Luxembourg e Stockholm</li>
    <li>Generazione di questo file <code>report.html</code> e del <code>README.md</code></li>
  </ul>

  <h3>AI per i Contenuti del Dataset</h3>
  <span class="ai-badge">city_descriptions.json</span>
  <p>
    Le sintesi strategiche in italiano in <code>city_descriptions.json</code>
    (mostrate come <i>Strategic Summary</i> nelle card) sono state generate con
    <b>Gemini</b> (Google AI) tramite prompt strutturati. Fonte: testo a scopo
    didattico, non estratto da una singola fonte primaria.
  </p>
  <pre style="font-size:0.8rem;">Genera una descrizione strategica in italiano (max 2 frasi) di [CITTÀ]
come capitale europea, focalizzandoti su: innovazione urbana, sostenibilità,
sicurezza, accessibilità economica. Tono: analitico, da report istituzionale.</pre>

  <h3 style="margin-top:28px;">Fonti degli Indici Numerici</h3>
  <span class="ai-badge">city_indices.json</span>

  <table style="width:100%;border-collapse:collapse;font-size:0.88rem;margin-top:12px">
    <thead>
      <tr style="background:var(--slate-50);text-align:left">
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Indicatore</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Fonte originale</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Rielaborazione</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Nota</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><b>Safety Index</b></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">
          <a href="https://www.numbeo.com/crime/region_rankings.jsp?title=2024&amp;region=150" target="_blank">Numbeo Safety Index 2024</a>
        </td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">AI (Gemini)</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">Valori adattati; scarto stimato ±5–10 pt rispetto ai dati Numbeo originali</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><b>Cost of Living</b></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">
          <a href="https://www.numbeo.com/cost-of-living/region_rankings.jsp?title=2024&amp;region=150" target="_blank">Numbeo Cost of Living Index 2024</a>
        </td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">AI (Gemini)</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100);color:var(--slate-500)">Normalizzato sulla scala europea (Numbeo usa NYC = 100 come riferimento)</td>
      </tr>
      <tr>
        <td style="padding:8px 12px"><b>Green Score</b></td>
        <td style="padding:8px 12px">
          <a href="https://environment.ec.europa.eu/topics/urban-environment/european-green-capital-award_en" target="_blank">EU Green Capital Award</a> + EEA City Statistics
        </td>
        <td style="padding:8px 12px">Stima sintetica AI (Gemini)</td>
        <td style="padding:8px 12px;color:#C0392B"><b>⚠️ Non validato da un indice ufficiale 0–100.</b> Stima composita basata su: EU Green Capital Award, aree verdi pro capite, emissioni CO₂, politiche mobilità.</td>
      </tr>
    </tbody>
  </table>

  <p style="background:#FEF3C7;border-left:4px solid #F59E0B;padding:12px 16px;border-radius:8px;font-size:0.85rem;margin-top:12px">
    ⚠️ <b>Avvertenza accademica:</b> i valori numerici in <code>city_indices.json</code>
    sono stime rielaborate con AI a partire da fonti pubbliche. Non sostituiscono
    la consultazione diretta dei dataset originali Numbeo o EEA per usi di ricerca.
  </p>

  <h3 style="margin-top:32px;">Elenco Completo dei File e Fonti</h3>
  <table style="width:100%;border-collapse:collapse;font-size:0.87rem;margin-top:12px">
    <thead>
      <tr style="background:var(--slate-50);text-align:left">
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">File</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Contenuto</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Fonte</th>
        <th style="padding:8px 12px;border-bottom:2px solid var(--slate-200)">Licenza</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>data/original_source/*.xml</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Dump MediaWiki delle 30 capitali (testi, trasporti, hotel, distretti)</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><a href="https://en.wikivoyage.org" target="_blank">Wikivoyage</a> — download manuale</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">CC-BY-SA 3.0</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>data/wiki_text_pulito.csv</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Trasporti, hotel e distretti estratti dai dump tramite <code>extract_wiki_info.py</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Derivato da Wikivoyage</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">CC-BY-SA 3.0</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>data/attrazione_descrizione_fixed.csv</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">300 attrazioni con nome, descrizione e coordinate geografiche</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Derivato da Wikivoyage + curato manualmente</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">CC-BY-SA 3.0</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>data/city_indices.json</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Safety Index, Cost of Living, Green Score per 30 città</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Numbeo 2024, EU Green Capital Award, EEA — rielaborati con AI (Gemini)</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Stima — non ufficiale</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>data/city_descriptions.json</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Sintesi strategiche in inglese per 30 città (campo <i>Strategic Summary</i>)</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Generato con AI (Gemini) — testo originale</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Testo didattico</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>data/nightlife.json</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">240 locali notturni (bar, pub, nightclub) con coordinate geografiche</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><a href="https://www.openstreetmap.org" target="_blank">OpenStreetMap</a> via Overpass API</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">ODbL (Open Database Licence)</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>data/xml_dataset/*.xml</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">30 file XML output, validati DTD, uno per capitale</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Generato dalla pipeline — derivato dalle fonti sopra</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">—</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)"><code>data/transport_patches.json</code></td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Testi trasporto AI per 5 città (Paris, Brussels, Luxembourg, Lisbon, Nicosia)</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Generato con AI (Gemini) — testo originale</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--slate-100)">Testo didattico</td>
      </tr>
      <tr>
        <td style="padding:8px 12px"><code>data/city_report.dtd</code></td>
        <td style="padding:8px 12px">Schema DTD per la validazione dei file XML</td>
        <td style="padding:8px 12px">Creato originalmente per il progetto</td>
        <td style="padding:8px 12px">—</td>
      </tr>
    </tbody>
  </table>
</section>

<section class="report-section" id="team">
  <h2>👥 Il Team</h2>
  <p class="section-intro">Progetto sviluppato nell'ambito della Laurea Magistrale in
    <a href="https://corsi.unibo.it/magistrale/PoliticheInnovazioneDigitale" target="_blank">
    Governance e Politiche dell'Innovazione Digitale (GEPID)</a> —
    Università di Bologna, A.A. 2024/2025.</p>
  <div class="team-grid">
    <article class="team-card">
      <div class="team-initials" style="background:linear-gradient(135deg,#E74C3C,#C0392B)">LT</div>
      <div>
        <p class="team-name">Laura Tonsi</p>
        <a href="https://github.com/lauratonsi" target="_blank" class="team-github">
          ⬡ github.com/lauratonsi</a>
      </div>
    </article>
    <article class="team-card">
      <div class="team-initials" style="background:linear-gradient(135deg,#3498DB,#2980B9)">SC</div>
      <div>
        <p class="team-name">Susanna Cioni</p>
        <a href="https://github.com/SusannaCioni" target="_blank" class="team-github">
          ⬡ github.com/SusannaCioni</a>
      </div>
    </article>
  </div>
</section>
</main>

<footer style="text-align:center; padding:40px; color:var(--slate-500); font-size:0.82rem;">
  Progetto TEAM — Laurea Magistrale in Governance e Politiche dell'Innovazione Digitale<br>
  Università di Bologna — A.A. 2024/2025
</footer>
<button id="back-to-top" title="Back to top">↑</button>
<script>
const btt = document.getElementById('back-to-top');
const hdr = document.querySelector('header');
window.addEventListener('scroll', () => {{
    btt.classList.toggle('visible', scrollY > 400);
    hdr.classList.toggle('scrolled', scrollY > 60);
}});
btt.onclick = () => window.scrollTo({{top: 0, behavior: 'smooth'}});
</script>
</body>
</html>"""

    with open(REPORT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ report.html generato correttamente.")


if __name__ == "__main__":
    deploy()