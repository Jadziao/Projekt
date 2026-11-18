"""ScoutPro — pełny profil zawodnika (A + B).

Wczytuje już przygotowany DataFrame PlayerScoutScore2025. Nie zmienia bazy.
Wykresy percentylowe wylicza w obrębie ligi i grupy pozycji.
"""
from __future__ import annotations

import html
import math
import re
from typing import Any, Callable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


POSITIONS = {
    "GK": "Bramkarz", "CB": "Środkowy obrońca", "FB": "Boczny obrońca",
    "DM": "Defensywny pomocnik", "CM": "Środkowy pomocnik",
    "AM": "Ofensywny pomocnik", "W": "Skrzydłowy", "ST": "Napastnik",
}
GROUPS = {"ST": "Atak", "W": "Atak", "AM": "Pomoc", "CM": "Pomoc",
          "DM": "Pomoc", "CB": "Obrona", "FB": "Obrona"}

# Radar: wskaźniki dobierane do roli. To percentyle porównawcze, nie oceny umiejętności.
METRICS = {
    "Atak": [
        ("xgoals_90", "xG/90"), ("xassists_90", "xA/90"),
        ("shots_on_target_90", "Strz. celne/90"),
        ("gplus_shooting_90", "g+ strzały/90"),
        ("gplus_above_avg_90", "g+ /90"),
    ],
    "Pomoc": [
        ("xassists_90", "xA/90"), ("key_passes_90", "Klucz. pod./90"),
        ("gplus_passing_90", "g+ podania/90"),
        ("passes_completed_over_expected_p100", "Podania +/100"),
        ("gplus_above_avg_90", "g+ /90"),
    ],
    "Obrona": [
        ("gplus_interrupting_90", "g+ odbiór/90"),
        ("gplus_passing_90", "g+ podania/90"),
        ("passes_completed_over_expected_p100", "Podania +/100"),
        ("gplus_above_avg_90", "g+ /90"), ("xassists_90", "xA/90"),
    ],
}

STAT_SEASON = [
    ("minutes_played", "Minuty", 0), ("count_games", "Mecze (jeśli dostępne)", 0),
    ("goals", "Bramki", 0), ("primary_assists", "Asysty", 0),
    ("shots", "Strzały", 0), ("shots_on_target", "Strzały celne", 0),
    ("key_passes", "Kluczowe podania", 0),
    ("xgoals", "Oczekiwane gole (xG)", 2),
    ("xassists", "Oczekiwane asysty (xA)", 2),
    ("attempted_passes", "Próby podań", 0),
    ("pass_completion_percentage", "Skuteczność podań (wartość API)", 2),
    ("passes_completed_over_expected", "Podania ponad oczekiwaną liczbę", 2),
]
STAT_90 = [
    ("goals_90", "Bramki / 90", 2),
    ("primary_assists_90", "Asysty / 90", 2),
    ("xgoals_90", "xG / 90", 3),
    ("xassists_90", "xA / 90", 3),
    ("shots_on_target_90", "Strzały celne / 90", 2),
    ("key_passes_90", "Kluczowe podania / 90", 2),
    ("gplus_above_avg_90", "g+ ponad średnią / 90", 3),
    ("passes_completed_over_expected_p100", "Podania ponad oczekiwania / 100", 3),
]
GA_CATEGORIES = [
    ("gplus_dribbling_90", "Drybling"),
    ("gplus_passing_90", "Podania"),
    ("gplus_receiving_90", "Przyjęcia"),
    ("gplus_shooting_90", "Strzały"),
    ("gplus_interrupting_90", "Przerywanie akcji"),
    ("gplus_fouling_90", "Faule"),
]


def n(value: Any) -> float | None:
    """Liczba lub None; nie traktujemy pustych wartości jako 0."""
    if isinstance(value, (list, dict, tuple)):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def f(value: Any, decimals: int = 1) -> str:
    number = n(value)
    if number is None:
        return "—"
    return f"{number:,.{decimals}f}".replace(",", " ")


def text(value: Any, fallback: str = "—") -> str:
    if value is None or isinstance(value, (dict, list, tuple)):
        return fallback
    try:
        if bool(pd.isna(value)):
            return fallback
    except (TypeError, ValueError):
        pass
    return str(value).strip() or fallback


