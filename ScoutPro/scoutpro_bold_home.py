"""Jasny, typograficzny Dashboard ScoutPro (Bold Type).

Każda liczba pochodzi z bazy; brak fikcyjnej historii zdarzeń lub wzrostów.
"""
from __future__ import annotations
import html
import math
from pathlib import Path
import pandas as pd
import streamlit as st
from scoutpro_players import SILHOUETTE, club_crest
from scoutpro_common import text, fmt, value, available_leagues, league_label


def _h(x):
    return html.escape(text(x), quote=True)


def _score(x):
    return fmt(x, 1)


def _stat(x, digits=0):
    return fmt(x, digits)


def _figure(x, fallback='—'):
    n = value(x)
    return fallback if n is None else f'{int(n):,}'.replace(',', ' ')


def _candidate(data: pd.DataFrame, league: str):
    eligible = data[(data['liga'] == league) &
                    (pd.to_numeric(data['wiek_2025'], errors='coerce') <= 21) &
                    (pd.to_numeric(data['minutes_played'], errors='coerce') >= 450) &
                    data['ScoutScore'].notna()].sort_values('ScoutScore', ascending=False)
    return eligible.index[0] if len(eligible) else None


def _pick_comparison(data, featured):
    if featured is None:
        return None, None
    p = data.loc[featured]
    peer = data[(data['liga'] == p['liga']) &
                (data['grupa'] == p['grupa']) &
                (data.index != featured) &
                (data['ScoutScore'].notna()) &
                (data['minutes_played'] >= 450)]
    if peer.empty:
        return None, None
    peer = peer.sort_values('ScoutScore', ascending=False)
    return featured, peer.index[0]


