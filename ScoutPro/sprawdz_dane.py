
import sqlite3

conn = sqlite3.connect("database/scoutpro.db")
cursor = conn.cursor()

tabele = [
    "uslc_xgoals_2025",
    "uslc_xpass_2025",
    "uslc_goals_added_2025"
]

for tabela in tabele:
    print(f"\n=== {tabela} ===")

    cursor.execute(f"PRAGMA table_info({tabela})")
    kolumny = [row[1] for row in cursor.fetchall()]

    print("Kolumny:", kolumny)

    cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
    print("Liczba rekordów:", cursor.fetchone()[0])

conn.close()