def esc(value: Any, fallback: str = "—") -> str:
    return html.escape(text(value, fallback), quote=True)


def _metric(row: pd.Series, key: str) -> float | None:
    return n(row.get(key))


def _peer_group(data: pd.DataFrame, player: pd.Series) -> pd.DataFrame:
    league = text(player.get("liga"))
    group = GROUPS.get(text(player.get("general_position")))
    if group is None:
        return data.iloc[:0].copy()
    positions = [key for key, value in GROUPS.items() if value == group]
    mins = pd.to_numeric(data.get("minutes_played", pd.Series(index=data.index, dtype=float)), errors="coerce")
    return data.loc[(data["liga"] == league) & data["general_position"].isin(positions) & (mins >= 450)]


def percentile(value: Any, peers: pd.Series) -> float | None:
    """Pozycja danej wartości na tle niezależnego zbioru zawodników.

    Mid-rank dla remisów; wynik nie zakłada, że niska wartość oznacza brak danych.
    """
    v = n(value)
    if v is None:
        return None
    vals = pd.to_numeric(peers, errors="coerce").dropna()
    if len(vals) < 5:
        return None
    result = (int((vals < v).sum()) + .5 * int((vals == v).sum())) / len(vals) * 100
    return round(float(result), 1)


def metric_percentiles(data: pd.DataFrame, player: pd.Series):
    group = GROUPS.get(text(player.get("general_position")))
    peers = _peer_group(data, player)
    result = []
    for key, label in METRICS.get(group, []):
        if key not in data.columns:
            continue
        numeric = pd.to_numeric(peers[key], errors="coerce")
        pct = percentile(player.get(key), numeric)
        if pct is None:
            continue
        result.append({"key": key, "label": label, "value": n(player.get(key)),
                       "percentile": pct, "peers": int(numeric.notna().sum()),
                       "median": n(numeric.median())})
    return result


def _radar(items: list[dict]) -> str:
    if len(items) < 3:
        return '<div class="spf-empty">Za mało porównywalnych wskaźników do wykresu radarowego.</div>'
    count = len(items)
    cx, cy, radius = 230, 178, 105
    def pt(i: int, r: float):
        ang = -math.pi / 2 + i * 2 * math.pi / count
        return cx + math.cos(ang) * r, cy + math.sin(ang) * r
    def pair(i: int, r: float) -> str:
        x, y = pt(i, r)
        return f"{x:.1f},{y:.1f}"
    layers = []
    for p in (25, 50, 75, 100):
        points = " ".join(pair(i, radius * p / 100) for i in range(count))
        layers.append(f'<polygon points="{points}" fill="none" stroke="#34594e" stroke-width="1" opacity=".6"/>')
    for i in range(count):
        x, y = pt(i, radius)
        layers.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#315247" stroke-width="1"/>')
    poly = " ".join(pair(i, radius * float(item["percentile"]) / 100) for i, item in enumerate(items))
    layers.append(f'<polygon points="{poly}" fill="#16dc91" fill-opacity=".23" stroke="#27e9a2" stroke-width="2.5"/>')
    for i, item in enumerate(items):
        x, y = pt(i, radius * float(item["percentile"]) / 100)
        layers.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#2ff1b0"/>')
        x, y = pt(i, radius + 27)
        anchor = "middle" if abs(x - cx) < 14 else ("start" if x > cx else "end")
        layers.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" fill="#adcfbe" font-size="10.5">{esc(item["label"])}</text>')
    return (f'<svg class="spf-radar" viewBox="0 0 460 360" role="img" '
            f'aria-label="Radar percentyli na tle zawodników z tej samej ligi i grupy pozycji">'
            + "".join(layers) + "</svg>")


def _comparison_bars(items: list[dict]) -> str:
    if not items:
        return '<p class="spf-empty">Brak wystarczających danych do porównania.</p>'
    blocks = []
    for item in items:
        v = max(0, min(100, float(item["percentile"])))
        blocks.append(
            '<div class="spf-compare-item">'
            f'<div class="spf-compare-top"><span>{esc(item["label"])}</span><b>{v:.0f}. percentyl</b></div>'
            f'<div class="spf-compare-track"><span style="width:{v:.1f}%"></span></div>'
            '</div>'
        )
    return "".join(blocks)


