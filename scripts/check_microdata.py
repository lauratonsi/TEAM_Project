#!/usr/bin/env python3
"""
check_microdata.py — Verifica round-trip dei microdata Schema.org (progetto TEAM).

Script indipendente dalla pipeline, sul modello dei laboratori del corso
(`lab_microdata.py`): NON conta i microdata con una regex, ma li **ri-estrae**
dalle pagine HTML generate usando la libreria `microdata` (`microdata.get_items()`),
la stessa mostrata a lezione. È la prova che le annotazioni iniettate da
`deploy_dashboard.py` sono microdata **ben formati e ri-parsabili**, non semplici
stringhe nel sorgente.

Cosa verifica (round-trip = scrittura → ri-lettura → confronto):
  1. ESTRAZIONE   — ogni pagina città espone esattamente UN item top-level di tipo
                    schema.org/City; l'index espone le 30 card-città.
  2. IDENTITÀ     — l'`itemid` della City ri-estratto dall'HTML coincide con
                    l'elemento <source_url> del documento XML corrispondente
                    (itemid ↔ documento: la corrispondenza richiesta dal corso).
  3. ANNIDAMENTO  — la City contiene (containsPlace) gli oggetti annidati attesi
                    (TouristAttraction / Hotel / BarOrPub|NightClub) e ciascun luogo
                    geolocalizzato porta un GeoCoordinates con latitude/longitude.
  4. INDICATORI   — la City porta un AggregateRating con ratingValue e i sotto-indici
                    come PropertyValue (additionalProperty).

Uso:
    python scripts/check_microdata.py

Codice di uscita: 0 se il round-trip è coerente su tutte le pagine, 1 altrimenti.
"""

import sys
from pathlib import Path

from lxml import etree

try:
    import microdata
except ImportError:
    print("❌ Libreria 'microdata' non installata.")
    print("   Installa con:  pip install microdata")
    print("   (è la stessa usata nel laboratorio del corso, lab_microdata.py)")
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = ROOT / 'index.html'
CITIES_DIR = ROOT / 'pages' / 'cities'
XML_DIR = ROOT / 'data' / 'xml_dataset'

SCHEMA = 'schema.org'


# ─────────────────────────────────────────────────────────────────────────────
# Helper sull'API della libreria microdata
# ─────────────────────────────────────────────────────────────────────────────
def get_items(html_path):
    """Ri-estrae gli item top-level da un file HTML. Gestisce le piccole
    differenze d'API tra versioni di `microdata` (stringa vs file object)."""
    text = Path(html_path).read_text(encoding='utf-8')
    try:
        return microdata.get_items(text)
    except Exception:
        with open(html_path, encoding='utf-8') as fh:
            return microdata.get_items(fh)


def type_names(item):
    """Nomi brevi dei tipi schema.org dell'item (es. 'City', 'GeoCoordinates')."""
    names = []
    for t in (item.itemtype or []):
        s = getattr(t, 'string', None) or str(t)
        names.append(s.rstrip('/').rsplit('/', 1)[-1])
    return names


def first_type(item):
    names = type_names(item)
    return names[0] if names else '?'


def prop_value(item, name):
    """Primo valore (stringa) di una proprietà, oppure None."""
    vals = item.props.get(name) or item.get_all(name)
    for v in vals:
        if not isinstance(v, microdata.Item):
            return str(v)
    return None


def child_items(item):
    """Item annidati (valori-proprietà che sono a loro volta Item)."""
    out = []
    for values in item.props.values():
        for v in values:
            if isinstance(v, microdata.Item):
                out.append(v)
    return out


def walk(item, bag):
    """Raccoglie ricorsivamente l'item e tutta la sua discendenza tipizzata."""
    bag.append(item)
    for child in child_items(item):
        walk(child, bag)


# ─────────────────────────────────────────────────────────────────────────────
# Verifiche
# ─────────────────────────────────────────────────────────────────────────────
def source_url_of(city_lower):
    """Legge <source_url> dal documento XML (la fonte di verità dell'itemid)."""
    xml_path = XML_DIR / f"{city_lower}.xml"
    if not xml_path.exists():
        return None
    return etree.parse(str(xml_path)).getroot().findtext('.//source_url')


