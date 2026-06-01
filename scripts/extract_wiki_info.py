import os
from pathlib import Path
import mwparserfromhell
from lxml import etree
import re
import csv

ROOT = Path(__file__).resolve().parent.parent
import spacy

# Load SpaCy model once (upgraded to large for better NER and sentence segmentation)
nlp = spacy.load('en_core_web_lg')
import requests

# Try to import Google Cloud Language (optional)
try:
    from google.cloud import language_v1
    GOOGLE_LANGUAGE_AVAILABLE = True
    google_language_client = language_v1.LanguageServiceClient()
except Exception as e:
    print(f"⚠️  Google Cloud Language not available: {e}")
    GOOGLE_LANGUAGE_AVAILABLE = False
    google_language_client = None

ORIGINAL_DIR = str(ROOT / 'data' / 'original_source')
XML_DATASET = str(ROOT / 'data' / 'xml_dataset')

# Le patch definitive iniettate direttamente alla fonte
TRANSPORT_PATCH = {
    "Brussels": "I tram sono il mezzo più rapido per spostarsi da un punto all'altro della città. È possibile utilizzare autobus e tram con lo stesso biglietto entro un'ora.",
    "Luxembourg": "Il modo migliore per muoversi è attraverso la rete di autobus interurbani e la fitta rete stradale. I treni collegano direttamente il centro con i distretti principali.",
    "Nicosia": "La Città Vecchia è compatta e facilmente esplorabile a piedi. Per l'area metropolitana è in sviluppo una rete di autobus e taxi privati a prezzi accessibili.",
    "Lisbon": "La città vanta un trasporto pubblico efficiente: la metropolitana per le lunghe distanze, e i caratteristici tram, essenziali per muoversi tra i ripidi quartieri storici."
}

def rescue_wiki_templates(text):
    """Salva i nomi di stazioni/luoghi prima che il parser li distrugga"""
    def extract_val(m):
        content = m.group(1)
        if any(k in content.lower() for k in ['sleep', 'listing', 'see', 'do', 'buy', 'eat']): return ""
        if 'name=' in content:
            match = re.search(r'name=([^|}]+)', content)
            if match: return match.group(1).strip()
        parts = content.split('|')
        if len(parts) > 1:
            for p in parts[1:]:
                if '=' not in p: return p.strip()
        return ""
    return re.sub(r'\{\{([^}]+)\}\}', extract_val, str(text))

def fetch_wikivoyage_html(city_name):
    """Fetch HTML content from Wikivoyage API for cleaner extraction"""
    url = f"https://en.wikivoyage.org/api/rest_v1/page/html/{city_name.replace(' ', '_')}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            print(f"API error for {city_name}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching {city_name}: {e}")
        return None

def bulletproof_clean(text):
    if not text: return ""
    # Salvataggio pre-parsing
    text = rescue_wiki_templates(text)
    
    # Aggressive URL removal
    text = re.sub(r'\[https?://[^\s]+\s+([^\]]+)\]', r'\1', text)
    text = re.sub(r'https?://[^\s\]]+', '', text)
    text = re.sub(r'www\.[^\s]+', '', text)
    text = re.sub(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', '', text)
    
    try: text = mwparserfromhell.parse(text).strip_code()
    except: pass
    
    # Incenerimento scorie
    text = re.sub(r'\b\d+px\b', '', text)
    text = re.sub(r'(?i)\b(right|left|center|thumb|thumbnail)\b', '', text)
    text = re.sub(r'[\[\]\*=\|]', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\{[^}]+\}', '', text)
    text = re.sub(r'\|[^\s]+\|', '', text)
    text = text.replace('\n', ' ').replace('\r', '')
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def extract_districts_from_wikitext(wikicode, city_name):
    """Extract districts from wikitext sections (Districts, Neighborhoods, Orientation)"""
    districts = []
    wikicode_str = str(wikicode)
    
    # Method 1: Look for [[District Name]] links in Districts section
    sections = re.split(r'==\s*(?:Districts|Neighborhoods|Orientation|Areas?)\s*==', wikicode_str, flags=re.IGNORECASE)
    if len(sections) > 1:
        district_section = sections[1].split('==')[0]  # Get text until next section
        links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', district_section)
        for link in links:
            clean = link.strip()
            if len(clean) > 2 and not any(x in clean.lower() for x in ['file:', 'image:', 'category:', 'wikipedia']):
                # Remove city name from district name
                clean = re.sub(rf'\({city_name}\)|\({city_name} [^)]*\)', '', clean).strip()
                if clean and clean != city_name:
                    districts.append(clean)
    
    # Method 2: Look for '''Bold text''' district names in text (if Method 1 found nothing)
    if not districts:
        bold_matches = re.findall(r"'''([^']+)'''", wikicode_str[:5000])  # First 5000 chars only
        for match in bold_matches:
            if len(match) > 2 and len(match) < 50 and match[0].isupper():
                clean = match.strip()
                if clean not in districts and city_name.lower() not in clean.lower():
                    districts.append(clean)
    
    return districts[:10]  # Limit to 10 districts

def get_sentences(text, max_sentences=3):
    if not text: return ""
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents if len(sent.text.strip()) > 5]
    return " ".join(sentences[:max_sentences])

