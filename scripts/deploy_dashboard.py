import os, json, re
from pathlib import Path
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Virtual Analyst — motore di query client-side
# Scritto come stringa Python normale (NON f-string) per evitare conflitti con
# le {} di JavaScript. __CITY_DATA__ viene sostituito a runtime con .replace().
# ---------------------------------------------------------------------------
_ANALYST_JS_TEMPLATE = """
<script>
const cityData = __CITY_DATA__;

/* ---------- helpers ---------- */
function badge(val, color) {
    return '<span style="background:' + color + '22;color:' + color +
           ';padding:2px 8px;border-radius:6px;font-weight:700;font-size:0.85em">' + val + '</span>';
}

function topRows(cities, key, unit) {
    unit = unit || '';
    return cities.slice(0, 5).map(function(c, i) {
        return '<li style="padding:5px 0;border-bottom:1px solid #f1f5f9">' +
               (i+1) + '. ' + c.flag + ' <b>' + c.name_it + '</b> — ' +
               badge(c[key] + unit, '#E74C3C') + '</li>';
    }).join('');
}

function sortBy(key, asc) {
    return cityData.slice().sort(function(a, b) {
        return asc ? parseFloat(a[key]) - parseFloat(b[key])
                   : parseFloat(b[key]) - parseFloat(a[key]);
    });
}

function rankOf(city, key) {
    var sorted = sortBy(key, false);
    return sorted.findIndex(function(x) { return x.name_en === city.name_en; }) + 1;
}

/* ---------- render: confronto due città ---------- */
function renderComparison(a, b) {
    var rows = [
        ['Appeal Score', 'appeal', 1],
        ['Safety',       'safety', 1],
        ['Green',        'green',  1],
        ['Accessibilità','economy',1],
        ['Budget/notte', 'price', -1],
        ['Strutture',    'hotel_count', 1],
    ];
    var rowsHtml = rows.map(function(r) {
        var lbl = r[0], key = r[1], dir = r[2];
        var va = a[key], vb = b[key];
        var na = parseFloat(va), nb = parseFloat(vb);
        var wa = (na !== nb && dir*(na-nb) > 0) ? ' ✅' : '';
        var wb = (na !== nb && dir*(nb-na) > 0) ? ' ✅' : '';
        return '<tr>' +
            '<td style="padding:6px 10px;color:#64748b;font-size:0.85em">' + lbl + '</td>' +
            '<td style="padding:6px 10px;text-align:center;font-weight:700">' + va + (key==='price'?'€':'') + wa + '</td>' +
            '<td style="padding:6px 10px;text-align:center;font-weight:700">' + vb + (key==='price'?'€':'') + wb + '</td>' +
            '</tr>';
    }).join('');
    return '<div style="font-size:0.9em">' +
        '<b>⚖️ Confronto: ' + a.flag + ' ' + a.name_it + ' vs ' + b.flag + ' ' + b.name_it + '</b>' +
        '<table style="width:100%;margin-top:10px;border-collapse:collapse">' +
            '<thead><tr>' +
                '<th style="padding:6px 10px;text-align:left;border-bottom:2px solid #e2e8f0">Indicatore</th>' +
                '<th style="padding:6px 10px;text-align:center;border-bottom:2px solid #e2e8f0">' + a.flag + ' ' + a.name_it + '</th>' +
                '<th style="padding:6px 10px;text-align:center;border-bottom:2px solid #e2e8f0">' + b.flag + ' ' + b.name_it + '</th>' +
            '</tr></thead>' +
            '<tbody>' + rowsHtml + '</tbody>' +
        '</table></div>';
}

/* ---------- render: query globale (senza nome città) ---------- */
function renderGlobal(q) {
    if (/sicur|safe/.test(q))
        return '<b>🛡️ Top 5 Città più Sicure</b><ol style="margin:8px 0;padding-left:0;list-style:none">' + topRows(sortBy('safety',false),'safety') + '</ol>';
    if (/verde|green|ecolog|sostenib|ambient/.test(q))
        return '<b>🌱 Top 5 Città più Verdi</b><ol style="margin:8px 0;padding-left:0;list-style:none">' + topRows(sortBy('green',false),'green') + '</ol>';
    if (/econom|cheap|convenien|afford|basso.cost|economica|prezzi.bass/.test(q))
        return '<b>💰 Top 5 Città più Economiche</b><ol style="margin:8px 0;padding-left:0;list-style:none">' + topRows(sortBy('price',true),'price','€/notte') + '</ol>';
    if (/cara|costosa|expensiv/.test(q))
        return '<b>💎 Top 5 Città più Costose</b><ol style="margin:8px 0;padding-left:0;list-style:none">' + topRows(sortBy('price',false),'price','€/notte') + '</ol>';
    if (/appeal|miglior|top|ranking|consigl|dove.andare|raccomand/.test(q))
        return '<b>⭐ Top 5 per Appeal Score</b><ol style="margin:8px 0;padding-left:0;list-style:none">' + topRows(sortBy('appeal',false),'appeal') + '</ol>';
    if (/quante|totale|dataset|statist/.test(q)) {
        var totH = cityData.reduce(function(s,c){ return s + parseInt(c.hotel_count||0); }, 0);
        var totA = cityData.reduce(function(s,c){ return s + c.attractions.length; }, 0);
        var wD   = cityData.filter(function(c){ return c.districts.length > 0; }).length;
        return '<b>📊 Dataset EuroCity</b><ul style="margin:8px 0">' +
            '<li>🏙️ Capitali analizzate: <b>' + cityData.length + '</b></li>' +
            '<li>🏨 Strutture ricettive: <b>' + totH + '</b></li>' +
            '<li>📍 Attrazioni geolocalizzate: <b>' + totA + '</b></li>' +
            '<li>🏘️ Città con distretti: <b>' + wD + '/' + cityData.length + '</b></li>' +
            '</ul>';
    }
    return '❓ Nessuna città riconosciuta. Prova:<br>' +
        '<span style="color:#64748b;font-size:0.9em">' +
        '<em>"Qual è la città più sicura?"</em> · ' +
        '<em>"Top appeal"</em> · ' +
        '<em>"Hotel a Vienna"</em> · ' +
        '<em>"Confronta Roma e Parigi"</em>' +
        '</span>';
}

/* ---------- render: query su singola città ---------- */
function renderCityIntent(c, q) {
    if (/hotel|alloggio|dorm|dormire|sleep|ostello/.test(q)) {
        var li = c.hotels.map(function(h) {
            return '<li style="margin-bottom:4px"><b>' + h.n + '</b> <span style="color:#64748b;font-size:0.9em">(' + h.p + ')</span></li>';
        }).join('');
        return '<b>🏨 Strutture — ' + c.flag + ' ' + c.name_it + '</b><ul style="margin:8px 0">' + (li || '<li>Nessun dato</li>') + '</ul>';
    }
    if (/trasport|muoversi|aeroporto|arriv|come.arrivare/.test(q))
        return '<b>🚇 Mobilità — ' + c.flag + ' ' + c.name_it + '</b><p style="margin:6px 0;font-size:0.9em">' + c.transport + '</p>';

    if (/distrett|quartier|zona|neighborhood/.test(q)) {
        if (!c.districts.length)
            return '<b>' + c.flag + ' ' + c.name_it + '</b>: nessun distretto disponibile nel dataset.';
        var li = c.districts.map(function(d) {
            var desc = d.d ? ': <span style="color:#64748b;font-size:0.88em">' +
                             d.d.substring(0, 90) + (d.d.length > 90 ? '…' : '') + '</span>' : '';
            return '<li style="margin-bottom:5px"><b>' + d.n + '</b>' + desc + '</li>';
        }).join('');
        return '<b>🏘️ Distretti — ' + c.flag + ' ' + c.name_it + '</b><ul style="margin:8px 0">' + li + '</ul>';
    }
    if (/attrazione|visitare|vedere|turismo|cosa.fare|sight|museo|monumento/.test(q)) {
        var li = c.attractions.slice(0, 5).map(function(a) {
            return '<li style="margin-bottom:7px"><b>' + a.n + '</b><br>' +
                   '<span style="color:#64748b;font-size:0.87em">' + a.d + '</span> ' +
                   '<a href="https://www.google.com/maps?q=' + a.lat + ',' + a.lon +
                   '" target="_blank" style="font-size:0.75em;color:#3498db">📍 Maps</a></li>';
        }).join('');
        return '<b>🗺️ Attrazioni — ' + c.flag + ' ' + c.name_it + '</b>' +
               '<ul style="padding-left:0;list-style:none;margin:8px 0">' + li + '</ul>';
    }
    if (/sicur|safety|pericol|crime/.test(q)) {
        var pos = rankOf(c, 'safety');
        return '<b>🛡️ Sicurezza — ' + c.flag + ' ' + c.name_it + '</b><br>' +
               'Safety Index: ' + badge(c.safety, '#27AE60') + '<br>' +
               '<small style="color:#64748b">Posizione globale: #' + pos + ' di ' + cityData.length + '</small>';
    }
    if (/verde|green|ecolog|ambient|sostenib/.test(q)) {
        var pos = rankOf(c, 'green');
        return '<b>🌱 Sostenibilità — ' + c.flag + ' ' + c.name_it + '</b><br>' +
               'Green Score: ' + badge(c.green, '#27AE60') + '<br>' +
               '<small style="color:#64748b">Posizione globale: #' + pos + ' di ' + cityData.length + '</small>';
    }
    if (/cost|prezz|budget|econom|afford|cara|costosa/.test(q))
        return '<b>💰 Budget — ' + c.flag + ' ' + c.name_it + '</b><br>' +
               'Costo medio strutture: ' + badge(c.price + '€', '#E74C3C') + '<br>' +
               'Accessibilità economica: ' + badge(c.economy + '/100', '#3498db');

    if (/appeal|score|voto|ranking|classifica/.test(q)) {
        var pos = rankOf(c, 'appeal');
        return '<b>⭐ Appeal — ' + c.flag + ' ' + c.name_it + '</b><br>' +
               'Appeal Score: ' + badge(c.appeal, '#E74C3C') + '<br>' +
               '<small style="color:#64748b">Safety×0.4 + Green×0.4 + Accesso×0.2 · Posizione: #' + pos + ' di ' + cityData.length + '</small>';
    }
    if (/wiki|storia|descriz|info|racconta|chi.è|intro/.test(q)) {
        var intro = c.wiki_intro || c.story_it;
        return '<b>📖 ' + c.flag + ' ' + c.name_it + '</b>' +
               '<p style="margin:6px 0;font-size:0.9em;color:#334155">' + intro + '</p>';
    }
    /* fallback: riepilogo città */
    return '<b>' + c.flag + ' ' + c.name_it + '</b>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:8px 0;font-size:0.87em">' +
            '<span>⭐ Appeal: <b>' + c.appeal + '</b></span>' +
            '<span>🛡️ Safety: <b>' + c.safety + '</b></span>' +
            '<span>🌱 Green: <b>' + c.green + '</b></span>' +
            '<span>💰 Budget: <b>' + c.price + '€/notte</b></span>' +
        '</div>' +
        '<p style="color:#64748b;font-size:0.88em;margin:4px 0">' + c.story_it + '</p>' +
        '<small style="color:#94a3b8">Chiedi su: <em>hotel · trasporti · distretti · attrazioni · sicurezza · appeal</em></small>';
}

/* ---------- dispatcher principale ---------- */
function runQuery() {
    var input = document.getElementById('chat-input');
    var out   = document.getElementById('chat-output');
    var q = input.value.toLowerCase().trim();
    if (!q) return;

    var matches = cityData.filter(function(c) {
        return q.includes(c.name_it.toLowerCase()) || q.includes(c.name_en.toLowerCase());
    });

    var html;
    if (matches.length >= 2)       html = renderComparison(matches[0], matches[1]);
    else if (matches.length === 0)  html = renderGlobal(q);
    else                            html = renderCityIntent(matches[0], q);

    out.innerHTML = html;
    out.style.color = 'var(--slate-800)';
}

/* ---------- event listeners ---------- */
document.getElementById('chat-btn').onclick = runQuery;
document.getElementById('chat-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') runQuery();
});
document.querySelectorAll('.query-chip').forEach(function(chip) {
    chip.onclick = function() {
        document.getElementById('chat-input').value = chip.dataset.q;
        runQuery();
    };
});

/* ---------- contatore dinamico ---------- */
(function() {
    var totH = cityData.reduce(function(s,c){ return s + parseInt(c.hotel_count||0); }, 0);
    var totA = cityData.reduce(function(s,c){ return s + c.attractions.length; }, 0);
    var el = document.getElementById('chat-status');
    if (el) el.textContent = cityData.length + ' capitali · ' + totA + ' attrazioni · ' + totH + ' strutture';
})();
</script>
"""

