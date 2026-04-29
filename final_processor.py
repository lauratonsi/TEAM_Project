import os
import json
import re
import pandas as pd
from lxml import etree

# --- CONFIGURAZIONE ---
ORIGINAL_XML_DIR = 'original_source'
INPUT_JSON_INDICES = 'city_indices.json'
INPUT_CSV_WIKI = 'wiki_text_pulito.csv'
INPUT_CSV_ATTR = 'attrazione_descrizione_fixed.csv'
INPUT_JSON_DESC = 'city_descriptions.json'
DTD_FILE = 'city_report.dtd'
OUTPUT_DIR = 'xml_dataset'

CITY_MAP = {
    "London": {"it": "Londra", "flag": "🇬🇧"}, "Prague": {"it": "Praga", "flag": "🇨🇿"},
    "Copenhagen": {"it": "Copenaghen", "flag": "🇩🇰"}, "Warsaw": {"it": "Varsavia", "flag": "🇵🇱"},
    "Bucharest": {"it": "Bucarest", "flag": "🇷🇴"}, "Stockholm": {"it": "Stoccolma", "flag": "🇸🇪"},
    "Athens": {"it": "Atene", "flag": "🇬🇷"}, "Berlin": {"it": "Berlino", "flag": "🇩🇪"},
    "Brussels": {"it": "Bruxelles", "flag": "🇧🇪"}, "Dublin": {"it": "Dublino", "flag": "🇮🇪"},
    "Lisbon": {"it": "Lisbona", "flag": "🇵🇹"}, "Ljubljana": {"it": "Lubiana", "flag": "🇸🇮"},
    "Luxembourg": {"it": "Lussemburgo", "flag": "🇱🇺"}, "Paris": {"it": "Parigi", "flag": "🇫🇷"},
    "Rome": {"it": "Roma", "flag": "🇮🇹"}, "Valletta": {"it": "La Valletta", "flag": "🇲🇹"},
    "Zagreb": {"it": "Zagabria", "flag": "🇭🇷"}, "Amsterdam": {"it": "Amsterdam", "flag": "🇳🇱"},
    "Vienna": {"it": "Vienna", "flag": "🇦🇹"}, "Madrid": {"it": "Madrid", "flag": "🇪🇸"},
    "Helsinki": {"it": "Helsinki", "flag": "🇫🇮"}, "Oslo": {"it": "Oslo", "flag": "🇳🇴"},
    "Bratislava": {"it": "Bratislava", "flag": "🇸🇰"}, "Budapest": {"it": "Budapest", "flag": "🇭🇺"},
    "Reykjavik": {"it": "Reykjavík", "flag": "🇮🇸"}, "Sofia": {"it": "Sofia", "flag": "🇧🇬"},
    "Tallinn": {"it": "Tallinn", "flag": "🇪🇪"}, "Riga": {"it": "Riga", "flag": "🇱🇻"},
    "Vilnius": {"it": "Vilnius", "flag": "🇱🇹"}, "Nicosia": {"it": "Nicosia", "flag": "🇨🇾"},
    "Bern": {"it": "Berna", "flag": "🇨🇭"}
}

def clean_xml_text(text):
    if not text or str(text).lower() == 'nan': return ""
    return str(text).strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def parse_hotels(hotel_str):
    hotels = []
    if not hotel_str or str(hotel_str).lower() == 'nan': return hotels
    parts = hotel_str.split('|')
    for p in parts:
        # Cerca il pattern "Nome (Prezzo)"
        match = re.search(r'^(.*?)\s*\((.*?)\)$', p.strip())
        if match:
            hotels.append({'n': match.group(1).strip(), 'p': match.group(2).strip()})
        else:
            hotels.append({'n': p.strip(), 'p': 'Prezzo N/D'})
    return hotels