def _ga_bars(items: list[tuple[str, float]]) -> str:
    if not items:
        return '<p class="spf-empty">Dla tego zawodnika nie ma szczegółowych danych Goals Added.</p>'
    biggest = max(abs(num) for _, num in items) or 1.0
    blocks = []
    for label, value in items:
        width = 48 * abs(value) / biggest
        left = 50 if value >= 0 else 50 - width
        cls = "spf-positive" if value >= 0 else "spf-negative"
        blocks.append(
            '<div class="spf-ga-row">'
            f'<span class="spf-ga-label">{esc(label)}</span>'
            '<div class="spf-ga-track"><span class="spf-ga-mid"></span>'
            f'<span class="spf-ga-bar {cls}" style="left:{left:.2f}%;width:{width:.2f}%"></span></div>'
            f'<strong>{value:+.3f}</strong></div>'
        )
    return "".join(blocks)


def _dataframe(row: pd.Series, specs: list[tuple[str, str, int]]) -> pd.DataFrame:
    records = []
    for key, label, decimals in specs:
        if key not in row.index:
            continue
        records.append({"Statystyka": label, "Wartość": f(row.get(key), decimals)})
    return pd.DataFrame(records)


def _source_note() -> None:
    st.markdown(
        '<p class="spf-source">Dane: American Soccer Analysis, sezon 2025 '
        '(<a href="https://www.americansocceranalysis.com/" target="_blank">źródło</a>, '
        '<a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank">CC BY-SA 4.0</a>). '
        'ScoutScore to autorska ocena statystyczna, nie prognoza potencjału zawodnika.</p>',
        unsafe_allow_html=True,
    )



# ===========================================================
# PODSUMOWANIE V2: interaktywne wykresy + realne statystyki
# ===========================================================
SCATTER_METRICS = {
    "Atak": ("xgoals_90", "xG / 90", "xassists_90", "xA / 90"),
    "Pomoc": ("xassists_90", "xA / 90", "key_passes_90", "Kluczowe podania / 90"),
    "Obrona": ("gplus_interrupting_90", "g+ przerywanie / 90", "gplus_passing_90", "g+ podania / 90"),
}
PLOT_BACKGROUND = "rgba(0,0,0,0)"
GREEN = "#4dcc23"
GREY = "#879084"


def _plot_layout(fig: go.Figure, height: int):
    fig.update_layout(
        height=height, margin=dict(t=22, r=17, b=22, l=17),
        paper_bgcolor=PLOT_BACKGROUND, plot_bgcolor=PLOT_BACKGROUND,
        font=dict(color="#263525", size=12),
        showlegend=False,
        hoverlabel=dict(bgcolor="#ffffff", font_color="#142415", bordercolor="#a9c2a2"),
    )
    return fig


def _plotly_radar(items: list[dict]) -> go.Figure | None:
    """Radar prawdziwych percentyli, nie subiektywnych 'umiejętności'."""
    if len(items) < 3:
        return None
    labels = [m["label"] for m in items]
    values = [float(m["percentile"]) for m in items]
    actual = [m["value"] for m in items]
    hover = [
        f"{html.escape(str(label))}<br>Wartość: {f(val, 3)}<br>Percentyl: {pct:.0f}"
        for label, val, pct in zip(labels, actual, values)
    ]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values+[values[0]], theta=labels+[labels[0]],
        fill="toself", mode="lines+markers",
        fillcolor="rgba(77,204,35,.17)",
        line=dict(color=GREEN, width=3),
        marker=dict(color=GREEN, size=7),
        hovertext=hover+[hover[0]], hoverinfo="text",
    ))
    _plot_layout(fig, 315)
    fig.update_layout(
        margin=dict(t=43, r=55, b=36, l=55),
        polar=dict(bgcolor=PLOT_BACKGROUND,
                   radialaxis=dict(range=[0,100], tickvals=[25,50,75,100],
                                   tickfont=dict(color="#818b7c",size=9),
                                   gridcolor="rgba(70,95,61,.14)",
                                   linecolor="rgba(70,95,61,.14)", angle=90),
                   angularaxis=dict(gridcolor="rgba(70,95,61,.12)",
                                    linecolor="rgba(70,95,61,.12)",
                                    tickfont=dict(color="#33452e", size=11))))
    return fig