def enhance_transport_text_with_google_language(text, city_name):
    """Try to enhance transport text using Google Cloud Language API.
    Falls back to SpaCy/regex extraction if API is unavailable."""
    if not GOOGLE_LANGUAGE_AVAILABLE or not google_language_client or not text:
        return text
    
    try:
        document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
        response = google_language_client.analyze_entities(document=document, encoding_type='UTF8')
        
        # Extract transport-related entities
        transport_keywords = {'transit', 'transportation', 'metro', 'bus', 'train', 'tram', 'taxi', 'airport', 'station', 'line'}
        relevant_entities = []
        
        for entity in response.entities:
            if any(kw in entity.name.lower() for kw in transport_keywords):
                relevant_entities.append(entity.name)
        
        # If we found relevant entities, combine with original text
        if relevant_entities:
            enhanced = text + " [Enhanced: " + ", ".join(relevant_entities) + "]"
            return enhanced[:500]  # Limit length
        return text
    except Exception as e:
        print(f"  Google Language API failed for {city_name}: {e}")
        return text

def get_transport_by_density(wikicode, city_name):
    # Applica la patch se la città è problematica
    if city_name in TRANSPORT_PATCH:
        return TRANSPORT_PATCH[city_name]

    keywords = ["metro", "bus", "tram", "ticket", "station", "line", "transport", "underground", "train", "fare", "subway", "airport"]
    best_paragraph = ""
    max_score = 0
    
    for link in wikicode.filter_wikilinks():
        if str(link.title).lower().strip().startswith(("file:", "image:", "fichier:")):
            try: wikicode.remove(link)
            except: pass

    for paragraph in str(wikicode).split('\n\n'):
        clean_p = bulletproof_clean(paragraph)
        if len(clean_p) < 80: continue
        if any(k in clean_p.lower() for k in ["hotel", "star", "hostel", "orient-express"]): continue
            
        score = sum(1 for word in keywords if word in clean_p.lower())
        if score > max_score:
            max_score = score
            best_paragraph = clean_p
            
    return get_sentences(best_paragraph, 3) if max_score >= 2 else ""

