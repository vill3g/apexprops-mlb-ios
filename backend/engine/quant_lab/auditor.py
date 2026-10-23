"""
Post-Mortem Auditor for ShadowTrader Quant Lab.
Performs root-cause failure analysis on failed backtests and losing incubation trades,
synthesizes defensive rules, and commits them to the Strategy Graveyard.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.engine.quant_lab.graveyard import StrategyGraveyard

logger = logging.getLogger(__name__)


class PostMortemAuditor:
    """Diagnoses strategy failures and writes actionable lessons to memory."""

    @classmethod
    def audit_backtest_failure(
        cls,
        strategy_id: str,
        name: str,
        hypothesis: str,
        asset: str,
        validation_result: Dict[str, Any],
        code_hash: Optional[str] = None
    ) -> int:
        """
        Diagnoses why a proposed strategy failed backtesting or Monte Carlo tests,
        and saves a negative rule to the graveyard.
        """
        failure_reason = validation_result.get("failure_reason", "Unspecified backtest failure")
        metrics = validation_result.get("metrics", {})
        win_rate = metrics.get("win_rate", 0.0)
        sharpe = metrics.get("sharpe", 0.0)
        max_dd = metrics.get("max_drawdown", 0.0)

        post_mortem = (
            f"Strategy failed out-of-sample backtest with {win_rate*100:.1f}% win rate, "
            f"Sharpe {sharpe:.2f}, and {max_dd*100:.1f}% max drawdown after Kalshi fee/slippage friction. "
            f"Primary failure bottleneck: {failure_reason}."
        )

        # Formulate defensive negative rule
        negative_rule = cls._synthesize_negative_rule(hypothesis, failure_reason, asset)

        entry_id = StrategyGraveyard.record_failure(
            strategy_id=strategy_id,
            name=name,
            hypothesis=hypothesis,
            asset=asset,
            failure_stage="BACKTEST_FAILED",
            post_mortem_summary=post_mortem,
            negative_rule=negative_rule,
            code_hash=code_hash,
            metrics_snapshot=metrics,
            regime_context={"source": "backtest_oos", "primary_cause": failure_reason}
        )

        logger.info(f"[PostMortemAuditor] Backtest failure logged to Graveyard #{entry_id} for {name}")
        return entry_id

    @classmethod
    def audit_incubation_loss(
        cls,
        strategy_id: str,
        name: str,
        hypothesis: str,
        asset: str,
        trade_data: Dict[str, Any],
        snapshot: Dict[str, Any],
        code_hash: Optional[str] = None
    ) -> int:
        """
        Diagnoses a live forward paper incubation loss.
        Inspects live market regime (RSI, ATR, CVD, delta) to identify the breakdown.
        """
        features = snapshot.get("raw_features") or snapshot.get("indicators") or {}
        side = str(trade_data.get("side", "YES")).upper()
        is_sports = str(asset).upper() in {
            "SPORTS", "SPORT", "NFL", "MLB", "NBA", "NHL", "NPB", "KBO", "NPB/KBO", "NPB_KBO", "NPB-KBO",
            "SOC", "SOCCER", "UFC", "MMA", "TEN", "TENNIS", "ALL", "WNBA", "NCAAF", "NCAAB",
            "EPL", "MLS", "BUNDESLIGA", "LALIGA", "SERIEA"
        }

        if is_sports:
            sim_prob = float(features.get("ai_win_prob", 50.0))
            sim_edge = float(features.get("ai_edge", 0.0))
            conf = float(features.get("confidence_score", 50.0))
            ask = float(features.get("market_ask", 0.50))

            diagnosis = f"Sports match outcome reversed against {side} pick bias."
            if ask > 0.72:
                diagnosis = f"Public heavy favorite priced at ${ask:.2f} suffered upset loss; risk-reward ratio failed to clear juice."
            elif sim_edge < 2.0:
                diagnosis = f"Entry had marginal model edge ({sim_edge:+.1f}%) insufficient to clear Kalshi taker fee friction."
            elif conf < 58.0:
                diagnosis = f"Low model simulation confidence ({conf:.1f}%) led to high-variance match settlement loss."

            regime_ctx = {"sim_prob": sim_prob, "sim_edge": sim_edge, "conf": conf, "ask": ask, "side": side}
        else:
            rsi = float(features.get("rsi") or 50.0)
            atr = float(features.get("atr") or 0.0)
            cvd = float(features.get("cvd") or 0.0)

            diagnosis = "Market reversed against prediction bias prior to contract expiration."
            if side == "YES" and rsi > 68:
                diagnosis = f"Bullish entry at overbought RSI ({rsi:.1f}) encountered instant exhaustion reversal."
            elif side == "NO" and rsi < 32:
                diagnosis = f"Bearish entry at oversold RSI ({rsi:.1f}) encountered instant bounce reversal."
            elif atr > 0 and atr < 35:
                diagnosis = f"Low ATR volatility (${atr:.1f}) caused directionless chop and pin failure."
            elif (side == "YES" and cvd < -1.5) or (side == "NO" and cvd > 1.5):
                diagnosis = f"Entry side ({side}) contradicted orderbook CVD volume pressure ({cvd:+.1f})."

            regime_ctx = {"rsi": rsi, "atr": atr, "cvd": cvd, "side": side}

        negative_rule = f"In {asset}, avoid {side} entries when: {diagnosis}"

        entry_id = StrategyGraveyard.record_failure(
            strategy_id=strategy_id,
            name=name,
            hypothesis=hypothesis,
            asset=asset,
            failure_stage="INCUBATION_DRAWDOWN",
            post_mortem_summary=diagnosis,
            negative_rule=negative_rule,
            code_hash=code_hash,
            metrics_snapshot=trade_data.get("metrics"),
            regime_context=regime_ctx
        )

        logger.info(f"[PostMortemAuditor] Incubation loss logged to Graveyard #{entry_id} for {name}")
        return entry_id

    @staticmethod
    def _synthesize_negative_rule(hypothesis: str, failure_reason: str, asset: str) -> str:
        # Insufficient sample frequency is a calibration issue, not an inherently flawed hypothesis.
        # Do not blacklist the alpha concept with an 'Avoid archetype' rule.
        if "INSUFFICIENT_SIGNALS" in str(failure_reason).upper():
            return f"Loosen overly restrictive filter thresholds on {asset}: strategy generated {failure_reason}; widen corridors and reduce multi-condition gates."

        h_lower = hypothesis.lower()
        is_sports = str(asset).upper() in {
            "SPORTS", "SPORT", "NFL", "MLB", "NBA", "NHL", "NPB", "KBO", "NPB/KBO", "NPB_KBO", "NPB-KBO",
            "SOC", "SOCCER", "UFC", "MMA", "TEN", "TENNIS", "ALL", "WNBA", "NCAAF", "NCAAB",
            "EPL", "MLS", "BUNDESLIGA", "LALIGA", "SERIEA"
        }

        if is_sports:
            if "favorite" in h_lower or "fade" in h_lower:
                return f"Do not fade public favorites on {asset} unless model edge exceeds 5.0% and consensus odds offer >= 35c reward."
            elif "rest" in h_lower or "situational" in h_lower:
                return f"Do not rely solely on rest days on {asset} without verifying starting lineup and weather confirmation."
            elif "edge" in h_lower:
                return f"Require a minimum simulated edge of 4.5% on {asset} to overcome Kalshi market friction and slippage."
            else:
                return f"Avoid sports hypothesis archetype '{hypothesis[:60]}...' on {asset} due to {failure_reason}."

        if "rsi" in h_lower and "overbought" in h_lower:
            return f"Do not rely solely on overbought RSI fade without confirming CVD orderbook divergence on {asset} 15M."
        elif "rsi" in h_lower and "oversold" in h_lower:
            return f"Do not buy oversold RSI dips on {asset} 15M when ATR volatility is below 40 or during low-volume sessions."
        elif "breakout" in h_lower or "momentum" in h_lower:
            return f"Do not trigger momentum breakouts on {asset} without a minimum ATR expansion (>45) and fee hurdle buffer."
        elif "bollinger" in h_lower:
            return f"Avoid Bollinger expansion entries on {asset} during range-bound chop with tight spreads."
        else:
            return f"Avoid hypothesis archetype '{hypothesis[:60]}...' on {asset} due to {failure_reason}."
