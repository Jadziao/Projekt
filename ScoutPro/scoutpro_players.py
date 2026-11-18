"""Widok Zawodnicy (Explorer) i pełny profil ScoutPro.

Wykorzystuje tylko dane z już istniejącej tabeli PlayerScoutScore2025.
Nie zmienia i nie nadpisuje bazy SQLite.
"""
from __future__ import annotations

import hashlib
import base64
import html
import math
import inspect
from typing import Any

import pandas as pd
import streamlit as st
from scoutpro_common import available_leagues, league_label

SORT_COLUMNS = {
    "ScoutScore": "ScoutScore",
    "Minuty": "minutes_played",
    "Bramki": "goals",
    "Asysty": "primary_assists",
    "Czyste konta": "clean_sheets",
}

POSITION_LABELS = {
    "GK": "Bramkarz (GK)",
    "CB": "Środkowy obrońca (CB)",
    "FB": "Boczny obrońca (FB)",
    "DM": "Defensywny pomocnik (DM)",
    "CM": "Środkowy pomocnik (CM)",
    "AM": "Ofensywny pomocnik (AM)",
    "W": "Skrzydłowy (W)",
    "ST": "Napastnik (ST)",
}

COLORS = ["#1fd39a", "#5bb2fe", "#c297f2", "#f4b85a", "#f27c84", "#7dd7bd"]


def txt(value: Any, fallback: str = "—") -> str:
    if value is None:
        return fallback
    try:
        if bool(pd.isna(value)):
            return fallback
    except (TypeError, ValueError):
        pass
    result = str(value).strip()
    return result if result else fallback


def h(value: Any, fallback: str = "—") -> str:
    return html.escape(txt(value, fallback), quote=True)


def fmt_number(value: Any, decimals: int = 0) -> str:
    try:
        num = float(value)
        if math.isnan(num) or math.isinf(num):
            return "—"
        return f"{num:,.{decimals}f}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def club_crest(team_name: Any, team_id: Any = None, league: Any = None) -> str:
    """Własny, nieoficjalny symbol. Nie pobieramy rzeczywistych herbów."""
    name = txt(team_name, "Nieznany klub")
    parts = [s for s in name.replace("-", " ").split() if s.upper() not in {"FC", "SC", "CF", "THE"}]
    initials = "".join(x[0] for x in parts[:2]).upper() if parts else "SP"
    seed = txt(team_id, name) + "|" + txt(league, "")
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    color = COLORS[digest[0] % len(COLORS)]
    return f'''<svg class="sp-club-crest" role="img" aria-label="Nieoficjalny symbol: {h(name)}" viewBox="0 0 62 72" xmlns="http://www.w3.org/2000/svg">
    <path d="M31 3 56 11 V35 Q55 55 31 68 Q7 55 6 35 V11 Z" fill="#0a151a" stroke="{color}" stroke-width="3.1"/>
    <path d="M31 9 50 15 V35 Q49 50 31 60 Q13 50 12 35 V15 Z" fill="{color}" opacity="0.09"/>
    <text x="31" y="42" text-anchor="middle" fill="#f7fffd" font-size="20" font-family="Arial,sans-serif" font-weight="800">{html.escape(initials)}</text>
    </svg>'''


SILHOUETTE = '''<svg viewBox="0 0 120 120" role="img" aria-label="Domyślna sylwetka piłkarza" xmlns="http://www.w3.org/2000/svg">
<defs><radialGradient id="spAvBg"><stop stop-color="#243c40"/><stop offset="1" stop-color="#0b171c"/></radialGradient></defs>
<circle cx="60" cy="60" r="58" fill="url(#spAvBg)" stroke="#35534a" stroke-width="1.5"/>
<ellipse cx="60" cy="42" rx="20" ry="24" fill="#020608"/>
<path d="M15 111C17 86 32 79 46 76 L47 67 Q60 73 73 67 L74 76 C92 80 105 89 106 111Z" fill="#020608"/>
</svg>'''


