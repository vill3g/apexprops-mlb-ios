"""Data for the dashboard's Head Trader Dossier card.

* panel_summary(dossier) trims the full intelligence dossier sent to Gemini down to
  what a person needs to judge the call and trade it manually.
* record_call() / call_stats() keep a small log of Gemini's calls per 15-minute
  market and score them against Kalshi's official result, so the card can show how
  often calls at a given confidence actually won (raw confidence overstates it).
"""
import json
import logging
import math
import os
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_CALLS = 3000              # calls kept on disk (~1 month of 15m intervals across assets)
BAND_WIDTH = 5.0              # confidence bands: 75-80%, 80-85%, ...
MIN_BAND_SAMPLES = 10         # below this, the band's win rate is too noisy to show
RECENT_CALLS = 12

_lock = threading.Lock()
_calls: Optional[List[Dict[str, Any]]] = None


def kalshi_taker_fee(price: float) -> float:
    """Per-contract taker fee in dollars: ceil(0.07 * P * (1 - P) * 100) / 100."""
    if not 0.0 < price < 1.0:
        return 0.0
    return math.ceil(round(0.07 * price * (1.0 - price) * 100.0, 9)) / 100.0


def _tone(value: Any) -> str:
    """'bull' when a signal favors YES / up, 'bear' for NO / down, else 'neut'."""
    s = str(value or "").upper()
    if any(k in s for k in ("BULL", "_YES", "YES_", "RISK_ON", "HIGHER_LOWS", "RECLAIM")):
        return "bull"
    if any(k in s for k in ("BEAR", "_NO", "NO_", "RISK_OFF", "LOWER_HIGHS", "BREAKDOWN")):
        return "bear"
    return "neut"


def _label(value: Any) -> str:
    """'FRESH_BULLISH_YES_OI_BUILDUP' -> 'Fresh bullish yes oi buildup'."""
    s = str(value or "").split("(")[0].strip().replace("_", " ").lower()
    return s[:1].upper() + s[1:] if s else "—"


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def panel_summary(dossier: Dict[str, Any]) -> Dict[str, Any]:
    """The parts of the Gemini dossier the dashboard card shows. Never raises."""
    try:
        d = dossier or {}
        contract = d.get("contract") or {}
        book = d.get("kalshi_orderbook") or {}
        micro = d.get("kalshi_microstructure_l2_oi_twap") or {}
        ind = (d.get("price_action_and_indicators") or {}).get("indicators") or {}
        exh = d.get("exhaustion_and_stretch_metrics") or {}
        perp = d.get("perp_liquidations_and_funding") or {}
        macro = d.get("macro_economic_event_horizon") or {}
        models = d.get("local_ai_models") or {}
        consensus = models.get("voting_ensemble_consensus") or {}
        l2 = _num((micro.get("level2_orderbook_depth") or {}).get("l2_book_imbalance_minus1_to_plus1"))
        rsi, bb = _num(ind.get("rsi"), 50.0), _num(ind.get("bb_pct_b"), 0.5)

        signals = [
            ("Opening 1m structure", (d.get("opening_1m_micro_trend") or {}).get("trajectory")),
            ("TWAP head start", (micro.get("twap_60s_strike_dislocation") or {}).get("opening_twap_regime")),
            ("L2 book imbalance", f"{l2:+.2f} " + ("YES" if l2 > 0.05 else "NO" if l2 < -0.05 else "balanced")),
            ("Whale tape", (d.get("live_kalshi_tape_and_whale_flow") or {}).get("tape_orderflow_verdict")),
            ("Open interest", (micro.get("contract_1m_candlesticks_and_open_interest") or {}).get("oi_conviction_regime")),
            ("CVD order flow", (d.get("cvd_orderflow_delta") or {}).get("cvd_trend")),
            ("RSI / BB %b", f"{rsi:.0f} / {bb:.2f}"),
            ("1h trend", ind.get("trend_1h")),
            ("Perp funding", perp.get("funding_rate_bias")),
            ("Macro beta", (d.get("cross_asset_macro_beta_flow") or {}).get("macro_risk_sentiment")),
        ]
        rows = []
        for name, value in signals:
            if value in (None, ""):
                continue
            if name == "L2 book imbalance":
                tone = "bull" if l2 > 0.05 else "bear" if l2 < -0.05 else "neut"
            elif name == "RSI / BB %b":
                tone = "neut"   # stretch is a warning, not a direction
            elif name == "Perp funding":
                # crowded longs risk a flush down, crowded shorts a squeeze up
                v = str(value).upper()
                tone = "bear" if "LONG_CROWDED" in v else "bull" if "SHORT_CROWDED" in v else "neut"
            else:
                tone = _tone(value)
            rows.append({"name": name, "value": value if name in ("L2 book imbalance", "RSI / BB %b") else _label(value), "tone": tone})

        warnings = []
        mins = _num(macro.get("minutes_to_nearest_event"), 999.0)
        if macro.get("volatility_freeze_recommended") or mins <= 60:
            warnings.append({"icon": "⚠️", "level": "amber",
                             "text": f"{macro.get('nearest_event_name', 'Macro event')} in {mins:.0f} min"
                                     + (" — volatility freeze active" if macro.get("volatility_freeze_recommended") else "")})
        lock = (d.get("synthetic_60s_settlement_lock") or {}).get("math_locked_outcome")
        if lock in ("LOCKED_YES", "LOCKED_NO"):
            warnings.append({"icon": "🔒", "level": "green", "text": f"Settlement average already locked {lock[7:]}"})
        snipe = d.get("stale_quote_arbitrage_opportunity") or {}
        if snipe.get("is_snipe_opportunity"):
            warnings.append({"icon": "⚡", "level": "green",
                             "text": f"Stale quote: {snipe.get('recommended_side')} looks mispriced by {_num(snipe.get('edge_cents')):.0f}¢"})
        for v in (d.get("recent_loss_regime_warnings") or [])[:2]:
            warnings.append({"icon": "📉", "level": "red", "text": str(v.get("reason", "")).replace("Loss Guard Veto: ", "")[:110]})
        if str(perp.get("short_squeeze_risk", "")).upper() == "HIGH":
            warnings.append({"icon": "🔥", "level": "amber", "text": "High short-squeeze risk — careful betting NO"})
        if str(exh.get("actionable_guard", "CLEAR")).upper() not in ("CLEAR", ""):
            warnings.append({"icon": "📈", "level": "amber", "text": f"Exhaustion guard: {_label(exh.get('actionable_guard'))}"})

        return {
            "ticker": contract.get("ticker"),
            "strike": contract.get("strike_price"),
            "spot": contract.get("current_spot_price"),
            "spot_minus_strike": contract.get("spot_minus_strike"),
            "outside_pin": contract.get("is_outside_deadzone"),
            "quotes_at_call": {k: book.get(k) for k in ("yes_ask", "yes_bid", "no_ask", "no_bid")},
            "signals": rows,
            "warnings": warnings,
            "models": {
                "ml_prob_up_pct": models.get("ml_ensemble_prob_above_strike_pct"),
                "tech_gate_direction": models.get("local_technical_gate_direction"),
                "voting_direction": consensus.get("consensus_direction"),
                "voting_agreement": consensus.get("agreement_ratio"),
            },
        }
    except Exception as e:
        logger.debug(f"[GeminiPanel] summary failed: {e}")
        return {}