# --- CONFIGURAZIONE ---
XML_DIR = str(ROOT / 'data' / 'xml_dataset')
OUTPUT_HTML = str(ROOT / 'index.html')
REPORT_HTML = str(ROOT / 'pages' / 'report.html')
MAP_FILE = str(ROOT / 'pages' / 'mappa_attrazioni.html')
DTD_FILE = str(ROOT / 'data' / 'city_report.dtd')

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

CITY_PALETTE = [
    '#E74C3C','#3498DB','#2ECC71','#F39C12','#9B59B6',
    '#1ABC9C','#E67E22','#34495E','#E91E63','#00BCD4',
    '#FF5722','#607D8B','#8BC34A','#FF9800','#673AB7',
    '#795548','#C0392B','#2980B9','#27AE60','#D35400',
    '#8E44AD','#16A085','#2C3E50','#F1C40F','#17A589',
    '#884EA0','#1A5276','#1E8449','#922B21','#1F618D',
]


def _map_js_block(city_data, div_id, city_link_prefix=''):
    """Restituisce il blocco <script> Leaflet per il div indicato.
    city_link_prefix: prefisso URL per i link alle pagine città."""
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
        map_data.append({
            'cl': cl, 'name': city['name_it'], 'flag': city['flag'],
            'appeal': city['appeal'], 'color': color,
            'link': city_link_prefix + cl + '.html',
            'capLat': coord[0], 'capLon': coord[1],
            'attrs': valid_attrs,
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
        "var cluster_VID=L.markerClusterGroup({chunkedLoading:true});\n"
        "var mapData_VID=DATA_JSON;\n"
        "mapData_VID.forEach(function(c){\n"
        "  c.attrs.forEach(function(a){\n"
        "    L.circleMarker([a.lat,a.lon],{radius:7,color:c.color,fillColor:c.color,fillOpacity:0.85,weight:2})\n"
        "    .addTo(cluster_VID)\n"
        "    .bindPopup('<div class=\"mp\"><h4 style=\"color:'+c.color+';margin:0 0 3px\">'+a.n+'</h4>'\n"
        "      +'<small style=\"color:#888\">'+c.flag+' '+c.name+'</small>'\n"
        "      +'<p style=\"margin:6px 0;font-size:.8rem\">'+a.d+'</p>'\n"
        "      +'<a href=\"'+c.link+'\" class=\"pl\">Scopri '+c.name+' \\u2192</a></div>')\n"
        "    .bindTooltip(a.n+' ('+c.name+')');\n"
        "  });\n"
        "  if(c.capLat!==null){\n"
        "    L.marker([c.capLat,c.capLon],{icon:L.divIcon({\n"
        "      className:'',\n"
        "      html:'<div class=\"cap-mk\" style=\"background:'+c.color+'\">'+'<span>'+c.flag+'</span><b>'+c.appeal+'</b></div>',\n"
        "      iconSize:[70,28],iconAnchor:[35,14]\n"
        "    })}).addTo(map_VID)\n"
        "    .bindPopup('<div class=\"mp\"><b>'+c.flag+' '+c.name+'</b>'\n"
        "      +'<br>Appeal: <b>'+c.appeal+'</b>'\n"
        "      +'<br><a href=\"'+c.link+'\" class=\"pl\">Scopri '+c.name+' \\u2192</a></div>');\n"
        "  }\n"
        "});\n"
        "map_VID.addLayer(cluster_VID);\n"
        "</script>"
    ).replace('VID', var_id).replace('DID', div_id).replace('DATA_JSON', map_data_json)

    return js


def generate_map(city_data):
    """Genera pages/mappa_attrazioni.html: Leaflet con marker colorati per città, capitali e popup."""
    map_js = _map_js_block(city_data, 'map', 'cities/')
    map_html = (
        "<!DOCTYPE html>\n<html lang='it'><head>\n"
        "<meta charset='UTF-8'>\n"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
        "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css'>\n"
        "<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css'>\n"
        "<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css'>\n"
        "<style>\n"
        "html,body,#map{height:100%;margin:0;font-family:Inter,sans-serif}\n"
        ".cap-mk{display:flex;align-items:center;gap:4px;padding:4px 9px;border-radius:20px;"
        "font-weight:800;font-size:.72rem;color:#fff;box-shadow:0 2px 8px rgba(0,0,0,.35);white-space:nowrap}\n"
        ".mp{min-width:190px;max-width:260px}\n"
        ".mp h4{font-size:.9rem;margin:0 0 2px}\n"
        ".pl{display:inline-block;margin-top:7px;color:#E74C3C;font-weight:700;font-size:.78rem;text-decoration:none}\n"
        ".pl:hover{text-decoration:underline}\n"
        "</style>\n"
        "</head><body>\n"
        "<div id='map'></div>\n"
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


def deploy():
    print("🚀 Generazione Dashboard: Reintegro Attrazioni + Griglia 3x2...")

    city_data = []
    cards_html = ""

    if not os.path.exists(XML_DIR): 
        print(f"Errore: Cartella {XML_DIR} non trovata.")
        return

    files = sorted([f for f in os.listdir(XML_DIR) if f.endswith('.xml')])
    for filename in files:
        try:
            city_lower = filename.replace('.xml', '')
            tree = etree.parse(os.path.join(XML_DIR, filename))
            root = tree.getroot()

            # 1. Estrazione dati strutturati
            city_obj = {
                'name_en': root.findtext(".//title"),
                'name_it': root.findtext(".//name_it") or root.findtext(".//title"),
                'flag': root.findtext(".//flag") or "🇪🇺",
                'appeal': root.get("appeal_score", "0"),
                'price': root.findtext(".//hotel_price", "0"),
                'safety': root.xpath("string(.//safety/@index_score)") or "0",
                'green': root.xpath("string(.//environment/@green_score)") or "0",
                'hotel_count': root.findtext(".//hotel_count", "0"),
                'economy': root.xpath("string(.//economic_accessibility/@score)") or "0",
                'transport': root.findtext("transport") or "Dati mobilità in aggiornamento.",
                'story_it': root.findtext("description") or "Analisi strategica non disponibile.",
                'wiki_intro': root.findtext("wiki_intro") or "",
                'hotels': [{'n': h.findtext("name"), 'p': h.findtext("price")} for h in root.xpath(".//hotel")],
                'attractions': [{'n': a.findtext("name"), 'd': a.findtext("description"), 'lat': a.get("lat"), 'lon': a.get("lon")} for a in root.xpath(".//attraction")],
                'districts': [
                    {'n': d.findtext('name', ''), 'd': d.findtext('description', '')}
                    for d in root.xpath(".//district")
                ],
                'landmark_image': root.findtext("landmark_image") or "",
                'city_lower': city_lower,
            }
            city_data.append(city_obj)

            # Card compatta per index: solo immagine + stats + CTA
            img_src = city_obj.get('landmark_image', '')
            n_attr = len(city_obj['attractions'])
            s_pct = _pct(city_obj['safety'])
            g_pct = _pct(city_obj['green'])
            p_pct = _pct(city_obj['price'], 2.5)   # max €250
            e_pct = _pct(city_obj['economy'])
            cards_html += f"""
            <article class="city-card" data-safety="{city_obj['safety']}" data-green="{city_obj['green']}" data-price="{city_obj['price']}" itemscope itemtype="https://schema.org/City">
                <div class="landmark-img-wrap">
                    <img src="{img_src}" alt="Landmark di {city_obj['name_it']}" class="landmark-img" loading="lazy">
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
                            <span class="stat-label">Budget/notte</span>
                            <span class="stat-val">{_price(city_obj['price'])}€</span>
                            <div class="score-bar-wrap"><div class="score-bar-fill amber" style="width:{p_pct}%"></div></div>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Sicurezza</span>
                            <span class="stat-val">{city_obj['safety']}</span>
                            <div class="score-bar-wrap"><div class="score-bar-fill green" style="width:{s_pct}%"></div></div>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Verde</span>
                            <span class="stat-val" style="color:var(--green-500)">{city_obj['green']}</span>
                            <div class="score-bar-wrap"><div class="score-bar-fill green" style="width:{g_pct}%"></div></div>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Strutture</span>
                            <span class="stat-val" style="color:var(--blue-500)">{city_obj['hotel_count']}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">P. acquisto</span>
                            <span class="stat-val">{city_obj['economy']}</span>
                            <div class="score-bar-wrap"><div class="score-bar-fill blue" style="width:{e_pct}%"></div></div>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Attrazioni</span>
                            <span class="stat-val">{n_attr}</span>
                        </div>
                    </div>
                    <a href="pages/cities/{city_lower}.html" class="card-cta">Scopri {city_obj['name_it']} →</a>
                </div>
            </article>"""
        except Exception as e:
            print(f"⚠️ Errore su {filename}: {e}")

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

/* filter buttons */
document.querySelectorAll('.filter-btn[data-filter]').forEach(function(btn) {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.filter-btn[data-filter]').forEach(function(b) { b.classList.remove('active'); });
        btn.classList.add('active');
        var f = btn.dataset.filter;
        document.querySelectorAll('#city-grid .city-card').forEach(function(card) {
            var s = parseFloat(card.dataset.safety || 0);
            var g = parseFloat(card.dataset.green  || 0);
            var p = parseFloat(card.dataset.price  || 999);
            var show = true;
            if (f === 'safety') show = s >= 70;
            if (f === 'green')  show = g >= 70;
            if (f === 'budget') show = p <= 120;
            card.style.display = show ? '' : 'none';
        });
    });
});

