import os, json, re
from lxml import etree

# --- CONFIGURAZIONE ---
XML_DIR = 'xml_dataset'
OUTPUT_HTML = 'index.html'
REPORT_HTML = 'report.html'
MAP_FILE = 'mappa_attrazioni.html'
DTD_FILE = 'city_report.dtd'

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
                'attractions': [{'n': a.findtext("name"), 'd': a.findtext("description"), 'lat': a.get("lat"), 'lon': a.get("lon")} for a in root.xpath(".//attraction")],
                'districts': [
                    {'n': d.findtext('name', ''), 'd': d.findtext('description', '')}
                    for d in root.xpath(".//district")
                ],
                'landmark_image': root.findtext("landmark_image") or "",
            }
            city_data.append(city_obj)

            # 2. Costruzione HTML Hotel (Top 3)
            hotel_li = "".join([f"<li><b>{h['n']}</b> <small>({h['p']})</small></li>" for h in city_obj['hotels'][:3]])
            hotel_html = f"<div class='info-block hotel-block'><span class='block-title'>🏨 Dove Dormire</span><ul style='margin:0; padding-left:15px;'>{hotel_li}</ul></div>" if hotel_li else ""

            # 3. Costruzione HTML Distretti
            if city_obj['districts']:
                district_li = "".join([
                    f"<li><b>{d['n']}</b>" + (f": {d['d']}" if d['d'] else "") + "</li>"
                    for d in city_obj['districts']
                ])
                districts_html = (
                    f"<div class='info-block district-block'>"
                    f"<span class='block-title'>🏙️ Distretti</span>"
                    f"<ul style='margin:0; padding-left:15px;'>{district_li}</ul></div>"
                )
            else:
                districts_html = ""

            # 3b. Landmark image
            landmark_html = ""
            if city_obj.get('landmark_image'):
                img_src = city_obj['landmark_image']
                img_alt = city_obj['name_it']
                landmark_html = (
                    f"<div class='landmark-img-wrap'>"
                    f"<img src='{img_src}' alt='Landmark di {img_alt}' "
                    f"class='landmark-img' loading='lazy'>"
                    f"</div>"
                )

            # 4. Costruzione HTML Attrazioni (Novità Reintegrata)
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
            <article class="city-card" itemscope itemtype="https://schema.org/City">
                {landmark_html}
                <h2 class="city-title"><span>{city_obj['flag']}</span> <span itemprop="name">{city_obj['name_it']}</span></h2>
                
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

                {districts_html}

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
            <nav style="margin-top:18px;">
                <a href="report.html" style="color:#fff; background:var(--accent); padding:8px 22px; border-radius:8px; font-weight:700; text-decoration:none; font-size:0.9rem;">📊 Report &amp; Documentazione</a>
            </nav>
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
                    }} else if (q.includes("distrett") || q.includes("quartier")) {{
                        const dn = c.districts.map(d => d.n).join(", ");
                        res = `<b>${{c.name_it}}</b> (Distretti): ${{dn || "Nessun distretto estratto."}}`;
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

    generate_report(city_data)


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
  <link rel="stylesheet" href="style.css">
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
<header>
  <h1>EuroCity — Report &amp; Documentazione</h1>
  <div class="desc-portale">
    <p>Statistiche estratte algoritmicamente dai file XML. Documentazione della pipeline TEAM.</p>
    <nav style="margin-top:18px;">
      <a href="index.html" style="color:#fff; background:rgba(255,255,255,0.15); padding:8px 22px; border-radius:8px; font-weight:700; text-decoration:none; font-size:0.9rem; border:1px solid rgba(255,255,255,0.3);">← Torna alla Dashboard</a>
    </nav>
  </div>
</header>

<nav class="report-nav">
  <a href="#statistiche">📊 Statistiche</a>
  <a href="#ranking">🏆 Classifiche</a>
  <a href="#architettura">⚙️ Architettura</a>
  <a href="#dtd">📄 Schema DTD</a>
  <a href="#parsing">🔬 Tecniche di Parsing</a>
  <a href="#ai">🤖 Utilizzo AI</a>
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
    Il progetto è composto da tre script Python eseguiti in sequenza. La pipeline trasforma
    dump MediaWiki (formato XML Wikivoyage) in file XML conformi al DTD, e da questi genera
    pagine HTML navigabili.
  </p>
  <div class="pipeline-steps">
    <div class="pipeline-step">
      <div class="step-num">1</div>
      <div class="step-body">
        <h3 style="margin:0;"><code>extract_wiki_info.py</code> — Fase di Preparazione</h3>
        <p>
          Scarica e analizza i dump Wikivoyage in <code>original_source/</code>. Utilizza
          <b>mwparserfromhell</b> e <b>spaCy</b> per l'estrazione di testo strutturato.
          Produce <code>wiki_text_pulito.csv</code> (trasporti, hotel, distretti) e
          <code>attrazione_descrizione_fixed.csv</code> (attrazioni con coordinate geografiche).
          I dati di sicurezza, costo della vita e green score provengono da
          <code>city_indices.json</code>.
        </p>
      </div>
    </div>
    <div class="pipeline-step">
      <div class="step-num">2</div>
      <div class="step-body">
        <h3 style="margin:0;"><code>final_processor.py</code> — Elaborazione Principale</h3>
        <p>
          Script centrale del progetto. Per ogni capitale: individua la pagina principale nel dump
          Wikivoyage (gestendo assenza della pagina principale e varianti accentate come
          <i>Reykjavík</i>), pulisce il testo Wikitext con regex, estrae i distretti dal CSV
          con descrizioni dalle sotto-pagine, valida il file XML risultante rispetto al DTD tramite
          <b>lxml.etree.DTD</b>, e scrive in <code>xml_dataset/</code>.
        </p>
      </div>
    </div>
    <div class="pipeline-step">
      <div class="step-num">3</div>
      <div class="step-body">
        <h3 style="margin:0;"><code>deploy_dashboard.py</code> — Generazione Output HTML</h3>
        <p>
          Legge i 30 file XML validati e produce <code>index.html</code> (dashboard navigabile
          con griglia di card) e questo file <code>report.html</code>. Le card includono
          <b>microdata Schema.org</b> (<code>itemscope itemtype="City"</code>) per la
          leggibilità da parte dei motori di ricerca. I dati delle città vengono anche serializzati
          come JSON inline per il <i>Virtual Analyst</i> interattivo.
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
    (mostrate come <i>Strategic Summary</i> nelle card) sono state generate con Claude
    (Anthropic) tramite prompt strutturati del tipo:
  </p>
  <pre style="font-size:0.8rem;">Genera una descrizione strategica in italiano (max 2 frasi) di [CITTÀ]
come capitale europea, focalizzandoti su: innovazione urbana, sostenibilità,
sicurezza, accessibilità economica. Tono: analitico, da report istituzionale.</pre>
  <p style="margin-top:16px;">
    I file XML sorgente in <code>original_source/</code> provengono da
    <b>Wikivoyage</b> (licenza CC-BY-SA), scaricati tramite le API MediaWiki.
    I dati di sicurezza e costo della vita provengono da dataset pubblici
    (Numbeo, EIU) aggregati in <code>city_indices.json</code>.
    Le immagini landmark provengono da <b>Wikimedia Commons</b> (licenza libera)
    tramite URL <code>Special:FilePath</code>.
  </p>
</section>

<footer style="text-align:center; padding:40px; color:var(--slate-500); font-size:0.82rem;">
  Progetto TEAM — Laurea Magistrale in Governance e Politiche dell'Innovazione Digitale<br>
  Università di Bologna — A.A. 2024/2025
</footer>
</body>
</html>"""

    with open(REPORT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ report.html generato correttamente.")


if __name__ == "__main__":
    deploy()