def _plotly_scatter(peers: pd.DataFrame, player: pd.Series) -> tuple[go.Figure | None, int]:
    """Porównujemy po 2 realnych wskaźnikach, w tej samej lidze i grupie pozycji."""
    group = GROUPS.get(text(player.get("general_position")))
    spec = SCATTER_METRICS.get(group)
    if spec is None:
        return None, 0
    xkey, xlabel, ykey, ylabel = spec
    if xkey not in peers.columns or ykey not in peers.columns:
        return None, 0
    clean = peers.copy()
    clean[xkey] = pd.to_numeric(clean[xkey], errors="coerce")
    clean[ykey] = pd.to_numeric(clean[ykey], errors="coerce")
    clean = clean.loc[clean[xkey].notna() & clean[ykey].notna()].copy()
    if len(clean) < 5:
        return None, len(clean)

    names = clean["player_name"].fillna("Nieznany zawodnik").astype(str) if "player_name" in clean else pd.Series("Zawodnik", index=clean.index)
    clubs = clean["team_name"].fillna("Nieznany klub").astype(str) if "team_name" in clean else pd.Series("Nieznany klub", index=clean.index)
    hoverdata = [[html.escape(name), html.escape(club)] for name,club in zip(names,clubs)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=clean[xkey], y=clean[ykey], mode="markers", name="Pozostali",
        marker=dict(color="rgba(133,169,155,.52)", size=9, line=dict(width=0)),
        customdata=hoverdata,
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                      + xlabel + ": %{x:.3f}<br>" + ylabel + ": %{y:.3f}<extra></extra>",
    ))
    xv, yv = n(player.get(xkey)), n(player.get(ykey))
    if xv is not None and yv is not None:
        fig.add_trace(go.Scatter(
            x=[xv], y=[yv], mode="markers", name="Wybrany zawodnik",
            marker=dict(size=17, color=GREEN, symbol="star", line=dict(color="#2d4528", width=1.5)),
            hovertemplate="Wybrany zawodnik<br>"+xlabel+": %{x:.3f}<br>"+ylabel+": %{y:.3f}<extra></extra>",
        ))
    _plot_layout(fig, 315)
    fig.update_layout(
        margin=dict(t=12, r=16, b=52, l=55),
        xaxis=dict(title=xlabel, gridcolor="rgba(70,95,61,.12)",
                   zerolinecolor="rgba(122,177,158,.17)",
                   title_font=dict(size=11), tickfont=dict(size=10)),
        yaxis=dict(title=ylabel, gridcolor="rgba(70,95,61,.12)",
                   zerolinecolor="rgba(122,177,158,.17)",
                   title_font=dict(size=11), tickfont=dict(size=10)),
    )
    return fig, len(clean)


def _plotly_ga(player: pd.Series) -> go.Figure | None:
    items = [(label, n(player.get(key))) for key, label in GA_CATEGORIES]
    items = [(label, val) for label, val in items if val is not None]
    if not items:
        return None
    names = [label for label, _ in items][::-1]
    values = [value for _, value in items][::-1]
    colors = [GREEN if v >= 0 else "#e88d80" for v in values]
    fig = go.Figure(go.Bar(
        x=values, y=names, orientation="h", marker=dict(color=colors),
        text=[f"{v:+.3f}" for v in values], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>g+ ponad średnią / 90: %{x:+.3f}<extra></extra>"
    ))
    _plot_layout(fig, 270)
    fig.update_layout(
        margin=dict(t=8, r=62, b=40, l=92),
        xaxis=dict(title="g+ ponad średnią / 90", gridcolor="rgba(70,95,61,.12)",
                   title_font=dict(size=10), tickfont=dict(size=9)),
        yaxis=dict(tickfont=dict(size=11)),
    )
    fig.add_vline(x=0, line_color="rgba(223,239,230,.5)", line_width=1)
    return fig


def _insights_html(items: list[dict]) -> str:
    """Wyłącznie opis percentyli z danych — bez opinii lub sztucznej oceny."""
    good = sorted((item for item in items if item["percentile"] >= 75 and item["peers"] >= 10),
                  key=lambda item: item["percentile"], reverse=True)[:3]
    if not good:
        return '<div class="spf-summary-empty">Brak wskaźników powyżej 75. percentyla lub zbyt mała próba porównawcza. Pełne dane są w zakładce Statystyki.</div>'
    return "".join(
        '<div class="spf-highlight">'
        '<span class="spf-highlight-dot">↗</span>'
        '<span class="spf-highlight-main">'
        f'<b>{esc(item["label"])}</b><small>Wartość: {f(item["value"],3)} · Mediana grupy: {f(item["median"],3)}</small>'
        '</span>'
        f'<strong>{float(item["percentile"]):.0f}. percentyl</strong>'
        '</div>' for item in good
    )


