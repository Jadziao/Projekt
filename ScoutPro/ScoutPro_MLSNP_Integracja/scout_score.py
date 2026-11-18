"""ScoutPro ScoutScore 2025: oryginalna metoda, rozszerzona o MLS Next Pro.

Wagi i minimum 450 minut oraz minimum 70% dostepnych wag - bez zmian.
GK nie sa jeszcze oceniani. Porownania wykonywane w obrebie ligi i grupy.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import sqlite3
from pathlib import Path

import pandas as pd

POZYCJE = {"ST": "Atak", "W": "Atak", "AM": "Pomoc", "CM": "Pomoc", "DM": "Pomoc", "CB": "Obrona", "FB": "Obrona"}
WAGI = {
    "Atak": {"xgoals_90": 0.30, "xassists_90": 0.20, "shots_on_target_90": 0.20, "gplus_above_avg_90": 0.30},
    "Pomoc": {"xassists_90": 0.20, "key_passes_90": 0.15, "passes_completed_over_expected_p100": 0.30, "gplus_above_avg_90": 0.35},
    "Obrona": {"gplus_interrupting_90": 0.40, "gplus_above_avg_90": 0.30, "passes_completed_over_expected_p100": 0.30},
}


def policz_i_zapisz(db_path: Path | str, verbose: bool = True):
    db_path = Path(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        dane = pd.read_sql_query("SELECT * FROM PlayerAnalysis2025_GPlus", conn)
        dane["grupa"] = dane["general_position"].map(POZYCJE)
        dane["minutes_played"] = pd.to_numeric(dane["minutes_played"], errors="coerce")
        dane["wiek_2025"] = pd.to_numeric(dane["wiek_2025"], errors="coerce")
        dane["ScoutScore"] = float("nan")
        # Tylko dodajemy MLSNP; poza tym to oryginalny algorytm.
        for liga in ["MLS", "USLC", "USL1", "MLSNP"]:
            for grupa, statystyki in WAGI.items():
                maska = ((dane["liga"] == liga) & (dane["grupa"] == grupa) & (dane["minutes_played"] >= 450))
                indeksy = dane.index[maska]
                if len(indeksy) < 10:
                    continue
                suma = pd.Series(0.0, index=indeksy)
                suma_wag = pd.Series(0.0, index=indeksy)
                for kolumna, waga in statystyki.items():
                    if kolumna not in dane.columns:
                        continue
                    wartosci = pd.to_numeric(dane.loc[indeksy, kolumna], errors="coerce")
                    percentyl = wartosci.rank(pct=True) * 100
                    suma += percentyl.fillna(0) * waga
                    suma_wag += wartosci.notna() * waga
                wynik = suma / suma_wag.where(suma_wag >= 0.69)
                dane.loc[indeksy, "ScoutScore"] = wynik.round(1)
        dane.to_sql("PlayerScoutScore2025", conn, if_exists="replace", index=False)
        conn.commit()
    if verbose:
        print("GOTOWE! Wierszy:", len(dane))
        print("Z oceną ScoutScore:", int(dane["ScoutScore"].notna().sum()))
        print("MLS Next Pro:", int(dane["liga"].eq("MLSNP").sum()))
        mlodzi = dane[(dane["wiek_2025"] <= 21) & (dane["ScoutScore"].notna())]
        print("Ocenieni zawodnicy U21:", len(mlodzi))
        print(mlodzi.sort_values("ScoutScore", ascending=False)[["player_name", "team_name", "liga", "general_position", "wiek_2025", "ScoutScore"]].head(10).to_string(index=False))
    return dane


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Przelicz ScoutScore w wskazanej bazie.")
    ap.add_argument("--db", type=Path, default=Path("database/scoutpro.db"))
    args = ap.parse_args()
    policz_i_zapisz(args.db)
