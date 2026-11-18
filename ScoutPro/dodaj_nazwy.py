
import sqlite3
import requests
import pandas as pd

conn = sqlite3.connect("database/scoutpro.db")

ligi = ["mls", "uslc", "usl1"]
wszystkie = []

base_url = "https://app.americansocceranalysis.com/api/v1"

def pobierz(liga, rodzaj):
    rekordy = []
    offset = 0

    while True:
        url = f"{base_url}/{liga}/{rodzaj}"

        response = requests.get(
            url,
            params={"offset": offset},
            timeout=30
        )
        response.raise_for_status()

        dane = response.json()

        if not dane:
            break

        rekordy.extend(dane)

        if len(dane) < 1000:
            break

        offset += 1000

    return pd.DataFrame(rekordy)


for liga in ligi:
    print(f"\nLiga: {liga.upper()}")

    # Pobieramy nazwiska i nazwy klubow
    players = pobierz(liga, "players")
    teams = pobierz(liga, "teams")

    players = players[
        ["player_id", "player_name"]
    ].drop_duplicates("player_id")

    teams = teams[
        ["team_id", "team_name"]
    ].drop_duplicates("team_id")

    # Pobieramy statystyki z naszej bazy
    stats = pd.read_sql_query(
        "SELECT * FROM PlayerStats2025 WHERE liga = ?",
        conn,
        params=(liga.upper(),)
    )

    # Dodajemy nazwiska
    stats = stats.merge(
        players,
        on="player_id",
        how="left",
        validate="many_to_one"
    )

    # Dodajemy nazwy klubow
    stats = stats.merge(
        teams,
        on="team_id",
        how="left",
        validate="many_to_one"
    )

    print("Rekordy:", len(stats))
    print("Nazwiska:", stats["player_name"].notna().sum())
    print("Nazwy klubow:", stats["team_name"].notna().sum())

    wszystkie.append(stats)

# Laczymy wszystkie ligi
wynik = pd.concat(wszystkie, ignore_index=True)

# Zapisujemy jako nowa tabele
wynik.to_sql(
    "PlayerStats2025_Pelne",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

print("\nGOTOWE!")
print("Laczna liczba rekordow:", len(wynik))
print("Zapisano tabele PlayerStats2025_Pelne")
