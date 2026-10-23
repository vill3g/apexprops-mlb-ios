"""Point-in-time Elo for non-tennis sports, built only from completed games in ApexProps' databases.

Walk-forward (each game's pre-game probability uses only earlier games). Used by history_builder to
attach a real `ai_win_prob` / `ai_edge` to historical Kalshi markets for UFC, NHL, soccer, NPB/KBO.
"""
import logging
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger("QuantLabTeamElo")

_DATA = r"C:\Users\Vill3\.gemini\antigravity\scratch\apexprops-mlb-ios\backend\data"

# sport -> (home_adv_elo, K, min_prior_games)
PARAMS = {
    "NHL": (35.0, 8.0, 10),
    "SOC": (65.0, 18.0, 8),
    "NPB": (25.0, 6.0, 12),
    "KBO": (25.0, 6.0, 12),
    "UFC": (0.0, 40.0, 2),
    "NFL": (45.0, 16.0, 3),
    "MLB": (24.0, 6.0, 8),
}
SOCCER_DRAW = 0.27
_cache: Dict[str, Tuple[dict, set]] = {}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def _p(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def _day(s) -> str:
    s = str(s or "")[:10]
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else ""


def _rows(sport: str):
    """Yield (day, a_norm, b_norm, a_is_home, a_won 1/0/0.5) chronologically."""
    out = []
    if sport == "NHL":
        c = sqlite3.connect(f"{_DATA}\\nhl_games.db")
        for d, h, a, hs, as_ in c.execute(
            "SELECT game_date, home_team, away_team, home_score, away_score FROM nhl_games "
            "WHERE home_score IS NOT NULL AND away_score IS NOT NULL"):
            if hs != as_:
                out.append((_day(d), norm(h), norm(a), True, 1.0 if hs > as_ else 0.0))
        try:
            from backend.engine.quant_lab.nhl_refresh import _conn as _qc
            _q = _qc()
            for d, h, a, hs, as_ in _q.execute("SELECT day, home, away, home_score, away_score FROM nhl_extra"):
                out.append((_day(d), norm(h), norm(a), True, 1.0 if hs > as_ else 0.0))
            _q.close()
        except Exception as e:
            logger.debug(f"[TeamElo] nhl_extra unavailable: {e}")
    elif sport == "SOC":
        c = sqlite3.connect(f"{_DATA}\\soccer_matches.db")
        for d, h, a, hs, as_ in c.execute(
            "SELECT match_date, home_club_norm, away_club_norm, home_score, away_score FROM soccer_matches "
            "WHERE home_score IS NOT NULL AND away_score IS NOT NULL"):
            out.append((_day(d), norm(h), norm(a), True, 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)))
    elif sport in ("NPB", "KBO"):
        c = sqlite3.connect(f"{_DATA}\\international_baseball.db")
        for d, h, a, hs, as_ in c.execute(
            "SELECT game_date, home_team_norm, away_team_norm, home_score, away_score FROM international_baseball_games "
            "WHERE league=? AND home_score IS NOT NULL AND away_score IS NOT NULL", (sport,)):
            if hs != as_:
                out.append((_day(d), norm(h), norm(a), True, 1.0 if hs > as_ else 0.0))
    elif sport == "UFC":
        c = sqlite3.connect(f"{_DATA}\\ufc_bouts.db")
        for d, an, bn, aid, wid in c.execute(
            "SELECT bout_date, fighter_a_norm, fighter_b_norm, fighter_a_norm, winner_norm FROM ufc_bouts "
            "WHERE winner_norm IS NOT NULL AND winner_norm != ''"):
            out.append((_day(d), norm(an), norm(bn), False, 1.0 if str(wid) == str(aid) else 0.0))
        c.close()
    elif sport == "NFL":
        import os, csv
        csv_p = os.path.join(os.path.dirname(_DATA), "nfl_data", "nflverse_games_cache.csv")
        if os.path.exists(csv_p):
            try:
                with open(csv_p, "r", encoding="utf-8") as f:
                    for r in csv.DictReader(f):
                        gday = _day(r.get("gameday"))
                        h_tm = norm(r.get("home_team"))
                        a_tm = norm(r.get("away_team"))
                        try:
                            hs = float(r.get("home_score") or 0)
                            as_ = float(r.get("away_score") or 0)
                        except (ValueError, TypeError):
                            continue
                        if hs != as_ and h_tm and a_tm:
                            out.append((gday, h_tm, a_tm, True, 1.0 if hs > as_ else 0.0))
            except Exception as e:
                logger.debug(f"[TeamElo] NFL parse error: {e}")
    elif sport == "MLB":
        import os
        from datetime import datetime, timezone
        ql_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "quant_lab.db"))
        if os.path.exists(ql_db):
            try:
                qc = sqlite3.connect(ql_db)
                mlb_rows = qc.execute(
                    "SELECT ticker, name, result, close_ts FROM sports_history "
                    "WHERE sport='MLB' AND result IN ('yes', 'no') AND name IS NOT NULL ORDER BY close_ts ASC"
                ).fetchall()
                qc.close()
                games = defaultdict(list)
                for tk, nm, res, cts in mlb_rows:
                    game_key = tk.rsplit("-", 1)[0] if "-" in tk else tk
                    games[game_key].append((nm, res, cts))
                for g_k, legs in games.items():
                    if len(legs) == 2:
                        (t1, r1, ts1), (t2, r2, ts2) = legs
                        w1 = 1.0 if r1 == "yes" else 0.0
                        d_str = datetime.fromtimestamp(ts1, tz=timezone.utc).strftime("%Y-%m-%d")
                        out.append((d_str, norm(t1), norm(t2), True, w1))
            except Exception as e:
                logger.debug(f"[TeamElo] MLB parse error: {e}")
    else:
        raise ValueError(sport)
    out = [r for r in out if r[0]]
    out.sort(key=lambda r: r[0])
    return out


