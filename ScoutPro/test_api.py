
from itscalledsoccer.client import AmericanSoccerAnalysis

api = AmericanSoccerAnalysis()

try:
    dane = api.get_player_xgoals(
        leagues="uslc",
        season_name="2025"
    )

    print("Pobieranie danych zakończone!")
    print("Liczba rekordów:", len(dane))
    print(dane.head(5))

except Exception as e:
    print("Błąd:", e)
