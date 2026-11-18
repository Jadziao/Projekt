"""Opcjonalny, ostrozny patch tekstowych list lig w ScoutPro V4.

Przed edycja tworzy pliki *.before_mlsnp.bak. Bez --apply tylko podglad zmian.
Nie modyfikuje nieznanych plikow, nie rusza danych ani logiki aplikacji.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPLACEMENTS = (
    ("['MLS','USLC','USL1','Wszystkie']", "['MLS','USLC','USL1','MLSNP','Wszystkie']"),
    ("['MLS','USLC','USL1']", "['MLS','USLC','USL1','MLSNP']"),
    ('["MLS", "USLC", "USL1"]', '["MLS", "USLC", "USL1", "MLSNP"]'),
    ('["Wszystkie", "MLS", "USLC", "USL1"]', '["Wszystkie", "MLS", "USLC", "USL1", "MLSNP"]'),
    ("['MLS', 'USLC', 'USL1']", "['MLS', 'USLC', 'USL1', 'MLSNP']"),
    ('MLS / USLC / USL1', 'MLS / USLC / USL1 / MLSNP'),
    ('MLS, USLC i USL1', 'MLS, USLC, USL1 i MLSNP'),
    ('MLS, USLC, USL1', 'MLS, USLC, USL1, MLSNP'),
)
FILES = ('app.py', 'scoutpro_players.py', 'scoutpro_reports.py',
         'scoutpro_bold_home.py', 'scoutpro_comparisons.py', 'scoutpro_talents.py')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', type=Path, default=Path('.'))
    ap.add_argument('--apply', action='store_true', help='Zapisz zmiany, tworzac kopie kazdego pliku')
    args = ap.parse_args()
    root = args.project
    changes = 0
    for name in FILES:
        path = root / name
        if not path.is_file():
            print(f'Brak pliku (pomijam): {path}')
            continue
        old = path.read_text(encoding='utf-8')
        new = old
        for find, repl in REPLACEMENTS:
            new = new.replace(find, repl)
        if new == old:
            continue
        changes += 1
        if args.apply:
            backup = path.with_name(path.name + '.before_mlsnp.bak')
            if backup.exists():
                print(f'Pomijam {name}: kopia {backup.name} juz istnieje (chronie ja przed nadpisaniem).')
                continue
            shutil.copy2(path, backup)
            path.write_text(new, encoding='utf-8')
            print(f'Poprawiono: {name} (backup: {backup.name})')
        else:
            print(f'Do poprawienia: {name}')
    print(f'Pliki ze zmianami: {changes}. ' + ('Zapisano ostrozne poprawki.' if args.apply else 'Do zapisania dodaj --apply.'))


if __name__ == '__main__':
    main()