/* card entrance animation */
document.body.classList.add('js-loaded');
var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(e) {
        if (e.isIntersecting) { e.target.classList.add('visible'); observer.unobserve(e.target); }
    });
}, {rootMargin: '0px 0px -50px 0px'});
document.querySelectorAll('.city-card').forEach(function(c) { observer.observe(c); });
</script>"""

    # Template finale HTML
    full_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css">
    <title>EuroCity Strategic Intelligence</title>
</head>
<body>

<!-- ═══ TOPBAR STICKY ══════════════════════════════════════════════════ -->
<header class="topbar">
    <div class="topbar-inner">
        <span class="topbar-logo">EuroCity <b>SI</b></span>
        <nav class="topbar-nav">
            <a href="#" class="active">🏠 Home</a>
            <a href="pages/report.html">📊 Report</a>
            <a href="pages/mappa_attrazioni.html">🗺️ Mappa</a>
        </nav>
    </div>
</header>

<!-- ═══ HERO ════════════════════════════════════════════════════════════ -->
<section class="hero">
    <div class="hero-content">
        <h1 class="hero-title">30 capitali europee,<br>un'unica intelligence.</h1>
        <p class="hero-sub">
            EuroCity raccoglie, struttura e analizza dati su sicurezza, sostenibilità
            e accessibilità delle capitali UE — estratti algoritmicamente da Wikivoyage
            e arricchiti con indici internazionali. Ogni città ha la sua scheda XML,
            validata DTD, e una pagina navigabile con mappa interattiva.
        </p>
        <div class="hero-stats">
            <div class="hero-stat"><span class="hs-num">{len(city_data)}</span><span class="hs-lbl">capitali</span></div>
            <div class="hero-stat"><span class="hs-num">{n_attractions}</span><span class="hs-lbl">attrazioni</span></div>
            <div class="hero-stat"><span class="hs-num">{n_hotels}</span><span class="hs-lbl">strutture</span></div>
            <div class="hero-stat"><span class="hs-num">30</span><span class="hs-lbl">file XML</span></div>
        </div>
    </div>
</section>

<!-- ═══ VIRTUAL ANALYST (chat + RAG unificati) ══════════════════════ -->
<section class="analyst-panel">
    <div class="analyst-header">
        <div class="analyst-icon">🤖</div>
        <div>
            <p class="analyst-title">Virtual Analyst</p>
            <p class="analyst-sub">Sistema RAG · BM25 + FAISS · 320 chunk XML</p>
        </div>
    </div>
    <div class="analyst-input-row">
        <input type="text" id="chat-input" class="analyst-input"
               placeholder="Es: sicurezza a Vienna, hotel Amsterdam, trasporti Roma…">
        <button id="chat-btn" class="analyst-btn">Chiedi</button>
    </div>
    <div id="chat-output" class="analyst-output">
        Sistema pronto — digita una domanda o clicca un esempio.
    </div>
    <div class="analyst-chips">
        <button class="chip" data-q="trasporti Roma">🚇 trasporti Roma</button>
        <button class="chip" data-q="hotel Amsterdam">🏨 hotel Amsterdam</button>
        <button class="chip" data-q="cosa vedere a Parigi">🗺️ vedere Parigi</button>
        <button class="chip" data-q="sicurezza Berlino">🛡️ sicurezza Berlino</button>
        <button class="chip" data-q="quartieri di Praga">🏘️ quartieri Praga</button>
        <button class="chip" data-q="città più verde">🌱 città più verde</button>
        <button class="chip" data-q="confronta Roma e Parigi">⚖️ Roma vs Parigi</button>
    </div>
    <details class="analyst-details">
        <summary>Come funziona? — architettura RAG</summary>
        <p>
            Il Virtual Analyst è un sistema <b>RAG</b> (Retrieval-Augmented Generation)
            costruito sui <b>320 chunk testuali</b> estratti dai 30 file XML validati.
            Ogni query usa ricerca ibrida <b>BM25 + vettoriale</b> (FAISS + <code>all-MiniLM-L6-v2</code>)
            con <b>Reciprocal Rank Fusion</b>, rileva l'intento (hotel / trasporti / attrazioni / sicurezza)
            e risponde in tempo reale senza LLM esterno.
        </p>
        <p style="font-size:0.8rem; color:var(--slate-500); margin:8px 0 0;">
            ⚠️ Conosce solo le 30 capitali del dataset; alcune mancano di dati hotel perché
            assenti nelle sorgenti Wikivoyage.
        </p>
    </details>
</section>

<!-- ═══ MAPPA INLINE ════════════════════════════════════════════════════ -->
<div id="map-inline"></div>

<!-- ═══ FILTRI + GRIGLIA ════════════════════════════════════════════════ -->
<div class="filter-bar">
    <button class="filter-btn active" data-filter="all">🌍 Tutte le capitali</button>
    <button class="filter-btn" data-filter="safety">🛡️ Sicurezza ≥ 70</button>
    <button class="filter-btn" data-filter="green">🌱 Verde ≥ 70</button>
    <button class="filter-btn" data-filter="budget">💰 Budget ≤ 120€/notte</button>
</div>
<main class="container" id="city-grid">{cards_html}</main>

<button id="back-to-top" title="Torna in cima">↑</button>

<footer class="site-footer">
    Progetto TEAM — Laurea Magistrale in Governance e Politiche dell'Innovazione Digitale ·
    Università di Bologna A.A. 2024/2025
    <br>
    <a href="pages/report.html">📊 Report &amp; Documentazione</a>
</footer>

<script>
const cityData = {json.dumps(city_data)};

/* chat query — tenta il server RAG locale, poi fallback client-side */
const RAG_API = 'http://127.0.0.1:8000';

async function runQuery() {{
    const q = document.getElementById('chat-input').value.trim();
    const out = document.getElementById('chat-output');
    if (!q) return;
    out.innerHTML = '<span style="color:#64748b;font-size:.9rem">⏳ Cerco...</span>';
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
                html += '<details style="margin-top:8px"><summary style="cursor:pointer;color:#64748b;font-size:.82rem">📚 Fonti (' + data.sources.length + ')</summary>' +
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

function clientSideAnswer(q) {{
    const out = document.getElementById('chat-output');
    let res = "❓ Città non trovata. Prova: <em>sicurezza Vienna</em>, <em>hotel Roma</em>, <em>confronta Oslo e Berlino</em>.";
    cityData.forEach(function(c) {{
        if (q.includes(c.name_it.toLowerCase()) || q.includes((c.name_en || '').toLowerCase())) {{
            if (/hotel|alloggio|dorm|ostello/.test(q)) {{
                var li = c.hotels.map(h => '<li><b>' + h.n + '</b> <span style="color:#64748b">(' + h.p + ')</span></li>').join('');
                res = '<b>🏨 Strutture — ' + c.flag + ' ' + c.name_it + '</b><ul style="margin:6px 0;padding-left:18px">' + (li || '<li>Nessun dato nel dataset</li>') + '</ul>';
            }} else if (/trasport|muoversi|aeroporto|arriv/.test(q)) {{
                res = '<b>🚇 Mobilità — ' + c.flag + ' ' + c.name_it + '</b><p style="margin:6px 0">' + c.transport + '</p>';
            }} else if (/distrett|quartier|zona/.test(q)) {{
                var dn = c.districts.map(d => d.n).join(', ');
                res = '<b>🏘️ Distretti — ' + c.flag + ' ' + c.name_it + '</b><p style="margin:6px 0">' + (dn || 'Nessun distretto disponibile.') + '</p>';
            }} else if (/attrazione|visitare|vedere|turismo|museo/.test(q)) {{
                var al = c.attractions.slice(0,5).map(a => '<li><b>' + a.n + '</b> — <span style="color:#64748b;font-size:.88em">' + a.d + '</span></li>').join('');
                res = '<b>📍 Attrazioni — ' + c.flag + ' ' + c.name_it + '</b><ul style="margin:6px 0;padding-left:18px">' + al + '</ul>';
            }} else if (/sicur|safety|pericol/.test(q)) {{
                res = '<b>🛡️ ' + c.flag + ' ' + c.name_it + '</b> — Safety Index: <b>' + c.safety + '</b> · Appeal: <b>' + c.appeal + '</b><p style="color:#64748b;margin:4px 0;font-size:.9em">' + c.story_it + '</p>';
            }} else {{
                res = '<b>' + c.flag + ' ' + c.name_it + '</b><p style="margin:6px 0">' + c.story_it + '</p>';
            }}
        }}
    }});
    /* query globali senza nome città */
    if (res.startsWith('❓')) {{
        if (/sicur|safe/.test(q)) {{
            var top = cityData.slice().sort((a,b) => b.safety-a.safety).slice(0,5);
            res = '<b>🛡️ Top 5 Sicurezza</b><ol style="padding-left:18px;margin:6px 0">' + top.map(c => '<li>' + c.flag + ' ' + c.name_it + ' — ' + c.safety + '</li>').join('') + '</ol>';
        }} else if (/verde|green|ecolog/.test(q)) {{
            var top = cityData.slice().sort((a,b) => b.green-a.green).slice(0,5);
            res = '<b>🌱 Top 5 Verde</b><ol style="padding-left:18px;margin:6px 0">' + top.map(c => '<li>' + c.flag + ' ' + c.name_it + ' — ' + c.green + '</li>').join('') + '</ol>';
        }} else if (/econom|cheap|economica|basso/.test(q)) {{
            var top = cityData.slice().sort((a,b) => a.price-b.price).slice(0,5);
            res = '<b>💰 Top 5 Economiche</b><ol style="padding-left:18px;margin:6px 0">' + top.map(c => '<li>' + c.flag + ' ' + c.name_it + ' — ' + Math.round(c.price) + '€/notte</li>').join('') + '</ol>';
        }} else if (/appeal|miglior|top|ranking/.test(q)) {{
            var top = cityData.slice().sort((a,b) => b.appeal-a.appeal).slice(0,5);
            res = '<b>⭐ Top 5 Appeal</b><ol style="padding-left:18px;margin:6px 0">' + top.map(c => '<li>' + c.flag + ' ' + c.name_it + ' — ' + c.appeal + '</li>').join('') + '</ol>';
        }} else if (/confronta|vs/.test(q)) {{
            res = 'Per confrontare due città digita: <em>"confronta Roma e Parigi"</em> o <em>"Roma vs Berlino"</em>.';
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
</script>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.js"></script>
""" + inline_map_js + "\n" + js_block + "\n</body></html>"

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(full_html)
    print(f"✅ Dashboard generata correttamente con {len(city_data)} città.")

    generate_report(city_data)
    generate_city_pages(city_data)
    generate_map(city_data)


