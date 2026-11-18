"""Automatyczny import wybranych lig CC0 OpenFootball do scoutpro_sources.db.

Przykłady:
    python importuj_ligi_europy.py
    python importuj_ligi_europy.py --only openfootball-czech-republic-cz1
    python importuj_ligi_europy.py --list
Nie zmienia scoutpro.db, scoutpro_mlsnp_2025_gotowe_v2.db ani ScoutScore.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

# Windows: użyj systemowych zaufanych certyfikatów, jeśli biblioteka jest dostępna.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / 'ScoutPro_Legalne_Zrodla' / 'scoutpro_legal_catalog.json'
DEST = ROOT / 'database' / 'scoutpro_sources.db'

TARGETS = (
    'openfootball-poland-pl1',
    'openfootball-poland-pl2',
    'openfootball-czech-republic-cz1',
    'openfootball-czech-republic-cz2',
    'openfootball-slovakia-sk1',
    'openfootball-hungary-hu1',
    'openfootball-croatia-hr1',
)


def catalog():
    entries = json.loads(CATALOG.read_text(encoding='utf-8'))['leagues']
    return {e['slug']:e for e in entries if e['slug'] in TARGETS and e['provider']=='openfootball' and e['license']=='CC0 1.0'}


def setup(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS source_records (
       source TEXT NOT NULL, league_key TEXT NOT NULL, season TEXT NOT NULL,
       kind TEXT NOT NULL, record_hash TEXT NOT NULL, payload TEXT NOT NULL,
       license TEXT NOT NULL, source_url TEXT NOT NULL, imported_at TEXT NOT NULL,
       PRIMARY KEY(source,league_key,season,kind,record_hash)
    );
    CREATE INDEX IF NOT EXISTS idx_scoutpro_import_lookup ON source_records(source,league_key,season);
    CREATE TABLE IF NOT EXISTS source_import_log (
       id INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT NOT NULL,league_key TEXT NOT NULL,
       season TEXT NOT NULL,kind TEXT NOT NULL,count_rows INTEGER,
       source_url TEXT,imported_at TEXT NOT NULL
    );
    ''')


def download(entry):
    url = entry['source_url']
    if urlsplit(url).scheme != 'https' or urlsplit(url).hostname != 'openfootball.github.io':
        raise ValueError('Niedozwolony host źródła (oczekiwano oficjalnego OpenFootball)')
    request = urllib.request.Request(url,headers={'User-Agent':'ScoutPro/1.1 (education; openfootball CC0)','Accept':'application/json'})
    with urllib.request.urlopen(request, timeout=35) as resp:
        payload = resp.read(3_000_001)
        if len(payload)>3_000_000:
            raise ValueError('Zbyt duży plik sezonu, przerwano import')
    obj = json.loads(payload)
    matches = obj.get('matches') if isinstance(obj,dict) else None
    if not isinstance(matches,list) or not matches:
        raise ValueError('Brak listy meczów — import anulowany')
    correct = [m for m in matches if isinstance(m,dict) and isinstance(m.get('team1'),str) and isinstance(m.get('team2'),str) and m['team1'].strip() and m['team2'].strip()]
    if len(correct) != len(matches):
        raise ValueError('Nieprawidłowe rekordy meczu — import anulowany')
    return correct


def store(con, entry, matches):
    stamp = datetime.now(timezone.utc).isoformat()
    tuples=[]
    for m in matches:
        raw=json.dumps(m,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        digest=hashlib.sha256(raw.encode('utf-8')).hexdigest()
        tuples.append(('openfootball',entry['slug'],entry['season'],'match',digest,raw,'CC0 1.0',entry['source_url'],stamp))
    with con:
        con.execute("DELETE FROM source_records WHERE source='openfootball' AND league_key=? AND season=? AND kind='match'",(entry['slug'],entry['season']))
        con.executemany('''INSERT OR REPLACE INTO source_records
            (source,league_key,season,kind,record_hash,payload,license,source_url,imported_at)
            VALUES(?,?,?,?,?,?,?,?,?)''',tuples)
        con.execute('''INSERT INTO source_import_log
            (source,league_key,season,kind,count_rows,source_url,imported_at) VALUES(?,?,?,?,?,?,?)''',
            ('openfootball',entry['slug'],entry['season'],'match',len(tuples),entry['source_url'],stamp))
    return len(tuples)


def main(argv=None):
    parser=argparse.ArgumentParser(description='ScoutPro — jawnie licencjonowane wyniki lig Europy (CC0)')
    parser.add_argument('--only',choices=TARGETS,help='Pobierz jedną ligę zamiast całego zestawu')
    parser.add_argument('--list',action='store_true',help='Pokaż wybrane ligi i ich źródła')
    args=parser.parse_args(argv)
    entries=catalog()
    if args.list:
        for slug in TARGETS:
            e=entries.get(slug)
            if e:print(slug,'|',e['competition'],'|',e['season'],'|',e['source_url'])
        return 0
    to_import=[args.only] if args.only else TARGETS
    DEST.parent.mkdir(parents=True,exist_ok=True)
    failures=[]
    with sqlite3.connect(DEST) as con:
        setup(con)
        for slug in to_import:
            entry=entries.get(slug)
            if not entry:
                print('[BŁĄD] Brak źródła CC0 w katalogu:',slug)
                failures.append(slug)
                continue
            print('\nPobieram:',entry['competition'],entry['season'])
            try:
                matches=download(entry)
                n=store(con,entry,matches)
                print('OK:',n,'meczów | CC0 1.0')
            except Exception as exc:
                print('[BŁĄD]',type(exc).__name__,str(exc))
                print('Dotychczasowe dane tej ligi pozostały bez zmian.')
                failures.append(slug)
    print('\nBaza:', DEST)
    print('Ligi z błędami:',', '.join(failures) if failures else 'brak')
    print('Nie zmieniono ScoutScore ani baz zawodników.')
    return 1 if failures else 0


if __name__=='__main__':
    sys.exit(main())
