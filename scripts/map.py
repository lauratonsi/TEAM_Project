import pandas as pd
import folium
from folium.plugins import MarkerCluster
import os
from pathlib import Path
import webbrowser

ROOT = Path(__file__).resolve().parent.parent

csv_path = str(ROOT / 'data' / 'attrazione_descrizione_fixed.csv')
output_map_path = str(ROOT / 'pages' / 'mappa_attrazioni.html')

if os.path.exists(csv_path):
    print(f"📖 Caricamento dati da {csv_path}...")
    
    # Leggiamo il CSV (quoting=0 per gestire correttamente i testi con virgolette)
    df_map = pd.read_csv(csv_path, quoting=0)

    # Configurazione mappa: OpenStreetMap centrata sull'Europa
    m = folium.Map(location=[48.8566, 2.3522], zoom_start=4, tiles="OpenStreetMap")
    marker_cluster = MarkerCluster().add_to(m)

    # Pulizia: Rimuoviamo righe con coordinate mancanti
    df_map_clean = df_map.dropna(subset=['Latitude', 'Longitude'])

    for _, row in df_map_clean.iterrows():
        name = str(row['Attraction'])
        city = str(row['City'])
        description = str(row['Description'])
        
        # Tronca la descrizione se troppo lunga per il popup
        short_desc = (description[:200] + '...') if len(description) > 200 else description

        # HTML per il popup con stile minimale
        html_popup = f"""
        <div style='font-family: sans-serif; min-width: 200px;'>
            <h4 style='color: #E74C3C; margin-bottom: 5px;'>{name}</h4>
            <small style='color: #7F8C8D;'>Città: {city}</small>
            <hr style='margin: 10px 0; border: 0; border-top: 1px solid #eee;'>
            <p style='font-size: 12px; color: #333;'>{short_desc}</p>
        </div>
        """

        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=folium.Popup(html_popup, max_width=300),
            tooltip=f"{name} ({city})",
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(marker_cluster)

    # 1. Salvataggio standard della mappa
    m.save(output_map_path)

    # 2. Patch per il Referrer (Sblocca caricamento tiles su alcuni browser)
    with open(output_map_path, 'r', encoding='utf-8') as f:
        content = f.read()

    unlock_meta = '<meta name="referrer" content="no-referrer">'
    
    if '<head>' in content:
        new_content = content.replace('<head>', f'<head>\n    {unlock_meta}')
    else:
        new_content = content.replace('<html>', f'<html>\n<head>\n    {unlock_meta}\n</head>')

    with open(output_map_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"✅ Mappa generata con successo: {output_map_path}")
    print(f"📍 Punti caricati: {len(df_map_clean)}")

    # 3. Apertura automatica del file nel browser predefinito
    webbrowser.open('file://' + os.path.realpath(output_map_path))

else:
    print(f"❌ Errore: Il file '{csv_path}' non è presente nella cartella corrente.")
    print("Suggerimento: Sposta il file CSV nella cartella ELABORAZIONE.")