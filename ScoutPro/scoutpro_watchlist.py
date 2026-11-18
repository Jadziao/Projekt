"""Obserwowani: osobna baza użytkownika, bez ingerencji w statystyki."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import html
import pandas as pd
import streamlit as st
from scoutpro_common import player_key, text, esc, fmt, numeric, badge, player_label
from scoutpro_players import club_crest, SILHOUETTE


def _ensure(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS watchlist (
            player_key TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'Do analizy',
            note TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )''')


def _read(path: Path) -> dict[str, dict]:
    _ensure(path)
    with sqlite3.connect(path) as db:
        rows = db.execute('SELECT player_key,status,note,updated_at FROM watchlist').fetchall()
    return {r[0]: {"status":r[1], "note":r[2], "updated_at":r[3]} for r in rows}


def _put(path: Path, key: str, status: str='Do analizy', note: str=''):
    _ensure(path)
    with sqlite3.connect(path) as db:
        db.execute('''INSERT INTO watchlist (player_key,status,note,updated_at)
                  VALUES (?,?,?,?)
                  ON CONFLICT(player_key) DO UPDATE SET status=excluded.status,
                  note=excluded.note,updated_at=excluded.updated_at''',
                  (key, status, note, datetime.now(timezone.utc).isoformat()))


def _delete(path: Path, key: str):
    _ensure(path)
    with sqlite3.connect(path) as db:
        db.execute('DELETE FROM watchlist WHERE player_key=?', (key,))


def sync_watchlist(data: pd.DataFrame, path: Path):
    """Synchronizacja także z istniejącymi przyciskami w profilu/Explorerze.

    Pierwsze wejście: odczyt zapisu z osobnego SQLite. Kolejne uruchomienia:
    różnice w st.session_state.watchlist są dodawane/usuwane w SQLite.
    """
    if 'watchlist' not in st.session_state:
        st.session_state.watchlist=[]
    try:
        disk=_read(path)
    except (OSError, sqlite3.Error) as exc:
        st.session_state.watchlist_error = str(exc)
        return
    lookup={player_key(row): int(i) for i,row in data.iterrows()}
    if '_sp2_watch_shadow' not in st.session_state:
        loaded=[idx for k,idx in lookup.items() if k in disk]
        st.session_state.watchlist=list(dict.fromkeys(st.session_state.watchlist+loaded))
        st.session_state['_sp2_watch_shadow']=set(disk)
    current={player_key(data.loc[i]) for i in st.session_state.watchlist if i in data.index}
    shadow=set(st.session_state['_sp2_watch_shadow'])
    # Najpierw zachowaj osobiste notatki dla niezmienionych rekordów
    try:
        for k in current-shadow:
            _put(path,k)
        for k in shadow-current:
            if k in lookup:
                _delete(path,k)
    except (OSError,sqlite3.Error) as exc:
        st.session_state.watchlist_error = str(exc)
    st.session_state['_sp2_watch_shadow']=current


def add_watch(data:pd.DataFrame,index:int):
    if index not in st.session_state.watchlist:
        st.session_state.watchlist.append(index)


def remove_watch(data:pd.DataFrame,index:int):
    if index in st.session_state.watchlist:
        st.session_state.watchlist.remove(index)


def render_watchlist(data:pd.DataFrame,open_player, path:Path):
    st.markdown('''<section class="sp2-hero"><div class="sp2-eyebrow">TWOJA LISTA SKAUTINGOWA</div>
      <div class="sp2-hero-line"><div><h1>Obserwowani<span>.</span></h1>
      <p>Zbieraj kandydatów, dodawaj notatki i zarządzaj etapami obserwacji.</p></div>
      <div class="sp2-hero-symbol">☆</div></div></section>''',unsafe_allow_html=True)
    if st.session_state.get('watchlist_error'):
        st.warning('Nie udało się zapisać listy na dysku: ' + st.session_state['watchlist_error'])
    saved=[i for i in st.session_state.get('watchlist',[]) if i in data.index]
    one,two,three=st.columns(3)
    with one: st.metric('Obserwowani',len(saved),border=True)
    try: disk=_read(path)
    except (OSError,sqlite3.Error): disk={}
    statuses={i:disk.get(player_key(data.loc[i]),{}).get('status','Do analizy') for i in saved}
    with two: st.metric('Polecani',sum(v=='Polecany' for v in statuses.values()),border=True)
    with three: st.metric('W trakcie analizy',sum(v=='Obserwowany' for v in statuses.values()),border=True)

    f1,f2,f3=st.columns([2.3,1.1,1.1])
    query=f1.text_input('Szukaj na liście',placeholder='Nazwisko lub klub...',key='sp2_watch_q')
    status=f2.selectbox('Status',['Wszystkie','Do analizy','Obserwowany','Polecany'],key='sp2_watch_status')
    sort=f3.selectbox('Sortuj',['ScoutScore','Nazwisko','Wiek'],key='sp2_watch_sort')
    filtered=[i for i in saved if (status=='Wszystkie' or statuses[i]==status) and
        (not query or query.casefold() in player_label(data.loc[i]).casefold())]
    if sort=='ScoutScore': filtered.sort(key=lambda i: numeric(data.loc[[i]],'ScoutScore').iloc[0] if pd.notna(numeric(data.loc[[i]],'ScoutScore').iloc[0]) else -999,reverse=True)
    elif sort=='Nazwisko': filtered.sort(key=lambda i:text(data.loc[i].get('player_name')))
    else: filtered.sort(key=lambda i: float(data.loc[i].get('wiek_2025')) if pd.notna(data.loc[i].get('wiek_2025')) else 999)

    if not saved:
        st.markdown('<div class="sp2-empty"><div class="sp2-empty-icon">☆</div><h3>Twoja lista jest pusta</h3><p>Otwórz bazę zawodników i dodaj pierwszą osobę do obserwowanych.</p></div>',unsafe_allow_html=True)
        if st.button('Przejdź do bazy zawodników →',type='primary',key='sp2_watch_go'):
            st.session_state.page='Zawodnicy';st.session_state.player_mode='explorer';st.rerun()
        return

    if not filtered:
        st.info('Brak zawodników pasujących do filtrów.')
        return
    with st.container(key='sp2_watch_list'):
        for i in filtered:
            row=data.loc[i]
            k=player_key(row)
            record=disk.get(k,{"note":"","status":"Do analizy"})
            with st.container(key=f'sp2_watch_{i}',border=True):
                header_left,header_center,header_right=st.columns([2.1,1.2,.65],gap='medium',vertical_alignment='center')
                with header_left:
                    crest=club_crest(row.get('team_name'),row.get('team_id'),row.get('liga'))
                    st.markdown(f'<div class="sp2-watch-name"><span class="sp2-roundface">{SILHOUETTE}</span><div><b>{esc(row.get("player_name"))}</b><div class="sp2-watch-club">{crest} {esc(row.get("team_name"))} · {esc(row.get("liga"))}</div></div></div>',unsafe_allow_html=True)
                with header_center:
                    st.markdown(f'<div class="sp2-watch-brief">{esc(row.get("general_position"))} · {fmt(row.get("wiek_2025"),0)} lat · {fmt(row.get("minutes_played"),0)} min</div>',unsafe_allow_html=True)
                with header_right:
                    st.markdown(badge(row.get('ScoutScore')),unsafe_allow_html=True)
                c1,c2=st.columns([1.2,3])
                with c1:
                    options=['Do analizy','Obserwowany','Polecany']
                    selection=st.selectbox('Status',options,index=options.index(record['status']) if record['status'] in options else 0,key=f'sp2_watch_state_{i}')
                with c2:
                    note=st.text_area('Notatka skauta',value=record['note'],height=82,key=f'sp2_watch_note_{i}',placeholder='Twoje obserwacje, do sprawdzenia podczas kolejnej analizy...')
                a,b,c=st.columns([1.2,1.2,1.0])
                if a.button('Zapisz notatkę',key=f'sp2_watch_save_{i}',type='primary',use_container_width=True):
                    try:
                        _put(path,k,selection,note)
                        st.toast('Zapisano notatkę i status')
                    except (OSError,sqlite3.Error) as exc: st.error(str(exc))
                if b.button('Pokaż profil →',key=f'sp2_watch_profile_{i}',use_container_width=True):
                    open_player(i);st.rerun()
                if c.button('Usuń z listy',key=f'sp2_watch_remove_{i}',use_container_width=True):
                    remove_watch(data,i)
                    try:_delete(path,k)
                    except (OSError,sqlite3.Error) as exc:st.error(str(exc))
                    st.rerun()
    fields=['player_name','team_name','liga','general_position','wiek_2025','minutes_played','ScoutScore']
    export=data.loc[filtered,[c for c in fields if c in data.columns]].copy()
    export['Status']=[statuses[i] for i in filtered]
    st.download_button('Eksportuj listę CSV',data=export.to_csv(index=False).encode('utf-8-sig'),file_name='scoutpro_obserwowani.csv',mime='text/csv',key='sp2_watch_csv')
    st.caption('Statusy i notatki zapisują się w osobnym pliku database/scoutpro_user.db. Zapisz notatkę przyciskiem, aby zachować zmiany.')
