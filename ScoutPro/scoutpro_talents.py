"""Talenty U21: filtrowany ranking, karty i lista do analizy."""
from __future__ import annotations
import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scoutpro_common import POSITION_GROUPS,numeric,fmt,value,esc,text,badge,player_label,percentile,peers,available_leagues,league_label
from scoutpro_players import club_crest,SILHOUETTE

SORTS={'ScoutScore':'ScoutScore','xG / 90':'xgoals_90','xA / 90':'xassists_90','Goals Added / 90':'gplus_above_avg_90','Minuty':'minutes_played'}

def _talent_card(row:pd.Series,index:int) -> str:
    crest=club_crest(row.get('team_name'),row.get('team_id'),row.get('liga'))
    return f'''<div class="sp2-talent"><div class="sp2-talent-label">TALENT #{index}</div>
      <div class="sp2-talent-row"><div class="sp2-talent-avatar">{SILHOUETTE}</div>
        <div class="sp2-talent-info"><h3>{esc(row.get('player_name'))}</h3><span class="sp2-club">{crest}{esc(row.get('team_name'))}</span>
        <p>{esc(row.get('liga'))} · {esc(row.get('general_position'))} · {fmt(row.get('wiek_2025'),0)} lat</p></div>
      </div><div class="sp2-talent-footer"><div><span>ScoutScore</span><strong>{fmt(row.get('ScoutScore'),1)}</strong></div>
      <div><span>Minuty</span><strong>{fmt(row.get('minutes_played'),0)}</strong></div></div></div>'''

