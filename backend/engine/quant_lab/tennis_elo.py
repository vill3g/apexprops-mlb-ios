"""Point-in-time tennis Elo built only from completed matches in ApexProps' tennis_matches.db.

Walk-forward: each match's pre-match win probability is computed from ratings that contain only
matches played BEFORE it, then ratings are updated. No look-ahead. Used to give Quant Lab a real
`ai_win_prob` / `ai_edge` for historical Kalshi tennis markets.
"""
import logging
import os
import re
import sqlite3
import unicodedata
from collections import defaultdict
from typing import Dict, Optional, Tuple

logger = logging.getLogger("QuantLabTennisElo")

_DB = r"C:\Users\Vill3\.gemini\antigravity\scratch\apexprops-mlb-ios\backend\data\tennis_matches.db"
MIN_PRIOR_MATCHES = 12
SURFACE_BLEND = 0.5  # weight of surface-specific rating


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[^a-z\s\-]", " ", s).replace("-", " ")
    return " ".join(s.split())


def _surface_key(s: str) -> str:
    s = (s or "").lower()
    if "clay" in s:
        return "clay"
    if "grass" in s:
        return "grass"
    return "hard"


def _p(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


_cache: Dict[str, object] = {}


def build_elo() -> Dict[Tuple[str, str], list]:
    """Returns {(day, player_norm): [(opp_norm, p_player_wins_pre, prior_matches_min)]} for every match."""
    if "table" in _cache:
        return _cache["table"]  # type: ignore
    conn = sqlite3.connect(_DB)
    rows = conn.execute(
        "SELECT match_date, surface, winner_norm, loser_norm, is_walkover FROM tennis_matches "
        "WHERE winner_norm != '' AND loser_norm != '' AND match_date != '' ORDER BY match_date ASC"
    ).fetchall()
    conn.close()

    overall: Dict[str, float] = defaultdict(lambda: 1500.0)
    surf: Dict[Tuple[str, str], float] = defaultdict(lambda: 1500.0)
    played: Dict[str, int] = defaultdict(int)
    table: Dict[Tuple[str, str], list] = defaultdict(list)

    for md, surface, w, l, wo in rows:
        sk = _surface_key(surface)
        w, l = norm_name(w), norm_name(l)
        ra = (1 - SURFACE_BLEND) * overall[w] + SURFACE_BLEND * surf[(w, sk)]
        rb = (1 - SURFACE_BLEND) * overall[l] + SURFACE_BLEND * surf[(l, sk)]
        p_w = _p(ra, rb)
        day = md[:10]
        mn = min(played[w], played[l])
        table[(day, w)].append((l, p_w, mn))
        table[(day, l)].append((w, 1.0 - p_w, mn))
        if wo:
            continue
        # FiveThirtyEight-style decaying K
        kw = 250.0 / ((played[w] + 5) ** 0.4)
        kl = 250.0 / ((played[l] + 5) ** 0.4)
        po = _p(overall[w], overall[l])
        overall[w] += kw * (1 - po)
        overall[l] -= kl * (1 - po)
        ps = _p(surf[(w, sk)], surf[(l, sk)])
        surf[(w, sk)] += kw * (1 - ps)
        surf[(l, sk)] -= kl * (1 - ps)
        played[w] += 1
        played[l] += 1
    _cache["table"] = table
    logger.info(f"[TennisElo] built from {len(rows)} matches, {len(played)} players")
    return table


def pre_match_prob(day: str, player_name: str) -> Optional[float]:
    """Pre-match win probability (0-1) for the player on/around `day` (YYYY-MM-DD), or None."""
    from datetime import date, timedelta
    table = build_elo()
    n = norm_name(player_name)
    try:
        d0 = date.fromisoformat(day)
    except ValueError:
        return None
    for off in (0, -1, 1):
        k = ((d0 + timedelta(days=off)).isoformat(), n)
        for opp, p, mn in table.get(k, []):
            if mn >= MIN_PRIOR_MATCHES:
                return p
    return None
