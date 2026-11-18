
import sqlite3
import pandas as pd

conn = sqlite3.connect("database/scoutpro.db")

ligi = ["mls", "uslc", "usl1"]
klucze = ["player_id", "team_id"]

wszystkie_dane = []

for liga in ligi:
    print(f"\nPrzetwarzanie: {liga.upper()}")

    xg = pd.read_sql_query(
        f"SELECT * FROM {liga}_xgoals_2025", conn
    )

    xp = pd.read_sql_query(
        f"SELECT * FROM {liga}_xpass_2025", conn
    )

    ga = pd.read_sql_query(
        f"SELECT * FROM {liga}_goals_added_2025", conn
    )

    # Sprawdzenie identyfikatorow
    for nazwa, dane in [
        ("xGoals", xg),
        ("xPass", xp),
        ("Goals Added", ga)
    ]:
        braki = dane[klucze].isna().any(axis=1).sum()
        duplikaty = dane.duplicated(klucze).sum()

        if braki or duplikaty:
            print(f"{nazwa}: braki={braki}, duplikaty={duplikaty}")
            conn.close()
            raise SystemExit("Sprawdz dane przed polaczeniem.")

    # Wybieramy statystyki podan
    kolumny_xp = klucze + [
        "xpass_completion_percentage",
        "pass_completion_percentage",
        "attempted_passes",
        "passes_completed_over_expected",
        "passes_completed_over_expected_p100",
        "count_games",
        "share_team_touches"
    ]

    xp = xp[kolumny_xp]

    # Dolaczamy statystyki podan
    dane = xg.merge(
        xp,
        on=klucze,
        how="left",
        validate="one_to_one",
        indicator="status_xpass"
    )

    # Dolaczamy Goals Added
    ga = ga[klucze + ["data"]]
    ga = ga.rename(columns={"data": "goals_added_data"})

    dane = dane.merge(
        ga,
        on=klucze,
        how="left",
        validate="one_to_one",
        indicator="status_goals_added"
    )

    print("Zawodnicy:", len(dane))
    print("Dopasowane xPass:",
          (dane["status_xpass"] == "both").sum())
    print("Dopasowane Goals Added:",
          (dane["status_goals_added"] == "both").sum())

    dane = dane.drop(
        columns=["status_xpass", "status_goals_added"]
    )

    dane["liga"] = liga.upper()
    dane["sezon"] = 2025

    wszystkie_dane.append(dane)

# Laczymy trzy ligi
wynik = pd.concat(wszystkie_dane, ignore_index=True)

# Konwersja wybranych statystyk na liczby
kolumny_liczbowe = [
    "minutes_played", "goals", "primary_assists",
    "xgoals", "xassists", "shots",
    "shots_on_target", "key_passes",
    "attempted_passes",
    "xpass_completion_percentage",
    "pass_completion_percentage",
    "passes_completed_over_expected"
]

for kolumna in kolumny_liczbowe:
    wynik[kolumna] = pd.to_numeric(
        wynik[kolumna], errors="coerce"
    )

# Zapis do jednej tabeli
wynik.to_sql(
    "PlayerStats2025",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

print("\nGotowe!")
print("Laczna liczba rekordow:", len(wynik))
print("Liczba kolumn:", len(wynik.columns))
print("Utworzono tabele PlayerStats2025")