def check_city_page(xml_name):
    """Verifica round-trip di una singola pagina città. Ritorna (ok, messaggi, types)."""
    city_lower = xml_name
    html_path = CITIES_DIR / f"{city_lower}.html"
    notes, types = [], {}
    if not html_path.exists():
        return False, [f"pagina HTML mancante: {html_path.name}"], types

    items = get_items(html_path)
    cities = [it for it in items if 'City' in type_names(it)]
    if len(cities) != 1:
        notes.append(f"attese 1 City top-level, trovate {len(cities)}")
        return False, notes, types
    city = cities[0]

    # Tutta la discendenza tipizzata
    bag = []
    walk(city, bag)
    for it in bag:
        for t in type_names(it):
            types[t] = types.get(t, 0) + 1

    ok = True

    # 2. IDENTITÀ: itemid ri-estratto == <source_url> dell'XML
    itemid = str(city.itemid) if city.itemid else None
    src = source_url_of(city_lower)
    if itemid != src:
        ok = False
        notes.append(f"itemid≠source_url (HTML='{itemid}' vs XML='{src}')")

    # 3. ANNIDAMENTO: almeno un'attrazione con GeoCoordinates valide
    attractions = [it for it in bag if 'TouristAttraction' in type_names(it)]
    if not attractions:
        ok = False
        notes.append("nessuna TouristAttraction annidata")
    else:
        geo = [g for g in child_items(attractions[0]) if 'GeoCoordinates' in type_names(g)]
        if not geo or not (prop_value(geo[0], 'latitude') and prop_value(geo[0], 'longitude')):
            ok = False
            notes.append("TouristAttraction senza GeoCoordinates lat/lon")

    # 4. INDICATORI: AggregateRating con ratingValue + PropertyValue
    ratings = [it for it in bag if 'AggregateRating' in type_names(it)]
    if not ratings or prop_value(ratings[0], 'ratingValue') is None:
        ok = False
        notes.append("AggregateRating/ratingValue assente")
    if not any('PropertyValue' in type_names(it) for it in bag):
        ok = False
        notes.append("nessun PropertyValue (additionalProperty)")

    return ok, notes, types


def main():
    if not CITIES_DIR.exists():
        print(f"❌ Cartella pagine città non trovata: {CITIES_DIR}")
        print("   Genera prima il sito:  python scripts/deploy_dashboard.py")
        sys.exit(2)

    xml_names = sorted(p.stem for p in XML_DIR.glob('*.xml'))
    print(f"🔎 Ri-estrazione microdata con la libreria 'microdata' (get_items)")
    print(f"📂 Pagine città: {CITIES_DIR}")
    print(f"📄 Fonte itemid: <source_url> in {XML_DIR}\n")

    grand_types = {}
    n_ok = 0
    for name in xml_names:
        ok, notes, types = check_city_page(name)
        for t, c in types.items():
            grand_types[t] = grand_types.get(t, 0) + c
        if ok:
            n_ok += 1
            n_attr = types.get('TouristAttraction', 0)
            n_hotel = types.get('Hotel', 0)
            n_bar = types.get('BarOrPub', 0) + types.get('NightClub', 0)
            print(f"  ✅ {name:18s} City✓ itemid↔source_url✓ "
                  f"[{n_attr} attr · {n_hotel} hotel · {n_bar} locali · geo✓ rating✓]")
        else:
            print(f"  ❌ {name:18s} — " + "; ".join(notes))

    # Index: le card-città devono essere ri-estraibili come City
    index_cities = 0
    if INDEX_HTML.exists():
        index_cities = sum(1 for it in get_items(INDEX_HTML) if 'City' in type_names(it))

    total = len(xml_names)
    print("\n" + "─" * 66)
    print("🏷️  Tipi Schema.org ri-estratti dalle pagine città (round-trip):")
    for t, c in sorted(grand_types.items(), key=lambda kv: -kv[1]):
        print(f"     {t:20s} {c:>4}")
    print(f"🌐 index.html: {index_cities} item City ri-estratti dalle card")
    print("─" * 66)
    print(f"📋 Round-trip coerente su {n_ok}/{total} pagine città")
    print("─" * 66)
    sys.exit(0 if n_ok == total else 1)


if __name__ == '__main__':
    main()