# ── Call log ──────────────────────────────────────────────────────────

def _path() -> str:
    from backend.database.models import DATA_DIR
    return os.path.join(os.path.abspath(DATA_DIR), "gemini_calls.json")


def _load() -> List[Dict[str, Any]]:
    global _calls
    if _calls is None:
        try:
            with open(_path(), "r") as f:
                _calls = [c for c in (json.load(f) or []) if isinstance(c, dict)]
        except (OSError, ValueError):
            _calls = []
    return _calls


def _save() -> None:
    try:
        tmp = _path() + ".tmp"
        with open(tmp, "w") as f:
            json.dump(_calls, f)
        os.replace(tmp, _path())
    except OSError as e:
        logger.debug(f"[GeminiPanel] save failed: {e}")


def record_call(asset: str, ticker: str, direction: str, confidence: Any) -> None:
    """Remember Gemini's latest call for one 15-minute market (one entry per market)."""
    direction = str(direction or "").upper()
    if not ticker or direction not in ("YES", "NO", "PASS") or str(ticker).upper().endswith("_SYNTH"):
        return
    entry = {"asset": str(asset).upper(), "ticker": str(ticker), "direction": direction,
             "confidence": round(_num(confidence, 50.0), 1), "ts": time.time()}
    with _lock:
        calls = _load()
        calls[:] = [c for c in calls if not (c.get("ticker") == entry["ticker"] and c.get("asset") == entry["asset"])]
        calls.append(entry)
        del calls[:-MAX_CALLS]
        _save()


def call_stats(asset: str, confidence: Any) -> Dict[str, Any]:
    """Recent scored calls for an asset, and the win rate of past calls in the
    same confidence band as `confidence`. Unscored markets are skipped."""
    from backend.btc.market_results import get_result
    a = str(asset).upper()
    with _lock:
        calls = [dict(c) for c in _load() if c.get("asset") == a and c.get("direction") in ("YES", "NO")]
    scored = []
    for c in calls:
        result = get_result(c["ticker"])
        if result in ("YES", "NO"):
            c["won"] = result == c["direction"]
            scored.append(c)

    conf = _num(confidence, 50.0)
    lo = math.floor(conf / BAND_WIDTH) * BAND_WIDTH
    band = [c for c in scored if lo <= c["confidence"] < lo + BAND_WIDTH]
    wins = sum(1 for c in band if c["won"])
    recent = scored[-RECENT_CALLS:]
    return {
        "band": {"low": lo, "high": lo + BAND_WIDTH, "n": len(band), "wins": wins,
                 "win_rate": round(wins / len(band), 3) if len(band) >= MIN_BAND_SAMPLES else None},
        "recent": [{"ticker": c["ticker"], "direction": c["direction"], "confidence": c["confidence"], "won": c["won"]}
                   for c in recent],
        "recent_wins": sum(1 for c in recent if c["won"]),
    }
