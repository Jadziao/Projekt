"""Wspólne, niezależne od UI funkcje widoków ScoutPro."""
from __future__ import annotations
import html
import json
import math
from typing import Any
import numpy as np
import pandas as pd

POSITION_GROUPS = {"ST": "Atak", "W": "Atak", "AM": "Pomoc", "CM": "Pomoc", "DM": "Pomoc", "CB": "Obrona", "FB": "Obrona"}
POSITIONS = {"ST": "Napastnik", "W": "Skrzydłowy", "AM": "Ofensywny pomocnik", "CM": "Środkowy pomocnik", "DM": "Defensywny pomocnik", "CB": "Środkowy obrońca", "FB": "Boczny obrońca", "GK": "Bramkarz"}
METRICS = {
    "Atak": [("xgoals_90", "xG / 90"), ("xassists_90", "xA / 90"), ("goals_90", "Gole / 90"), ("shots_on_target_90", "Celne strzały / 90"), ("gplus_above_avg_90", "g+ / 90")],
    "Pomoc": [("xassists_90", "xA / 90"), ("key_passes_90", "Kluczowe podania / 90"), ("passes_completed_over_expected_p100", "Podania ponad ocz. / 100"), ("gplus_passing_90", "g+ podań / 90"), ("gplus_above_avg_90", "g+ / 90")],
    "Obrona": [("gplus_interrupting_90", "g+ przechwytów / 90"), ("gplus_passing_90", "g+ podań / 90"), ("passes_completed_over_expected_p100", "Podania ponad ocz. / 100"), ("gplus_above_avg_90", "g+ / 90"), ("xassists_90", "xA / 90")],
}

def value(x: Any) -> float | None:
    try:
        if x is None or isinstance(x, (list,dict,tuple)):
            return None
        a = float(x)
        return a if math.isfinite(a) else None
    except (ValueError, TypeError):
        return None

def text(x: Any, fallback: str = "—") -> str:
    if x is None or isinstance(x,(list,dict,tuple)):
        return fallback
    try:
        if bool(pd.isna(x)):
            return fallback
    except (ValueError,TypeError):
        pass
    return str(x).strip() or fallback

def esc(x: Any, fallback: str = "—") -> str:
    return html.escape(text(x, fallback), quote=True)

def fmt(x: Any, digits: int = 1) -> str:
    v = value(x)
    return "—" if v is None else f"{v:,.{digits}f}".replace(",", " ")

def normalized_id(x: Any) -> str:
    raw = text(x, "")
    for _ in range(2):
        try:
            v = json.loads(raw)
            if isinstance(v,str):
                raw = v.strip()
            else:
                break
        except (TypeError, ValueError):
            break
    return raw

def player_key(row: pd.Series) -> str:
    return "|".join(["2025", normalized_id(row.get("liga")), normalized_id(row.get("player_id")), normalized_id(row.get("team_id"))])

def player_label(row: pd.Series) -> str:
    return f"{text(row.get('player_name'))} · {text(row.get('team_name'), 'Nieznany klub')} ({text(row.get('liga'))})"

def numeric(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[name], errors="coerce")

def peers(df: pd.DataFrame, player: pd.Series, min_minutes: int = 450) -> pd.DataFrame:
    liga = text(player.get("liga"))
    group = POSITION_GROUPS.get(text(player.get("general_position")))
    if group is None:
        return df.iloc[0:0].copy()
    positions = df["general_position"].fillna("").astype(str).map(POSITION_GROUPS)
    return df[(df["liga"] == liga) & (positions == group) & (numeric(df, "minutes_played") >= min_minutes)]

def percentile(x: Any, series: pd.Series) -> float | None:
    v = value(x)
    arr = pd.to_numeric(series,errors="coerce").dropna()
    if v is None or len(arr) < 5:
        return None
    return round(100.0 * (float((arr < v).sum()) + 0.5 * float((arr == v).sum())) / len(arr), 1)

def score_color(v: Any) -> str:
    n = value(v)
    return "#88adac" if n is None else ("#35eb9d" if n >= 75 else "#b9d97a" if n >= 50 else "#e8ac78")

def badge(v: Any) -> str:
    return f'<span class="sp2-score">{fmt(v,1)}</span>'

def kpi_html(label: str, x: Any, sub: str = "", digits: int = 0) -> str:
    return f'<div class="sp2-stat"><span>{esc(label)}</span><strong>{fmt(x,digits)}</strong><small>{esc(sub, "")}</small></div>'

def field_present(df: pd.DataFrame, field: str) -> bool:
    return field in df.columns and numeric(df,field).notna().any()


# Jeden wspólny katalog lig dla wszystkich widoków.
# Pokazujemy wyłącznie ligi rzeczywiście obecne w wybranej bazie.
LEAGUE_ORDER = ("MLS", "USLC", "USL1", "MLSNP")
LEAGUE_LABELS = {
    "MLS": "MLS",
    "USLC": "USL Championship",
    "USL1": "USL League One",
    "MLSNP": "MLS Next Pro",
}


def available_leagues(data: pd.DataFrame) -> list[str]:
    if "liga" not in data.columns:
        return []
    present = {str(v).strip() for v in data["liga"].dropna() if str(v).strip()}
    return [v for v in LEAGUE_ORDER if v in present] + sorted(present.difference(LEAGUE_ORDER))


def league_label(league: str) -> str:
    return LEAGUE_LABELS.get(league, str(league))
