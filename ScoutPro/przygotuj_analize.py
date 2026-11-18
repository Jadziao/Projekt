
import sqlite3
import json
import requests
import pandas as pd

conn = sqlite3.connect("database/scoutpro.db")

dane = pd.read_sql_query(
    "SELECT * FROM PlayerStats2025_Pelne", conn
)

def popraw_id(wartosc):
    if pd.isna(wartosc):
        return ""

    tekst = str(wartosc).strip()

    try:
        wynik = json.loads(tekst)
        if isinstance(wynik, str):
            tekst = wynik
    except (ValueError, TypeError):
        pass

    return tekst.strip()


wszystkie = []

for liga in ["mls", "uslc", "usl1"]:
    print(f"\nLiga: {liga.upper()}")

    stats = dane[dane["liga"] == liga.upper()].copy()
    stats["player_id"] = stats["player_id"].apply(popraw_id)

    url = (
        "https://app.americansocceranalysis.com"
        f"/api/v1/{liga}/players"
    )

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    gracze = pd.DataFrame(response.json())
    gracze["player_id"] = gracze["player_id"].apply(popraw_id)

    for kolumna in ["birth_date", "nationality"]:
        if kolumna not in gracze.columns:
            gracze[kolumna] = None

    gracze = gracze[
        ["player_id", "birth_date", "nationality"]
    ].drop_duplicates("player_id")

    stats = stats.merge(
        gracze,
        on="player_id",
        how="left",
        validate="many_to_one"
    )

    # Wiek na koniec sezonu 2025
    daty = pd.to_datetime(
        stats["birth_date"], errors="coerce"
    )

    stats["wiek_2025"] = 2025 - daty.dt.year
    stats.loc[
        daty.dt.year > 2025, "wiek_2025"
    ] = None

    # Statystyki na 90 minut
    stats["minutes_played"] = pd.to_numeric(
        stats["minutes_played"], errors="coerce"
    )

    minuty = stats["minutes_played"].where(
        stats["minutes_played"] > 0
    )

    kolumny = [
        "goals",
        "primary_assists",
        "xgoals",
        "xassists",
        "shots",
        "key_passes"
    ]

    for kolumna in kolumny:
        if kolumna in stats.columns:
            liczby = pd.to_numeric(
                stats[kolumna], errors="coerce"
            )

            stats[kolumna + "_90"] = (
                liczby / minuty * 90
            ).round(3)

    print("Rekordy:", len(stats))
    print("Znany wiek:", stats["wiek_2025"].notna().sum())
    print("Wiek do 21 lat:",
          (stats["wiek_2025"] <= 21).sum())

    wszystkie.append(stats)

wynik = pd.concat(wszystkie, ignore_index=True)

wynik.to_sql(
    "PlayerAnalysis2025",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

print("\nGOTOWE!")
print("Rekordy:", len(wynik))
print("Utworzono tabele PlayerAnalysis2025")
