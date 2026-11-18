# ScoutPro — sprawdzone źródła i granice importu (18.11.2026)

## Źródła obecnie używane

**OpenFootball / openfootball-europe — CC0 1.0**
- Dane: terminarze i wyniki meczów europejskich lig.
- Zakres ScoutPro: osobna zakładka `Ligi Europy`, bilans klubów i eksport CSV.
- Brak: nazwisk zawodników, minut, xG, asyst i ScoutScore.
- Licencja: https://github.com/openfootball/europe (CC0 1.0).
- Warto zachować link do pochodzenia każdego pobranego pliku, choć CC0 nie wymaga przypisania autorstwa.

**American Soccer Analysis — CC BY-SA 4.0**
- Dane: zawodnicy i statystyki lig północnoamerykańskich już obecne w ScoutPro.
- Przy publikowaniu adaptacji wymagane uznanie autorstwa, wskazanie zmian i stosowanie warunków ShareAlike, jeśli mają zastosowanie.
- Dokumentacja: https://app.americansocceranalysis.com/api/v1/__docs__/

## Źródła wstrzymane, nie należą do automatycznego importu

- **openplay**: autor wskazuje CC BY 4.0, ale nie potwierdzono prawa do sublicencjonowania danych pierwotnych (możliwe zewnętrzne źródła zdarzeń). Wstrzymane do uzyskania potwierdzenia.
- **Wyscout/Pappalardo**: wymaga osobnej weryfikacji zakresu pierwotnych praw do publikowanych zdarzeń.
- **StatsBomb Open Data** i **Impect Open Data**: mają własne warunki badawcze, w tym możliwe ograniczenia dalszej dystrybucji; nie kopiujemy danych do archiwum aplikacji bez sprawdzenia pełnych licencji.
- **Ekstraklasa / Opta / Chance Liga / Stats Perform, PitchAPI i serwisy statystyczne bez wyraźnej licencji na dane**: brak zgody potwierdzającej pożądany sposób użycia; odkładamy.

## Zasady ScoutPro

1. Każdy rekord zachowuje nazwę dostawcy, adres źródła, sezon i licencję.
2. Wyniki meczów i statystyki zawodników znajdują się w różnych tabelach/bazach.
3. Nie obliczamy ScoutScore z samych wyników meczowych.
4. Licencja nie zastępuje osobnego sprawdzenia praw do zdjęć, herbów i innych grafik.
5. Nawet jawna licencja deklarowana przez osobę trzecią nie daje automatycznej 100% pewności prawnej co do danych zewnętrznych.
