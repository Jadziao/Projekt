"""Sprawdzenie kompletności aplikacji i baz danych bez ich modyfikacji."""
from pathlib import Path
import ast
import sqlite3

ROOT = Path(__file__).resolve().parent
NEEDED = ["app.py", "styles.css", "scoutpro_profile.py", "scoutpro_watchlist.py", "scoutpro_players.py", "scoutpro_reports.py", "scoutpro_talents.py", "scoutpro_comparisons.py", "scoutpro_bold_home.py", "scoutpro_common.py", "database/scoutpro_mlsnp_2025_gotowe_v2.db", "database/scoutpro_user.db"]

def main():
    missing = [p for p in NEEDED if not (ROOT / p).is_file()]
    if missing:
        raise SystemExit("Brakuje plików: " + ", ".join(missing))
    for p in ROOT.rglob("*.py"):
        if ".venv" in p.parts:
            continue
        ast.parse(p.read_text(encoding="utf-8-sig"), filename=str(p))
    db = ROOT / "database" / "scoutpro_mlsnp_2025_gotowe_v2.db"
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as con:
        chk = con.execute("PRAGMA integrity_check").fetchone()[0]
        if chk != "ok":
            raise SystemExit("Błąd integralności bazy: " + chk)
        print("Dane w bazie (liga: profile / ScoutScore):")
        for league, cnt, score in con.execute("SELECT liga, COUNT(*), COUNT(ScoutScore) FROM PlayerScoutScore2025 GROUP BY liga ORDER BY liga"):
            print(f"  {league}: {cnt} / {score}")
    print("OK: pliki, składnia Pythona i integralność głównej bazy.")

if __name__ == "__main__":
    main()
