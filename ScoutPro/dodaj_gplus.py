
import sqlite3
import json
import requests
import pandas as pd

conn = sqlite3.connect("database/scoutpro.db")

baza = pd.read_sql_query(
    "SELECT * FROM PlayerAnalysis2025", conn
)

def popraw_id(wartosc):
    if wartosc is None:
        return None

    tekst = str(wartosc).strip()

    for _ in range(2):
        try:
            wynik = json.loads(tekst)
            if isinstance(wynik, str):
                tekst = wynik.strip()
            else:
                break
        except (ValueError, TypeError):
            break

    return tekst


baza["player_id"] = baza["player_id"].apply(popraw_id)

klucze = ["liga", "player_id"]

# Sprawdzamy, czy zawodnicy sa unikalni
duplikaty = baza.duplicated(klucze).sum()

if duplikaty > 0:
    conn.close()
    raise SystemExit(
        f"Znaleziono {duplikaty} duplikatow. "
        "Trzeba sprawdzic dane przed polaczeniem."
    )

wszystkie = []

for liga in ["mls", "uslc", "usl1"]:
    print(f"\nLiga: {liga.upper()}")

    rekordy = []
    offset = 0

    while True:
        url = (
            "https://app.americansocceranalysis.com"
            f"/api/v1/{liga}/players/goals-added"
        )

        response = requests.get(
            url,
            params={
                "season_name": "2025",
                "offset": offset
            },
            timeout=60
        )
        response.raise_for_status()

        paczka = response.json()
        rekordy.extend(paczka)

        if len(paczka) < 1000:
            break

        offset += 1000

    print("Pobrano zawodnikow g+:", len(rekordy))

    # Rozdzielamy rodzaje akcji
    for rekord in rekordy:
        player_id = popraw_id(rekord.get("player_id"))

        for akcja in rekord.get("data", []) or []:
            if not isinstance(akcja, dict):
                continue

            wszystkie.append({
                "liga": liga.upper(),
                "player_id": player_id,
                "action_type": akcja.get("action_type"),
                "goals_added_raw": akcja.get("goals_added_raw"),
                "goals_added_above_avg": akcja.get(
                    "goals_added_above_avg"
                ),
                "count_actions": akcja.get("count_actions")
            })


if not wszystkie:
    conn.close()
    raise SystemExit("Nie pobrano danych Goals Added.")

dane = pd.DataFrame(wszystkie)

# Konwersja statystyk na liczby
for kolumna in [
    "goals_added_raw",
    "goals_added_above_avg",
    "count_actions"
]:
    dane[kolumna] = pd.to_numeric(
        dane[kolumna], errors="coerce"
    )

# Suma g+ dla zawodnika
suma = dane.groupby(klucze, as_index=False).agg(
    gplus_total=("goals_added_raw", "sum"),
    gplus_above_avg=("goals_added_above_avg", "sum"),
    gplus_actions=("count_actions", "sum")
)

# G+ w podziale na rodzaj akcji
kategorie = (
    dane.groupby(klucze + ["action_type"])[
        "goals_added_above_avg"
    ]
    .sum(min_count=1)
    .unstack("action_type")
    .reset_index()
)

kategorie.columns = [
    kol if kol in klucze
    else "gplus_" + str(kol).lower().replace(" ", "_")
    for kol in kategorie.columns
]

suma = suma.merge(
    kategorie,
    on=klucze,
    how="left",
    validate="one_to_one"
)

# Laczymy z baza zawodnikow
wynik = baza.merge(
    suma,
    on=klucze,
    how="left",
    validate="one_to_one"
)

if len(wynik) != len(baza):
    conn.close()
    raise SystemExit("Blad liczby rekordow!")

# Statystyki na 90 minut
minuty = pd.to_numeric(
    wynik["minutes_played"], errors="coerce"
)

minuty = minuty.where(minuty > 0)

kolumny_gplus = [
    "gplus_total",
    "gplus_above_avg"
] + [
    kol for kol in wynik.columns
    if kol.startswith("gplus_")
    and kol not in [
        "gplus_total",
        "gplus_above_avg",
        "gplus_actions"
    ]
]

for kolumna in kolumny_gplus:
    wynik[kolumna + "_90"] = (
        wynik[kolumna] / minuty * 90
    ).round(4)

dopasowane = wynik["gplus_total"].notna().sum()

if dopasowane == 0:
    conn.close()
    raise SystemExit("Nie dopasowano danych g+!")

# Zapis nowej tabeli
wynik.to_sql(
    "PlayerAnalysis2025_GPlus",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

print("\nGOTOWE!")
print("Wszystkie rekordy:", len(wynik))
print("Dopasowane g+:", dopasowane)
print("Brakujace g+:", len(wynik) - dopasowane)
print("Liczba kolumn:", len(wynik.columns))
print("Utworzono tabele PlayerAnalysis2025_GPlus")
