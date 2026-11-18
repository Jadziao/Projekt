"""ScoutPro | Ligi Europy — mecze z osobnej bazy OpenFootball CC0.

Nigdy nie nadajemy ScoutScore z danych zawierających wyłącznie wyniki meczów.
"""
from __future__ import annotations
import html
import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "scoutpro_sources.db"
CATALOG = ROOT / "ScoutPro_Legalne_Zrodla" / "scoutpro_legal_catalog.json"

COUNTRIES = {
    "poland": "Polska", "czech-republic": "Czechy", "slovakia": "Słowacja",
    "hungary": "Węgry", "croatia": "Chorwacja", "austria": "Austria",
}


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def catalog() -> dict:
    try:
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
        return {v["slug"]: v for v in data.get("leagues", []) if v.get("provider") == "openfootball" and v.get("license") == "CC0 1.0"}
    except (OSError, ValueError, KeyError):
        return {}


@st.cache_data(show_spinner=False)
def read_matches(db_path: str, stamp: int):
    """Czyta wszystkie legalnie oznaczone mecze; bez wyszukiwania i łączenia po nazwach zespołów."""
    if not Path(db_path).exists():
        return pd.DataFrame(), pd.DataFrame()
    with sqlite3.connect(db_path) as con:
        has_table = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_records'").fetchone()
        if not has_table:
            return pd.DataFrame(), pd.DataFrame()
        rows = con.execute('''
            SELECT league_key, season, payload, source_url, license
            FROM source_records
            WHERE source='openfootball' AND kind='match' AND license='CC0 1.0'
        ''').fetchall()
    parsed = []
    for slug, season, payload, source_url, license_name in rows:
        try:
            m = json.loads(payload)
        except (ValueError, TypeError):
            continue
        if not isinstance(m, dict):
            continue
        home, away = m.get('team1'), m.get('team2')
        if not isinstance(home, str) or not isinstance(away, str) or not home.strip() or not away.strip():
            continue
        score = m.get('score')
        ft = score.get('ft') if isinstance(score, dict) else score
        hgoals = agoals = None
        if isinstance(ft, list) and len(ft) == 2 and all(isinstance(i, int) and not isinstance(i, bool) and i >= 0 for i in ft):
            hgoals, agoals = ft
        parsed.append({
            'slug': slug, 'sezon': season, 'data': m.get('date', ''),
            'kolejka': str(m.get('round', '')), 'gospodarze': home.strip(), 'goście': away.strip(),
            'gole_g': hgoals, 'gole_w': agoals, 'źródło': source_url, 'licencja': license_name,
        })
    frame = pd.DataFrame(parsed)
    if frame.empty:
        return frame, pd.DataFrame()
    frame = frame.drop_duplicates(subset=['slug','sezon','data','kolejka','gospodarze','goście','gole_g','gole_w'])
    frame['wynik'] = frame.apply(lambda m: f"{int(m.gole_g)}:{int(m.gole_w)}" if pd.notna(m.gole_g) and pd.notna(m.gole_w) else "—", axis=1)
    frame['data_sort'] = pd.to_datetime(frame['data'], errors='coerce')
    frame.sort_values(['slug','data_sort','gospodarze'], inplace=True)
    overview = (frame.groupby(['slug','sezon'], as_index=False)
                .agg(mecze=('wynik','size'), rozegrane=('gole_g','count'), kluby=('gospodarze','nunique')))
    return frame, overview


def standings(matches: pd.DataFrame):
    """Bilans meczów w zbiorze; NIE tabela oficjalna (bez podziału punktów/kar)."""
    results = {}
    played = matches.dropna(subset=['gole_g','gole_w'])
    for m in played.itertuples():
        hg, ag = int(m.gole_g), int(m.gole_w)
        for team, gf, ga in [(m.gospodarze, hg, ag), (m.goście, ag, hg)]:
            r = results.setdefault(team, {'Klub': team, 'M': 0, 'W': 0, 'R': 0, 'P': 0, 'BZ': 0, 'BS': 0, 'Pkt': 0})
            r['M'] += 1
            r['BZ'] += gf
            r['BS'] += ga
            if gf > ga:
                r['W'] += 1
                r['Pkt'] += 3
            elif gf == ga:
                r['R'] += 1
                r['Pkt'] += 1
            else:
                r['P'] += 1
    if not results:
        return pd.DataFrame(columns=['Klub','M','W','R','P','BZ','BS','RB','Pkt'])
    df = pd.DataFrame(results.values())
    df['RB'] = df['BZ'] - df['BS']
    return df.sort_values(['Pkt','RB','BZ','Klub'], ascending=[False,False,False,True], kind='stable').reset_index(drop=True)