def render_dashboard(data: pd.DataFrame, open_player, navigate):
    # Liga na panelu startowym jest filtrem, nie rankingiem międzyligowym.
    choices = available_leagues(data)
    if not choices:
        st.error('Brak lig w bazie ScoutPro.')
        return
    if st.session_state.get('bd_league') not in choices:
        st.session_state.bd_league = choices[0]

    with st.container(key='bd-dashboard'):
        # Styl graficzny zgodny z zaakceptowanym konceptem #9, wariantem 1.
        hleft, hright = st.columns([1.04, .96], gap='large', vertical_alignment='top')
        with hleft:
            st.markdown('''
        <section class="bd-hero-copy" aria-label="ScoutPro — strona główna">
          <div class="bd-welcome">Witaj w ScoutPro,</div>
          <h1><em>Lepszy scouting.</em><br><span class="bd-slanted"><em>Szybsze</em></span> <em>decyzje.</em></h1>
          <p>PLATFORMA DO SKAUTINGU <span>·</span> ANALIZY ZAWODNIKÓW</p>
        </section>''', unsafe_allow_html=True)

            rated = int(data['ScoutScore'].notna().sum())
            under21 = int(((data['wiek_2025'] <= 21) & data['ScoutScore'].notna()).sum())
            watching = len([i for i in st.session_state.get('watchlist', []) if i in data.index])
            kpis = [
                ('REKORDÓW W BAZIE', _figure(len(data))),
                ('OCENIONYCH', _figure(rated)),
                ('REKORDÓW U21', _figure(under21)),
                ('OBSERWOWANYCH', _figure(watching)),
            ]
            rows = ''.join(f'<div><strong>{num}</strong><span>{lab}</span></div>' for lab, num in kpis)
            st.markdown(f'<div class="bd-stats-strip">{rows}</div>', unsafe_allow_html=True)
            st.markdown('<div class="bd-context">Oceny dotyczą sezonu 2025. Porównuj ScoutScore w tej samej lidze i grupie pozycji.</div>', unsafe_allow_html=True)

        with hright:
            fc, btncol = st.columns([2.5, 1.1], vertical_alignment='bottom')
            with fc:
                st.selectbox('Wyróżniony zawodnik z ligi', choices, format_func=league_label, key='bd_league')
            featured = _candidate(data, st.session_state.bd_league)
            with btncol:
                st.caption('Sezon 2025')
            if featured is not None:
                p = data.loc[featured]
                asset = Path(__file__).parent / "assets" / "bold_silhouette.svg"
                avatar = asset.read_text(encoding="utf-8") if asset.exists() else SILHOUETTE
                crest = club_crest(p.get('team_name'), p.get('team_id'), p.get('liga'))
                st.markdown(f'''
                <div class="bd-feature">
                  <div class="bd-feature-art"><div class="bd-cutout">{avatar}</div><span class="bd-art-number">25</span></div>
                  <div class="bd-feature-text">
                    <div class="bd-overline">WYRÓŻNIONY ZAWODNIK · {_h(p.get('liga'))}</div>
                    <h2>{_h(p.get('player_name'))}</h2>
                    <div class="bd-team">{crest}<span>{_h(p.get('team_name'))} · {_h(p.get('general_position'))}</span></div>
                    <div class="bd-feature-numbers"><div><span>Wiek</span><strong>{_stat(p.get('wiek_2025'))}</strong></div>
                    <div><span>Minuty</span><strong>{_stat(p.get('minutes_played'))}</strong></div>
                    <div><span>Gole</span><strong>{_stat(p.get('goals'))}</strong></div>
                    <div><span>Asysty</span><strong>{_stat(p.get('primary_assists'))}</strong></div></div>
                    <div class="bd-feature-score"><small>ScoutScore</small><strong>{_score(p.get('ScoutScore'))}</strong></div>
                  </div>
                </div>''', unsafe_allow_html=True)
                st.button('Zobacz pełny profil  ↗', key='bd_feature_btn', type='primary', on_click=open_player, args=(featured,), use_container_width=True)
            else:
                st.info('Brak ocenionych zawodników U21 w wybranej lidze.')

        st.markdown('<div class="bd-major-rule"></div>', unsafe_allow_html=True)

        c_activity, c_compare, c_talents = st.columns([1.06, 1.11, .96], gap='medium')
        with c_activity:
            st.markdown('<h2 class="bd-section-name">Ostatnio analizowani</h2>', unsafe_allow_html=True)
            recent = [i for i in st.session_state.get('recent_indices', []) if i in data.index]
            if not recent:
                # Bez udawania historii. Pokazujemy faktyczne propozycje do obejrzenia.
                recent = data[(data['liga'] == st.session_state.bd_league) &
                              (data['wiek_2025'] <= 21) & data['ScoutScore'].notna()].sort_values('ScoutScore', ascending=False).head(4).index.tolist()
                st.caption('Propozycje do sprawdzenia — historia pojawi się po otwarciu profili.')
            else:
                st.caption('Profile otwierane podczas tej sesji')
            for i in recent[:4]:
                p = data.loc[i]
                with st.container(key=f'bd_recent_{i}'):
                    textcol, actioncol = st.columns([5, 1], vertical_alignment='center', gap='small')
                    with textcol:
                        st.markdown(f'<div class="bd-row-main"><span class="bd-slash"></span><div><b>{_h(p.get("player_name"))}</b><small>{_h(p.get("team_name"))} · {_h(p.get("liga"))}</small></div><strong>{_score(p.get("ScoutScore"))}</strong></div>', unsafe_allow_html=True)
                    with actioncol:
                        st.button('↗', key=f'bd_recent_open_{i}', on_click=open_player, args=(i,), use_container_width=True)
            st.button('Otwórz bazę zawodników  →', key='bd_go_players', on_click=navigate, args=('Zawodnicy',), use_container_width=True)

        with c_compare:
            st.markdown('<h2 class="bd-section-name">Szybkie porównanie</h2>', unsafe_allow_html=True)
            ai, bi = _pick_comparison(data, featured)
            if ai is None:
                st.info('Brak pary zawodników do porównania w wybranej lidze.')
            else:
                a, b = data.loc[ai], data.loc[bi]
                st.markdown(f'<div class="bd-duel"><div><small>ZAWODNIK A</small><b>{_h(a.get("player_name"))}</b><span>{_h(a.get("team_name"))}</span></div><strong>VS</strong><div><small>ZAWODNIK B</small><b>{_h(b.get("player_name"))}</b><span>{_h(b.get("team_name"))}</span></div></div>', unsafe_allow_html=True)
                specs = [('ScoutScore', 'ScoutScore', 1), ('xG / 90', 'xgoals_90', 2), ('xA / 90', 'xassists_90', 2), ('g+ / 90', 'gplus_above_avg_90', 3)]
                for lab, name, places in specs:
                    st.markdown(f'<div class="bd-duel-stat"><b>{fmt(a.get(name),places)}</b><span>{lab}</span><b>{fmt(b.get(name),places)}</b></div>', unsafe_allow_html=True)
                st.caption('Obaj zawodnicy z tej samej ligi i grupy pozycji.')
                st.button('Przejdź do porównania  →', key='bd_go_compare', on_click=navigate, args=('Porównania',), use_container_width=True)

        with c_talents:
            st.markdown('<h2 class="bd-section-name">Talenty <span>U21.</span></h2>', unsafe_allow_html=True)
            league = st.session_state.bd_league
            pool = data[(data['liga'] == league) & (data['wiek_2025'] <= 21) & data['ScoutScore'].notna()]
            # Nie interpretujemy listy jako rankingu talentów w różnych ligach.
            for i in pool.sort_values('ScoutScore', ascending=False).head(4).index:
                p = data.loc[i]
                with st.container(key=f'bd_talent_{i}'):
                    left, right = st.columns([5, 1], gap='small', vertical_alignment='center')
                    with left:
                        st.markdown(f'<div class="bd-talent-row"><span class="bd-slash"></span><div><b>{_h(p.get("player_name"))}</b><small>{_h(p.get("team_name"))} · {_stat(p.get("wiek_2025"))} lat</small></div><strong>{_score(p.get("ScoutScore"))}</strong></div>', unsafe_allow_html=True)
                    with right:
                        st.button('↗', key=f'bd_talent_go_{i}', on_click=open_player, args=(i,), use_container_width=True)
            st.button('Zobacz wszystkie talenty  →', key='bd_go_talents', on_click=navigate, args=('Talenty',), use_container_width=True)
        st.markdown('<div class="bd-footer">SCOUTPRO <span>/</span> SEZON 2025 <span>/</span> DANE: AMERICAN SOCCER ANALYSIS</div>', unsafe_allow_html=True)
