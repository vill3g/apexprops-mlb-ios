"""Dynamic Volatility-Based Risk Management (ATR).

When a user enables `atr_risk_enabled`, their Take Profit % and Stop Loss % are scaled by how volatile
the underlying asset is *right now* compared with its own recent norm:

    ratio      = ATR14(15m, now) / median(ATR14 over the last ~24h of 15m candles)
    multiplier = clamp(ratio, ATR_MULT_MIN, ATR_MULT_MAX)
    eff_tp     = user_tp * multiplier
    eff_sl     = user_sl * multiplier   (capped at 95%)

High volatility -> wider stops/targets (avoid getting wicked out); quiet markets -> tighter ones.

Design constraints:
  * Never blocks the settlement loop: candles are fetched in a background thread; callers get the
    last known value (or 1.0 = "no change") immediately.
  * The multiplier is locked per trade the first time it is evaluated (stored as `atr_mult` on the
    trade dict) so a position's exits don't jitter tick-to-tick.
  * Any failure degrades to 1.0, i.e. exactly the user's configured settings.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

ATR_MULT_MIN = 0.6
ATR_MULT_MAX = 1.8
REFRESH_SEC = 60.0
STALE_SEC = 15 * 60.0      # ignore cached values older than this
_LOOKBACK = 96             # 24h of 15m candles

_cache: Dict[str, Tuple[float, float, float]] = {}   # asset -> (fetched_at, multiplier, ratio)
_inflight: set = set()
_lock = threading.Lock()


def _series_asset(ticker: str) -> Optional[str]:
    tk = str(ticker or "").upper()
    series = tk.split("-", 1)[0].replace("_SYNTH", "")
    if series.startswith("KX"):
        series = series[2:]
    if series.endswith("15M"):
        series = series[:-3]
    return series or None


def _compute(asset: str) -> Tuple[float, float]:
    from backend.btc.indicators import compute_atr
    from backend.engine.multi_asset_fetcher import fetch_asset_candles

    df = fetch_asset_candles(asset, "15m", _LOOKBACK + 30)
    if df is None or len(df) < 30:
        raise ValueError(f"not enough candles for {asset}")
    atr = compute_atr(df, 14).dropna().tail(_LOOKBACK)
    if atr.empty:
        raise ValueError(f"ATR unavailable for {asset}")
    current = float(atr.iloc[-1])
    baseline = float(atr.median())
    if baseline <= 0 or current <= 0:
        raise ValueError(f"degenerate ATR for {asset}")
    ratio = current / baseline
    return max(ATR_MULT_MIN, min(ATR_MULT_MAX, ratio)), ratio


def _refresh(asset: str) -> None:
    try:
        mult, ratio = _compute(asset)
        with _lock:
            _cache[asset] = (time.time(), mult, ratio)
        logger.debug(f"[ATR Risk] {asset}: ATR ratio {ratio:.2f} -> multiplier {mult:.2f}")
    except Exception as e:
        logger.debug(f"[ATR Risk] refresh failed for {asset}: {e}")
    finally:
        with _lock:
            _inflight.discard(asset)


def get_multiplier(asset_or_ticker: str, blocking: bool = False) -> float:
    """Current volatility multiplier for an asset (or Kalshi ticker). Returns 1.0 when unknown."""
    asset = _series_asset(asset_or_ticker)
    if not asset:
        return 1.0
    now = time.time()
    with _lock:
        entry = _cache.get(asset)
        need = entry is None or now - entry[0] > REFRESH_SEC
        start = need and asset not in _inflight
        if start:
            _inflight.add(asset)
    if start:
        if blocking:
            _refresh(asset)
            with _lock:
                entry = _cache.get(asset)
        else:
            threading.Thread(target=_refresh, args=(asset,), daemon=True, name=f"atr-{asset}").start()
    if entry is None or now - entry[0] > STALE_SEC:
        return 1.0
    return entry[1]


def effective_tp_sl(user: dict, trade: Optional[dict], tp_frac: float, sl_frac: float) -> Tuple[float, float, float]:
    """Return (tp_frac, sl_frac, multiplier) after applying the user's ATR setting.

    `trade` (if given) gets `atr_mult` stored on first use so its exits stay stable; callers that persist
    the trade dict should mark it modified when the key was newly added."""
    try:
        if not bool(int(user.get("atr_risk_enabled") or 0)):
            return tp_frac, sl_frac, 1.0
    except (TypeError, ValueError):
        return tp_frac, sl_frac, 1.0
    mult = None
    if trade is not None:
        try:
            mult = float(trade.get("atr_mult")) if trade.get("atr_mult") is not None else None
        except (TypeError, ValueError):
            mult = None
    if mult is None:
        mult = get_multiplier((trade or {}).get("ticker") or user.get("target_asset") or "BTC")
        if trade is not None and mult != 1.0:
            trade["atr_mult"] = round(mult, 3)
    return tp_frac * mult, min(0.95, sl_frac * mult), mult


def snapshot(assets=("BTC", "ETH", "SOL", "DOGE", "GOLD", "NDQ", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD")) -> Dict[str, dict]:
    """Current multipliers for display in the UI (non-blocking)."""
    out = {}
    for a in assets:
        m = get_multiplier(a)
        with _lock:
            e = _cache.get(a)
        out[a] = {"multiplier": round(m, 2), "ratio": round(e[2], 2) if e else None,
                  "age_sec": int(time.time() - e[0]) if e else None}
    return out
