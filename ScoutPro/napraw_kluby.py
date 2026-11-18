
import sqlite3
import json
import requests
import pandas as pd

conn = sqlite3.connect("database/scoutpro.db")

dane = pd.read_sql_query(
    "SELECT * FROM PlayerStats2025_Pelne",
    conn
)

# Usuwamy stara, pusta kolumne z nazwami klubow
dane = dane.drop(columns=["team_name"], errors="ignore")

def popraw_id(wartosc):
    if pd.isna(wartosc):
        return None

    tekst = str(wartosc).strip()

    # Usuwamy dodatkowe cudzyslowy z JSON
    if tekst.startswith('"') and tekst.endswith('"'):
        try:
            tekst = json.loads(tekst)
        except json.JSONDecodeError:
            pass

    return str(tekst).strip()

wyniki = []

for liga in ["mls", "uslc", "usl1"]:
    print(f"\nLiga: {liga.upper()}")

    statystyki = dane[
        dane["liga"] == liga.upper()
    ].copy()

    url = f"https://app.americansocceranalysis.com/api/v1/{liga}/teams"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    kluby = pd.DataFrame(response.json())

    statystyki["id_klubu"] = (
        statystyki["team_id"].apply(popraw_id)
    )

    kluby["id_klubu"] = (
        kluby["team_id"].apply(popraw_id)
    )

    kluby = kluby[
        ["id_klubu", "team_name"]
    ].drop_duplicates("id_klubu")

    statystyki = statystyki.merge(
        kluby,
        on="id_klubu",
        how="left",
        validate="many_to_one"
    )

    statystyki = statystyki.drop(columns=["id_klubu"])

    dopasowane = statystyki["team_name"].notna().sum()

    print("Zawodnicy:", len(statystyki))
    print("Dopasowane kluby:", dopasowane)

    if dopasowane == 0:
        print("Przykladowe ID z bazy:")
        print(statystyki["team_id"].head(3).tolist())
        print("Przykladowe ID z API:")
        print(kluby["id_klubu"].head(3).tolist())

    wyniki.append(statystyki)

wynik = pd.concat(wyniki, ignore_index=True)

dopasowane = wynik["team_name"].notna().sum()

if dopasowane > 0:
    wynik.to_sql(
        "PlayerStats2025_Pelne",
        conn,
        if_exists="replace",
        index=False
    )

    print("\nGOTOWE!")
    print("Wszystkie rekordy:", len(wynik))
    print("Dopasowane kluby:", dopasowane)
    print("Brakujace kluby:", len(wynik) - dopasowane)
else:
    print("\nBrak dopasowan. Baza nie zostala zmieniona.")

conn.close()