def run_pipeline():
    print("🚀 Iniezione dati totali negli XML...")
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    
    try:
        dtd = etree.DTD(open(DTD_FILE, 'rb'))
        df_wiki = pd.read_csv(INPUT_CSV_WIKI).set_index('City')
        df_attr = pd.read_csv(INPUT_CSV_ATTR)
        with open(INPUT_JSON_INDICES, 'r', encoding='utf-8') as f:
            indices = {c['city'].upper(): c for c in json.load(f)['capitali']}
        with open(INPUT_JSON_DESC, 'r', encoding='utf-8') as f:
            narratives = json.load(f)
    except Exception as e:
        print(f"❌ Errore fatale: {e}")
        return

    for city_name_upper, wiki_row in df_wiki.iterrows():
        city_idx = indices.get(city_name_upper)
        if not city_idx: continue
        
        name = city_idx['city']
        # Calcolo appeal basato sui tuoi indici
        score = round((city_idx['safety']*0.4 + city_idx['green_score']*0.4 + (100-city_idx['cost_of_living'])*0.2), 1)
        
        root = etree.Element("city_report", appeal_score=str(score))
        
        meta = etree.SubElement(root, "metadata")
        etree.SubElement(meta, "title").text = name
        etree.SubElement(meta, "name_it").text = CITY_MAP.get(name, {}).get("it", name)
        etree.SubElement(meta, "flag").text = CITY_MAP.get(name, {}).get("flag", "🇪🇺")

        ind = etree.SubElement(root, "indicators")
        etree.SubElement(ind, "hotel_count").text = str(wiki_row['Hotel_Count'])
        etree.SubElement(ind, "hotel_price").text = str(round(city_idx['cost_of_living'] * 1.85, 2))
        etree.SubElement(ind, "safety", index_score=str(city_idx['safety']))
        etree.SubElement(ind, "environment", green_score=str(city_idx['green_score']))
        etree.SubElement(ind, "cost_index", value=str(city_idx['cost_of_living']))
        etree.SubElement(ind, "economic_accessibility", score=str(round(100 - city_idx['cost_of_living'], 1)))

        etree.SubElement(root, "transport").text = clean_xml_text(wiki_row['Transport_Text'])

        acc_node = etree.SubElement(root, "accommodation")
        for h in parse_hotels(str(wiki_row['Hotels_Extracted'])):
            h_node = etree.SubElement(acc_node, "hotel")
            etree.SubElement(h_node, "name").text = clean_xml_text(h['n'])
            etree.SubElement(h_node, "price").text = clean_xml_text(h['p'])

        high = etree.SubElement(root, "highlights")
        for _, row in df_attr[df_attr['City'] == name].head(10).iterrows():
            attr = etree.SubElement(high, "attraction", lat=str(row['Latitude']), lon=str(row['Longitude']))
            etree.SubElement(attr, "name").text = clean_xml_text(row['Attraction'])
            etree.SubElement(attr, "description").text = clean_xml_text(row['Description'])

        etree.SubElement(root, "description").text = clean_xml_text(narratives.get(name, f"Analisi di {name}"))

        # Recupero Wiki Intro per completezza
        orig_file = os.path.join(ORIGINAL_XML_DIR, f"{name}.xml")
        wiki_intro_text = "Intro non disponibile."
        if os.path.exists(orig_file):
            tree_orig = etree.parse(orig_file)
            full_text = tree_orig.xpath("string(//*[local-name()='text'])")
            wiki_intro_text = re.sub(r'\{\{.*?\}\}|\[\[|\]\]', '', full_text)[:400] + "..."
        etree.SubElement(root, "wiki_intro").text = clean_xml_text(wiki_intro_text)

        if dtd.validate(root):
            tree = etree.ElementTree(root)
            tree.write(os.path.join(OUTPUT_DIR, f"{name.lower()}.xml"), 
                       xml_declaration=True, encoding='UTF-8', pretty_print=True,
                       doctype=f'<!DOCTYPE city_report SYSTEM "{DTD_FILE}">')
            print(f"✅ {name} generato correttamente.")
        else:
            print(f"⚠️ Errore DTD su {name}: {dtd.error_log.filter_from_errors()}")

if __name__ == "__main__": run_pipeline()