#!/usr/bin/env python3
"""
validate.py — Validatore DTD standalone per il progetto TEAM.

Script indipendente dal resto della pipeline: legge la directory dei documenti
XML, ne costruisce il DOM e li valida rispetto al DTD `city_report.dtd`,
esattamente con l'approccio mostrato a lezione (lab_castles_validation.py e
lab_castles_files_aggiornato13.04.py):

    from lxml import etree
    dtd = etree.DTD(open(DTD_FILE, 'rb'))    # carica il DTD
    tree = etree.parse(xml_file)             # parsing → DOM (buona forma)
    dtd.validate(tree)                        # validazione → booleano
    dtd.error_log.filter_from_errors()        # eventuali errori di validità

Distingue i tre esiti possibili:
  • MALFORMATO  → etree.parse() solleva XMLSyntaxError (NON ben formato)
  • NON VALIDO  → ben formato ma dtd.validate() == False
  • VALIDO      → ben formato e valido rispetto al DTD

Uso:
    python scripts/validate.py            # valida data/xml_dataset/
    python scripts/validate.py <dir>      # valida un'altra directory

Codice di uscita: 0 se tutti i file sono validi, 1 altrimenti
(così è utilizzabile anche in script/CI).
"""

import os
import sys
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
DTD_FILE = ROOT / 'data' / 'city_report.dtd'
# Directory di input in UNA variabile, sovrascrivibile da ambiente o da argomento
# a riga di comando (cfr. slide "Documenti XML in input").
DEFAULT_XML_DIR = Path(os.environ.get('TEAM_XML_DIR', str(ROOT / 'data' / 'xml_dataset')))


def inspect_dom(tree):
    """Piccola ispezione del DOM costruito da etree.parse(): mostra che il
    documento è navigabile come albero (radice, attributi, n. di elementi)."""
    root = tree.getroot()
    n_elements = sum(1 for _ in root.iter())
    n_attractions = len(root.findall('.//attraction'))
    title = root.findtext('.//title')
    return {
        'root_tag': root.tag,
        'appeal_score': root.get('appeal_score'),
        'title': title,
        'n_elements': n_elements,
        'n_attractions': n_attractions,
    }


def validate_directory(xml_dir, dtd_file=DTD_FILE):
    """Valida tutti i file .xml in `xml_dir` rispetto al DTD. Ritorna un dict
    con i contatori e l'elenco degli errori."""
    # 1. Carica il DTD (solleva se il DTD stesso è sintatticamente errato)
    try:
        dtd = etree.DTD(open(dtd_file, 'rb'))
    except (OSError, etree.DTDParseError) as e:
        print(f"❌ Impossibile caricare il DTD {dtd_file}: {e}")
        sys.exit(2)

    print(f"📄 DTD     : {dtd_file}")
    print(f"📂 Sorgente: {xml_dir}\n")

    result = {'valid': 0, 'invalid': 0, 'malformed': 0, 'errors': []}
    files = sorted(f for f in os.listdir(xml_dir) if f.endswith('.xml'))

    for filename in files:
        path = os.path.join(xml_dir, filename)
        try:
            # 2. Parsing → costruzione del DOM. Solleva se NON ben formato.
            tree = etree.parse(path)
        except etree.XMLSyntaxError as e:
            result['malformed'] += 1
            result['errors'].append((filename, f"malformato: {e}"))
            print(f"  ❌ {filename:24s} MALFORMATO (non ben formato) — {e}")
            continue

        # 3. Validazione del DOM rispetto al DTD
        if dtd.validate(tree):
            dom = inspect_dom(tree)
            result['valid'] += 1
            print(f"  ✅ {filename:24s} VALIDO   "
                  f"[root=<{dom['root_tag']}> · {dom['n_elements']:>3} elementi · "
                  f"{dom['n_attractions']} attractions · appeal={dom['appeal_score']}]")
        else:
            err = dtd.error_log.filter_from_errors()
            result['invalid'] += 1
            result['errors'].append((filename, str(err)))
            print(f"  ⚠️  {filename:24s} NON VALIDO — {err}")

    total = len(files)
    print("\n" + "─" * 60)
    print(f"📋 Risultato: {result['valid']}/{total} validi · "
          f"{result['invalid']} non validi · {result['malformed']} malformati")
    print("─" * 60)
    return result


def main():
    xml_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XML_DIR
    if not xml_dir.exists():
        print(f"❌ Directory non trovata: {xml_dir}")
        sys.exit(2)

    result = validate_directory(xml_dir)
    # Uscita non-zero se qualcosa non è valido (utile per automazioni)
    sys.exit(0 if (result['invalid'] == 0 and result['malformed'] == 0) else 1)


if __name__ == '__main__':
    main()
