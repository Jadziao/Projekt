"""ScoutPro legal sources -> separate SQLite staging database.

Does not modify database/scoutpro.db or current ScoutScore.
Usage examples in README.md. Requires an internet connection for remote sources.
"""
from __future__ import annotations

# Korzystaj z magazynu certyfikatow systemu Windows przy HTTPS.
import truststore
truststore.inject_into_ssl()

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CATALOG_PATH = Path(__file__).with_name('scoutpro_legal_catalog.json')
ALLOWED_HOSTS = {'app.americansocceranalysis.com', 'openfootball.github.io'}


def read_catalog():
    return json.loads(CATALOG_PATH.read_text(encoding='utf-8'))


def convert_json(value: Any):
    if value is None:
        return None
    if isinstance(value, (float,)) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): convert_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [convert_json(v) for v in value]
    if hasattr(value, 'item'):
        try:
            return convert_json(value.item())
        except Exception:
            pass
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def init_db(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS source_records (
       source TEXT NOT NULL,
       league_key TEXT NOT NULL,
       season TEXT NOT NULL,
       kind TEXT NOT NULL,
       record_hash TEXT NOT NULL,
       payload TEXT NOT NULL,
       license TEXT NOT NULL,
       source_url TEXT NOT NULL,
       imported_at TEXT NOT NULL,
       PRIMARY KEY (source, league_key, season, kind, record_hash)
    );
    CREATE INDEX IF NOT EXISTS idx_scoutpro_import_lookup
       ON source_records(source, league_key, season);
    CREATE TABLE IF NOT EXISTS source_import_log (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       source TEXT NOT NULL, league_key TEXT NOT NULL,
       season TEXT NOT NULL, kind TEXT NOT NULL, count_rows INTEGER,
       source_url TEXT, imported_at TEXT NOT NULL
    );
    ''')


def write_rows(con, entry, source_kind, season, records, source_url):
    now = datetime.now(timezone.utc).isoformat()
    rows=[]
    for rec in records:
        text=json.dumps(convert_json(rec), ensure_ascii=False, sort_keys=True, separators=(',',':'))
        digest=hashlib.sha256(text.encode('utf-8')).hexdigest()
        rows.append((entry['provider'],entry['slug'],season,source_kind,digest,text,entry['license'],source_url,now))
    with con:
        con.executemany('''INSERT OR REPLACE INTO source_records
        (source,league_key,season,kind,record_hash,payload,license,source_url,imported_at)
        VALUES (?,?,?,?,?,?,?,?,?)''',rows)
        con.execute('''INSERT INTO source_import_log
        (source,league_key,season,kind,count_rows,source_url,imported_at)
        VALUES (?,?,?,?,?,?,?)''',
        (entry['provider'], entry['slug'], season, source_kind, len(rows),source_url,now))
    return len(rows)


def get_json(url, params=None):
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode
    if urlparse(url).hostname not in ALLOWED_HOSTS:
        raise ValueError('Niedozwolona domena pobierania: '+url)
    full = url + ('?' + urlencode(params) if params else '')
    req=Request(full, headers={'User-Agent':'ScoutPro/1.0 research data import (respect published license)','Accept':'application/json'})
    with urlopen(req, timeout=45) as response:
        return json.load(response)


def import_openfootball(con,entry,season):
    if season != entry['season']:
        raise ValueError('W katalogu potwierdzono jedynie '+entry['season']+'. Wybierz odpowiedni wpis sezonowy z katalogu.')
    obj=get_json(entry['source_url'])
    matches=obj.get('matches')
    if not isinstance(matches,list):
        raise ValueError('Nieoczekiwany format OpenFootball: brak listy matches')
    n=write_rows(con,entry,'match',season,matches,entry['source_url'])
    return [('match',n)]


def import_asa(con,entry,season,kind,max_pages=30):
    if kind not in ('players','teams','xgoals','xpass','goals-added'):
        raise ValueError('Obsługiwany rodzaj ASA: players, teams, xgoals, xpass, goals-added')
    code=entry['source_code']
    url=(f'https://app.americansocceranalysis.com/api/v1/{code}/{kind}'
         if kind in ('players','teams') else
         f'https://app.americansocceranalysis.com/api/v1/{code}/players/{kind}')
    total=0
    for page in range(max_pages):
        params={'offset':page*1000}
        if kind not in ('players','teams'):
            params['season_name']=season
        rows=get_json(url,params)
        if not isinstance(rows,list):
            raise ValueError(f'Nieoczekiwany format ASA ({kind}): oczekiwano listy')
        if not rows:
            break
        total+=write_rows(con,entry,kind,season,rows,url)
        print(f'   {kind}: strona {page+1}: {len(rows)} rekordow')
        if len(rows)<1000: break
    else:
        raise RuntimeError('Przekroczono max_pages; mozliwie niepelny import. Zweryfikuj limit API.')
    return [(kind,total)]


def import_openplay(con,entry,season,comp_override=None):
    try:
        import openplay as op
    except ImportError as e:
        raise SystemExit('Zainstaluj: python -m pip install openplay') from e
    # No guessing of league codes: show official code table and require explicit code if unset.
    comp=comp_override or entry['source_code']
    if not comp:
        print('Kody rozgrywek dostepne w bibliotece openplay:')
        print(op.competitions().to_string(index=False))
        raise SystemExit('Podaj oficjalny kod z powyzszej tabeli: --comp KOD')
    df=op.player_season_stats(comp,season,per90=False)
    if df is None or df.empty:
        raise ValueError('Brak statystyk w op.player_season_stats('+repr(comp)+','+repr(season)+')')
    url='https://github.com/nlbair/openplay/releases'
    n=write_rows(con,entry,'player_season_stats',season,df.to_dict('records'),url)
    return [('player_season_stats',n)]


def import_local_wyscout(con,entry,season,file_path):
    if not file_path:
        raise ValueError('Podaj --file dla zbioru JSON pobranego z oficjalnego figshare')
    path=Path(file_path)
    if path.suffix.lower()!='.json':
        raise ValueError('Obslugiwany format danych historycznych: JSON')
    rows=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(rows,list):
        raise ValueError('Oczekiwano listy zdarzen/wystepow w JSON')
    n=write_rows(con,entry,'historical_json',season,rows,entry['source_url'])
    return [('historical_json',n)]


def main(argv=None):
    p=argparse.ArgumentParser(description='ScoutPro: bezpieczny etap STAGING z jawnie licencjonowanych zrodel.')
    p.add_argument('--list',action='store_true',help='Wyswietl liste zrodel, lig i sezonow')
    p.add_argument('--slug',help='Slug z katalogu, np. openfootball-poland-pl1')
    p.add_argument('--season',help='Sezon (dla ASA np. 2025, openplay 2024/25, OpenFootball 2024-25)')
    p.add_argument('--kind',default='xgoals',help='ASA: players|teams|xgoals|xpass|goals-added')
    p.add_argument('--comp',help='Oficjalny kod rozgrywek openplay odczytany z op.competitions()')
    p.add_argument('--file',help='Sciezka do oryginalnego pliku JSON Wyscout z figshare')
    p.add_argument('--db',default='database/scoutpro_sources.db',help='ODDZIELNA baza staging, bez modyfikowania scoutpro.db')
    args=p.parse_args(argv)
    entries=read_catalog()['leagues']
    if args.list:
        for x in entries:
            print(f"{x['slug']:<41} {x['competition']:<36} {x['season']:<23} {x['license']}")
        return 0
    if not args.slug: p.error('Podaj --slug lub --list')
    entry=next((x for x in entries if x['slug']==args.slug),None)
    if entry is None: p.error('Brak --slug w legalnym katalogu; sprawdz --list')
    if entry['provider']=='openfootball_austria':
        raise SystemExit('OpenFootball Austria: wybierz konkretny plik sezonowy z repozytorium; nie ma automatycznego URL w katalogu.')
    if entry['provider'] in ('openplay', 'wyscout_open'):
        raise SystemExit('Import źródła wstrzymany: niepotwierdzone uprawnienia do danych pierwotnych. Użyj OpenFootball CC0 lub ASA CC BY-SA.')
    season=args.season or entry['season']
    if 'do wyboru' in season or 'historyczny' in season:
        raise SystemExit('Podaj rzeczywisty sezon przez --season (sprawdz katalog wydawcy)')
    if entry['provider']=='openplay' and ('–' in season or ',' in season):
        raise SystemExit('Podaj JEDEN sezon openplay, np. --season 2024/25')
    db=Path(args.db)
    if db.name.lower()=='scoutpro.db':
        raise SystemExit('Nie wolno nadpisac produkcyjnej bazy scoutpro.db. Uzyj scoutpro_sources.db')
    db.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db) as con:
        init_db(con)
        print('Import:',entry['competition'],'|',entry['provider'],'|',season,'|',entry['license'])
        if entry['provider']=='openfootball': out=import_openfootball(con,entry,season)
        elif entry['provider']=='asa': out=import_asa(con,entry,season,args.kind)
        elif entry['provider']=='openplay': out=import_openplay(con,entry,season,args.comp)
        elif entry['provider']=='wyscout_open': out=import_local_wyscout(con,entry,season,args.file)
        else: raise SystemExit('Obslugiwany typ zrodla nie ma importera.')
    print('Zapisano do',db,':',out)
    print('UWAGA: rekordy sa surowe. Ich nie mozna bez normalizacji laczyc z obecnym ScoutScore.')
    return 0

if __name__=='__main__':
    sys.exit(main())
