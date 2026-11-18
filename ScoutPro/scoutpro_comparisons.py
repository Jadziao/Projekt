"""Porównania dwóch piłkarzy w tej samej lidze i grupie pozycji."""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scoutpro_common import METRICS, POSITION_GROUPS, peers, percentile, numeric, text, esc, fmt, value, badge, player_label, available_leagues, league_label
from scoutpro_players import club_crest, SILHOUETTE

GREEN='#4bd726'; BLUE='#61785a'

def _person_card(row:pd.Series, label:str) -> str:
    crest=club_crest(row.get('team_name'),row.get('team_id'),row.get('liga'))
    return f'''<div class="sp2-person"><div class="sp2-person-title">{esc(label)}</div>
      <div class="sp2-person-head"><span class="sp2-person-avatar">{SILHOUETTE}</span>
      <div><h2>{esc(row.get('player_name'))}</h2><span class="sp2-club">{crest}{esc(row.get('team_name'))}</span>
      <p>{esc(row.get('liga'))} · {esc(row.get('general_position'))} · {fmt(row.get('wiek_2025'),0)} lat</p></div></div>
      <div class="sp2-person-metrics"><div><span>ScoutScore</span><strong>{fmt(row.get('ScoutScore'),1)}</strong></div>
      <div><span>Minuty</span><strong>{fmt(row.get('minutes_played'),0)}</strong></div>
      <div><span>Bramki</span><strong>{fmt(row.get('goals'),0)}</strong></div>
      <div><span>Asysty</span><strong>{fmt(row.get('primary_assists'),0)}</strong></div></div></div>'''

def _radar(data:pd.DataFrame,a:pd.Series,b:pd.Series, group:str):
    cohort=peers(data,a)
    items=[]
    for key,label in METRICS.get(group,[]):
        pa=percentile(a.get(key),numeric(cohort,key))
        pb=percentile(b.get(key),numeric(cohort,key))
        if pa is not None and pb is not None:
            items.append((key,label,pa,pb))
    if len(items)<3:return None,items
    labels=[x[1] for x in items]; av=[x[2] for x in items];bv=[x[3] for x in items]
    fig=go.Figure()
    for vals,name,color in [(av,text(a.get('player_name')),GREEN),(bv,text(b.get('player_name')),BLUE)]:
        fig.add_trace(go.Scatterpolar(r=vals+[vals[0]],theta=labels+[labels[0]],name=name,
            fill='toself',fillcolor='rgba(34,230,154,0.16)' if color==GREEN else 'rgba(117,184,252,0.12)',
            line=dict(color=color,width=2.5),marker=dict(color=color,size=6),hovertemplate='%{theta}: %{r:.1f} percentyl<extra>'+name+'</extra>'))
    fig.update_layout(height=360,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=45,r=45,t=20,b=25),font=dict(color='#253525'),
        polar=dict(bgcolor='rgba(0,0,0,0)',radialaxis=dict(range=[0,100],gridcolor='rgba(72,101,69,.14)',tickfont=dict(size=9)),angularaxis=dict(gridcolor='rgba(72,101,69,.12)',tickfont=dict(size=11))),
        legend=dict(orientation='h',y=-.12,x=.5,xanchor='center',font=dict(size=11)),
        hoverlabel=dict(bgcolor='#fffefa',font_color='#172415'))
    return fig,items

def _bars(items,a,b):
    if not items:return None
    labels=[it[1] for it in items]
    fig=go.Figure()
    fig.add_trace(go.Bar(y=labels,x=[it[2] for it in items],name=text(a.get('player_name')),orientation='h',marker_color=GREEN))
    fig.add_trace(go.Bar(y=labels,x=[it[3] for it in items],name=text(b.get('player_name')),orientation='h',marker_color=BLUE))
    fig.update_layout(barmode='group',height=330,margin=dict(t=8,b=15,l=12,r=10),
        plot_bgcolor='rgba(0,0,0,0)',paper_bgcolor='rgba(0,0,0,0)',font=dict(color='#253525',size=11),
        xaxis=dict(range=[0,100],title='Percentyl',gridcolor='rgba(190,225,210,.10)'),
        yaxis=dict(autorange='reversed',gridcolor='rgba(0,0,0,0)'),
        legend=dict(orientation='h',y=-.22),hoverlabel=dict(bgcolor='#fffefa',font_color='#172415'))
    return fig

