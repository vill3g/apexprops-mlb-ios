"""Up/down outcome-sequence pattern analyzer for Kalshi 15-minute markets.

Looks for exploitable regularities in the settled YES/NO history of a series
(e.g. KXBTC15M-...), not in the live price chart:
  * Streaks - is the market on a run of same-direction closes, and does that
    historically predict what comes next (continuation vs. mean-reversion)?
  * Alternation - is it mid zig-zag (YES/NO/YES/NO...), and does that pattern
    historically keep alternating or break?
  * Time-of-day - does the hour (ET) of the *next* close skew YES/NO more than
    chance, independent of any streak?

This module is advisory only. `get_pattern_signal()` never picks a side by
itself - contract_eval.py blends its output into a probability it has already
computed, capped to a few points, and only after a real signal has fired.
A thin sample returns has_signal=False rather than a guess.

History is pooled from two sources so the picture fills in fast even right
after a fresh deploy:
  * backend/data/market_results.json (backend.btc.market_results) - the
    authoritative Kalshi settlement cache, built as markets close.
  * the shared `trades` table (every account) - backfills any ticker not yet
    in that cache using the real outcome already resolved for that trade, and
    feeds it back into the shared cache for next time.
"""
import json
import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_ET = ZoneInfo("America/New_York")

MIN_STREAK_SAMPLES = 20      # historical instances of a streak length needed before trusting it
MIN_HOUR_SAMPLES = 15        # historical closes in an hour bucket needed before trusting it
MIN_EDGE = 0.06              # ignore anything closer to 50/50 than this (noise floor)
MIN_HOUR_EDGE = 0.08
MAX_NUDGE = 4.0              # advisory-only cap: never move the blended probability more than this
MAX_STREAK_LEN = 6           # streaks/zig-zags longer than this fold into a "6+" bucket (thin tail otherwise)
HISTORY_LIMIT = 1500         # most recent settled markets mined per asset
CACHE_TTL = 60.0             # seconds; this is a rolling analytic, not a per-request query

_lock = threading.Lock()
_cache = {}   # asset -> (ts, signal_dict)


def _series_prefix(asset: str) -> str:
    return f"KX{str(asset or 'BTC').upper()}15M-"


def _pooled_sequence(asset: str, limit: int = HISTORY_LIMIT):
    """Chronological [(close_epoch, 'YES'|'NO', ticker), ...] for this asset's settled
    markets, merging the market-results cache with the shared trades table."""
    from backend.btc import market_results as _mr
    from backend.btc.market_results import (get_result, market_close_epoch,
                                            remember)
    prefix = _series_prefix(asset)

    seen = {}  # ticker -> result

    try:
        with _mr._lock:
            cached = dict(_mr._load())
        for ticker, result in cached.items():
            if ticker.upper().startswith(prefix):
                seen[ticker] = result
    except Exception as e:
        logger.debug(f"[PatternAnalyzer] cache read failed: {e}")

    try:
        from backend.database.models import get_db_connection
        rows = get_db_connection().execute(
            "SELECT ticker, raw_json FROM trades WHERE status != 'OPEN' AND ticker LIKE ? "
            "ORDER BY rowid DESC LIMIT 5000", (prefix + "%",)).fetchall()
        for ticker, raw in rows:
            if not ticker or ticker in seen or ticker.upper().endswith("_SYNTH"):
                continue
            try:
                trade = json.loads(raw)
            except (TypeError, ValueError):
                continue
            result = get_result(ticker, trade)
            if result in ("YES", "NO"):
                seen[ticker] = result
                remember(ticker, result)  # backfill the shared cache for next time
    except Exception as e:
        logger.debug(f"[PatternAnalyzer] trade backfill failed: {e}")

    seq = []
    for ticker, result in seen.items():
        epoch = market_close_epoch(ticker)
        if epoch is not None:
            seq.append((epoch, result, ticker))
    seq.sort(key=lambda r: r[0])
    return seq[-limit:]


def _streak_signal(seq):
    """Does the length/direction of the current run historically predict the next close?

    Slides a window of the current streak's length over history: whenever the trailing
    `capped_len` results all match the streak's direction, records whether the very next
    result continued that direction or reverted. This naturally weighs regimes where long
    runs are common (momentum) against ones where streaks reliably snap back (mean reversion).
    """
    if len(seq) < 30:
        return None
    results = [r for _, r, _ in seq]
    n = len(results)

    tail = results[-1]
    streak_len = 1
    for r in reversed(results[:-1]):
        if r == tail:
            streak_len += 1
        else:
            break
    capped_len = min(streak_len, MAX_STREAK_LEN)

    cont, flip = 0, 0
    for i in range(capped_len - 1, n - 1):
        window = results[i - capped_len + 1:i + 1]
        if all(v == tail for v in window):
            if results[i + 1] == tail:
                cont += 1
            else:
                flip += 1
    total = cont + flip
    if total < MIN_STREAK_SAMPLES:
        return None
    continuation_rate = cont / total
    edge = continuation_rate - 0.5
    if abs(edge) < MIN_EDGE:
        return None
    direction = tail if continuation_rate > 0.5 else ("NO" if tail == "YES" else "YES")
    verb = "extend the streak" if continuation_rate > 0.5 else "reverse the streak"
    len_label = f"{capped_len}+" if streak_len >= MAX_STREAK_LEN else str(capped_len)
    return {
        "kind": "STREAK",
        "direction": "ABOVE" if direction == "YES" else "BELOW",
        "edge": edge,
        "sample_size": total,
        "description": (f"Pattern Watch: after {len_label} consecutive {tail} closes, this series has "
                         f"gone on to {verb} {continuation_rate * 100:.0f}% of the time ({total} samples)."),
    }


