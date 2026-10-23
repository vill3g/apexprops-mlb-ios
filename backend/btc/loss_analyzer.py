import json
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class LossAnalyzer:
    """
    Analyzes settled losing trades to identify root causes (e.g., false breakout, 
    low-volume chop, orderbook imbalance, volatility spike, oversold bounce).
    Dynamically tracks asset-specific failure regimes and outputs real-time defensive
    policy vetoes and conviction adjustments so future entries avoid repeating identical losses.
    """
    def __init__(self):
        self.recent_loss_categories: List[Dict[str, Any]] = []
        self._diagnosed_cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _extract_features(self, trade: Dict[str, Any], market_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Robustly extracts snapshot and raw technical features from a trade dict,
        handling JSON strings, nested dicts, raw_features, ml_features, or raw_json.
        """
        snapshot = market_snapshot or trade.get("market_snapshot") or {}
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except Exception:
                snapshot = {}

        raw_features = trade.get("raw_features") or snapshot.get("raw_features") or {}
        if isinstance(raw_features, str):
            try:
                raw_features = json.loads(raw_features)
            except Exception:
                raw_features = {}

        ml_features = trade.get("ml_features") or {}
        if isinstance(ml_features, str):
            try:
                ml_features = json.loads(ml_features)
            except Exception:
                ml_features = {}

        indicators = snapshot.get("indicators") or trade.get("indicators") or {}
        if isinstance(indicators, str):
            try:
                indicators = json.loads(indicators)
            except Exception:
                indicators = {}

        # Fallback to trade raw_json if features are still empty
        if not raw_features and trade.get("raw_json"):
            try:
                raw_j = json.loads(trade["raw_json"]) if isinstance(trade["raw_json"], str) else trade["raw_json"]
                snap_j = raw_j.get("market_snapshot") or {}
                if isinstance(snap_j, str):
                    snap_j = json.loads(snap_j)
                raw_features = raw_j.get("raw_features") or snap_j.get("raw_features") or {}
            except Exception:
                pass

        return {
            "snapshot": snapshot,
            "raw_features": raw_features,
            "ml_features": ml_features,
            "indicators": indicators
        }

    def diagnose_loss(self, trade: Dict[str, Any], market_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Takes a settled trade marked as LOSS and inspects its entry snapshot features 
        to diagnose the exact failure mechanism.
        """
        feats = self._extract_features(trade, market_snapshot)
        raw_features = feats["raw_features"]
        indicators = feats["indicators"]

        def _first_not_none(*values, default):
            for v in values:
                if v is not None:
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        pass
            return default

        rsi   = _first_not_none(raw_features.get("rsi"),       indicators.get("rsi"),       trade.get("rsi"), default=50.0)
        atr   = _first_not_none(raw_features.get("atr"),       indicators.get("atr"),       trade.get("atr"), default=0.0)
        cvd   = _first_not_none(raw_features.get("cvd_value"), indicators.get("cvd"),       trade.get("cvd"), default=0.0)
        delta = _first_not_none(raw_features.get("delta_to_target"), trade.get("delta_to_target"),            default=0.0)
        side = str(trade.get("side", trade.get("direction", "YES"))).upper().strip()
        ticker = str(trade.get("ticker", "")).upper()
        
        # Derive asset from ticker (e.g. KXBTC15M -> BTC, KXETH15M -> ETH)
        asset = "BTC"
        for a in ["BTC", "ETH", "SOL", "DOGE", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "GOLD"]:
            if a in ticker:
                asset = a
                break

        # Extract lagged RSI values across previous 4 candles (handling both 0-1 and 0-100 scaling)
        min_rsi_lag = rsi
        max_rsi_lag = rsi
        for i in range(1, 5):
            val = raw_features.get(f"rsi_lag_{i}")
            if val is not None:
                try:
                    fv = float(val)
                    if fv <= 1.0:
                        fv *= 100.0
                    min_rsi_lag = min(min_rsi_lag, fv)
                    max_rsi_lag = max(max_rsi_lag, fv)
                except (ValueError, TypeError):
                    pass

        # Extract Bollinger %b lags to detect band boundary traps
        bb_vals = []
        for i in range(5):
            val = raw_features.get(f"bb_percent_b_lag_{i}")
            if val is not None:
                try:
                    bb_vals.append(float(val))
                except (ValueError, TypeError):
                    pass
        min_bb_b = min(bb_vals) if bb_vals else 0.5
        max_bb_b = max(bb_vals) if bb_vals else 0.5

        category = "UNKNOWN"
        summary = "Unclassified market reversal"
        severity = "MODERATE"

        # 1. False Breakout / Mean-Reversion Bounce Reversal Diagnosis
        if side in ["NO", "BELOW", "DOWN"] and (rsi < 38.0 or min_rsi_lag < 34.0 or min_bb_b < 0.15):
            category = "FALSE_BREAKOUT_OVERSOLD"
            summary = f"Bearish entry at oversold level (RSI {rsi:.1f}, recent low {min_rsi_lag:.1f}, BB %b {min_bb_b:.2f}) suffered mean-reversion bounce reversal"
            severity = "HIGH"
        elif side in ["YES", "ABOVE", "UP"] and (rsi > 62.0 or max_rsi_lag > 66.0 or max_bb_b > 0.85):
            category = "FALSE_BREAKOUT_OVERBOUGHT"
            summary = f"Bullish entry at overbought level (RSI {rsi:.1f}, recent high {max_rsi_lag:.1f}, BB %b {max_bb_b:.2f}) encountered exhaustion reversal"
            severity = "HIGH"
        
        # 2. Choppy / Narrow Range Bound Diagnosis (asset-scaled)
        elif (asset in ["BTC", "GOLD"] and 0 < atr < 50.0) or (asset == "ETH" and 0 < atr < 3.0) or (asset in ["SOL", "DOGE"] and 0 < atr < 0.20):
            category = "CHOPPY_RANGE_BOUND"
            summary = f"Low ATR volatility (${atr:.2f}) caused sideways chop without clear directional expansion"
            severity = "HIGH"
            
        # 3. Orderbook / CVD Volume Divergence Diagnosis
        elif (side in ["YES", "ABOVE"] and cvd < -2.0) or (side in ["NO", "BELOW"] and cvd > 2.0):
            category = "ORDERBOOK_CVD_DIVERGENCE"
            summary = f"Trade side ({side}) contradicted spot orderbook CVD volume pressure ({cvd:+.1f})"
            severity = "HIGH"
            
        # 4. Narrow Target Pinning
        elif 0 < abs(delta) < 0.05:  # Delta as percentage to target within 0.05%
            category = "NARROW_TARGET_PIN"
            summary = f"Price closed extremely tight to target ({delta:+.3f}%), pinned at expiration"
            severity = "LOW"
        else:
            category = "MOMENTUM_EXHAUSTION"
            summary = f"Market momentum reversed against entry bias ({side}) prior to expiration"

        trade_key = str(trade.get("id") or ticker)
        with self._lock:
            if trade_key and trade_key in self._diagnosed_cache:
                return self._diagnosed_cache[trade_key]

        diagnosis = {
            "trade_id": trade_key,
            "ticker": ticker,
            "asset": asset,
            "side": side,
            "category": category,
            "summary": summary,
            "severity": severity,
            "rsi_at_entry": round(rsi, 1),
            "min_rsi_lag": round(min_rsi_lag, 1),
            "max_rsi_lag": round(max_rsi_lag, 1),
            "min_bb_b": round(min_bb_b, 2),
            "atr_at_entry": round(atr, 2),
            "cvd_at_entry": round(cvd, 1),
            "delta_at_entry": round(delta, 3)
        }

        with self._lock:
            if trade_key:
                self._diagnosed_cache[trade_key] = diagnosis
                if len(self._diagnosed_cache) > 500:
                    oldest_key = next(iter(self._diagnosed_cache))
                    self._diagnosed_cache.pop(oldest_key, None)
            self.recent_loss_categories.append(diagnosis)
            if len(self.recent_loss_categories) > 50:
                self.recent_loss_categories = self.recent_loss_categories[-50:]

        logger.info(f"[LossAnalyzer] Loss Diagnosis for {ticker} ({side}): {category} -> {summary}")
        return diagnosis

    def calculate_regime_penalties(self, trades_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates dynamic conviction adjustments based on recent loss patterns.
        Returns multiplier penalties and additional filters to protect future trades.
        """
        recent_settled = [t for t in trades_history if t.get("status") in ["SETTLED", "CLOSED"]][-20:]
        losses = [t for t in recent_settled if (float(t.get("pnl") or 0.0) < 0 or "LOSS" in str(t.get("result", "")).upper())]
        
        if not losses:
            return {
                "conviction_multiplier": 1.0,
                "extra_min_rsi_cushion": 0,
                "chop_warning": False,
                "loss_rate_15": 0.0
            }

        loss_rate = len(losses) / len(recent_settled) if recent_settled else 0.0
        
        categories = []
        for t in losses:
            la = t.get("loss_analysis")
            if isinstance(la, str):
                try:
                    la = json.loads(la)
                except Exception:
                    la = {}
            if isinstance(la, dict) and la.get("category"):
                categories.append(la["category"])

        chop_count = sum(1 for c in categories if "CHOPPY" in c or "PIN" in c)
        breakout_count = sum(1 for c in categories if "FALSE_BREAKOUT" in c)

        conviction_mult = 1.0
        extra_rsi_cushion = 0
        chop_warning = False

        if loss_rate >= 0.4:  # 40%+ loss rate in last 20 trades
            conviction_mult = 0.85  # Require higher conviction to trade
        if chop_count >= 2:
            chop_warning = True
            conviction_mult *= 0.9  # Reduce confidence in choppy markets
        if breakout_count >= 2:
            extra_rsi_cushion = 6  # Require 6 extra points of RSI margin

        return {
            "conviction_multiplier": round(conviction_mult, 2),
            "extra_min_rsi_cushion": extra_rsi_cushion,
            "chop_warning": chop_warning,
            "recent_loss_count": len(losses),
            "recent_total_trades": len(recent_settled),
            "loss_rate_percent": round(loss_rate * 100, 1)
        }

    def get_loss_regime_vetoes(self, asset: str, trades_history: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Inspects the most recent settled trades for the specified asset (or globally across memory).
        If 2 or more recent trades failed due to a specific pattern (e.g. FALSE_BREAKOUT_OVERSOLD,
        FALSE_BREAKOUT_OVERBOUGHT, ORDERBOOK_CVD_DIVERGENCE, or CHOPPY_RANGE_BOUND),
        returns active defensive policy vetoes to enforce in contract_eval.py.
        """
        asset_norm = str(asset or "BTC").upper().strip()
        recent_diagnoses = []

        # 1. Inspect recent trades from DB/history if provided or auto-load from DB
        if trades_history is None:
            try:
                from backend.database.models import get_db_connection
                conn = get_db_connection()
                c = conn.cursor()
                # Query the most recent settled trades for this asset
                c.execute(
                    """
                    SELECT raw_json FROM trades 
                    WHERE (pnl < 0 OR status IN ('SETTLED', 'CLOSED'))
                    AND ticker LIKE ?
                    ORDER BY rowid DESC LIMIT 25
                    """,
                    (f"%{asset_norm}%",)
                )
                db_trades = []
                for row in c.fetchall():
                    if row[0]:
                        try:
                            t_parsed = json.loads(row[0])
                            if isinstance(t_parsed, dict):
                                db_trades.append(t_parsed)
                        except Exception:
                            pass
                conn.close()
                trades_history = db_trades
            except Exception as _dbe:
                logger.debug(f"[LossAnalyzer] Could not load trades from DB: {_dbe}")

        if trades_history:
            recent_trades = [t for t in trades_history if t.get("status") in ["SETTLED", "CLOSED"]][-25:]
            for t in recent_trades:
                if float(t.get("pnl") or 0.0) < 0 or "LOSS" in str(t.get("result", "")).upper():
                    ticker = str(t.get("ticker", "")).upper()
                    if asset_norm not in ticker and ticker.startswith("KX"):
                        continue
                    la = t.get("loss_analysis")
                    if isinstance(la, str):
                        try:
                            la = json.loads(la)
                        except Exception:
                            la = {}
                    if not la or not isinstance(la, dict) or not la.get("category"):
                        la = self.diagnose_loss(t)
                    recent_diagnoses.append(la)

        # 2. Combine with in-memory singleton diagnoses
        with self._lock:
            for d in self.recent_loss_categories:
                if d.get("asset") == asset_norm or asset_norm in str(d.get("ticker", "")):
                    if d not in recent_diagnoses:
                        recent_diagnoses.append(d)

        # Look at the last 10 asset-specific losses
        recent_asset_losses = recent_diagnoses[-10:]
        if not recent_asset_losses:
            return []

        counts = {}
        for d in recent_asset_losses:
            cat = d.get("category", "UNKNOWN")
            counts[cat] = counts.get(cat, 0) + 1

        active_vetoes = []

        # Rule A: Recent Oversold Bounce Failures (blocks repeat NO / BELOW bids at low RSI)
        if counts.get("FALSE_BREAKOUT_OVERSOLD", 0) >= 2:
            active_vetoes.append({
                "veto_type": "BLOCK_OVERSOLD_NO",
                "blocked_side": "NO",
                "rsi_threshold": 38.0,
                "reason": f"Loss Guard Veto: {counts['FALSE_BREAKOUT_OVERSOLD']} recent losses on oversold breakdown bounce. Blocking NO bids when RSI < 38 (or recent oversold dip)."
            })

        # Rule B: Recent Overbought Exhaustion Failures (blocks repeat YES / ABOVE bids at high RSI)
        if counts.get("FALSE_BREAKOUT_OVERBOUGHT", 0) >= 2:
            active_vetoes.append({
                "veto_type": "BLOCK_OVERBOUGHT_YES",
                "blocked_side": "YES",
                "rsi_threshold": 62.0,
                "reason": f"Loss Guard Veto: {counts['FALSE_BREAKOUT_OVERBOUGHT']} recent losses on overbought exhaustion. Blocking YES bids when RSI > 62 (or recent overbought surge)."
            })

        # Rule C: Recent CVD Divergence Failures
        if counts.get("ORDERBOOK_CVD_DIVERGENCE", 0) >= 2:
            active_vetoes.append({
                "veto_type": "BLOCK_CVD_CONTRADICTION",
                "reason": f"Loss Guard Veto: {counts['ORDERBOOK_CVD_DIVERGENCE']} recent losses on CVD divergence. Requiring strict orderbook CVD flow alignment."
            })

        # Rule D: Choppy Range Bound Chop Trap
        if counts.get("CHOPPY_RANGE_BOUND", 0) >= 2 or counts.get("NARROW_TARGET_PIN", 0) >= 2:
            active_vetoes.append({
                "veto_type": "REQUIRE_EXPANSION_EDGE",
                "reason": f"Loss Guard Veto: {counts.get('CHOPPY_RANGE_BOUND', 0) + counts.get('NARROW_TARGET_PIN', 0)} recent losses in tight range chop. Enforcing capital protection."
            })

        return active_vetoes

# Global singleton
loss_analyzer = LossAnalyzer()