def _profile_summary(data: pd.DataFrame, player: pd.Series, peers: pd.DataFrame, items: list[dict], selected: int) -> None:
    """Zwięzły, responsywny widok A+B. Tylko wartości z istniejącej bazy SQLite."""
    league = text(player.get("liga"))
    group = GROUPS.get(text(player.get("general_position")), "Nieustalona")

    # Na górze pokazujemy statystyki dobrane do roli, bez powtarzania czterech kart nagłówka.
    if group == "Obrona":
        selected_kpis = [("g+ przerywanie / 90", "gplus_interrupting_90", 3),
                         ("Podania + / 100", "passes_completed_over_expected_p100", 2),
                         ("g+ ponad średnią / 90", "gplus_above_avg_90", 3)]
    elif group == "Pomoc":
        selected_kpis = [("xA / 90", "xassists_90", 3),
                         ("Kluczowe podania / 90", "key_passes_90", 2),
                         ("g+ ponad średnią / 90", "gplus_above_avg_90", 3)]
    else:
        selected_kpis = [("xG / 90", "xgoals_90", 3),
                         ("xA / 90", "xassists_90", 3),
                         ("g+ ponad średnią / 90", "gplus_above_avg_90", 3)]
    boxes = "".join(
        f'<div class="spf-summary-kpi"><span>{esc(label)}</span><b>{f(player.get(key), digs)}</b></div>'
        for label, key, digs in selected_kpis
    )
    st.markdown(f'<div class="spf-summary-kpis">{boxes}</div>', unsafe_allow_html=True)

    left, right = st.columns([1, 1], gap="medium")
    with left:
        with st.container(key="spf_summary_radar"):
            st.markdown('<div class="spf-card-head"><h3>Profil statystyczny</h3><span>PERCENTYLE</span></div>', unsafe_allow_html=True)
            radar = _plotly_radar(items)
            if radar is None:
                st.info("Brak wystarczających statystyk do radaru.")
            else:
                st.plotly_chart(radar, use_container_width=True, theme=None,
                                config={"displayModeBar": False}, key=f"spf_radar_v2_{selected}")
            st.caption("Percentyle 0–100 na tle tej samej ligi i grupy pozycji. To nie oceny umiejętności.")
    with right:
        with st.container(key="spf_summary_scatter"):
            st.markdown('<div class="spf-card-head"><h3>Na tle innych zawodników</h3><span>WYBRANY GRACZ: ZIELONA GWIAZDKA</span></div>', unsafe_allow_html=True)
            chart, count = _plotly_scatter(peers, player)
            if chart is None:
                st.info("Za mało danych do pokazania pozycji zawodnika na tle innych.")
            else:
                st.plotly_chart(chart, use_container_width=True, theme=None,
                                config={"displayModeBar": False}, key=f"spf_scatter_v2_{selected}")
            st.caption(f"{league} · {group} · {count} porównywalnych rekordów (min. 450 minut). Najedź na punkt, by zobaczyć szczegóły.")

    l2, r2 = st.columns([1, 1], gap="medium")
    with l2:
        with st.container(key="spf_summary_ga"):
            st.markdown('<div class="spf-card-head"><h3>Goals Added według akcji</h3><span>G+ / 90</span></div>', unsafe_allow_html=True)
            figure = _plotly_ga(player)
            if figure is None:
                st.info("Brak szczegółowych danych Goals Added.")
            else:
                st.plotly_chart(figure, use_container_width=True, theme=None,
                                config={"displayModeBar": False}, key=f"spf_ga_v2_{selected}")
            st.caption("Dodatnie i ujemne wartości są względne wobec średniej modelu g+, nie oznaczają procentów.")
    with r2:
        with st.container(key="spf_summary_highlights"):
            st.markdown('<div class="spf-card-head"><h3>Wyróżniające się statystyki</h3><span>MIN. 75. PERCENTYL</span></div>', unsafe_allow_html=True)
            st.markdown(_insights_html(items), unsafe_allow_html=True)
            st.caption("Wybrane automatycznie na podstawie liczb, nie są opinią skauta ani prognozą rozwoju.")

    if (minutes := n(player.get("minutes_played"))) is not None and minutes < 450:
        st.warning("Zawodnik ma mniej niż 450 minut. Percentyle są poglądowe; nie należy nadmiernie interpretować ich wartości.")
    st.markdown(
        '<div class="spf-note">Porównujemy wyłącznie zawodników tej samej ligi i grupy pozycji. '
        'Brak danych pozostaje brakiem — nie jest zastępowany zerem. '
        'Wykresy nie wskazują samodzielnie potencjału piłkarza.</div>', unsafe_allow_html=True
    )

