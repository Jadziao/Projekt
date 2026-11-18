
from itscalledsoccer.client import AmericanSoccerAnalysis

api = AmericanSoccerAnalysis()

dane = api.get_player_goals_added(
    leagues="uslc",
    season_name="2025"
)

print("Liczba rekordow:", len(dane))
print("Kolumny:", dane.columns)
print("Typ danych g+:", dane.schema["data"])

print("\nPrzyklad danych:")
print(dane.select(["player_id", "data"]).head(1))

try:
    rozbite = dane.explode("data").unnest("data")

    print("\nRozwiniete kolumny:")
    print(rozbite.columns)

    print("\nPrzykladowe rekordy:")
    print(rozbite.head(5))

except Exception as e:
    print("Blad rozwijania:", e)
