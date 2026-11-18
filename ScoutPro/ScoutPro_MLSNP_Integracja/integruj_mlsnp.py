"""ScoutPro: bezpieczne polaczenie MLS Next Pro (ASA, CC BY-SA 4.0) z baza 2025.

Wynik ZAWSZE tworzy nowa baze. Oryginalne scoutpro.db i scoutpro_sources.db
nigdy nie sa modyfikowane. Brakujacych nazw ani wieku nie zgadujemy.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import math
import sqlite3
import sys
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

API = "https://app.americansocceranalysis.com/api/v1/mlsnp"
KIND_NAMES = ("xgoals", "xpass", "goals-added")
ACTION_NAMES = ("Dribbling", "Fouling", "Interrupting", "Passing", "Receiving", "Shooting")


def good(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v)) and str(v).strip() not in ("", "None", "nan")


def number(v):
    if not good(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def rate(value, mins, precision=3):
    n, m = number(value), number(mins)
    return round(n * 90 / m, precision) if n is not None and m is not None and m > 0 else None


def get_nested_rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "records"):
            if isinstance(payload.get(key), list):
                return payload[key]
        if "player_id" in payload or "team_id" in payload:
            return [payload]
    raise ValueError("Nieznany format odpowiedzi API (oczekiwano listy rekordow).")


def fetch_asa(path):
    # Systemowy magazyn certyfikatow Windows; bez wylaczania weryfikacji TLS.
    try:
        import truststore
    except ImportError as exc:
        raise RuntimeError("Brak truststore. Zainstaluj: python -m pip install truststore") from exc
    truststore.inject_into_ssl()
    rows = []
    for page in range(100):
        offset = page * 1000
        url = f"{API}/{path}?offset={offset}"
        req = urllib.request.Request(url, headers={"User-Agent": "ScoutPro-research/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            part = get_nested_rows(json.load(r))
        rows.extend(part)
        print(f"  {path}: strona {page + 1} - {len(part)} rekordow")
        if len(part) < 1000:
            return rows
    raise RuntimeError("API zwrocilo ponad 100 stron; przerwano dla bezpieczenstwa")


def load_cached_metadata(path: Path, offline: bool, refresh: bool):
    if path.exists() and not refresh:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(cached.get("players"), list) and isinstance(cached.get("teams"), list):
            print(f"Metadane: pamiec lokalna ({path})")
            return cached
    if offline:
        print("Tryb offline: bez zapytan o nazwiska i kluby; uzywam tylko znanych identyfikatorow.")
        return {"players": [], "teams": []}
    print("Pobieram oficjalne nazwy zawodnikow i klubow z ASA:")
    data = {"players": fetch_asa("players"), "teams": fetch_asa("teams")}
    if not data["players"] or not data["teams"]:
        raise RuntimeError("API nie zwrocilo listy zawodnikow lub klubow; przerwano bez zapisu.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)
    return data


def fetch_source_rows(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Nie ma bazy ze zrodlami: {path}")
    con = sqlite3.connect(path)
    try:
        if not con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='source_records'").fetchone():
            raise ValueError("Brak tabeli source_records w bazie ze zrodlami")
        kinds = {}
        for kind in KIND_NAMES:
            raw = con.execute("""SELECT payload, license, source_url FROM source_records
                WHERE source='asa' AND league_key='asa-mlsnp' AND season='2025' AND kind=?""", (kind,)).fetchall()
            if not raw:
                raise ValueError(f"Brak importu: MLS Next Pro / 2025 / {kind}")
            if any(license_ != "CC BY-SA 4.0" or "americansocceranalysis.com" not in url for _, license_, url in raw):
                raise ValueError(f"Niespojne informacje o licencji lub zrodle dla {kind}")
            rows = {}
            for content, _, _ in raw:
                item = json.loads(content)
                pid = item.get("player_id")
                if not good(pid):
                    raise ValueError(f"Rekord {kind} bez player_id")
                if pid in rows and rows[pid] != item:
                    raise ValueError(f"Dwa rozne rekordy {kind} tego samego gracza {pid}; import trzeba sprawdzic")
                rows[pid] = item
            kinds[kind] = rows
            print(f"  {kind}: {len(rows)} unikalnych zawodnikow")
        if set(kinds["xgoals"]) != set(kinds["xpass"]):
            print("UWAGA: nie wszyscy zawodnicy maja oba zbiory xgoals/xpass")
        return kinds
    finally:
        con.close()


def old_people(df):
    """Fallback tylko po identycznym, stabilnym player_id. Bez dopasowania po nazwie."""
    known = {}
    for row in df.to_dict("records"):
        pid = row.get("player_id")
        if good(pid) and good(row.get("player_name")):
            known.setdefault(str(pid), row)
    return known


def meta_indices(meta):
    players = {str(p["player_id"]): p for p in meta["players"] if isinstance(p, dict) and good(p.get("player_id"))}
    teams = {str(t["team_id"]): t for t in meta["teams"] if isinstance(t, dict) and good(t.get("team_id"))}
    return players, teams


def tid_list(v):
    if isinstance(v, list):
        return [str(x) for x in v if good(x)]
    return [str(v)] if good(v) else []


def join_team_names(tids, meta_teams, known_team_names):
    names = []
    for tid in tids:
        entry = meta_teams.get(tid, {})
        n = entry.get("team_name") or known_team_names.get(tid)
        if good(n) and str(n) not in names:
            names.append(str(n))
    return " / ".join(names) if len(names) == len(tids) and names else None


def derive_age(birthdate):
    if not good(birthdate):
        return None
    try:
        # Tak jak w starej bazie: 2025 - rok urodzenia (wiek sezonowy, nie wiek w dniu meczu).
        year = int(str(birthdate)[:4])
        return float(2025 - year) if 1940 <= year <= 2025 else None
    except (TypeError, ValueError):
        return None


def compute_row(pid, types, main_cols, meta_players, meta_teams, known_p, known_team_names):
    xg = types["xgoals"].get(pid, {})
    xp = types["xpass"].get(pid, {})
    ga = types["goals-added"].get(pid, {})
    primary = xg or xp or ga
    mins = number(primary.get("minutes_played"))
    teams = tid_list(primary.get("team_id"))
    if not teams:
        teams = tid_list(xp.get("team_id"))
    pmeta = meta_players.get(pid, {})
    old = known_p.get(pid, {})
    # Dane o graczu: preferuj oficjalne metadane, potem stara baze po player_id.
    pname = pmeta.get("player_name") or old.get("player_name")
    birth = pmeta.get("birth_date") or old.get("birth_date")
    nationality = pmeta.get("nationality") or old.get("nationality")
    team_name = join_team_names(teams, meta_teams, known_team_names)
    if not team_name:
        # Jesli nie ma metadanych klubowych, NIE kopiuj klubu z MLS na MLSNP.
        team_name = None

    row = {c: None for c in main_cols}
    row.update({
        "player_id": pid,
        "team_id": json.dumps(teams[0] if len(teams) == 1 else teams, ensure_ascii=False),
        "liga": "MLSNP", "sezon": 2025,
        "general_position": primary.get("general_position"),
        "minutes_played": int(mins) if mins is not None else None,
        "player_name": pname if good(pname) else None,
        "team_name": team_name,
        "birth_date": birth if good(birth) else None,
        "nationality": nationality if good(nationality) else None,
        "wiek_2025": derive_age(birth),
    })
    for k in xg:
        if k in row and k not in ("player_id", "team_id", "general_position", "minutes_played"):
            row[k] = xg[k]
    for k in xp:
        if k in row and k not in ("player_id", "team_id", "general_position", "minutes_played"):
            row[k] = xp[k]
    for raw, per90 in (("goals", "goals_90"), ("primary_assists", "primary_assists_90"),
                       ("xgoals", "xgoals_90"), ("xassists", "xassists_90"),
                       ("shots", "shots_90"), ("key_passes", "key_passes_90")):
        if per90 in row:
            row[per90] = rate(row.get(raw), mins)
    # Goals Added - sumujemy te same kategorie i pola, co w obecnej bazie.
    actions = ga.get("data") if isinstance(ga.get("data"), list) else []
    by_type = {a.get("action_type"): a for a in actions if isinstance(a, dict)}
    if actions:
        row["goals_added_data"] = json.dumps(actions, ensure_ascii=False)
        row["gplus_total"] = round(sum(number(a.get("goals_added_raw")) or 0 for a in actions), 4)
        row["gplus_above_avg"] = round(sum(number(a.get("goals_added_above_avg")) or 0 for a in actions), 4)
        row["gplus_actions"] = sum(int(number(a.get("count_actions")) or 0) for a in actions)
        if "gplus_total_90" in row:
            row["gplus_total_90"] = rate(row["gplus_total"], mins, 4)
        if "gplus_above_avg_90" in row:
            row["gplus_above_avg_90"] = rate(row["gplus_above_avg"], mins, 4)
        for action in ACTION_NAMES:
            name = "gplus_" + action.lower()
            if name in row:
                row[name] = number(by_type[action].get("goals_added_above_avg")) if action in by_type else None
            if name + "_90" in row:
                row[name + "_90"] = rate(row.get(name), mins, 4)
    return row


def validate_snapshot(main: Path, output: Path, offline: bool, overwrite: bool, metadata: dict, kinds: dict):
    if not main.is_file():
        raise FileNotFoundError(f"Brak glownej bazy danych: {main}")
    if main.resolve() == output.resolve():
        raise ValueError("Nie wolno nadpisac oryginalnej bazy; podaj osobny plik --output")
    # Nie nadpisujemy istniejacego wyniku ani nie wykonujemy os.replace/Path.replace.
    # Stara wersja pozostawiala otwarte polaczenia SQLite i Windows blokowal rename.
    if output.exists():
        raise FileExistsError(
            f"Plik {output} juz istnieje. Uzyj innej nazwy --output, "
            "np. database/scoutpro_mlsnp_2025_gotowe_v3.db"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        # closing zamyka polaczenia (zwykly `with sqlite3.connect` tylko commit/rollback!).
        with closing(sqlite3.connect(main)) as source, closing(sqlite3.connect(output)) as target:
            source.backup(target)
        with closing(sqlite3.connect(output)) as con:
            old = pd.read_sql_query("SELECT * FROM PlayerAnalysis2025_GPlus", con)
            main_cols = list(old.columns)
            base_count = len(old[old["liga"].astype(str) != "MLSNP"])
            known = old_people(old)
            team_names = {}
            for r in old.to_dict("records"):
                if good(r.get("team_id")) and good(r.get("team_name")):
                    try:
                        tv = json.loads(str(r["team_id"]))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        tv = str(r["team_id"])
                    for tid in tid_list(tv):
                        team_names.setdefault(tid, r["team_name"])
            players, teams = meta_indices(metadata)
            ids = sorted(set().union(*(set(x.keys()) for x in kinds.values())))
            new_rows = [compute_row(pid, kinds, main_cols, players, teams, known, team_names) for pid in ids]
            new_df = pd.DataFrame(new_rows, columns=main_cols)
            new_df["name_ready"] = new_df["player_name"].notna().astype(int)
            new_df["team_ready"] = new_df["team_name"].notna().astype(int)
            new_df["source_provider"] = "American Soccer Analysis"
            new_df["source_license"] = "CC BY-SA 4.0"
            new_df["source_url"] = API + "/players/xgoals"
            # Staging zawiera WSZYSTKIE rekordy, takze bez metadanych.
            new_df.to_sql("MLSNP_Staging2025", con, if_exists="replace", index=False)
            # Do wyszukiwarki przenosimy tylko zawodnikow z prawdziwymi imionami/nazwiskami.
            ready = new_df[new_df["name_ready"].eq(1)][main_cols].copy()
            combined = pd.concat([old[old["liga"].astype(str) != "MLSNP"], ready], ignore_index=True)
            combined.to_sql("PlayerAnalysis2025_GPlus", con, if_exists="replace", index=False)
            con.commit()
        return base_count, len(new_df), len(ready), int(new_df["team_ready"].sum()), int(new_df["wiek_2025"].notna().sum()), output
    except Exception:
        # Ten plik utworzylo aktualne wywolanie; oryginal jest nietkniety.
        try:
            output.unlink(missing_ok=True)
        except OSError:
            print(f"UWAGA: Nie udalo sie usunac niepelnego pliku {output}", file=sys.stderr)
        raise


def main():
    ap = argparse.ArgumentParser(description="ScoutPro: polacz MLS Next Pro 2025 z obecna baza, zachowujac oryginal.")
    ap.add_argument("--main", type=Path, default=Path("database/scoutpro.db"))
    ap.add_argument("--sources", type=Path, default=Path("database/scoutpro_sources.db"))
    ap.add_argument("--output", type=Path, default=Path("database/scoutpro_mlsnp_2025_gotowe_v2.db"))
    ap.add_argument("--metadata-cache", type=Path, default=Path("database/mlsnp_metadata_2025.json"))
    ap.add_argument("--offline", action="store_true", help="Nie lacz z API; przy nowych graczach brak nazw pozostanie w staging")
    ap.add_argument("--refresh-meta", action="store_true", help="Ponownie pobierz listy players i teams")
    ap.add_argument("--overwrite", action="store_true", help="Przestarzala opcja: ignorowana. Dla bezpieczenstwa nie nadpisujemy istniejacych baz.")
    args = ap.parse_args()

    print("MLS Next Pro 2025 - bezpieczna integracja")
    kinds = fetch_source_rows(args.sources)
    metadata = load_cached_metadata(args.metadata_cache, args.offline, args.refresh_meta)
    before, total, matched, teams, ages, tmp = validate_snapshot(args.main, args.output, args.offline,
                                                                   args.overwrite, metadata, kinds)
    print(f"Dane: {total} graczy w staging, {matched} z imieniem i nazwiskiem, {teams} z klubem, {ages} z wiekiem sezonowym")
    if matched < 100:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Zbyt malo nazw zawodnikow. Baza wynikowa nie powstala; sprawdz metadane API.")
    # Ocena wg dokladnie tej samej funkcji, co dla trzech dotychczasowych lig.
    from scout_score import policz_i_zapisz
    policz_i_zapisz(tmp, verbose=False)
    with closing(sqlite3.connect(tmp)) as cx:
        old_scored = cx.execute("SELECT count(*) FROM PlayerScoutScore2025 WHERE liga <> 'MLSNP' AND ScoutScore IS NOT NULL").fetchone()[0]
        new_scored = cx.execute("SELECT count(*) FROM PlayerScoutScore2025 WHERE liga='MLSNP' AND ScoutScore IS NOT NULL").fetchone()[0]
        ready_count = cx.execute("SELECT count(*) FROM PlayerScoutScore2025 WHERE liga='MLSNP'").fetchone()[0]
        audit = pd.DataFrame([{"liga":"MLSNP", "sezon":2025,"staging":total,"gotowe_profile":ready_count,
            "z_ocena":new_scored,"nazwiska":matched,"kluby":teams,"wiek":ages,
            "source":"American Soccer Analysis", "license":"CC BY-SA 4.0"}])
        audit.to_sql("ScoutPro_DataAudit", cx, if_exists="replace", index=False)
        cx.commit()
    # Zapis bez podmiany pliku; po wyjsciu z closing polaczenie jest zamkniete.
    print(f"Baza oryginalna: {before} zawodnikow - bez zmian")
    print(f"Nowe profile MLSNP: {matched} (z ocenami ScoutScore: {new_scored})")
    print(f"Stare profile z ocenami: {old_scored}")
    print(f"GOTOWE: {args.output}")
    if matched < total:
        print(f"UWAGA: {total-matched} rekordow bez nazw zostalo w MLSNP_Staging2025, nie w wyszukiwarce.")
        if args.offline:
            print("Aby uzupelnic nazwiska z ASA, uruchom bez --offline.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print("BLAD:", exc, file=sys.stderr)
        sys.exit(1)
