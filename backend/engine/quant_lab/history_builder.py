"""Builds real, point-in-time labelled snapshots for sports from Kalshi's settled markets.

For each settled market we take the bid/ask from hourly candlesticks LEAD_HOURS before the market
closed (so well before the result was known) and label it with the actual result. Features are
market-only (price, spread, drift) - they are exactly reproducible and carry no look-ahead.
Results are cached in quant_lab.db so each market is fetched once.
"""
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("QuantLabHistory")

BASE = "https://api.elections.kalshi.com/trade-api/v2"
LEAD_HOURS = 12          # snapshot taken this long before close
DRIFT_HOURS = 12         # price change measured over this window before the snapshot
MAX_MARKETS_PER_BUILD = 120
TARGET_MARKETS = 600       # stop growing the cache per sport once it reaches this
REQ_SLEEP = 0.15

SERIES = {
    "NFL": ["KXNFLGAME"], "MLB": ["KXMLBGAME"], "NHL": ["KXNHLGAME"], "NBA": ["KXNBAGAME"],
    "NCAAF": ["KXNCAAFGAME"], "NCAAB": ["KXNCAABGAME"], "WNBA": ["KXWNBAGAME"],
    "NPB": ["KXNPBGAME"], "KBO": ["KXKBOGAME"],
    "EPL": ["KXEPLGAME"], "MLS": ["KXMLSGAME"],
    "SOC": ["KXEPLGAME", "KXMLSGAME", "KXLALIGAGAME", "KXBUNDESLIGAGAME", "KXSERIEAGAME"],
    "UFC": ["KXUFCFIGHT"], "TEN": ["KXATPMATCH", "KXWTAMATCH"],
}

_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "quant_lab.db"))


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB, timeout=30)
    c.execute(
        """CREATE TABLE IF NOT EXISTS sports_history (
            ticker TEXT PRIMARY KEY, sport TEXT, series TEXT, close_ts INTEGER, result TEXT,
            bid REAL, ask REAL, bid_prev REAL, ask_prev REAL, created_at REAL)"""
    )
    for col in ("name TEXT", "ai_win_prob REAL", "ai_edge REAL", "confidence_score REAL", "sim_score REAL"):
        try:
            c.execute(f"ALTER TABLE sports_history ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass  # already exists
    return c


def record_sports_ai_prediction(
    ticker: str,
    sport: str,
    ai_win_prob: float,
    ai_edge: float,
    confidence_score: float,
    sim_score: Optional[float] = None,
    name: Optional[str] = None
) -> None:
    """Persistently archive AI model predictions alongside settled or active game contracts."""
    if not ticker:
        return
    c = _conn()
    try:
        now_ts = time.time()
        c.execute(
            """INSERT INTO sports_history (ticker, sport, ai_win_prob, ai_edge, confidence_score, sim_score, name, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET
                   ai_win_prob=excluded.ai_win_prob,
                   ai_edge=excluded.ai_edge,
                   confidence_score=excluded.confidence_score,
                   sim_score=COALESCE(excluded.sim_score, sports_history.sim_score),
                   name=COALESCE(excluded.name, sports_history.name)""",
            (ticker, (sport or "SPORTS").upper(), float(ai_win_prob), float(ai_edge), float(confidence_score),
             float(sim_score) if sim_score is not None else None, name, now_ts)
        )
        c.commit()
    except Exception as e:
        logger.debug(f"[QuantLabHistory] record_sports_ai_prediction error for {ticker}: {e}")
    finally:
        c.close()



def _f(d: Dict[str, Any], key: str) -> Optional[float]:
    try:
        v = (d.get(key) or {}).get("close_dollars")
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _iso_to_ts(s: str) -> Optional[int]:
    from datetime import datetime
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


def _candle_at(candles: List[Dict[str, Any]], ts: int) -> Optional[Dict[str, Optional[float]]]:
    """Last candle ending at or before ts that has a real two-sided quote."""
    best = None
    for c in candles:
        if c.get("end_period_ts", 0) <= ts:
            bid, ask = _f(c, "yes_bid"), _f(c, "yes_ask")
            if bid is not None and ask is not None and 0 < bid <= ask < 1:
                best = {"bid": bid, "ask": ask}
    return best


def build_history(sport: str, max_markets: int = MAX_MARKETS_PER_BUILD) -> int:
    """Fetch and cache up to max_markets new settled markets for the sport. Returns rows added."""
    series_list = SERIES.get(sport.upper())
    if series_list:
        _c = _conn()
        try:
            have = _c.execute("SELECT COUNT(*) FROM sports_history WHERE sport=?", (sport.upper(),)).fetchone()[0]
        finally:
            _c.close()
        if have >= TARGET_MARKETS:
            return 0
    if not series_list:
        return 0
    conn = _conn()
    added = 0
    try:
        for series in series_list:
            cursor = None
            while added < max_markets:
                params: Dict[str, Any] = {"series_ticker": series, "status": "settled", "limit": 100}
                if cursor:
                    params["cursor"] = cursor
                try:
                    js = requests.get(f"{BASE}/markets", params=params, timeout=20).json()
                except Exception as e:
                    logger.warning(f"[QuantLabHistory] market list failed for {series}: {e}")
                    break
                markets = js.get("markets", [])
                for m in markets:
                    if added >= max_markets:
                        break
                    tk, res = m.get("ticker"), m.get("result")
                    if res not in ("yes", "no") or not tk:
                        continue
                    if conn.execute("SELECT 1 FROM sports_history WHERE ticker=?", (tk,)).fetchone():
                        continue
                    close_ts = _iso_to_ts(m.get("close_time") or "")
                    if not close_ts:
                        continue
                    snap_ts = close_ts - LEAD_HOURS * 3600
                    prev_ts = snap_ts - DRIFT_HOURS * 3600
                    try:
                        cj = requests.get(
                            f"{BASE}/series/{series}/markets/{tk}/candlesticks",
                            params={"start_ts": prev_ts - 7200, "end_ts": close_ts, "period_interval": 60},
                            timeout=20,
                        ).json()
                    except Exception:
                        continue
                    time.sleep(REQ_SLEEP)
                    candles = cj.get("candlesticks", [])
                    now_q, prev_q = _candle_at(candles, snap_ts), _candle_at(candles, prev_ts)
                    if not now_q:
                        continue  # no tradable quote at snapshot time
                    conn.execute(
                        "INSERT OR IGNORE INTO sports_history "
                        "(ticker, sport, series, close_ts, result, bid, ask, bid_prev, ask_prev, created_at, name) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (tk, sport.upper(), series, close_ts, res, now_q["bid"], now_q["ask"],
                         (prev_q or {}).get("bid"), (prev_q or {}).get("ask"), time.time(),
                         m.get("yes_sub_title")),
                    )
                    added += 1
                conn.commit()
                cursor = js.get("cursor")
                if not cursor or not markets:
                    break
    finally:
        conn.commit()
        conn.close()
    logger.info(f"[QuantLabHistory] {sport}: cached {added} new settled markets")
    return added


