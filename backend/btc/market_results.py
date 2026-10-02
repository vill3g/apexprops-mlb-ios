"""Kalshi's official result (YES/NO) for each 15-minute market, for display.

Results are final once a market settles, so they are cached in memory and in
<DATA_DIR>/market_results.json. Lookups never block a request: an unknown finished
market is fetched in the background and shows up on the next poll.
"""
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

RETRY_SECONDS = 20            # how often to re-ask Kalshi about a finished but unsettled market
_ET = ZoneInfo("America/New_York")
_MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
_TICKER_TIME = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})(?:-|$)")

_lock = threading.Lock()
_results = None               # ticker -> "YES" | "NO"
_last_try = {}
_in_flight = set()
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kalshi-result")


def _path():
    from backend.database.models import DATA_DIR
    return os.path.join(os.path.abspath(DATA_DIR), "market_results.json")


def _load():
    global _results
    if _results is None:
        try:
            with open(_path(), "r") as f:
                _results = {k: v for k, v in (json.load(f) or {}).items() if v in ("YES", "NO")}
        except (OSError, ValueError):
            _results = {}
    return _results


def _save():
    try:
        tmp = _path() + ".tmp"
        with open(tmp, "w") as f:
            json.dump(_results, f)
        os.replace(tmp, _path())
    except OSError as e:
        logger.debug(f"[MarketResults] save failed: {e}")


def market_close_epoch(ticker):
    """KXBTC15M-26SEP271015-15 closes 2026-09-27 10:15 ET. None if the ticker has no time."""
    m = _TICKER_TIME.search(str(ticker or "").upper())
    if not m or m.group(2) not in _MONTHS:
        return None
    yy, mon, dd, hh, mi = m.groups()
    try:
        return datetime(2000 + int(yy), _MONTHS[mon], int(dd), int(hh), int(mi), tzinfo=_ET).timestamp()
    except ValueError:
        return None


def market_finished(ticker) -> bool:
    close = market_close_epoch(ticker)
    return close is not None and time.time() >= close


def remember(ticker, result) -> None:
    result = str(result or "").upper()
    if not ticker or result not in ("YES", "NO"):
        return
    with _lock:
        res = _load()
        if res.get(ticker) != result:
            res[ticker] = result
            _save()


def _fetch(ticker):
    try:
        from backend.btc.kalshi_trader import kalshi_trader
        r = kalshi_trader.get_market_result(ticker)
        if r.get("success") and r.get("result"):
            remember(ticker, r["result"])
    except Exception as e:
        logger.debug(f"[MarketResults] {ticker}: {e}")
    finally:
        with _lock:
            _in_flight.discard(ticker)


def get_result(ticker, trade: dict = None):
    """'YES', 'NO', or None if not known yet (a background fetch is started if due)."""
    ticker = str(ticker or "").strip()
    if not ticker or ticker.upper().endswith("_SYNTH"):
        return None
    with _lock:
        known = _load().get(ticker)
    if known:
        return known
    # A trade held to settlement already tells us the answer
    if trade:
        own = str(trade.get("official_result") or "").upper()
        if own in ("YES", "NO"):
            remember(ticker, own)
            return own
        if str(trade.get("exit_reason") or "").upper().startswith("SETTLE") and trade.get("exit_price") is not None:
            try:
                px, side = float(trade["exit_price"]), str(trade.get("side") or "").upper()
                if side in ("YES", "NO") and px in (0.0, 1.0):
                    won_side = side if px == 1.0 else ("NO" if side == "YES" else "YES")
                    remember(ticker, won_side)
                    return won_side
            except (TypeError, ValueError):
                pass
    if not market_finished(ticker):
        return None
    now = time.time()
    with _lock:
        if ticker in _in_flight or now - _last_try.get(ticker, 0) < RETRY_SECONDS:
            return None
        _last_try[ticker] = now
        _in_flight.add(ticker)
    _pool.submit(_fetch, ticker)
    return None
