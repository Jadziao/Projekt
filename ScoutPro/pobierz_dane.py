
from pathlib import Path
import json
import polars as pl
from itscalledsoccer.client import AmericanSoccerAnalysis

api = AmericanSoccerAnalysis()

folder = Path("data")
folder.mkdir(exist_ok=True)

ligi = ["mls", "uslc", "usl1"]
sezon = "2025"

statystyki = {
    "xgoals": api.get_player_xgoals,
    "xpass": api.get_player_xpass,
    "goals_added": api.get_player_goals_added
}

def przygotuj_dane(dane):
    for kolumna, typ in dane.schema.items():

        if typ == pl.Object:
            dane = dane.with_columns(
                pl.col(kolumna).map_elements(
                    lambda x: json.dumps(x, default=str),
                    return_dtype=pl.String
                )
            )

        elif isinstance(typ, (pl.List, pl.Struct, pl.Array)):
            dane = dane.with_columns(
                pl.col(kolumna).map_elements(
                    lambda x: json.dumps(x, default=str),
                    return_dtype=pl.String
                )
            )

    return dane


for liga in ligi:
    print(f"\nLiga: {liga.upper()}")

    for nazwa, metoda in statystyki.items():
        try:
            dane = metoda(
                leagues=liga,
                season_name=sezon
            )

            if dane.is_empty():
                print(f"{nazwa}: brak danych")
                continue

            dane = przygotuj_dane(dane)

            sciezka = folder / f"{liga}_{nazwa}_{sezon}.csv"
            dane.write_csv(sciezka)

            print(f"{nazwa}: zapisano {len(dane)} rekordów")

        except Exception as e:
            print(f"Błąd {nazwa}: {e}")

print("\nZakończono pobieranie danych!")