def backfill_names(sport: str, max_pages: int = 10) -> int:
    """Fill the player/team name for cached rows (list calls only, no candlestick fetches)."""
    conn = _conn()
    updated = 0
    try:
        for series in SERIES.get(sport.upper(), []):
            cursor = None
            for _ in range(max_pages):
                params: Dict[str, Any] = {"series_ticker": series, "status": "settled", "limit": 100}
                if cursor:
                    params["cursor"] = cursor
                try:
                    js = requests.get(f"{BASE}/markets", params=params, timeout=20).json()
                except Exception:
                    break
                for m in js.get("markets", []):
                    cur = conn.execute(
                        "UPDATE sports_history SET name=? WHERE ticker=? AND (name IS NULL OR name='')",
                        (m.get("yes_sub_title"), m.get("ticker")),
                    )
                    updated += cur.rowcount
                conn.commit()
                cursor = js.get("cursor")
                if not cursor:
                    break
    finally:
        conn.close()
    return updated


def load_history_snapshots(sport: str, limit: int = 600) -> List[Dict[str, Any]]:
    """Chronological validator-ready snapshots from the cache (building it on first use)."""
    sport_upper = sport.upper()
    # Handle sport leagues and aliases
    if sport_upper in ("EPL", "MLS", "BUNDESLIGA", "LALIGA", "SERIEA", "SOC", "SOCCER"):
        sport_clause = "sport IN ('EPL', 'MLS', 'SOC', 'SOCCER') OR series IN ('KXEPLGAME', 'KXMLSGAME', 'KXLALIGAGAME', 'KXBUNDESLIGAGAME', 'KXSERIEAGAME')"
        query_params = (limit,)
        count_clause = "sport IN ('EPL', 'MLS', 'SOC', 'SOCCER') OR series IN ('KXEPLGAME', 'KXMLSGAME')"
        count_params = ()
    else:
        sport_clause = "sport=? AND bid IS NOT NULL AND ask IS NOT NULL"
        query_params = (sport_upper, limit)
        count_clause = "sport=? AND bid IS NOT NULL AND ask IS NOT NULL"
        count_params = (sport_upper,)

    conn = _conn()
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM sports_history WHERE {count_clause}", count_params).fetchone()[0]
    finally:
        conn.close()
    if n < 60:
        try:
            build_history(sport)
        except Exception as e:
            logger.warning(f"[QuantLabHistory] build failed for {sport}: {e}")
    conn = _conn()
    try:
        if sport_upper in ("EPL", "MLS", "BUNDESLIGA", "LALIGA", "SERIEA", "SOC", "SOCCER"):
            rows = conn.execute(
                f"SELECT ticker, close_ts, result, bid, ask, bid_prev, ask_prev, name, "
                f"ai_win_prob, ai_edge, confidence_score, sim_score FROM sports_history "
                f"WHERE ({sport_clause}) AND bid IS NOT NULL AND ask IS NOT NULL ORDER BY close_ts DESC LIMIT ?",
                query_params
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT ticker, close_ts, result, bid, ask, bid_prev, ask_prev, name, "
                f"ai_win_prob, ai_edge, confidence_score, sim_score FROM sports_history "
                f"WHERE {sport_clause} ORDER BY close_ts DESC LIMIT ?",
                query_params
            ).fetchall()
    finally:
        conn.close()
    out = []
    updates_to_persist = []
    for tk, close_ts, result, bid, ask, bp, ap, name, a_prob, a_edge, conf_sc, sim_sc in reversed(rows):
        if bid is None or ask is None:
            continue
        feats = {
            "market_bid": bid, "market_ask": ask, "spread": round(ask - bid, 4),
            "market_mid": round((ask + bid) / 2, 4),
        }
        if bp is not None and ap is not None:
            feats["price_drift"] = round((ask + bid) / 2 - (ap + bp) / 2, 4)

        # 1. Use existing persisted AI predictions if present
        if a_prob is not None:
            feats["ai_win_prob"] = float(a_prob)
            feats["ai_edge"] = float(a_edge) if a_edge is not None else round(float(a_prob) - feats["market_mid"] * 100.0, 2)
            feats["confidence_score"] = float(conf_sc) if conf_sc is not None else round(abs(float(a_prob) - 50.0) * 2.0, 1)
            if sim_sc is not None:
                feats["sim_score"] = float(sim_sc)
        else:
            # 2. Point-in-time Walk-forward Elo / Model probability calculation
            calc_prob = None
            if sport.upper() == "TEN" and name:
                try:
                    from datetime import datetime, timezone
                    from backend.engine.quant_lab.tennis_elo import pre_match_prob
                    day = datetime.fromtimestamp(close_ts or time.time(), tz=timezone.utc).strftime("%Y-%m-%d")
                    calc_prob = pre_match_prob(day, name)
                except Exception as e:
                    logger.debug(f"[QuantLabHistory] tennis elo attach failed for {tk}: {e}")
            elif sport.upper() in ("UFC", "NHL", "SOC", "EPL", "MLS", "NPB", "KBO", "MLB", "NFL") and name:
                try:
                    from datetime import datetime, timezone
                    from backend.engine.quant_lab.team_elo import pre_match_prob as _tp
                    _sp = "SOC" if sport.upper() in ("EPL", "MLS") else sport.upper()
                    day = datetime.fromtimestamp(close_ts or time.time(), tz=timezone.utc).strftime("%Y-%m-%d")
                    calc_prob = _tp(_sp, day, name)
                except Exception as e:
                    logger.debug(f"[QuantLabHistory] team elo attach failed for {tk}: {e}")

            if calc_prob is not None:
                ai_wp = round(calc_prob * 100.0, 2)
                ai_ed = round(calc_prob * 100.0 - feats["market_mid"] * 100.0, 2)
                c_sc = round(abs(calc_prob - 0.5) * 200.0, 1)
                feats["ai_win_prob"] = ai_wp
                feats["ai_edge"] = ai_ed
                feats["confidence_score"] = c_sc
                updates_to_persist.append((ai_wp, ai_ed, c_sc, tk))

        out.append({
            "trade_id": f"hist_{tk}", "ticker": tk, "entry_price": ask,
            "actual_outcome": "YES" if result == "yes" else "NO",
            "raw_features": feats, "cur_price": ask, "yes_bid": bid, "yes_ask": ask,
        })

    # Persist computed point-in-time features into database for subsequent runs
    if updates_to_persist:
        try:
            up_conn = _conn()
            up_conn.executemany(
                "UPDATE sports_history SET ai_win_prob=?, ai_edge=?, confidence_score=? WHERE ticker=?",
                updates_to_persist
            )
            up_conn.commit()
            up_conn.close()
        except Exception as e:
            logger.debug(f"[QuantLabHistory] Batch persist error: {e}")

    try:
        from backend.engine.quant_lab.regime_classifier import MarketRegimeClassifier
        for snap in out:
            MarketRegimeClassifier.classify_snapshot(snap, asset=sport)
    except Exception as e:
        logger.debug(f"[QuantLabHistory] Regime enrichment error: {e}")

    return out