def render_profile(
    data: pd.DataFrame,
    open_player: Callable,
    *,
    silhouette: str,
    club_crest_fn: Callable,
) -> None:
    """Wyświetla profil wybranego zawodnika. Wystarczy aktualny DataFrame z app.py."""
    if st.button("← Wróć do bazy piłkarzy", key="spf_back"):
        st.session_state.player_mode = "explorer"
        st.rerun()

    selected = st.session_state.get("selected_player")
    if selected is None or selected not in data.index:
        st.info("Najpierw wybierz zawodnika z bazy piłkarzy.")
        return
    row = data.loc[selected]
    league, position = text(row.get("liga")), text(row.get("general_position"))
    group = GROUPS.get(position)
    crest = club_crest_fn(row.get("team_name"), row.get("team_id"), row.get("liga"))
    score = _metric(row, "ScoutScore")
    scoutscore = f(score, 1)
    score_status = "Brak oceny" if score is None else "na 100 punktów"
    selected_name = esc(row.get("player_name"), "Nieznany zawodnik")

    with st.container(key="spf_header"):
        st.markdown(f'''
        <section class="spf-hero">
          <div class="spf-hero-profile">
            <div class="spf-portrait">{silhouette}</div>
            <div class="spf-main-meta">
              <div class="spf-eyebrow">PROFIL ZAWODNIKA · SEZON 2025</div>
              <h1>{selected_name}</h1>
              <div class="spf-club">{crest}<span>{esc(row.get("team_name"), "Nieznany klub")}</span></div>
              <div class="spf-pills">
                <span>{esc(league)}</span><span>{esc(position)} · {esc(POSITIONS.get(position, position))}</span>
                <span>{f(row.get("wiek_2025"), 0)} lat w 2025</span>
              </div>
            </div>
          </div>
          <div class="spf-score-box"><span>SCOUTSCORE</span><strong>{scoutscore}</strong>
            <small>{score_status}</small><em>Na tle ligi i grupy pozycji</em></div>
        </section>''', unsafe_allow_html=True)

        if group == "Obrona":
            fourth = ("Próby podań", f(row.get("attempted_passes"), 0))
        elif group == "Pomoc":
            fourth = ("Kluczowe podania", f(row.get("key_passes"), 0))
        else:
            fourth = ("Strzały", f(row.get("shots"), 0))
        facts = [
            ("Rozegrane minuty", f(row.get("minutes_played"), 0)),
            ("Bramki", f(row.get("goals"), 0)),
            ("Asysty", f(row.get("primary_assists"), 0)),
            fourth,
        ]
        cards = "".join(
            f'<div class="spf-fact"><span>{esc(label)}</span><strong>{esc(value)}</strong></div>'
            for label, value in facts
        )
        st.markdown(f'<div class="spf-facts">{cards}</div>', unsafe_allow_html=True)

        saved = int(selected) in st.session_state.get("watchlist", [])
        c1, c2, c3 = st.columns([1.35, 1.35, 1], gap="small")
        with c1:
            if st.button("Usuń z obserwowanych" if saved else "☆ Dodaj do obserwowanych", key="spf_watch", use_container_width=True):
                watchlist = st.session_state.setdefault("watchlist", [])
                if saved:
                    watchlist.remove(int(selected))
                else:
                    watchlist.append(int(selected))
                st.rerun()
        with c2:
            if st.button("Porównaj zawodników →", key="spf_compare", use_container_width=True):
                st.session_state.page = "Porównania"
                st.rerun()
        with c3:
            # Pozwala pobrać faktyczne wartości z tabeli, bez zapisywania do bazy.
            csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
            safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", text(row.get("player_name"), "zawodnik")).strip("_")
            st.download_button("Pobierz dane CSV", data=csv, file_name=f"ScoutPro_{safe_name}_2025.csv", mime="text/csv", key="spf_export", use_container_width=True)

    st.markdown('<div class="spf-section-heading">ANALIZA ZAWODNIKA</div>', unsafe_allow_html=True)
    summary, stats, gplus, comparison, history = st.tabs(
        ["Podsumowanie", "Statystyki", "Goals Added", "Porównanie z ligą", "Historia"]
    )
    peer = _peer_group(data, row)
    metrics = metric_percentiles(data, row)

    with summary:
        _profile_summary(data, row, peer, metrics, int(selected))

    with stats:
        st.markdown('### Statystyki sezonu 2025')
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            st.markdown('#### Statystyki łączne')
            season_df = _dataframe(row, STAT_SEASON)
            if season_df.empty:
                st.info("Brak statystyk sezonowych.")
            else:
                st.dataframe(season_df, hide_index=True, use_container_width=True)
        with c2:
            st.markdown('#### Statystyki na 90 minut')
            per90_df = _dataframe(row, STAT_90)
            if per90_df.empty:
                st.info("Brak statystyk przeliczonych na 90 minut.")
            else:
                st.dataframe(per90_df, hide_index=True, use_container_width=True)
        st.caption("Kreska oznacza brak danych. Nie zastępujemy braków zerami. Wartości procentowe z API prezentujemy zgodnie z wartościami źródłowymi.")

    with gplus:
        st.markdown('### Goals Added — wkład w grę')
        c1, c2, c3 = st.columns(3, gap="small")
        c1.metric("G+ surowe", f(row.get("gplus_total"), 3))
        c2.metric("G+ ponad średnią", f(row.get("gplus_above_avg"), 3))
        c3.metric("G+ ponad średnią / 90", f(row.get("gplus_above_avg_90"), 3))
        ga_items = [(name, value) for key, name in GA_CATEGORIES if (value := n(row.get(key))) is not None]
        with st.container(key="spf_goals_added"):
            st.markdown('<div class="spf-card-head"><h3>Wkład według rodzaju akcji</h3><span>g+ / 90</span></div>', unsafe_allow_html=True)
            st.markdown(_ga_bars(ga_items), unsafe_allow_html=True)
        st.caption("Dodatnie i ujemne wartości oznaczają wkład względem średniej w modelu Goals Added. Słupki pokazują wartości, nie procenty.")

    with comparison:
        st.markdown('### Porównanie z ligą i grupą pozycji')
        st.write(f"**Liga:** {league}  ·  **Grupa pozycji:** {group or 'nieokreślona'}  ·  **Minimum minut grupy:** 450")
        if not metrics:
            st.info("Za mało danych do rzetelnego porównania. Nie tworzymy sztucznych ocen.")
        else:
            out = []
            for item in metrics:
                out.append({
                    "Wskaźnik": item["label"],
                    "Zawodnik": f(item["value"], 3),
                    "Mediana grupy": f(item["median"], 3),
                    "Percentyl": f(item["percentile"], 1),
                    "Próba": item["peers"],
                })
            st.dataframe(pd.DataFrame(out), hide_index=True, use_container_width=True)
            st.markdown('<div class="spf-note">Wskaźniki są liczone wyłącznie dla zawodników tej samej ligi i grupy pozycji, którzy rozegrali co najmniej 450 minut. Nie należy porównywać ScoutScore pomiędzy ligami.</div>', unsafe_allow_html=True)
        if st.button("Otwórz porównywarkę dwóch zawodników →", key="spf_compare_tab", use_container_width=True):
            st.session_state.page = "Porównania"
            st.rerun()

    with history:
        st.markdown('### Historia występów')
        st.info("Na razie baza ScoutPro obejmuje sezon 2025. Nie mamy jeszcze zweryfikowanych danych mecz po meczu ani wcześniejszych sezonów, więc nie pokazujemy fikcyjnego wykresu formy.")
        st.markdown('**Co dodamy później:** porównanie sezonów oraz wykres formy meczowej — po pobraniu i zweryfikowaniu odpowiednich danych.')

    _source_note()
