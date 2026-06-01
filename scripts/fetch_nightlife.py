"""
Script one-shot: recupera venue notturni (bar/pub/biergarten/nightclub) da OpenStreetMap
via Overpass API per le 30 capitali europee. Usa bounding box invece di area query
(molto più veloce — nessuna ricerca per nome area). Salva in data/nightlife.json.
Ricarica il JSON esistente e ritenta solo le città con 0 venue.
"""
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "data" / "nightlife.json"
HEADERS = {"User-Agent": "EuroCityBot/1.0 (educational project; ltonsi13@gmail.com)"}

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]

MAX_VENUES = 8
SLEEP_BETWEEN = 2

# Coordinate centro città (lat, lon) — stesse di CAPITAL_COORDS in deploy_dashboard.py
CITY_COORDS = {
    "Amsterdam":  (52.3676,  4.9041),
    "Athens":     (37.9838, 23.7275),
    "Berlin":     (52.5200, 13.4050),
    "Bratislava": (48.1486, 17.1077),
    "Brussels":   (50.8503,  4.3517),
    "Bucharest":  (44.4268, 26.1025),
    "Budapest":   (47.4979, 19.0402),
    "Copenhagen": (55.6761, 12.5683),
    "Dublin":     (53.3498, -6.2603),
    "Helsinki":   (60.1699, 24.9384),
    "Lisbon":     (38.7169, -9.1395),
    "Ljubljana":  (46.0569, 14.5058),
    "London":     (51.5074, -0.1278),
    "Luxembourg": (49.6117,  6.1319),
    "Madrid":     (40.4168, -3.7038),
    "Nicosia":    (35.1856, 33.3823),
    "Oslo":       (59.9139, 10.7522),
    "Paris":      (48.8566,  2.3522),
    "Prague":     (50.0755, 14.4378),
    "Reykjavik":  (64.1355,-21.8954),
    "Riga":       (56.9460, 24.1059),
    "Rome":       (41.9028, 12.4964),
    "Sofia":      (42.6977, 23.3219),
    "Stockholm":  (59.3293, 18.0686),
    "Tallinn":    (59.4370, 24.7536),
    "Valletta":   (35.8989, 14.5146),
    "Vienna":     (48.2082, 16.3738),
    "Vilnius":    (54.6872, 25.2797),
    "Warsaw":     (52.2297, 21.0122),
    "Zagreb":     (45.8150, 15.9819),
}

# Raggio bbox in gradi (lat ±0.06 ≈ 6-7 km, lon ±0.09)
LAT_OFFSET = 0.06
LON_OFFSET = 0.09

AMENITY_TYPES = ["bar", "pub", "biergarten", "nightclub"]


def build_query(lat: float, lon: float) -> str:
    s = lat - LAT_OFFSET
    n = lat + LAT_OFFSET
    w = lon - LON_OFFSET
    e = lon + LON_OFFSET
    bbox = f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}"
    node_clauses = "\n  ".join(
        f'node["amenity"="{a}"]["name"]({bbox});'
        for a in AMENITY_TYPES
    )
    return (
        f'[out:json][timeout:20];\n'
        f'(\n'
        f'  {node_clauses}\n'
        f');\n'
        f'out body 50;'
    )


def fetch_venues(city: str) -> list:
    lat, lon = CITY_COORDS[city]
    query = build_query(lat, lon)

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(
                endpoint,
                data={"data": query},
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()
            elements = r.json().get("elements", [])
            venues = []
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name", "").strip()
                if not name:
                    continue
                venues.append({
                    "name": name,
                    "category": tags.get("amenity", "bar"),
                    "lat": el.get("lat"),
                    "lon": el.get("lon"),
                })
            venues.sort(key=lambda v: v["name"].lower())
            return venues[:MAX_VENUES]
        except Exception as e:
            short = str(e)[:80]
            print(f"  ⚠️  [{endpoint.split('/')[2]}] {short}", end=" ")
            time.sleep(1)

    return []


def main():
    existing: dict = {}
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
        skip = [c for c in CITY_COORDS if existing.get(c)]
        retry = [c for c in CITY_COORDS if not existing.get(c)]
        print(f"📂 JSON esistente: {len(skip)} città OK, {len(retry)} da ritentare")
    else:
        retry = list(CITY_COORDS)

    results = dict(existing)

    for city in retry:
        print(f"🔍 {city}...", end=" ", flush=True)
        venues = fetch_venues(city)
        results[city] = venues
        print(f"{len(venues)} venue trovati")
        time.sleep(SLEEP_BETWEEN)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in results.values())
    empty = [c for c in CITY_COORDS if not results.get(c)]
    print(f"\n✅ Salvato — {total} venue totali, {len(results) - len(empty)}/{len(CITY_COORDS)} città con dati")
    if empty:
        print(f"⚠️  Ancora vuoti: {', '.join(empty)}")


if __name__ == "__main__":
    main()
