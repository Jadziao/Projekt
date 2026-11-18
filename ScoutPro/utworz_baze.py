
from pathlib import Path
import polars as pl
from sqlalchemy import create_engine, text

folder = Path("data")
pliki = sorted(folder.glob("*.csv"))

Path("database").mkdir(exist_ok=True)

engine = create_engine("sqlite:///database/scoutpro.db")

if not pliki:
    print("Brak plików CSV!")
    raise SystemExit(1)

zapisane = 0

for plik in pliki:
    try:
        dane = pl.read_csv(plik, infer_schema_length=0)

        nazwa_tabeli = plik.stem

        dane.write_database(
            table_name=nazwa_tabeli,
            connection=engine,
            if_table_exists="replace"
        )

        print(f"Zapisano: {nazwa_tabeli} ({len(dane)} rekordów)")
        zapisane += 1

    except Exception as e:
        print(f"Błąd dla {plik.name}: {e}")

with engine.connect() as conn:
    wynik = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    tabele = [row[0] for row in wynik]

print(f"\nZapisano {zapisane} z {len(pliki)} plików.")
print(f"Tabele w bazie: {len(tabele)}")

engine.dispose()
