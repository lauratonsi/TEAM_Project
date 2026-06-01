import os
import json
import re
from pathlib import Path
import pandas as pd
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent

# --- CONFIGURAZIONE ---
ORIGINAL_XML_DIR = str(ROOT / 'data' / 'original_source')
INPUT_JSON = str(ROOT / 'data' / 'city_indices.json')
INPUT_CSV = str(ROOT / 'data' / 'attrazione_descrizione_fixed.csv')
DTD_FILE = str(ROOT / 'data' / 'city_report.dtd')
OUTPUT_DIR = str(ROOT / 'data' / 'xml_dataset')

if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

def clean_text(text):
    """Pulizia di base per evitare caratteri illegali XML"""
    if not text: return ""
    return text.strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def extract_districts(wiki_text):
    if not wiki_text: return []
    section_match = re.search(r'==\s*(Districts|Neighborhoods|Distretti|Zones|Sectors)\s*==\n(.*?)\n==', wiki_text, re.DOTALL | re.IGNORECASE)
    if not section_match: return []
    
    content = section_match.group(2)
    districts = []
    pattern_links = r'(?:\*\s*)?(?:\'\'\')?\[\[(?:[^|\]]*\|)?([^\]]*)\]\](?:\'\'\')?\s*[:\-\u2013\u2014]\s*([^.\n]*)'
    matches_links = re.findall(pattern_links, content)
    for m in matches_links:
        districts.append({'n': clean_text(m[0]), 'd': clean_text(m[1])})

    pattern_template = r'\{\{district\s*\|\s*name\s*=\s*([^|}]*).*?\|\s*content\s*=\s*([^|}]*)'
    matches_temp = re.findall(pattern_template, content, re.DOTALL)
    for m in matches_temp:
        districts.append({'n': clean_text(m[0]), 'd': clean_text(m[1])})
            
    return districts[:5]

def run_pipeline():
    print("🚀 Avvio Pipeline con Validazione DTD incorporata...")
    
    # 1. Caricamento DTD per validazione
    if not os.path.exists(DTD_FILE):
        print(f"❌ Errore critico: {DTD_FILE} non trovato. Impossibile validare.")
        return
    
    try:
        dtd = etree.DTD(open(DTD_FILE, 'rb'))
        df_attr = pd.read_csv(INPUT_CSV)
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            indices = json.load(f)['capitali']
    except Exception as e:
        print(f"❌ Errore inizializzazione: {e}")
        return

    for city in indices:
        name = city['city']
        wiki_text = ""
        orig_file = os.path.join(ORIGINAL_XML_DIR, f"{name}.xml")
        
        if os.path.exists(orig_file):
            tree_orig = etree.parse(orig_file)
            wiki_text = tree_orig.xpath("string(//*[local-name()='text'])")
        
        districts_data = extract_districts(wiki_text)
        score = round((city['safety']*0.4 + city['green_score']*0.4 + (100-city['cost_of_living'])*0.2), 1)
        
        # COSTRUZIONE XML
        root = etree.Element("city_report", appeal_score=str(score))
        
        meta = etree.SubElement(root, "metadata")
        etree.SubElement(meta, "title").text = name

        ind = etree.SubElement(root, "indicators")
        etree.SubElement(ind, "hotel_price").text = str(round(city['cost_of_living'] * 1.85, 2))
        etree.SubElement(ind, "safety", index_score=str(city['safety']))
        etree.SubElement(ind, "environment", green_score=str(city['green_score']))
        etree.SubElement(ind, "cost_index", value=str(city['cost_of_living']))
        etree.SubElement(ind, "economic_accessibility", score=str(round(100 - city['cost_of_living'], 1)))

        high = etree.SubElement(root, "highlights")
        city_attractions = df_attr[df_attr['City'] == name].head(10)
        for _, row in city_attractions.iterrows():
            attr = etree.SubElement(high, "attraction", lat=str(row['Latitude']), lon=str(row['Longitude']))
            etree.SubElement(attr, "name").text = clean_text(str(row['Attraction']))
            etree.SubElement(attr, "description").text = clean_text(str(row['Description']))

        if districts_data:
            dist_tag = etree.SubElement(root, "districts")
            for d in districts_data:
                d_node = etree.SubElement(dist_tag, "district")
                etree.SubElement(d_node, "name").text = d['n']
                etree.SubElement(d_node, "description").text = d['d']

        etree.SubElement(root, "description").text = f"Analisi urbana di {name}"

        # --- GATE DI VALIDAZIONE ---
        if dtd.validate(root):
            tree = etree.ElementTree(root)
            output_path = os.path.join(OUTPUT_DIR, f"{name.lower()}.xml")
            tree.write(output_path, 
                       xml_declaration=True, 
                       encoding='UTF-8', 
                       pretty_print=True,
                       doctype=f'<!DOCTYPE city_report SYSTEM "{DTD_FILE}">')
            print(f"✅ {name}: Validato e salvato.")
        else:
            print(f"⚠️ {name}: Errore di validazione DTD!")
            print(dtd.error_log.filter_from_errors())

    print(f"\n✨ Pipeline conclusa. Dataset normalizzato in: {OUTPUT_DIR}")

if __name__ == "__main__": run_pipeline()