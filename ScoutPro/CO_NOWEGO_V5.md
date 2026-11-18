# ScoutPro V5 — Ligi Europy (OpenFootball / CC0)

## Co jest gotowe

- Nowa zakładka **Ligi Europy** w menu oraz styl Bold Type zgodny z resztą aplikacji.
- Przegląd meczów, filtrowanie klubów, bilans punktowy, wykresy Plotly i eksport do CSV.
- Dołączona rzeczywista baza **Ekstraklasa 2024/25: 306 meczów** z poprzedniego importu.
- `IMPORTUJ_LIGI_EUROPY.bat` — pobiera 7 rozgrywek: Ekstraklasa, polska 1. liga, czeska 1. i 2. liga, Słowacja, Węgry, Chorwacja (sezon 2024/25).
- Nie trzeba nic kopiować ani podmieniać: to pełny projekt, bez `.venv`.

## Rozróżnienie danych

- MLS, USLC, USL1, MLS Next Pro: dane zawodników i ScoutScore w `database/scoutpro_mlsnp_2025_gotowe_v2.db`.
- Polska/Czechy/Słowacja/Węgry/Chorwacja: **wyniki meczów**, nie statystyki zawodników, w `database/scoutpro_sources.db`. Nie liczymy dla nich ScoutScore.
- Bilans punktowy pokazany w module to wyliczenie ze spotkań w bazie, nie oficjalna tabela ligi. Przy fazach mistrzowskich, podziałach punktów lub karach może się różnić.

## Ważne dla praw do danych

- Dane OpenFootball pochodzą z publicznego zbioru CC0: https://github.com/openfootball/europe
- Zachowujemy link, rok i licencję każdego importu.
- Wcześniej proponowane openplay nie jest włączone — jego licencja deklarowana przez autora nie rozstrzyga praw do pierwotnego źródła zdarzeń.
- Wyscout / StatsBomb / Impect oraz nieoficjalne serwisy zawodników wymagają osobnej weryfikacji; nie wchodzą do automatycznego importu.

## Testy wykonane

- Kompilacja wszystkich plików Pythona.
- Dane Ekstraklasy: 306 spotkań, 18 klubów, poprawne sumy bilansów W/P/G/M.
- Transakcyjny import dwukrotny do tymczasowej bazy — bez duplikatów i z `PRAGMA integrity_check=ok`.
- Test na rzeczywistych danych: zachowano cztery ligi i dotychczasowe bazy.

**Ograniczenie testów**: import z sieci dla pozostałych sześciu lig oraz pełny render Streamlit należy sprawdzić na komputerze z dostępem do internetu. Endpointy Czech, Słowacji, Chorwacji i Węgier sprawdzono w publicznym serwisie wydawcy.