def _alternation_signal(seq):
    """Is the market mid zig-zag, and does that historically keep alternating or break?

    Same sliding-window idea as the streak check, but the window has to itself be a
    strict A/B/A/B run rather than a single repeated value.
    """
    if len(seq) < 30:
        return None
    results = [r for _, r, _ in seq]
    n = len(results)

    alt_len = 1
    for k in range(n - 1, 0, -1):
        if results[k] != results[k - 1]:
            alt_len += 1
        else:
            break
    if alt_len < 4:  # need at least A-B-A-B before calling it a zig-zag worth tracking
        return None
    capped_alt = min(alt_len, MAX_STREAK_LEN)
    expected_next = "NO" if results[-1] == "YES" else "YES"

    def _is_alternating(window):
        return all(window[k] != window[k - 1] for k in range(1, len(window)))

    keep_alt, breaks = 0, 0
    for i in range(capped_alt - 1, n - 1):
        window = results[i - capped_alt + 1:i + 1]
        if _is_alternating(window):
            if results[i + 1] != results[i]:
                keep_alt += 1
            else:
                breaks += 1
    total = keep_alt + breaks
    if total < MIN_STREAK_SAMPLES:
        return None
    keep_rate = keep_alt / total
    edge = keep_rate - 0.5
    if abs(edge) < MIN_EDGE:
        return None
    direction = expected_next if keep_rate > 0.5 else results[-1]
    return {
        "kind": "ALTERNATION",
        "direction": "ABOVE" if direction == "YES" else "BELOW",
        "edge": edge,
        "sample_size": total,
        "description": (f"Pattern Watch: this series is {alt_len} closes into a YES/NO zig-zag; historically "
                         f"that keeps alternating {keep_rate * 100:.0f}% of the time ({total} samples)."),
    }


def _time_of_day_signal(seq):
    """Does the hour (ET) of the upcoming close skew YES/NO historically?"""
    if len(seq) < 60:
        return None
    target_hour = datetime.fromtimestamp(time.time(), tz=_ET).hour
    buckets = {}
    for epoch, result, _ in seq:
        h = datetime.fromtimestamp(epoch, tz=_ET).hour
        b = buckets.setdefault(h, {"YES": 0, "NO": 0})
        b[result] += 1
    b = buckets.get(target_hour)
    if not b:
        return None
    total = b["YES"] + b["NO"]
    if total < MIN_HOUR_SAMPLES:
        return None
    yes_rate = b["YES"] / total
    edge = yes_rate - 0.5
    if abs(edge) < MIN_HOUR_EDGE:
        return None
    direction = "ABOVE" if yes_rate > 0.5 else "BELOW"
    return {
        "kind": "TIME_OF_DAY",
        "direction": direction,
        "edge": edge,
        "sample_size": total,
        "description": (f"Pattern Watch: the {target_hour}:00 ET close has resolved YES "
                         f"{yes_rate * 100:.0f}% of the time historically ({total} samples)."),
    }


def get_pattern_signal(asset: str = "BTC") -> dict:
    """Advisory-only pattern signal for `asset`'s 15m series, cached briefly.
    {"has_signal": False} when there isn't enough settled history to be meaningful yet."""
    asset = str(asset or "BTC").upper()
    now = time.time()
    with _lock:
        cached = _cache.get(asset)
        if cached and now - cached[0] < CACHE_TTL:
            return cached[1]
    try:
        seq = _pooled_sequence(asset)
        candidates = [s for s in (_streak_signal(seq), _alternation_signal(seq), _time_of_day_signal(seq)) if s]
        if not candidates:
            signal = {"has_signal": False}
        else:
            best = max(candidates, key=lambda s: abs(s["edge"]) * min(1.0, s["sample_size"] / 100.0))
            nudge = max(-MAX_NUDGE, min(MAX_NUDGE, best["edge"] * 40.0))
            signal = {
                "has_signal": True,
                "direction": best["direction"],
                "nudge": round(nudge, 2),
                "kind": best["kind"],
                "sample_size": best["sample_size"],
                "description": best["description"],
                "candidates": candidates,
            }
    except Exception as e:
        logger.debug(f"[PatternAnalyzer] {asset}: {e}")
        signal = {"has_signal": False}
    with _lock:
        _cache[asset] = (now, signal)
    return signal
