import os, json, re
from lxml import etree

# --- CONFIGURAZIONE ---
XML_DIR = 'xml_dataset'
OUTPUT_HTML = 'index.html'
MAP_FILE = 'mappa_attrazioni.html'

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
                'attractions': [{'n': a.findtext("name"), 'd': a.findtext("description"), 'lat': a.get("lat"), 'lon': a.get("lon")} for a in root.xpath(".//attraction")]
            }
            city_data.append(city_obj)

            # 2. Costruzione HTML Hotel (Top 3)
            hotel_li = "".join([f"<li><b>{h['n']}</b> <small>({h['p']})</small></li>" for h in city_obj['hotels'][:3]])
            hotel_html = f"<div class='info-block hotel-block'><span class='block-title'>🏨 Dove Dormire</span><ul style='margin:0; padding-left:15px;'>{hotel_li}</ul></div>" if hotel_li else ""

            # 3. Costruzione HTML Attrazioni (Novità Reintegrata)
            attr_li = ""
            for a in city_obj['attractions']:
                attr_li += f"""
                <li class="attr-item">
                    <span class="attr-name">{a['n']}</span>
                    <p class="attr-desc">{a['d']}</p>
                    <a href="https://www.google.com/maps?q={a['lat']},{a['lon']}" target="_blank" class="maps-link">📍 MAPS</a>
                </li>"""
            
            attractions_html = f"""
            <div class="attractions">
                <span class="block-title">Strategic Sights & Coordinates</span>
                <ul style="padding:0; margin:0;">{attr_li}</ul>
            </div>"""

            # 4. Iniezione nel template della Card
            cards_html += f"""
            <article class="city-card">
                <h2 class="city-title"><span>{city_obj['flag']}</span> {city_obj['name_it']}</h2>
                
                <div class="stats-box">
                    <div class="stat-item"><span class="stat-label">Appeal</span><span class="stat-val" style="color:var(--accent)">{city_obj['appeal']}</span></div>
                    <div class="stat-item"><span class="stat-label">Budget</span><span class="stat-val">{city_obj['price']}€</span></div>
                    <div class="stat-item"><span class="stat-label">Safety</span><span class="stat-val">{city_obj['safety']}</span></div>
                    <div class="stat-item"><span class="stat-label">Green</span><span class="stat-val" style="color:var(--green-500)">{city_obj['green']}</span></div>
                    <div class="stat-item"><span class="stat-label">Strutture</span><span class="stat-val" style="color:var(--blue-500)">{city_obj['hotel_count']}</span></div>
                    <div class="stat-item"><span class="stat-label">Accesso</span><span class="stat-val">{city_obj['economy']}</span></div>
                </div>
                
                <div class="info-block transport-block">
                    <span class="block-title">🚇 Mobilità Urbana</span>
                    <p style="margin:0;">{city_obj['transport']}</p>
                </div>

                {hotel_html}

                <div class="city-desc">
                    <div class="desc-section" style="border-left: 3px solid var(--blue-500); padding-left: 15px; background: #f0f9ff;">
                        <span class="source-tag">🎯 Strategic Summary</span>
                        <p style="font-weight:600; margin:0;">{city_obj['story_it']}</p>
                    </div>
                    {'<div class="desc-section"><span class="source-tag">📂 Wiki Archive</span><p style="font-size:0.85rem; margin:0;">' + city_obj['wiki_intro'] + '</p></div>' if city_obj['wiki_intro'] else ''}
                </div>

                {attractions_html}
            </article>"""
        except Exception as e:
            print(f"⚠️ Errore su {filename}: {e}")

    # Template finale HTML
    full_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8"><link rel="stylesheet" href="style.css">
    <title>EuroCity Strategic Intelligence</title>
</head>
<body>
    <header>
        <h1>EuroCity Strategic Intelligence</h1>
        <div class="desc-portale">
            <p>Analisi comparativa delle capitali europee basata su dati estratti algoritmicamente da MediaWiki. <b>Appeal Score:</b> Sicurezza (40%), Ambiente (40%), Accesso (20%).</p>
        </div>
    </header>
    <section class="chat-section">
        <strong style="display:block; margin-bottom:10px; color:var(--accent)">🤖 Virtual Analyst</strong>
        <div style="display:flex; gap:10px;">
            <input type="text" id="chat-input" style="flex:1; padding:12px; border:1px solid #ddd; border-radius:8px;" placeholder="Chiedi dettagli su una città...">
            <button id="chat-btn" style="background:var(--accent); color:white; border:none; padding:10px 25px; border-radius:8px; font-weight:800; cursor:pointer;">ASK</button>
        </div>
        <div id="chat-output" style="margin-top:15px; padding:10px; font-size:0.9rem; color:var(--slate-500); border-left:3px solid var(--accent)">Sistema pronto. Caricamento dati V16 completato.</div>
    </section>
    <iframe id="map-frame" src="{MAP_FILE}"></iframe>
    <main class="container">{cards_html}</main>
    <script>
        const cityData = {json.dumps(city_data)};
        document.getElementById('chat-btn').onclick = function() {{
            const q = document.getElementById('chat-input').value.toLowerCase();
            const out = document.getElementById('chat-output');
            let res = "Città non trovata nel database.";
            
            cityData.forEach(c => {{
                if (q.includes(c.name_it.toLowerCase()) || q.includes(c.name_en.toLowerCase())) {{
                    if (q.includes("hotel") || q.includes("quanti")) {{
                        res = `<b>${{c.name_it}}</b>: Abbiamo analizzato ${{c.hotel_count}} strutture. Le principali selection includono: ${{c.hotels.map(h => h.n).join(", ")}}.`;
                    }} else if (q.includes("trasport") || q.includes("muoversi")) {{
                        res = `<b>${{c.name_it}}</b> (Mobilità): ${{c.transport}}`;
                    }} else {{
                        res = `<b>${{c.name_it}}</b>: ${{c.story_it}}`;
                    }}
                }}
            }});
            out.innerHTML = res;
        }};
    </script>
</body></html>"""

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(full_html)
    print(f"✅ Dashboard generata correttamente con {len(city_data)} città.")

if __name__ == "__main__":
    deploy()