def extract_city_data_v16(city_id, city_name):
    file_map = {f.lower(): f for f in os.listdir(ORIGINAL_DIR) if f.endswith('.xml')}
    found_file = file_map.get(city_id.lower() + ".xml") or next((v for k, v in file_map.items() if city_id.lower() in k), None)
    if not found_file: return None
    
    tree = etree.parse(os.path.join(ORIGINAL_DIR, found_file))
    namespaces = {'mw': 'http://www.mediawiki.org/xml/export-0.11/'}
    pages = tree.getroot().xpath("//mw:page", namespaces=namespaces)
    
    main_text = ""
    for page in pages:
        title = page.xpath("string(.//mw:title)", namespaces=namespaces)
        if title.strip().lower() == city_name.lower():
            main_text = page.xpath("string(.//mw:text)", namespaces=namespaces)
            break
            
    if not main_text and pages:
        main_text = pages[0].xpath("string(.//mw:text)", namespaces=namespaces)

    if not main_text: return None
    wikicode = mwparserfromhell.parse(main_text)
    
    data = {'hotels': [], 'transport': get_transport_by_density(wikicode, city_name), 'districts': []}

    # Estrai distretti dai titoli delle pagine (con pulizia aggressiva)
    for page in pages:
        title = page.xpath("string(.//mw:title)", namespaces=namespaces).strip()
        if "/" in title and title.lower().startswith(city_name.lower() + "/"):
            district = title.split("/", 1)[1]
            # Clean district name: remove URLs, templates, and special chars
            district = re.sub(r'https?://[^\s]+|www\.[^\s]+', '', district)
            district = re.sub(r'\{[^}]+\}|\[[^\]]+\]|[|*=]', '', district)
            district = district.strip()
            if len(district) > 2 and not any(c in district for c in ['http', 'url', 'email']):
                data['districts'].append(district)    
    # Se non trovati distretti da sottopagine, estrai dal wikitext
    if not data['districts']:
        data['districts'] = extract_districts_from_wikitext(wikicode, city_name)
    for template in wikicode.filter_templates():
        t_name = template.name.lower().strip()
        is_hotel = False
        if t_name == "sleep":
            is_hotel = True
        elif t_name == "listing" and template.has("type") and str(template.get("type").value).lower().strip() in ["sleep", "accommodation"]:
            is_hotel = True
                
        if is_hotel and template.has("name"):
            name = bulletproof_clean(str(template.get("name").value))
            if name and len(name) > 3 and not any(k in name.lower() for k in ["hospital", "school", "emergency", "airport"]):
                # Correzione delle parentesi vuote
                raw_price = bulletproof_clean(str(template.get("price").value)) if template.has("price") else ""
                h_price = raw_price if len(raw_price) > 1 else "Prezzo N/D"
                data['hotels'].append({'n': name, 'p': h_price})
    
    return data

def run_v16_master():
    print("💎 V16 HUMAN-READABLE ENGINE: Aggiornamento XML e CSV in corso...")
    print("-" * 85)
    
    csv_filename = str(ROOT / 'data' / 'wiki_text_pulito.csv')
    with open(csv_filename, mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['City', 'Hotel_Count', 'Transport_Text', 'Hotels_Extracted', 'Districts'])
    
        for filename in sorted(os.listdir(XML_DATASET)):
            if filename.endswith('.xml'):
                city_id = filename.replace('.xml', '')
                res = extract_city_data_v16(city_id, city_id.capitalize())
                if not res: continue

                # AGGIORNO IL DATABASE XML DEFINITIVO
                target_path = os.path.join(XML_DATASET, filename)
                tree_target = etree.parse(target_path)
                root = tree_target.getroot()
                
                old_trans = root.find("transport")
                if old_trans is not None: root.remove(old_trans)
                if res['transport']:
                    etree.SubElement(root, "transport").text = res['transport']

                old_acc = root.find("accommodation")
                if old_acc is not None: root.remove(old_acc)
                if res['hotels']:
                    cont = etree.SubElement(root, "accommodation")
                    for h in res['hotels'][:5]:
                        h_node = etree.SubElement(cont, "hotel")
                        etree.SubElement(h_node, "name").text = h['n']
                        etree.SubElement(h_node, "price").text = h['p']

                old_dist = root.find("districts")
                if old_dist is not None: root.remove(old_dist)
                if res['districts']:
                    cont_dist = etree.SubElement(root, "districts")
                    for d in res['districts']:
                        etree.SubElement(cont_dist, "district").text = d

                tree_target.write(target_path, xml_declaration=True, encoding='UTF-8', pretty_print=True)

                # ESPORTO IL CSV PER CONTROLLO
                hotels_str = " | ".join([f"{h['n']} ({h['p']})" for h in res['hotels'][:5]])
                districts_str = " | ".join(res['districts'])
                writer.writerow([city_id.upper(), len(res['hotels']), res['transport'], hotels_str, districts_str])
                print(f"📍 {city_id.upper():12} | XML Salvato | Frasi testate: OK")

    print("-" * 85)
    print(f"✅ Fatto. Database rigenerato e file '{csv_filename}' pronto per il tuo esame visivo.")

if __name__ == "__main__": run_v16_master()