def build(sport: str):
    sport = sport.upper()
    if sport in _cache:
        return _cache[sport]
    home_adv, K, _ = PARAMS[sport]
    rating: Dict[str, float] = defaultdict(lambda: 1500.0)
    played: Dict[str, int] = defaultdict(int)
    table: Dict[Tuple[str, str], Tuple[float, int]] = {}
    for day, a, b, a_home, won in _rows(sport):
        ra = rating[a] + (home_adv if a_home else 0.0)
        e = _p(ra, rating[b])
        if sport == "SOC":
            draw = SOCCER_DRAW * (1 - abs(2 * e - 1))
            pa, pb = e - draw / 2, (1 - e) - draw / 2
        else:
            pa, pb = e, 1 - e
        mn = min(played[a], played[b])
        table[(day, a)] = (pa, mn)
        table[(day, b)] = (pb, mn)
        k = K * (1.6 if sport == "UFC" and min(played[a], played[b]) < 4 else 1.0)
        rating[a] += k * (won - e)
        rating[b] -= k * (won - e)
        played[a] += 1
        played[b] += 1
    teams = set(played)
    _cache[sport] = (table, teams)
    logger.info(f"[TeamElo] {sport}: {len(played)} teams/fighters")
    return _cache[sport]


NFL_ABBR_MAP = {
    "arizona": "ari", "cardinals": "ari", "atlanta": "atl", "falcons": "atl",
    "baltimore": "bal", "ravens": "bal", "buffalo": "buf", "bills": "buf",
    "carolina": "car", "panthers": "car", "chicago": "chi", "bears": "chi",
    "cincinnati": "cin", "bengals": "cin", "cleveland": "cle", "browns": "cle",
    "dallas": "dal", "cowboys": "dal", "denver": "den", "broncos": "den",
    "detroit": "det", "lions": "det", "green bay": "gb", "packers": "gb",
    "houston": "hou", "texans": "hou", "indianapolis": "ind", "colts": "ind",
    "jacksonville": "jax", "jaguars": "jax", "kansas city": "kc", "chiefs": "kc",
    "las vegas": "lv", "raiders": "lv", "oakland": "lv", "la chargers": "lac", "chargers": "lac",
    "la rams": "lar", "rams": "lar", "miami": "mia", "dolphins": "mia",
    "minnesota": "min", "vikings": "min", "new england": "ne", "patriots": "ne",
    "new orleans": "no", "saints": "no", "ny giants": "nyg", "giants": "nyg",
    "ny jets": "nyj", "jets": "nyj", "philadelphia": "phi", "eagles": "phi",
    "pittsburgh": "pit", "steelers": "pit", "san francisco": "sf", "49ers": "sf",
    "seattle": "sea", "seahawks": "sea", "tampa bay": "tb", "buccaneers": "tb",
    "tennessee": "ten", "titans": "ten", "washington": "was", "commanders": "was",
}


def _resolve(name: str, teams: set) -> Optional[str]:
    n = norm(name)
    if not n or n in ("tie", "draw"):
        return None
    if n in teams:
        return n
    for word, abbr in NFL_ABBR_MAP.items():
        if word in n and abbr in teams:
            return abbr
    toks = set(n.split())
    cands = [t for t in teams if toks <= set(t.split()) or set(t.split()) <= toks]
    return cands[0] if len(cands) == 1 else None


def pre_match_prob(sport: str, day: str, name: str) -> Optional[float]:
    sport = sport.upper()
    if sport not in PARAMS:
        return None
    table, teams = build(sport)
    key = _resolve(name, teams)
    if key is None:
        return None
    try:
        d0 = date.fromisoformat(day)
    except ValueError:
        return None
    min_prior = PARAMS[sport][2]
    offsets = (0, -1, 1, -2, 2, -3, 3) if sport == "NFL" else (0, -1, 1, -2, 2)
    for off in offsets:
        v = table.get(((d0 + timedelta(days=off)).isoformat(), key))
        if v and v[1] >= min_prior:
            return v[0]
    return None
