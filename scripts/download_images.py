"""
Script one-shot: scarica le immagini landmark in assets/images/.
Usa la Wikipedia pageimages API come fonte affidabile, poi salva in locale.
"""
import os
import sys
import time
from pathlib import Path
from typing import Optional
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = str(ROOT / 'assets' / 'images')
HEADERS = {"User-Agent": "EuroCityBot/1.0 (educational project; ltonsi13@gmail.com)"}

# Sovrascritture manuali per città con nomi Wikipedia non standard
WIKI_TITLE_OVERRIDE = {
    "Reykjavik": "Reykjavík",
}

os.makedirs(OUT_DIR, exist_ok=True)

CITIES = [
    "Amsterdam", "Athens", "Berlin", "Bratislava", "Brussels",
    "Bucharest", "Budapest", "Copenhagen", "Dublin", "Helsinki",
    "Lisbon", "Ljubljana", "London", "Luxembourg", "Madrid",
    "Nicosia", "Oslo", "Paris", "Prague", "Reykjavik",
    "Riga", "Rome", "Sofia", "Stockholm", "Tallinn",
    "Valletta", "Vienna", "Vilnius", "Warsaw", "Zagreb",
]


def get_wiki_image_url(city: str) -> Optional[str]:
    title = WIKI_TITLE_OVERRIDE.get(city, city)
    params = {
        "action": "query",
        "titles": title,
        "prop": "pageimages",
        "format": "json",
        "pithumbsize": 1200,
        "pilicense": "free",
    }
    r = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params=params, headers=HEADERS, timeout=15
    )
    r.raise_for_status()
    pages = r.json()["query"]["pages"]
    for page in pages.values():
        if "thumbnail" in page:
            return page["thumbnail"]["source"]
    return None


def download_image(url: str, dest: str) -> None:
    r = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=30, stream=True)
    r.raise_for_status()
    ct = r.headers.get("Content-Type", "")
    if "image" not in ct:
        raise ValueError(f"Content-Type inatteso: {ct}")
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)


ok, fail = [], []

for city in CITIES:
    dest = os.path.join(OUT_DIR, f"{city.lower()}.jpg")
    if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
        print(f"  SKIP {city:12} (già presente)")
        ok.append(city)
        continue

    try:
        img_url = get_wiki_image_url(city)
        if not img_url:
            raise ValueError("Nessuna immagine trovata via Wikipedia API")
        download_image(img_url, dest)
        print(f"  OK   {city:12} → {img_url[:90]}")
        ok.append(city)
        time.sleep(0.5)  # rispetta rate limit Wikimedia
    except Exception as e:
        print(f" FAIL  {city:12} → {e}")
        fail.append(city)
        time.sleep(1)

print(f"\nScaricate: {len(ok)}/30")
if fail:
    print(f"Fallite:   {fail}")
    sys.exit(1)
