"""ScoutPro V4 Bold Type – aplikacja skautingowa.
Czyta bazę MLS Next Pro, jeśli istnieje; starsza baza i obserwowani pozostają bez zmian.
"""
from pathlib import Path
import base64
import html
import sqlite3

import pandas as pd
import streamlit as st
from scoutpro_players import render_players, live_search
from scoutpro_comparisons import render_comparisons
from scoutpro_talents import render_talents
from scoutpro_watchlist import sync_watchlist, render_watchlist
from scoutpro_reports import render_reports
from scoutpro_bold_home import render_dashboard
from scoutpro_europe import render_europe
from scoutpro_common import available_leagues, league_label

ROOT = Path(__file__).resolve().parent
# Obie bazy pozostają na dysku. Nie kopiujemy ani nie zmieniamy oryginału.
ORIGINAL_DB = ROOT / "database" / "scoutpro.db"
INTEGRATED_DB = ROOT / "database" / "scoutpro_mlsnp_2025_gotowe_v2.db"
DB_PATH = INTEGRATED_DB if INTEGRATED_DB.is_file() else ORIGINAL_DB
CSS_PATH = ROOT / "styles.css"
HERO_PATH = ROOT / "assets" / "hero.svg"

st.set_page_config(page_title="ScoutPro | Football Scouting", page_icon="⚽", layout="wide", initial_sidebar_state="expanded")

if CSS_PATH.exists():
    st.markdown("<style>" + CSS_PATH.read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)

if not DB_PATH.exists():
    st.error(f"Brak bazy danych: {DB_PATH}. Sprawdź folder database.")
    st.stop()

@st.cache_data(show_spinner=False)
def load_data(db_path: str, modified: float):
    with sqlite3.connect(db_path) as con:
        df = pd.read_sql_query("SELECT * FROM PlayerScoutScore2025", con)
    return df

try:
    dane = load_data(str(DB_PATH), DB_PATH.stat().st_mtime_ns)
except Exception as error:
    st.error("Nie udało się odczytać tabeli PlayerScoutScore2025. " + str(error))
    st.stop()

for field in ["player_name", "team_name", "liga", "general_position", "player_id"]:
    if field not in dane.columns:
        dane[field] = None
for field in ["ScoutScore", "wiek_2025", "minutes_played", "xgoals_90", "xassists_90", "goals_90", "primary_assists_90", "gplus_above_avg_90"]:
    if field not in dane.columns:
        dane[field] = pd.NA
    dane[field] = pd.to_numeric(dane[field], errors="coerce")

# Gdy nowa baza nie jest jeszcze w projekcie, aplikacja działa na oryginalnej.
if DB_PATH == ORIGINAL_DB:
    st.warning("Nie znaleziono bazy MLS Next Pro. Działa starsza baza 3 lig; skopiuj plik scoutpro_mlsnp_2025_gotowe_v2.db do folderu database.")

pozycje = {"ST": "Atak", "W": "Atak", "AM": "Pomoc", "CM": "Pomoc", "DM": "Pomoc", "CB": "Obrona", "FB": "Obrona"}
dane["grupa"] = dane["general_position"].map(pozycje)

PAGES = ["Dashboard", "Zawodnicy", "Ligi Europy", "Porównania", "Talenty", "Raporty AI", "Obserwowani", "Ustawienia"]
NAV_ICONS = [":material/home:", ":material/person_outline:", ":material/public:", ":material/compare_arrows:", ":material/kid_star:", ":material/description:", ":material/bookmark_border:"]

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if st.session_state.page == "Raporty":
    st.session_state.page = "Raporty AI"
if "recent_indices" not in st.session_state:
    st.session_state.recent_indices = []
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []
if "selected_player" not in st.session_state:
    st.session_state.selected_player = None

# Oddzielny, bezpieczny zapis obserwowanych; oryginalna baza analityczna bez zmian.
USER_DB = ROOT / "database" / "scoutpro_user.db"
sync_watchlist(dane, USER_DB)


def navigate(page):
    st.session_state.page = page
    if page == "Zawodnicy":
        st.session_state.player_mode = "explorer"


def open_player(index):
    st.session_state.selected_player = int(index)
    st.session_state.pop("profile_player", None)
    st.session_state.page = "Zawodnicy"
    st.session_state.player_mode = "full"
    recent = st.session_state.recent_indices
    if int(index) in recent:
        recent.remove(int(index))
    recent.insert(0, int(index))
    st.session_state.recent_indices = recent[:6]


def fmt(value, digits=1):
    return "—" if pd.isna(value) else f"{float(value):.{digits}f}"


def txt(value, default="—"):
    return default if pd.isna(value) or not str(value).strip() else str(value)


def esc(value, default="—"):
    return html.escape(txt(value, default))


def player_label(idx):
    row = dane.loc[idx]
    return f"{txt(row['player_name'])} — {txt(row['team_name'], 'Nieznany klub')} ({txt(row['liga'])})"


def score_badge(value):
    css = "sp-score" if pd.notna(value) else "sp-score sp-muted-score"
    return f'<span class="{css}">{fmt(value, 1)}</span>'


