# ScoutPro V4 — pełny projekt z MLS Next Pro

To jest **cały gotowy folder projektu**, a nie aktualizacja do ręcznej podmiany.
Możesz rozpakować go obok starszego folderu ScoutPro. Nowy folder nazywa się `ScoutPro_Gotowy`.

## Start na Windows

1. Rozpakuj ZIP do wybranej lokalizacji (np. `Dokumenty`), tak aby mieć folder `ScoutPro_Gotowy`.
2. Otwórz folder i kliknij dwukrotnie **`START_SCOUTPRO.bat`**.
3. Przy pierwszym uruchomieniu skrypt automatycznie tworzy `.venv` i instaluje biblioteki (wymaga internetu).
4. Gdy Streamlit wystartuje, otwórz w przeglądarce adres pokazany w konsoli, zwykle `http://localhost:8501`.

Z terminala PowerShell też możesz uruchomić aplikację ręcznie (po pierwszym starcie):

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Co zawiera projekt

- Główną aplikację `app.py` z nowym wyglądem **Bold Type V4** i modułami Dashboard, Zawodnicy, Profil, Ligi Europy, Porównania, Talenty, Obserwowani, Raporty AI, Ustawienia.
- Style `styles.css`, `bold-theme.css`, elementy `assets/` i konfigurację `.streamlit`.
- Zintegrowaną bazę `database/scoutpro_mlsnp_2025_gotowe_v2.db` dla **MLS, USLC, USL1 i MLS Next Pro**.
- Oryginalną bazę `database/scoutpro.db`, bazę pobranych źródeł `scoutpro_sources.db` i bazę obserwowanych `scoutpro_user.db`.
- Dane CSV, skrypty ETL oraz katalog źródeł/licencji.

## Dlaczego w ZIP nie ma `.venv`?

Środowisko `.venv` jest przypisane do instalacji Pythona i lokalnych ścieżek Windows; przeniesione do nowego folderu bywa niesprawne. Dlatego `START_SCOUTPRO.bat` odtworzy je automatycznie, bez ręcznej instalacji i podmieniania plików.

## Kontrola danych

```powershell
python sprawdz_projekt.py
```

Zintegrowana baza zawiera 2865 profili, w tym 1033 w MLS Next Pro; 545 z nich ma wyliczony ScoutScore. Oceny porównujemy tylko w obrębie lig i grup pozycyjnych, a brakującą ocenę pokazujemy jako `—`.

## Dodatkowe uwagi

- Raporty z wykorzystaniem lokalnego Qwen wymagają osobno uruchomionego Ollama; podstawowe raporty statystyczne działają bez niego.
- Skrypty importu/ETL mogą wymagać dodatkowych bibliotek z `requirements_import_data.txt`.
- Starszego folderu ScoutPro nie trzeba usuwać ani zmieniać; nowy projekt przechowuje własne bazy.
- W źródłach znajdują się odnośniki i uwagi o licencjach danych. Dla ASA obowiązuje CC BY-SA 4.0 — zachowuj informacje o źródle przy dalszym wykorzystaniu.
- Przetestowano składnię plików i integralność SQLite. Uruchomienie całego interfejsu Streamlit w przeglądarce sprawdź lokalnie.


## Nowość: Ligi Europy (CC0)

W menu jest nowa zakładka **Ligi Europy**. Wyniki Ekstraklasy 2024/25 są już dostępne z przesłanej wcześniej bazy.
Aby jednorazowo dodać Polską 1. ligę, czeską 1. i 2. ligę, Słowację, Węgry i Chorwację:

1. Uruchom `IMPORTUJ_LIGI_EUROPY.bat` (wymaga internetu).
2. Po komunikacie `OK` odśwież aplikację Streamlit.

Możesz również użyć:

```powershell
.\.venv\Scripts\python.exe importuj_ligi_europy.py
.\.venv\Scripts\python.exe importuj_ligi_europy.py --only openfootball-czech-republic-cz1
```

Importer nie zmienia bazy ScoutScore. Dla lig europejskich pokazywane są wyłącznie wyniki, bilans klubów i terminarz; brak statystyk zawodników. Wszystkie siedem wskazanych źródeł jest opisanych w katalogu `ScoutPro_Legalne_Zrodla/scoutpro_legal_catalog.json` i mają deklarowaną licencję CC0 1.0.

**Ważne:** Wstrzymaliśmy import openplay mimo deklarowanej CC BY 4.0 — prawa do danych pierwotnych nie zostały wystarczająco wyjaśnione.
