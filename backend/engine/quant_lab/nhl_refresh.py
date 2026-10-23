"""Fills the NHL results gap in ApexProps' nhl_games.db without modifying it.

Fetches finished games from the public NHL score API into quant_lab.db (`nhl_extra`), from the day
after ApexProps' last game up to today. team_elo reads both sources. Safe to re-run (idempotent).
"""
import logging
import os
import sqlite3
import time
from datetime import date, timedelta

import requests

logger = logging.getLogger("QuantLabNHLRefresh")

_APEX = r"C:\Users\Vill3\.gemini\antigravity\scratch\apexprops-mlb-ios\backend\data\nhl_games.db"
_QL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "quant_lab.db"))
URL = "https://api-web.nhle.com/v1/score/{d}"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_QL, timeout=30)
    c.execute(
        "CREATE TABLE IF NOT EXISTS nhl_extra (game_id TEXT PRIMARY KEY, day TEXT, home TEXT, away TEXT, "
        "home_score INTEGER, away_score INTEGER)"
    )
    return c


def refresh(max_days: int = 400) -> int:
    a = sqlite3.connect(_APEX)
    abbr_name = {}
    for ab, nm in a.execute("SELECT home_abbr, home_team FROM nhl_games UNION SELECT away_abbr, away_team FROM nhl_games"):
        abbr_name[ab] = nm
    last = a.execute("SELECT MAX(game_date) FROM nhl_games").fetchone()[0]
    a.close()
    c = _conn()
    have = c.execute("SELECT MAX(day) FROM nhl_extra").fetchone()[0]
    start = date.fromisoformat(max(last, have or last)[:10]) + timedelta(days=1)
    end = date.today()
    added = 0
    d = start
    n = 0
    while d <= end and n < max_days:
        n += 1
        try:
            r = requests.get(URL.format(d=d.isoformat()), timeout=15)
            if r.status_code != 200:
                break
            games = r.json().get("games", [])
        except Exception as e:
            logger.warning(f"[NHLRefresh] {d}: {e}")
            break
        for g in games:
            if g.get("gameState") not in ("OFF", "FINAL") or g.get("gameDate") != d.isoformat():
                continue
            h, aw = g["homeTeam"], g["awayTeam"]
            if h.get("score") is None or aw.get("score") is None or h["score"] == aw["score"]:
                continue
            hn = abbr_name.get(h["abbrev"]) or h["abbrev"]
            an = abbr_name.get(aw["abbrev"]) or aw["abbrev"]
            c.execute(
                "INSERT OR IGNORE INTO nhl_extra VALUES (?,?,?,?,?,?)",
                (str(g["id"]), d.isoformat(), hn, an, h["score"], aw["score"]),
            )
            added += 1
        d += timedelta(days=1)
        time.sleep(0.2)
    c.commit()
    c.close()
    logger.info(f"[NHLRefresh] added {added} games ({start} -> {d - timedelta(days=1)})")
    return added


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("added", refresh())
