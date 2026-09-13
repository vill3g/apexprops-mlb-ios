import logging
import threading
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class LossAnalyzer:
    """
    Analyzes settled losing trades to identify root causes (e.g., false breakout, 
    low-volume chop, orderbook imbalance, volatility spike).
    Dynamically adjusts regime penalty multipliers so future trade entries avoid 
    repeating recent failure patterns.
    """
    def __init__(self):
        self.recent_loss_categories: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def diagnose_loss(self, trade: Dict[str, Any], market_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Takes a settled trade marked as LOSS and inspects its entry snapshot features 
        to diagnose the exact failure mechanism.
        """
        snapshot = market_snapshot or trade.get("market_snapshot") or {}
        raw_features = snapshot.get("raw_features") or {}
        indicators = snapshot.get("indicators") or {}
        
        rsi = raw_features.get("rsi") or indicators.get("rsi") or 50.0
        bb_upper = raw_features.get("bb_upper") or indicators.get("bb_upper") or 0.0
        bb_lower = raw_features.get("bb_lower") or indicators.get("bb_lower") or 0.0
        atr = raw_features.get("atr") or indicators.get("atr") or 0.0
        cvd = raw_features.get("cvd_value") or indicators.get("cvd") or 0.0
        delta = raw_features.get("delta_to_target") or 0.0
        side = str(trade.get("side", "YES")).upper()
        
        category = "UNKNOWN"
        summary = "Unclassified market reversal"
        severity = "MODERATE"

        # 1. False Breakout / Momentum Reversal Diagnosis
        if side == "YES" and rsi > 68:
            category = "FALSE_BREAKOUT_OVERBOUGHT"
            summary = f"Bullish entry at overbought RSI ({rsi:.1f}) encountered instant exhaustion reversal"
            severity = "HIGH"
        elif side == "NO" and rsi < 32:
            category = "FALSE_BREAKOUT_OVERSOLD"
            summary = f"Bearish entry at oversold RSI ({rsi:.1f}) encountered instant bounce reversal"
            severity = "HIGH"
        
        # 2. Choppy / Narrow Range Bound Diagnosis
        elif atr > 0 and atr < 45.0:
            category = "CHOPPY_RANGE_BOUND"
            summary = f"Low ATR volatility (${atr:.1f}) caused sideways chop without clear direction"
            severity = "HIGH"
            
        # 3. Orderbook / CVD Volume Divergence Diagnosis
        elif (side == "YES" and cvd < -2.0) or (side == "NO" and cvd > 2.0):
            category = "ORDERBOOK_CVD_DIVERGENCE"
            summary = f"Trade side ({side}) contradicted orderbook CVD volume pressure ({cvd:+.1f})"
            severity = "MODERATE"
            
        # 4. Sudden Volatility Reversal
        elif abs(delta) < 15.0:
            category = "NARROW_TARGET_PIN"
            summary = f"Price closed extremely tight to target (${abs(delta):.1f} delta), pinned at expiration"
            severity = "LOW"
        else:
            category = "MOMENTUM_EXHAUSTION"
            summary = f"Market trend reversed against entry bias ({side}) prior to 15m contract close"

        diagnosis = {
            "trade_id": trade.get("id") or trade.get("ticker"),
            "category": category,
            "summary": summary,
            "severity": severity,
            "rsi_at_entry": round(rsi, 1),
            "atr_at_entry": round(atr, 1),
            "cvd_at_entry": round(cvd, 1)
        }

        with self._lock:
            self.recent_loss_categories.append(diagnosis)
            if len(self.recent_loss_categories) > 20:
                self.recent_loss_categories = self.recent_loss_categories[-20:]

        logger.info(f"[LossAnalyzer] Loss Diagnosis for {trade.get('ticker')}: {category} -> {summary}")
        return diagnosis

    def calculate_regime_penalties(self, trades_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates dynamic conviction adjustments based on recent loss patterns.
        Returns multiplier penalties and additional filters to protect future trades.
        """
        recent_settled = [t for t in trades_history if t.get("status") in ["SETTLED", "CLOSED"]][-15:]
        losses = [t for t in recent_settled if "LOSS" in str(t.get("result", "")).upper()]
        
        if not losses:
            return {
                "conviction_multiplier": 1.0,
                "extra_min_rsi_cushion": 0,
                "chop_warning": False,
                "loss_rate_15": 0.0
            }

        loss_rate = len(losses) / len(recent_settled) if recent_settled else 0.0
        
        # Count loss categories from trade histories or internal list
        categories = [t.get("loss_analysis", {}).get("category", "") for t in losses if t.get("loss_analysis")]
        chop_count = sum(1 for c in categories if "CHOPPY" in c or "PIN" in c)
        breakout_count = sum(1 for c in categories if "FALSE_BREAKOUT" in c)

        conviction_mult = 1.0
        extra_rsi_cushion = 0
        chop_warning = False

        if loss_rate >= 0.4:  # 40%+ loss rate in last 15 trades
            conviction_mult = 0.85  # Require higher conviction to trade
        if chop_count >= 2:
            chop_warning = True
            conviction_mult *= 0.9  # Reduce confidence in choppy markets
        if breakout_count >= 2:
            extra_rsi_cushion = 5  # Require 5 extra points of RSI margin

        return {
            "conviction_multiplier": round(conviction_mult, 2),
            "extra_min_rsi_cushion": extra_rsi_cushion,
            "chop_warning": chop_warning,
            "recent_loss_count": len(losses),
            "recent_total_trades": len(recent_settled),
            "loss_rate_percent": round(loss_rate * 100, 1)
        }

# Global singleton
loss_analyzer = LossAnalyzer()