def generate_city_pages(city_data):
    """Generate one HTML file per city: {city_lower}.html with full content, microdata, XML download link."""
    print("📄 Generazione pagine individuali per città...")
    cities = sorted(city_data, key=lambda c: c['city_lower'])
    n = len(cities)

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

        # --- Landmark image ---
        lm_html = ""
        if city['landmark_image']:
            img_url = city['landmark_image']
            if not img_url.startswith('http'):
                img_url = '../../' + img_url.lstrip('/')
            lm_html = (
                f"<div style='border-radius:20px; overflow:hidden; height:280px; margin-bottom:30px;'>"
                f"<img itemprop='image' src='{img_url}' alt='Landmark di {city['name_it']}' "
                f"style='width:100%; height:100%; object-fit:cover;'></div>"
            )

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
                <span class='stat-val'>{city['price']}€</span>
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
                <span class='stat-label'>Strutture</span>
                <span class='stat-val' style='color:var(--blue-500)'>{city['hotel_count']}</span>
            </div>
            <div class='stat-item'>
                <span class='stat-label'>Accesso</span>
                <span class='stat-val'>{city['economy']}</span>
                <div class='score-bar-wrap'><div class='score-bar-fill blue' style='width:{_e}%'></div></div>
            </div>
        </div>"""

        # --- Hotels ---
        hotel_li = "".join([f"<li><b>{h['n']}</b> <small>({h['p']})</small></li>" for h in city['hotels']])
        hotel_html = (
            f"<div class='info-block hotel-block'><span class='block-title'>🏨 Dove Dormire</span>"
            f"<ul style='margin:0; padding-left:15px;'>{hotel_li}</ul></div>"
        ) if hotel_li else ""

        # --- Transport ---
        transport_html = (
            f"<div class='info-block transport-block'>"
            f"<span class='block-title'>🚇 Mobilità Urbana</span>"
            f"<p style='margin:0;'>{city['transport']}</p></div>"
        )

        # --- Districts ---
        dist_li = "".join([
            f"<li><b>{d['n']}</b>" + (f": {d['d'][:200]}..." if len(d['d']) > 200 else (f": {d['d']}" if d['d'] else "")) + "</li>"
            for d in city['districts']
        ])
        districts_html = (
            f"<div class='info-block district-block'><span class='block-title'>🏙️ Distretti</span>"
            f"<ul style='margin:0; padding-left:15px;'>{dist_li}</ul></div>"
        ) if dist_li else ""

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
            "<thead><tr><th>#</th><th>Attrazione</th><th>Descrizione</th><th></th></tr></thead>"
            f"<tbody>{attr_rows}</tbody>"
            "</table></div>"
        )

        page_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="../../style.css">
    <title>{city['name_it']} — EuroCity Strategic Intelligence</title>
</head>
<body>
<header class="topbar">
    <div class="topbar-inner">
        <a href="../../index.html" class="topbar-logo">EuroCity <b>SI</b></a>
        <nav class="topbar-nav">
            <a href="../../index.html">🏠 Home</a>
            <a href="../../pages/report.html">📊 Report</a>
            <a href="../../pages/mappa_attrazioni.html">🗺️ Mappa</a>
        </nav>
    </div>
</header>
<nav class="city-nav">
    <a href="{prev_city['city_lower']}.html">← {prev_city['flag']} {prev_city['name_it']}</a>
    <span class="city-nav-title">{city['flag']} {city['name_it']}</span>
    <a href="{next_city['city_lower']}.html">{next_city['flag']} {next_city['name_it']} →</a>
</nav>
<main class="city-detail" itemscope itemtype="https://schema.org/City">
    <meta itemprop="name" content="{city['name_it']}">
    <link itemprop="url" href="https://en.wikipedia.org/wiki/{city['name_en']}">
    {geo_html}
    {lm_html}
    <h1 class="city-title" style="margin-bottom:25px;">{city['flag']} {city['name_it']}</h1>
    {stats_html}
    {transport_html}
    {hotel_html}
    {districts_html}
    {desc_html}
    {attractions_html}
    <div class="download-block">
        <p style="color:var(--slate-500); font-size:0.85rem; margin-bottom:12px;">Sorgente dati strutturato (XML valido secondo <code>city_report.dtd</code>):</p>
        <a href="../../data/xml_dataset/{cl}.xml" download class="download-link">📥 Scarica file XML sorgente</a>
    </div>
</main>
<footer style="text-align:center; padding:40px; color:var(--slate-500); font-size:0.82rem;">
    Progetto TEAM — Laurea Magistrale in Governance e Politiche dell'Innovazione Digitale<br>
    Università di Bologna — A.A. 2024/2025
</footer>
<button id="back-to-top" title="Torna in cima">↑</button>
<script>
var btt = document.getElementById('back-to-top');
window.addEventListener('scroll', function() {{
    btt.classList.toggle('visible', window.scrollY > 400);
}});
btt.onclick = function() {{ window.scrollTo({{top: 0, behavior: 'smooth'}}); }};
</script>
</body>
</html>"""

        with open(ROOT / 'pages' / 'cities' / f"{cl}.html", 'w', encoding='utf-8') as f:
            f.write(page_html)

    print(f"✅ Generate {n} pagine HTML individuali.")