# LEWY PANEL
with st.sidebar:
    st.markdown('''<div class="sp-brand"><span class="sp-brand-icon"><i></i><i></i></span><span>ScoutPro<small>FOOTBALL SCOUTING & ANALYSIS</small></span></div>''', unsafe_allow_html=True)
    for label, icon in zip(PAGES[:7], NAV_ICONS):
        st.button(label, icon=icon, key=f"nav_{label.lower().replace(' ', '_')}", on_click=navigate, args=(label,), use_container_width=True)
    st.markdown(f'<div class="sp-side-divider"></div><div class="sp-side-note">SEZON 2025 · {html.escape(" / ".join(available_leagues(dane)))}</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:clamp(40px,13vh,140px)"></div>', unsafe_allow_html=True)
    st.button("Ustawienia", icon=":material/settings:", key="nav_settings", on_click=navigate, args=("Ustawienia",), use_container_width=True)

# Podświetlenie bieżącej zakładki (klasa widgetu odpowiada jego kluczowi)
active_key = "nav_" + st.session_state.page.lower().replace(" ", "_")
st.markdown(f'''<style>[data-testid="stSidebar"] .st-key-{active_key} button{{background:#55ed24!important;color:#11140e!important;border-color:#55ed24!important;font-weight:800!important;}}</style>''', unsafe_allow_html=True)

# GÓRNY PASEK
with st.container(key="topbar"):
    col_search, col_tools = st.columns([6, 1.2], gap="medium", vertical_alignment="center")
    with col_search:
        query = live_search("Szukaj zawodnika, klubu lub ligi", "global_search", "⌕   Szukaj zawodnika, klubu lub ligi...", label_visibility="collapsed")
    with col_tools:
        st.markdown('''<div class="sp-top-actions"><span class="sp-bell" title="Sezon 2025"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></svg></span><span class="sp-avatar" title="ScoutPro"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="7" r="4"/><path d="M3.7 21a8.3 8.3 0 0 1 16.6 0Z"/></svg></span></div>''', unsafe_allow_html=True)

# Górne pole wyszukiwania działa w całej aplikacji
if query.strip() and st.session_state.page != "Zawodnicy":
    q = query.strip().casefold()
    match = dane[
        dane["player_name"].fillna("").astype(str).str.casefold().str.contains(q, regex=False)
        | dane["team_name"].fillna("").astype(str).str.casefold().str.contains(q, regex=False)
        | dane["liga"].fillna("").astype(str).str.casefold().str.contains(q, regex=False)
    ].head(6)
    with st.container(border=True):
        st.caption(f"Wyniki wyszukiwania: {len(match)} (pokazujemy maksymalnie 6)")
        if match.empty:
            st.info("Nie znaleziono pasujących zawodników.")
        else:
            for idx in match.index:
                st.button(player_label(idx), key=f"search_result_{idx}", on_click=open_player, args=(idx,), use_container_width=True)

# DASHBOARD — Bold Type (wersja 4)
if st.session_state.page == "Dashboard":
    render_dashboard(dane, open_player, navigate)

# ZAWODNICY – Explorer + wstępny pełny profil
elif st.session_state.page == "Zawodnicy":
    render_players(dane, open_player, global_query=query)

elif st.session_state.page == "Ligi Europy":
    render_europe()

elif st.session_state.page == "Porównania":
    render_comparisons(dane, open_player)

elif st.session_state.page == "Talenty":
    render_talents(dane, open_player)

elif st.session_state.page == "Raporty AI":
    render_reports(dane, open_player)

elif st.session_state.page == "Obserwowani":
    render_watchlist(dane, open_player, USER_DB)

elif st.session_state.page == "Ustawienia":
    st.markdown('<div class="sp2-eyebrow">SCOUTPRO · KONFIGURACJA</div><h1 class="sp2-title">Ustawienia.</h1>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown('#### Dane projektu')
            st.write('**Sezon:** 2025')
            st.write('**Ligi:** ' + ', '.join(league_label(liga) for liga in available_leagues(dane)))
            st.write('**Źródło zawodników:** American Soccer Analysis (CC BY-SA 4.0)')
            st.write('**Źródło wyników Europy:** OpenFootball (CC0 1.0)')
            st.write('**Baza wyników:** `database/scoutpro_sources.db`')
            st.caption('Openplay pozostaje poza importem: niezweryfikowane pochodzenie części danych.')
            st.write(f'**Baza statystyczna:** `database/{DB_PATH.name}`')
            st.write('**Zapis obserwowanych:** `database/scoutpro_user.db`')
            st.caption('Dane osobiste skauta pozostają w oddzielnym pliku.')
    with c2:
        with st.container(border=True):
            st.markdown('#### Metodologia')
            st.write('ScoutScore to autorski wskaźnik liczony w obrębie ligi i grupy pozycyjnej.')
            st.write('Raporty bazują na dostępnych statystykach i nie zastępują obserwacji meczów.')
            st.write('Qwen3.5-4B działa opcjonalnie lokalnie przez Ollama.')
            st.caption('Dotrenowanie LoRA pozostaje osobnym etapem projektu.')