def prepare_players(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for field in ["player_name", "team_name", "liga", "general_position", "player_id", "team_id"]:
        if field not in result.columns:
            result[field] = None
    numerical = ["ScoutScore", "wiek_2025", "minutes_played", "goals", "primary_assists", "xgoals_90", "xassists_90", "goals_90", "primary_assists_90", "gplus_above_avg_90"]
    for field in numerical:
        if field not in result.columns:
            result[field] = pd.NA
        result[field] = pd.to_numeric(result[field], errors="coerce")
    # Nie mylimy czystego konta drużyny z czystym kontem zawodnika.
    # Pole dostępne dopiero po dołączeniu zweryfikowanych występów meczowych.
    clean_sheet_col = next((c for c in ["clean_sheets", "czyste_konta", "clean_sheets_2025"] if c in result.columns), None)
    result["clean_sheets"] = pd.to_numeric(result[clean_sheet_col], errors="coerce") if clean_sheet_col else float("nan")
    return result


def filter_players(df: pd.DataFrame, search: str = "", league: str = "Wszystkie", position: str = "Wszystkie", age: str = "Dowolny", club: str = "Wszystkie") -> pd.DataFrame:
    filtered = df
    if search.strip():
        search_normal = search.strip().casefold()
        mask = (
            filtered["player_name"].fillna("").astype(str).str.casefold().str.contains(search_normal, regex=False)
            | filtered["team_name"].fillna("").astype(str).str.casefold().str.contains(search_normal, regex=False)
        )
        filtered = filtered[mask]
    if league != "Wszystkie":
        filtered = filtered[filtered["liga"] == league]
    if position != "Wszystkie":
        filtered = filtered[filtered["general_position"] == position]
    if age != "Dowolny":
        age_num = pd.to_numeric(filtered["wiek_2025"], errors="coerce")
        if age.startswith("Do "):
            filtered = filtered[age_num <= int(age.split()[1])]
        elif age == "24+":
            filtered = filtered[age_num >= 24]
    if club != "Wszystkie":
        filtered = filtered[filtered["team_name"] == club]
    return filtered


def sort_players(df: pd.DataFrame, sort_name: str, descending: bool) -> tuple[pd.DataFrame, bool]:
    column = SORT_COLUMNS[sort_name]
    has_data = column in df.columns and df[column].notna().any()
    if not has_data:
        column = "ScoutScore"
    # Zawsze brakujące na końcu, bez dopisywania zer.
    result = df.sort_values(column, ascending=not descending, na_position="last", kind="stable")
    return result, has_data


def svg_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _short_form(row: pd.Series) -> str:
    return txt(row.get("general_position")) + " • " + txt(row.get("liga"))


def _preview(row: pd.Series) -> None:
    score = fmt_number(row.get("ScoutScore"), 1)
    crest = club_crest(row.get("team_name"), row.get("team_id"), row.get("liga"))
    st.markdown(f'''
    <div class="sp-player-card-top">
      <div class="sp-preview-label">PODGLĄD ZAWODNIKA</div>
      <div class="sp-player-portrait">{SILHOUETTE}</div>
      <h2 class="sp-player-title">{h(row.get("player_name"))}</h2>
      <div class="sp-club-line">{crest}<span>{h(row.get("team_name"), "Nieznany klub")}</span></div>
      <div class="sp-player-meta">{h(_short_form(row))}</div>
    </div>
    <div class="sp-player-facts">
       <div><span>Wiek w 2025</span><strong>{fmt_number(row.get("wiek_2025"))} lat</strong></div>
       <div><span>Minuty</span><strong>{fmt_number(row.get("minutes_played"))}</strong></div>
    </div>
    <div class="sp-player-score"><span>ScoutScore</span><strong>{score}<small> / 100</small></strong></div>
    <p class="sp-score-note">Ocena względem zawodników z tej samej ligi i grupy pozycji.</p>
    ''', unsafe_allow_html=True)


def render_full_profile(data: pd.DataFrame, open_player) -> None:
    """Nowy pełny profil A+B; zachowuje istniejącą nawigację Explorer."""
    from scoutpro_profile import render_profile
    render_profile(data, open_player, silhouette=SILHOUETTE, club_crest_fn=club_crest)


def live_search(label: str, key: str, placeholder: str, label_visibility: str = "visible") -> str:
    """Wyszukiwanie na żywo na Streamlit 1.66+, starsze wydania: st_keyup."""
    if "live" in inspect.signature(st.text_input).parameters:
        return st.text_input(
            label, key=key, placeholder=placeholder,
            live="300ms", width="stretch", label_visibility=label_visibility
        ) or ""
    try:
        from st_keyup import st_keyup
    except ImportError:
        st.caption("Aby wyszukiwać podczas pisania, zaktualizuj Streamlit: pip install -U streamlit")
        return st.text_input(label, key=key, placeholder=placeholder, label_visibility=label_visibility) or ""
    return st_keyup(label, key=key, placeholder=placeholder, debounce=300, label_visibility=label_visibility) or ""


def _player_row_html(row: pd.Series, selected: bool, saved: bool) -> str:
    """Jeden wiersz HTML (bez dataframe i checkboxa); wybór realizuje st.button."""
    crest = club_crest(row.get("team_name"), row.get("team_id"), row.get("liga"))
    score = fmt_number(row.get("ScoutScore"), 1)
    score_class = "sp-score" if score != "—" else "sp-score sp-muted-score"
    fav = '<span class="sp-row-star" title="Obserwowany">★</span>' if saved else ""
    def field(class_name: str, content: str) -> str:
        return f'<span class="sp-col-{class_name}">{content}</span>'
    player_name = f'<span class="sp-mini-portrait">{SILHOUETTE}</span><strong>{h(row.get("player_name"))}</strong>{fav}'
    club = f'<span class="sp-mini-crest">{crest}</span><span class="sp-club-text">{h(row.get("team_name"), "Nieznany klub")}</span>'
    clean = fmt_number(row.get("clean_sheets"))
    extra_items = [
        ("Liga", h(row.get("liga"))),
        ("Poz.", h(row.get("general_position"))),
        ("Wiek", fmt_number(row.get("wiek_2025"))),
        ("Min.", fmt_number(row.get("minutes_played"))),
        ("Gole", fmt_number(row.get("goals"))),
        ("Asysty", fmt_number(row.get("primary_assists"))),
        ("Czyste konta", clean),
    ]
    extras = "".join(f'<span><small>{name}</small><b>{value}</b></span>' for name, value in extra_items)
    return f'''<div class="sp-player-grid sp-grid-row {'sp-grid-selected' if selected else ''}">
        {field('name', player_name)}
        {field('club', club)}
        {field('league', h(row.get('liga')))}
        {field('position', h(row.get('general_position')))}
        {field('age', fmt_number(row.get('wiek_2025')))}
        {field('minutes', fmt_number(row.get('minutes_played')))}
        {field('goals', fmt_number(row.get('goals')))}
        {field('assists', fmt_number(row.get('primary_assists')))}
        {field('clean', clean)}
        {field('score', f'<span class="{score_class}">{score}</span>')}
        <div class="sp-row-extras">{extras}</div>
    </div>'''


def _selected_player(index: int) -> None:
    st.session_state.selected_player = index


def render_players(df: pd.DataFrame, open_player, global_query: str = "") -> None:
    data = prepare_players(df)
    if "player_mode" not in st.session_state:
        st.session_state.player_mode = "explorer"
    if st.session_state.player_mode == "full":
        render_full_profile(data, open_player)
        return

    leagues_description = h(', '.join(league_label(lg) for lg in available_leagues(data)))
    st.markdown(f'''<section class="sp-players-banner">
      <div class="sp-players-eyebrow">FOOTBALL SCOUTING ANALYTICS</div>
      <h1>Zawodnicy — <span>Baza piłkarzy</span></h1>
      <p>Przeglądaj, wyszukuj i analizuj zawodników z {leagues_description}.</p>
      <div class="sp-banner-ball" aria-hidden="true">⚽</div>
    </section>''', unsafe_allow_html=True)

    # Wszystko w jednym obramowanym panelu: filtry + tabela + profil.
    with st.container(key="sp_workspace"):
        with st.container(key="explorer_filters"):
            c0, c1, c2, c3, c4 = st.columns([2.5, 1, 1.15, 1, 1.7], gap="small", vertical_alignment="bottom")
            with c0:
                query_local = live_search("Szukaj zawodnika lub klubu", "player_search", "Szukaj zawodnika...")
            with c1:
                league = st.selectbox("Liga", ["Wszystkie"] + available_leagues(data), format_func=league_label, key="player_league")
            with c2:
                position_options = ["Wszystkie"] + [p for p in POSITION_LABELS if p in data["general_position"].dropna().unique()]
                position = st.selectbox("Pozycja", position_options, format_func=lambda p: POSITION_LABELS.get(p, p), key="player_position")
            with c3:
                age = st.selectbox("Wiek", ["Dowolny", "Do 18 lat", "Do 21 lat", "Do 23 lat", "24+"], key="player_age")
            with c4:
                available_clubs = data if league == "Wszystkie" else data[data["liga"] == league]
                clubs = sorted(available_clubs["team_name"].dropna().astype(str).unique().tolist())
                club_options = ["Wszystkie"] + clubs
                if st.session_state.get("player_club", "Wszystkie") not in club_options:
                    st.session_state.player_club = "Wszystkie"
                club = st.selectbox("Klub", club_options, key="player_club")

        # Górna wyszukiwarka na stronie Zawodnicy również filtruje bazę.
        found = filter_players(data, query_local, league, position, age, club)
        if global_query.strip():
            q = global_query.strip().casefold()
            mask = (
                found["player_name"].fillna("").astype(str).str.casefold().str.contains(q, regex=False)
                | found["team_name"].fillna("").astype(str).str.casefold().str.contains(q, regex=False)
                | found["liga"].fillna("").astype(str).str.casefold().str.contains(q, regex=False)
            )
            found = found[mask]

        st.markdown('<div class="sp-workspace-line"></div>', unsafe_allow_html=True)
        with st.container(key="explorer_main"):
            left, right = st.columns([4.25, 1.25], gap="medium", vertical_alignment="top")
            with left:
                with st.container(key="explorer_results"):
                    count_col, sort_col, order_col = st.columns([3.4, 1.5, 1.1], gap="small", vertical_alignment="bottom")
                    with count_col:
                        st.markdown(f'<div class="sp-results-count">Znaleziono <strong>{len(found):,}</strong> rekordów zawodników</div>'.replace(",", " "), unsafe_allow_html=True)
                    with sort_col:
                        sort_by = st.selectbox("Sortuj po", list(SORT_COLUMNS), key="player_sort")
                    with order_col:
                        order = st.selectbox("Kolejność", ["Malejąco ↓", "Rosnąco ↑"], key="player_order")
                    sorted_df, available = sort_players(found, sort_by, order.startswith("Malejąco"))
                    if sort_by == "Czyste konta" and not available:
                        st.caption("Czyste konta: brak zweryfikowanych danych. Tymczasowo kolejność według ScoutScore.")

                    per_page = 10
                    pages = max(1, math.ceil(len(sorted_df) / per_page))
                    filter_signature = hashlib.sha256(
                        repr((query_local, global_query, league, position, age, club, sort_by, order)).encode("utf-8")
                    ).hexdigest()[:12]
                    if st.session_state.get("explorer_last_filter") != filter_signature:
                        st.session_state.explorer_page = 1
                        st.session_state.explorer_last_filter = filter_signature
                    page = min(max(1, int(st.session_state.get("explorer_page", 1))), pages)
                    st.session_state.explorer_page = page
                    subset = sorted_df.iloc[(page - 1) * per_page : page * per_page]

                    if len(subset) and st.session_state.get("selected_player") not in subset.index:
                        st.session_state.selected_player = int(subset.index[0])
                    if not len(subset):
                        st.session_state.selected_player = None

                    headings = [
                        ("name", "Zawodnik"), ("club", "Klub"), ("league", "Liga"),
                        ("position", "Poz."), ("age", "Wiek"), ("minutes", "Minuty"),
                        ("goals", "Bramki"), ("assists", "Asysty"),
                        ("clean", "Czyste konta"), ("score", "ScoutScore"),
                    ]
                    head_html = "".join(f'<span class="sp-col-{name}">{label}</span>' for name, label in headings)
                    st.markdown(f'<div class="sp-player-grid sp-grid-head">{head_html}</div>', unsafe_allow_html=True)
                    if len(subset) == 0:
                        st.info("Nie znaleziono zawodników pasujących do filtrów.")
                    for index, row in subset.iterrows():
                        chosen_index = int(index)
                        with st.container(key=f"sp_row_{chosen_index}"):
                            st.markdown(
                                _player_row_html(row, chosen_index == st.session_state.selected_player,
                                                 chosen_index in st.session_state.watchlist),
                                unsafe_allow_html=True,
                            )
                            st.button(
                                f"Wybierz {txt(row.get('player_name'))}",
                                key=f"sp_choose_{chosen_index}",
                                on_click=_selected_player,
                                args=(chosen_index,),
                                use_container_width=True,
                            )

                    nav_left, nav_middle, nav_right = st.columns([1.2, 2, 1.2], vertical_alignment="center")
                    with nav_left:
                        if st.button("‹ Poprzednia", disabled=page <= 1, key="explorer_prev", use_container_width=True):
                            st.session_state.explorer_page = page - 1
                            st.rerun()
                    with nav_middle:
                        start = (page - 1) * per_page + 1 if len(sorted_df) else 0
                        end = min(page * per_page, len(sorted_df))
                        st.markdown(f'<div class="sp-page-indicator">{start}–{end} z {len(sorted_df)} &nbsp; • &nbsp; Strona {page}/{pages}</div>', unsafe_allow_html=True)
                    with nav_right:
                        if st.button("Następna ›", disabled=page >= pages, key="explorer_next", use_container_width=True):
                            st.session_state.explorer_page = page + 1
                            st.rerun()

            with right:
                with st.container(key="explorer_profile"):
                    chosen = st.session_state.get("selected_player")
                    if chosen is None:
                        st.info("Wybierz zawodnika z listy, aby zobaczyć jego podgląd.")
                    else:
                        row = data.loc[int(chosen)]
                        _preview(row)
                        if st.button("Pokaż pełny profil  →", type="primary", key="explorer_full_profile", use_container_width=True):
                            open_player(int(chosen))
                            st.session_state.player_mode = "full"
                            st.rerun()