def generate_report(city_data):
    """Generate report.html: statistics extracted from XML files + pipeline documentation."""
    print("📊 Generazione report.html...")

    def fv(x):
        try: return float(x)
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
    avg_appeal = round(sum(fv(c['appeal'])  for c in city_data) / total_cities, 1)
    avg_safety = round(sum(fv(c['safety'])  for c in city_data) / total_cities, 1)
    avg_green  = round(sum(fv(c['green'])   for c in city_data) / total_cities, 1)

    def ranking_rows(cities, key, unit="", n=5):
        rows = ""
        for i, c in enumerate(cities[:n], 1):
            val = c[key]
            bar = round(fv(val) / 100 * 220)
            rows += (
                f"<tr>"
                f"<td style='color:var(--slate-500); width:28px'>{i}</td>"
                f"<td>{c['flag']} {c['name_it']}</td>"
                f"<td>"
                f"<div style='display:flex; align-items:center; gap:8px;'>"
                f"<div style='height:8px; width:{bar}px; background:var(--accent); border-radius:4px;'></div>"
                f"<b>{val}{unit}</b>"
                f"</div>"
                f"</td>"
                f"</tr>"
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
        stat_card("Capitali analizzate", total_cities)
        + stat_card("Strutture ricettive", total_hotels, "var(--blue-500)")
        + stat_card("Attrazioni catalogate", total_attractions, "var(--green-500)")
        + stat_card("Città con distretti", f"{cities_with_dist}/{total_cities}", "#8b5cf6")
        + stat_card("Appeal medio", avg_appeal, "var(--accent)")
        + stat_card("Safety medio", avg_safety, "var(--blue-500)")
        + stat_card("Green medio", avg_green, "var(--green-500)")
        + stat_card("File XML validati", total_cities, "#f59e0b")
    )

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="../style.css">
  <title>Report &amp; Documentazione — EuroCity</title>
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
    .report-nav a:hover {{ background: var(--accent); color: white; }}
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
    .rank-grid {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 24px;
      margin-bottom: 10px;
    }}
    .rank-block h3 {{ margin-top: 0; }}
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
      background: var(--slate-100); padding: 2px 6px; border-radius: 4px;
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
    .technique-card h4 {{
      margin: 0 0 8px; font-size: 0.9rem; color: var(--accent);
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
    @media (max-width: 768px) {{
      .rstat-grid {{ grid-template-columns: 1fr 1fr; }}
      .rank-grid, .technique-grid {{ grid-template-columns: 1fr; }}
      .report-section {{ padding: 24px 20px; }}
    }}
  </style>
</head>
<body>
<header class="topbar">
  <div class="topbar-inner">
    <a href="../index.html" class="topbar-logo">EuroCity <b>SI</b></a>
    <nav class="topbar-nav">
      <a href="../index.html">🏠 Home</a>
      <a href="report.html" class="active">📊 Report</a>
      <a href="mappa_attrazioni.html">🗺️ Mappa</a>
    </nav>
  </div>
</header>
<div style="background:linear-gradient(135deg,#0F172A 0%,#1a2e4a 60%,#1e3a58 100%);
            color:white; padding:40px 24px 50px; text-align:center; border-bottom:4px solid var(--accent);">
  <h1 style="font-size:clamp(1.5rem,3vw,2.4rem);font-weight:800;margin:0 0 8px;letter-spacing:-0.03em;">
    Report &amp; Documentazione</h1>
  <p style="opacity:0.7;font-size:1rem;margin:0;">
    Statistiche estratte algoritmicamente · Pipeline TEAM · UniBo A.A. 2024/2025</p>
</div>

<nav class="report-nav">
  <a href="#statistiche">📊 Statistiche</a>
  <a href="#ranking">🏆 Classifiche</a>
  <a href="#architettura">⚙️ Architettura</a>
  <a href="#dtd">📄 Schema DTD</a>
  <a href="#parsing">🔬 Tecniche di Parsing</a>
  <a href="#ai">🤖 Utilizzo AI</a>
  <a href="#team">👥 Team</a>
</nav>

<!-- ===== STATISTICHE ===== -->
<section class="report-section" id="statistiche">
  <h2>📊 Statistiche Comparative — Dati Estratti dai File XML</h2>
  <div class="rstat-grid">
    {summary_cards}
  </div>
  <p style="font-size:0.85rem; color:var(--slate-500); margin:0;">
    Tutti i valori sono calcolati a runtime leggendo i {total_cities} file XML nella cartella
    <code>xml_dataset/</code>. Formula <b>Appeal Score</b> = Safety×0.4 + Green×0.4 + (100−Costo)×0.2.
  </p>
</section>

<!-- ===== CLASSIFICHE ===== -->
<section class="report-section" id="ranking">
  <h2>🏆 Classifiche per Indicatore</h2>
  <div class="rank-grid">
    <div class="rank-block">
      <h3>Appeal Score (composito)</h3>
      <table class="rank-table"><tbody>{ranking_rows(by_appeal, 'appeal')}</tbody></table>
    </div>
    <div class="rank-block">
      <h3>Indice di Sicurezza</h3>
      <table class="rank-table"><tbody>{ranking_rows(by_safety, 'safety')}</tbody></table>
    </div>
    <div class="rank-block">
      <h3>Green Score (sostenibilità)</h3>
      <table class="rank-table"><tbody>{ranking_rows(by_green, 'green')}</tbody></table>
    </div>
    <div class="rank-block">
      <h3>Più Accessibili Economicamente</h3>
      <table class="rank-table"><tbody>{ranking_rows(by_cost, 'price', '€/notte')}</tbody></table>
    </div>
  </div>
</section>

<!-- ===== ARCHITETTURA ===== -->
<section class="report-section" id="architettura">
  <h2>⚙️ Architettura della Pipeline TEAM</h2>
  <p>
    Il progetto è composto da quattro componenti Python. La pipeline trasforma dump MediaWiki
    in file XML conformi al DTD, genera le pagine HTML navigabili e indicizza i contenuti
    in un sistema RAG per le query in linguaggio naturale.
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
          pulisce il Wikitext con regex, estrae distretti con descrizioni dalle sotto-pagine,
          valida il file XML risultante rispetto al DTD tramite <b>lxml.etree.DTD</b>
          e scrive i file in <code>data/xml_dataset/</code>.
        </p>
      </div>
    </div>
    <div class="pipeline-step">
      <div class="step-num">3</div>
      <div class="step-body">
        <h3 style="margin:0;"><code>deploy_dashboard.py</code> — Generazione HTML</h3>
        <p>
          Legge i 30 file XML validati e produce <code>index.html</code> (dashboard con griglia
          di card), le 30 pagine città e questo <code>report.html</code>. Le card includono
          <b>microdata Schema.org</b> (<code>itemscope itemtype="City"</code>). I dati vengono
          anche serializzati come JSON inline per il Virtual Analyst client-side.
        </p>
      </div>
    </div>
    <div class="pipeline-step">
      <div class="step-num">4</div>
      <div class="step-body">
        <h3 style="margin:0;"><code>rag/</code> — Sistema RAG per query in linguaggio naturale</h3>
        <p>
          Modulo indipendente composto da tre file: <code>ingest.py</code> legge i 30 XML e
          costruisce <b>320 chunk testuali</b> tematici (trasporti, hotel, distretti, attrazioni,
          descrizione strategica, panoramica wiki) prefissati con il nome della città.
          <code>vectorstore.py</code> indicizza i chunk in un indice <b>FAISS IndexFlatIP</b>
          (384 dimensioni, <code>all-MiniLM-L6-v2</code>) e mantiene un indice <b>BM25Okapi</b>
          parallelo; la ricerca ibrida applica <b>Reciprocal Rank Fusion</b> (α=0.5).
          <code>api.py</code> (FastAPI su <code>127.0.0.1:8000</code>) riceve la query,
          rileva l'intento (transport / hotel / attractions / safety / general), boosta i chunk
          della sezione corrispondente e sintetizza la risposta estraendo le frasi più rilevanti
          — senza LLM esterno.
        </p>
        <p style="font-size:0.82rem;color:var(--slate-500);margin:8px 0 0;">
          <b>Limiti noti:</b> alcune città (Londra, Budapest, Parigi…) mancano di dati hotel
          nelle sorgenti Wikivoyage originali; l'estrazione di frasi è euristica e non
          garantisce coerenza sintattica sulle risposte lunghe.
        </p>
      </div>
    </div>
  </div>
</section>

<!-- ===== SCHEMA DTD ===== -->
<section class="report-section" id="dtd">
  <h2>📄 Schema DTD — Struttura dei Documenti XML</h2>
  <p>
    Ogni file in <code>xml_dataset/</code> è validato rispetto a <code>city_report.dtd</code>
    prima della scrittura. La validazione è eseguita a runtime con <code>lxml.etree.DTD</code>.
    I file non validi vengono segnalati ma non scritti.
  </p>
  <h3>Struttura ad albero</h3>
  <pre>city_report [@appeal_score]
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
      <h4>Parsing MediaWiki XML con lxml</h4>
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
      <h4>Selezione della Pagina Principale</h4>
      <p>
        L'algoritmo cerca nell'ordine: (1) pagina con titolo esatto uguale al nome della
        città; (2) prima pagina con titolo <code>Città/XYZ</code>; (3) prima pagina che
        contiene il nome della città. La comparazione è <b>accent-insensitive</b>
        tramite <code>unicodedata.normalize('NFKD')</code>, necessario per Reykjavík.
      </p>
    </div>
    <div class="technique-card">
      <h4>Pulizia del Wikitext</h4>
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
      <h4>Estrazione dei Distretti</h4>
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
      <h4>Validazione DTD con lxml</h4>
      <p>
        Prima di ogni scrittura, l'albero XML viene validato con
        <code>lxml.etree.DTD(open('city_report.dtd', 'rb')).validate(root)</code>.
        Tutti i {total_cities} file superano la validazione. Gli elementi opzionali
        (<code>districts?</code>, <code>wiki_intro?</code>, <code>landmark_image?</code>)
        non vengono creati se i dati corrispondenti sono assenti.
      </p>
    </div>
    <div class="technique-card">
      <h4>Microdata Schema.org nell'HTML</h4>
      <p>
        Ogni card nella dashboard è annotata con
        <code>itemscope itemtype="https://schema.org/City"</code>
        e <code>itemprop="name"</code> sul nome della città.
        Le annotazioni microdata sono generate direttamente dallo script
        <code>deploy_dashboard.py</code>, come richiesto dalle linee guida del progetto.
      </p>
    </div>
    <div class="technique-card">
      <h4>Gestione delle Eccezioni</h4>
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
      <h4>Coordinate Geografiche e Mappa</h4>
      <p>
        Le attrazioni hanno attributi <code>@lat</code> e <code>@lon</code> estratti
        dal CSV <code>attrazione_descrizione_fixed.csv</code>. La dashboard genera link
        diretti a Google Maps (<code>?q=lat,lon</code>) e la mappa interattiva
        <code>mappa_attrazioni.html</code> visualizza tutti i punti su Leaflet.js.
      </p>
    </div>
  </div>
</section>

<!-- ===== AI ===== -->
<section class="report-section" id="ai">
  <h2>🤖 Dichiarazione Utilizzo Strumenti AI</h2>
  <p>
    Come previsto dalle linee guida del progetto TEAM, l'utilizzo di strumenti AI è
    dichiarato e documentato di seguito.
  </p>

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

  <p style="margin-top:20px;">
    I file XML sorgente provengono da <b>Wikivoyage</b> (licenza CC-BY-SA), scaricati
    tramite le API MediaWiki. Le immagini landmark provengono da <b>Wikimedia Commons</b>
    (licenza libera) tramite Wikipedia pageimages API.
  </p>
  <p style="background:#FEF3C7;border-left:4px solid #F59E0B;padding:12px 16px;border-radius:8px;font-size:0.85rem;margin-top:12px">
    ⚠️ <b>Avvertenza accademica:</b> i valori numerici in <code>city_indices.json</code>
    sono stime rielaborate con AI a partire da fonti pubbliche. Non sostituiscono
    la consultazione diretta dei dataset originali Numbeo o EEA per usi di ricerca.
  </p>
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

<footer style="text-align:center; padding:40px; color:var(--slate-500); font-size:0.82rem;">
  Progetto TEAM — Laurea Magistrale in Governance e Politiche dell'Innovazione Digitale<br>
  Università di Bologna — A.A. 2024/2025
</footer>
<button id="back-to-top" title="Torna in cima">↑</button>
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