def render_europe():
    st.markdown('''<div class="eu-kicker">SCOUTPRO / ANALIZA ROZGRYWEK / EUROPA</div>
        <div class="eu-headline">Wyniki.<br><span>Bez zgadywania.</span></div>
        <p class="eu-intro">Przegląd lig europejskich oparty na otwartych danych meczowych. Najpierw źródło, potem analiza.</p>''', unsafe_allow_html=True)
    if not DB.exists():
        st.info('Nie znaleziono scoutpro_sources.db. Dane meczowe pobierzesz poleceniem IMPORTUJ_LIGI_EUROPY.bat.')
        return
    frame, summary = read_matches(str(DB), DB.stat().st_mtime_ns)
    if frame.empty:
        st.info('Baza nie zawiera jeszcze wyników OpenFootball. Uruchom IMPORTUJ_LIGI_EUROPY.bat.')
        return
    entries = catalog()
    seasons = frame[['slug','sezon']].drop_duplicates()
    slugs = sorted(seasons['slug'].unique(), key=lambda k: (0 if k == 'openfootball-poland-pl1' else 1, entries.get(k, {}).get('competition', k)))
    country_names = {k: COUNTRIES.get(entries.get(k, {}).get('country',''), 'Europa') for k in slugs}
    def league_display(k):
        item = entries.get(k, {})
        return f"{item.get('competition',k)}  ·  {country_names[k]}"
    with st.container(key='eu-filters'):
        c1, c2, c3 = st.columns([2.1, 1, 1], gap='medium')
        with c1:
            league = st.selectbox('Rozgrywki', slugs, format_func=league_display, key='eu-league')
        with c2:
            seasons_available = sorted(frame.loc[frame['slug']==league, 'sezon'].unique(), reverse=True)
            season = st.selectbox('Sezon', seasons_available, key='eu-season')
        with c3:
            st.markdown('<div class="eu-tag">OTWARTE DANE<br><b>CC0 1.0</b></div>', unsafe_allow_html=True)
    games = frame[(frame['slug']==league) & (frame['sezon']==season)].copy()
    played = games.dropna(subset=['gole_g','gole_w'])
    clubs = sorted(set(games['gospodarze']).union(games['goście']))
    stats = standings(games)
    with st.container(key='eu-totals'):
        a,b,c,d = st.columns(4, gap='small')
        a.metric('Mecze w zbiorze', f'{len(games):,}'.replace(',',' '))
        b.metric('Zapisane wyniki', f'{len(played):,}'.replace(',',' '))
        c.metric('Kluby', len(clubs))
        d.metric('Gole w meczach', int(played['gole_g'].sum() + played['gole_w'].sum()))
    info, table = st.columns([1.05, 1.5], gap='large')
    with info:
        st.markdown('<div class="eu-block-heading">Bilans punktowy<span>01 / PRZEGLĄD</span></div>', unsafe_allow_html=True)
        if len(stats):
            top = stats.head(10).sort_values('Pkt', ascending=True)
            fig = px.bar(top, x='Pkt', y='Klub', orientation='h', text='Pkt', custom_data=['M','W','R','P'], color_discrete_sequence=['#5aeb36'])
            fig.update_traces(hovertemplate='<b>%{y}</b><br>Punkty: %{x}<extra></extra>', marker_line_width=0, textposition='outside', textfont_color='#172016')
            fig.update_layout(template='plotly_white', height=370, margin=dict(l=0,r=28,t=8,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(family='Arial',color='#253028'), xaxis=dict(visible=False, range=[0,max(1,stats['Pkt'].max())*1.17]), yaxis=dict(title=None,ticks='',tickfont=dict(size=12)), showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})
        else:
            st.info('Brak wyników do stworzenia bilansu.')
    with table:
        st.markdown('<div class="eu-block-heading">Mecze<span>02 / TERMINARZ</span></div>', unsafe_allow_html=True)
        team_options = ['Wszystkie kluby'] + clubs
        chosen = st.selectbox('Filtr klubu', team_options, key='eu-team')
        filtered = games if chosen == team_options[0] else games[(games['gospodarze']==chosen) | (games['goście']==chosen)]
        if len(filtered):
            show = filtered.sort_values(['data_sort','gospodarze'], ascending=[False,True]).head(100)
            show = show[['data','kolejka','gospodarze','wynik','goście']].rename(columns={'data':'Data','kolejka':'Kolejka','gospodarze':'Gospodarze','wynik':'Wynik','goście':'Goście'})
            st.dataframe(show, use_container_width=True, hide_index=True, height=396)
        else:
            st.info('Nie ma meczów dla wybranego klubu.')
        if len(filtered)>100:
            st.caption('Tabela pokazuje 100 ostatnich spotkań. Pełne dane pobierzesz poniżej.')
    st.markdown('<div class="eu-block-heading">Bilans drużyn<span>03 / PUNKTY I BRAMKI</span></div>', unsafe_allow_html=True)
    st.caption('Tabela obliczona ze spotkań zapisanych w bazie — nie jest tabelą oficjalną. W ligach z fazą mistrzowską, podziałem punktów, karami i innymi zasadami może się od niej różnić.')
    st.dataframe(stats, hide_index=True, use_container_width=True, height=min(420, 38*len(stats)+40))
    with st.expander('Źródło danych, licencja i eksport'):
        source = str(games.iloc[0]['źródło'])
        st.markdown(f'**Dostawca:** OpenFootball · **Licencja:** CC0 1.0  \n**Plik źródłowy:** {escape(source)}  \n**Sezon:** {escape(season)}')
        st.caption('Dostępne są wyniki meczów, ale bez indywidualnych statystyk, xG, wieku, asyst i ScoutScore. Dane nie trafiają do bazy zawodników.')
        st.download_button('Eksport meczów do CSV', data=games[['data','kolejka','gospodarze','wynik','goście']].to_csv(index=False).encode('utf-8-sig'), file_name=f'{league}_{season}_mecze.csv', mime='text/csv', key='eu-download')
    st.markdown('<div class="eu-footnote">SCOUTPRO / LIGI EUROPY <span>DANE MECZOWE ≠ OCENA ZAWODNIKA</span></div>', unsafe_allow_html=True)