def render_talents(data:pd.DataFrame,open_player):
    st.markdown('''<section class="sp2-hero sp2-hero-talent"><div class="sp2-eyebrow">SCOUTPRO · DISCOVERY</div>
      <div class="sp2-hero-line"><div><h1>Talenty<span>.</span></h1>
      <p>Odkrywaj młodych piłkarzy, porównuj ich wyniki i buduj własną shortlistę.</p></div>
      <div class="sp2-hero-symbol">✦</div></div></section>''',unsafe_allow_html=True)
    u21=data[numeric(data,'wiek_2025').le(21)]
    eligible=u21[numeric(u21,'ScoutScore').notna()]
    c1,c2,c3=st.columns(3)
    c1.metric('Rekordy U21',len(u21),border=True)
    c2.metric('Z oceną ScoutScore',len(eligible),border=True)
    c3.metric('Obserwowani U21',sum(i in u21.index for i in st.session_state.get('watchlist',[])),border=True)
    with st.container(key='sp2_talent_filters',border=True):
        f1,f2,f3,f4=st.columns(4)
        league=f1.selectbox('Liga',available_leagues(data)+['Wszystkie'],format_func=league_label,key='sp2_tal_league')
        group=f2.selectbox('Grupa pozycji',['Wszystkie','Atak','Pomoc','Obrona'],key='sp2_tal_group')
        age=f3.selectbox('Maksymalny wiek',[21,20,19,18,17],key='sp2_tal_age')
        mins=f4.selectbox('Min. rozegranych minut',[450,900,1350,0],format_func=lambda n:f'{n} min' if n else 'Bez minimum',key='sp2_tal_mins')
        f5,f6=st.columns([1,1])
        sort=f5.selectbox('Sortuj po',list(SORTS),key='sp2_tal_sort')
        only_rated=f6.toggle('Tylko z oceną ScoutScore',value=True,key='sp2_tal_rated')
    mask=numeric(data,'wiek_2025').le(age)&numeric(data,'minutes_played').ge(mins)
    if league!='Wszystkie': mask &= data['liga'].eq(league)
    groups=data['general_position'].fillna('').astype(str).map(POSITION_GROUPS)
    if group!='Wszystkie': mask &= groups.eq(group)
    if only_rated: mask &= numeric(data,'ScoutScore').notna()
    result=data[mask].copy()
    key=SORTS[sort]
    result['_sp2_sort']=numeric(result,key)
    result=result.sort_values('_sp2_sort',ascending=False,na_position='last',kind='stable')
    st.markdown(f'<div class="sp2-sectionline"><h3>Wyróżnieni zawodnicy</h3><span>{len(result)} rekordów spełniających kryteria</span></div>',unsafe_allow_html=True)
    if league=='Wszystkie':
        st.info('ScoutScore jest liczony oddzielnie dla każdej ligi i grupy pozycji. Przy wyborze wszystkich lig ranking ma charakter orientacyjny — nie jest porównaniem poziomu rozgrywek.')
    if len(result)==0:
        st.info('Brak zawodników dla wybranych filtrów. Zmień ligę, wiek lub minimalną liczbę minut.');return
    top=result.head(3)
    cols=st.columns(3,gap='medium')
    for rank,(i,row) in enumerate(top.iterrows(),start=1):
        with cols[rank-1]:
            st.markdown(_talent_card(row,rank),unsafe_allow_html=True)
            a,b=st.columns([1,1])
            if a.button('Otwórz profil →',key=f'sp2_tal_open_{i}',use_container_width=True):open_player(i);st.rerun()
            watching=i in st.session_state.get('watchlist',[])
            if b.button('★ Zapisany' if watching else '☆ Obserwuj',key=f'sp2_tal_watch_{i}',use_container_width=True):
                if watching: st.session_state.watchlist.remove(i)
                else:st.session_state.watchlist.append(i)
                st.rerun()
    left,right=st.columns([1.75,1],gap='medium')
    with left:
        with st.container(key='sp2_tal_table',border=True):
            st.markdown('#### Ranking talentów')
            columns={'player_name':'Zawodnik','team_name':'Klub','liga':'Liga','general_position':'Poz.','wiek_2025':'Wiek','minutes_played':'Minuty','ScoutScore':'ScoutScore'}
            tab=result[[c for c in columns if c in result.columns]].copy().rename(columns=columns)
            tab['ScoutScore']=pd.to_numeric(tab.get('ScoutScore'),errors='coerce')
            config={'ScoutScore':st.column_config.ProgressColumn('ScoutScore',min_value=0,max_value=100,format='%.1f')}
            st.dataframe(tab,hide_index=True,use_container_width=True,height=460,column_config=config)
            st.download_button('Eksportuj ranking CSV',tab.to_csv(index=False).encode('utf-8-sig'),file_name='scoutpro_talenty_2025.csv',mime='text/csv',key='sp2_tal_download')
    with right:
        with st.container(key='sp2_tal_explore',border=True):
            st.markdown('#### Odkrywaj zawodników')
            st.caption('Wybierz piłkarza, aby przejść do jego pełnego profilu.')
            index=st.selectbox('Zawodnik',result.index.tolist(),format_func=lambda i:player_label(data.loc[i]),key='sp2_tal_choose')
            player=data.loc[index]
            st.markdown(f'<div class="sp2-focus"><span>ScoutScore</span><strong>{fmt(player.get("ScoutScore"),1)}</strong><small>{esc(player.get("liga"))} · {esc(player.get("general_position"))}</small></div>',unsafe_allow_html=True)
            if st.button('Pokaż pełny profil →',type='primary',use_container_width=True,key='sp2_tal_focus_open'):open_player(index);st.rerun()
        with st.container(key='sp2_tal_signals',border=True):
            st.markdown('#### Statystyki do sprawdzenia')
            group_for=POSITION_GROUPS.get(text(player.get('general_position')))
            metrics={'Atak':[('xgoals_90','xG / 90'),('xassists_90','xA / 90')],
                     'Pomoc':[('xassists_90','xA / 90'),('key_passes_90','Kluczowe podania / 90')],
                     'Obrona':[('gplus_interrupting_90','g+ obrona / 90'),('gplus_passing_90','g+ podania / 90')]}.get(group_for,[])
            cohort=peers(data,player)
            any_signal=False
            for key,label in metrics:
                pct=percentile(player.get(key),numeric(cohort,key))
                if pct is None:continue
                any_signal=True
                st.markdown(f'<div class="sp2-meter-head"><span>{esc(label)}</span><strong>{pct:.0f}. percentyl</strong></div><div class="sp2-meter"><i style="width:{max(0,min(100,pct)):.1f}%"></i></div>',unsafe_allow_html=True)
            if not any_signal:st.caption('Za mało danych porównawczych dla wybranej pozycji.')
            st.caption('Wskaźniki są porównywane tylko w obrębie ligi i grupy pozycji, przy minimum 450 minutach.')