def render_comparisons(data:pd.DataFrame,open_player):
    st.markdown('''<section class="sp2-hero"><div class="sp2-eyebrow">ANALIZA PORÓWNAWCZA</div>
      <div class="sp2-hero-line"><div><h1>Porównania<span>.</span></h1>
      <p>Zestaw dwóch zawodników i sprawdź ich przewagi na podstawie rzeczywistych statystyk.</p></div>
      <div class="sp2-hero-symbol">⇄</div></div></section>''',unsafe_allow_html=True)
    f1,f2=st.columns(2)
    liga=f1.selectbox('Liga',available_leagues(data),format_func=league_label,key='sp2_cmp_liga')
    groups=['Atak','Pomoc','Obrona']
    group=f2.selectbox('Grupa pozycji',groups,key='sp2_cmp_group')
    mapped=data['general_position'].fillna('').astype(str).map(POSITION_GROUPS)
    subset=data[(data['liga']==liga)&(mapped==group)&(numeric(data,'minutes_played')>=450)].copy()
    choices=subset.sort_values('player_name').index.tolist()
    if len(choices)<2:
        st.info('W tej lidze i grupie brakuje co najmniej dwóch zawodników z minimum 450 minutami.')
        return
    l,r=st.columns(2,gap='medium')
    with l:
        ai=st.selectbox('Zawodnik A',choices,format_func=lambda i:player_label(data.loc[i]),key='sp2_cmp_a')
    with r:
        bi=st.selectbox('Zawodnik B',choices,index=1,format_func=lambda i:player_label(data.loc[i]),key='sp2_cmp_b')
    if ai==bi:
        st.warning('Wybierz dwóch różnych zawodników.');return
    a,b=data.loc[ai],data.loc[bi]
    ca,cb=st.columns(2,gap='medium')
    with ca:
        st.markdown(_person_card(a,'ZAWODNIK A'),unsafe_allow_html=True)
        x,y=st.columns(2)
        if x.button('Pokaż profil A →',use_container_width=True,key='sp2_cmp_view_a'):
            open_player(ai);st.rerun()
        if y.button('☆ Obserwuj A' if ai not in st.session_state.get('watchlist',[]) else '★ Obserwowany',use_container_width=True,key='sp2_cmp_watch_a'):
            if ai not in st.session_state.watchlist: st.session_state.watchlist.append(ai)
            else: st.session_state.watchlist.remove(ai)
            st.rerun()
    with cb:
        st.markdown(_person_card(b,'ZAWODNIK B'),unsafe_allow_html=True)
        x,y=st.columns(2)
        if x.button('Pokaż profil B →',use_container_width=True,key='sp2_cmp_view_b'):
            open_player(bi);st.rerun()
        if y.button('☆ Obserwuj B' if bi not in st.session_state.get('watchlist',[]) else '★ Obserwowany',use_container_width=True,key='sp2_cmp_watch_b'):
            if bi not in st.session_state.watchlist: st.session_state.watchlist.append(bi)
            else: st.session_state.watchlist.remove(bi)
            st.rerun()
    radar,items=_radar(data,a,b,group)
    c1,c2=st.columns([1.05,1],gap='medium')
    with c1:
        with st.container(key='sp2_cmp_radar',border=True):
            st.markdown('#### Radar statystyczny')
            if radar:st.plotly_chart(radar,use_container_width=True,config={'displayModeBar':False})
            else:st.info('Za mało wspólnych wskaźników, aby pokazać radar.')
            st.caption('Percentyle wśród zawodników tej samej ligi i grupy pozycji (min. 450 minut).')
    with c2:
        with st.container(key='sp2_cmp_bars',border=True):
            st.markdown('#### Różnice względem ligi')
            bars=_bars(items,a,b)
            if bars:st.plotly_chart(bars,use_container_width=True,config={'displayModeBar':False})
            else:st.info('Za mało porównywalnych statystyk.')
            st.caption('Skala 0–100 oznacza percentyle, a nie procent skuteczności.')
    details=[('ScoutScore','ScoutScore',1),('Minuty','minutes_played',0),('Bramki','goals',0),('Asysty','primary_assists',0),('xG / 90','xgoals_90',3),('xA / 90','xassists_90',3),('Gole / 90','goals_90',3),('Asysty / 90','primary_assists_90',3),('Goals Added / 90','gplus_above_avg_90',3),('Celne strzały / 90','shots_on_target_90',3),('Kluczowe podania / 90','key_passes_90',3)]
    out=pd.DataFrame([{'Statystyka':label,text(a.get('player_name')):fmt(a.get(key),dig),text(b.get('player_name')):fmt(b.get(key),dig)} for label,key,dig in details if key in data.columns])
    with st.container(key='sp2_cmp_details',border=True):
        st.markdown('#### Pełne zestawienie')
        st.dataframe(out,hide_index=True,use_container_width=True)
        st.download_button('Pobierz porównanie CSV',out.to_csv(index=False).encode('utf-8-sig'),file_name='scoutpro_porownanie.csv',mime='text/csv')
    st.caption('ScoutScore pokazuje wynik względem piłkarzy z tej samej ligi i grupy pozycji. Nie jest prognozą potencjału.')
