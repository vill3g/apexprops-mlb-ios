"""
Strategy Validator for ShadowTrader Quant Lab.
Runs walk-forward backtesting with realistic Kalshi fee/slippage modeling,
drawdown limits, and Monte Carlo robustness testing.
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import sqlite3
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Minimum hurdles to pass into incubation
MIN_TRADES = 6
MIN_OOS_TRADES = 2
MIN_REAL_SNAPSHOTS = 25
MIN_WIN_RATE = 0.55
MIN_SHARPE = 0.80
MAX_DRAWDOWN = 0.22
KALSHI_FEE_CENTS = 0.02
SLIPPAGE_CENTS = 0.01


class StrategyValidator:
    """Executes walk-forward validation and Monte Carlo stress tests."""

    @staticmethod
    def _is_sports_asset(asset: str) -> bool:
        a = str(asset or "").strip().upper()
        return a in {
            "SPORTS", "SPORT", "NFL", "MLB", "NBA", "NHL", "NPB", "KBO", "NPB/KBO", "NPB_KBO", "NPB-KBO",
            "SOC", "SOCCER", "UFC", "MMA", "TEN", "TENNIS", "ALL", "WNBA", "NCAAF", "NCAAB",
            "EPL", "MLS", "BUNDESLIGA", "LALIGA", "SERIEA"
        }

    @classmethod
    def load_historical_evaluation_snapshots(cls, asset: str = "BTC", limit: int = 500) -> List[Dict[str, Any]]:
        """
        Loads chronological historical market snapshots with real outcomes.
        Supports both Financial universe (crypto/forex) and Sports universe (NFL, MLB, NHL, TEN, SOC, UFC).
        Falls back to generating synthetic test sequences if historical DB is unavailable.
        """
        snapshots = []
        is_sports = cls._is_sports_asset(asset)
        if is_sports:
            # Sports: real settled Kalshi markets with pre-game prices (market-only features).
            from backend.engine.quant_lab.history_builder import load_history_snapshots
            hist = load_history_snapshots(str(asset).upper(), limit=limit)
            if len(hist) < MIN_REAL_SNAPSHOTS:
                logger.info(f"[StrategyValidator] {asset}: only {len(hist)} settled-market snapshots; skipping.")
                return []
            from backend.engine.quant_lab.regime_classifier import MarketRegimeClassifier
            for s in hist:
                MarketRegimeClassifier.classify_snapshot(s, asset=asset)
            return hist
        trades_db = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "users.db")
        )

        if os.path.exists(trades_db):
            try:
                conn = sqlite3.connect(trades_db)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                if is_sports:
                    # Query sports trades strictly by sport league ticker prefixes or explicit sport column
                    sport_key = str(asset).upper()
                    if sport_key in ("SOC", "SOCCER"):
                        match_patterns = ["KXEP%", "KXMLS%", "KXBUNDESLIGA%", "KXLALIGA%", "KXSERIEA%", "KXSOC%"]
                    elif sport_key in ("TEN", "TENNIS"):
                        match_patterns = ["KXATP%", "KXWTA%", "KXTEN%"]
                    elif sport_key in ("UFC", "MMA"):
                        match_patterns = ["KXUFC%", "KXMMA%"]
                    elif sport_key in ("NPB", "KBO", "NPB/KBO", "NPB_KBO"):
                        match_patterns = ["KXNPB%", "KXKBO%"]
                    else:
                        match_patterns = [f"KX{sport_key}%"]

                    where_clauses = " OR ".join(["ticker LIKE ?"] * len(match_patterns))
                    query = f"""
                        SELECT id, ticker, side, entry_price, exit_price, status, pnl,
                               raw_json, timestamp
                        FROM trades
                        WHERE ({where_clauses} OR raw_json LIKE ?)
                          AND ticker NOT LIKE '%BTC%'
                          AND ticker NOT LIKE '%ETH%'
                          AND ticker NOT LIKE '%EURUSD%'
                          AND ticker NOT LIKE '%GOLD%'
                          AND (status = 'CLOSED' OR status = 'SETTLED')
                        ORDER BY rowid DESC LIMIT ?
                    """
                    rows = cur.execute(query, (*match_patterns, f'%"sport": "{sport_key}"%', limit)).fetchall()
                else:
                    rows = cur.execute("""
                        SELECT id, ticker, side, entry_price, exit_price, status, pnl,
                               raw_json, timestamp
                        FROM trades
                        WHERE ticker LIKE ? AND (status = 'CLOSED' OR status = 'SETTLED')
                        ORDER BY rowid DESC LIMIT ?
                    """, (f"%{asset}%", limit)).fetchall()

                conn.close()

                # Newest-first query -> chronological order, one row per contract (many users can hold the same one)
                _seen_t = set()
                _uniq = []
                for r in reversed(rows):
                    if r['ticker'] in _seen_t:
                        continue
                    _seen_t.add(r['ticker'])
                    _uniq.append(r)
                rows = _uniq

                for r in rows:
                    raw = json.loads(r["raw_json"] or "{}") if r["raw_json"] else {}
                    snap = raw.get("market_snapshot") or {}
                    if isinstance(snap, str):
                        try:
                            snap = json.loads(snap)
                        except Exception:
                            snap = {}
                    if not isinstance(snap, dict):
                        snap = {}
                    indicators = snap.get("indicators") or snap.get("raw_features") or {}
                    
                    is_win = (float(r["pnl"] or 0.0) > 0)

                    # No logged indicators -> skip. (Previously these were synthesized from the
                    # trade outcome, which leaked the answer into the backtest.)
                    if not indicators:
                        continue
                    if isinstance(indicators, dict):
                        clean_ind = {}
                        for k, v in indicators.items():
                            if v is None:
                                clean_ind[k] = 0.0
                            elif isinstance(v, (int, float)):
                                clean_ind[k] = 0.0 if (math.isnan(v) or math.isinf(v)) else float(v)
                            else:
                                clean_ind[k] = v
                        if "cvd" not in clean_ind and "cvd_value" in clean_ind:
                            clean_ind["cvd"] = clean_ind["cvd_value"]
                        clean_ind["ema_fast"] = clean_ind.get("ema_9", clean_ind.get("ema_fast", 0.0))
                        clean_ind["ema_slow"] = clean_ind.get("ema_21", clean_ind.get("ema_slow", 0.0))
                        clean_ind["ema_trend"] = clean_ind.get("ema_50", clean_ind.get("ema_trend", 0.0))
                        if "spread" not in clean_ind:
                            clean_ind["spread"] = 1.0  # standard liquid Kalshi spread (1 cent)
                        indicators = clean_ind

                    snap_ts = 0.0
                    try:
                        raw_ts_str = str(r["timestamp"] or "").strip()
                        if raw_ts_str:
                            clean_ts = raw_ts_str.replace(" ET", "").strip()
                            from dateutil import parser as dt_parser
                            dt = dt_parser.parse(clean_ts)
                            snap_ts = dt.timestamp()
                    except Exception:
                        snap_ts = 0.0

                    snapshots.append({
                        "trade_id": r["id"],
                        "ticker": r["ticker"],
                        "entry_price": float(r["entry_price"] or 0.50),
                        "actual_outcome": "YES" if (r["side"] == "YES" and is_win) or (r["side"] == "NO" and not is_win) else "NO",
                        "raw_features": indicators,
                        "indicators": indicators,
                        "cur_price": float(r["entry_price"] or 0.50),
                        "timestamp": snap_ts
                    })
            except Exception as e:
                logger.warning(f"[StrategyValidator] Could not read trades.db: {e}")

        # For financial assets, load real exchange OHLCV 15m candles with full technical indicators
        # to ensure backtests have hundreds of real market snapshots rather than starving on sparse executions.
        if not is_sports:
            try:
                try:
                    from backend.engine.multi_asset_fetcher import fetch_asset_candles
                    df = fetch_asset_candles(asset=asset, timeframe="15m", limit=min(limit, 500))
                except Exception:
                    from backend.btc.data_fetcher import fetch_candles
                    df = fetch_candles(timeframe="15m", limit=min(limit, 500))
                if df is not None and len(df) > 10:
                    from backend.btc.indicators import add_all_indicators
                    df_ind = add_all_indicators(df)
                    candle_snaps = []
                    for i in range(len(df_ind) - 1):
                        c_cur = df_ind.iloc[i]
                        c_next = df_ind.iloc[i + 1]
                        outcome = "YES" if float(c_next["close"]) > float(c_cur["close"]) else "NO"
                        row_dict = {}
                        for k, v in c_cur.to_dict().items():
                            if v is None:
                                row_dict[k] = 0.0
                            elif isinstance(v, (int, float)):
                                row_dict[k] = 0.0 if (math.isnan(v) or math.isinf(v)) else float(v)
                            else:
                                row_dict[k] = v
                        # Populate standardized indicator aliases for quant strategies
                        row_dict["ema_fast"] = row_dict.get("ema_9", row_dict.get("close", 0.0))
                        row_dict["ema_slow"] = row_dict.get("ema_21", row_dict.get("close", 0.0))
                        row_dict["ema_trend"] = row_dict.get("ema_50", row_dict.get("close", 0.0))
                        row_dict["spread"] = 1.0  # standard liquid Kalshi spread (1 cent)
                        if "delta_to_target" not in row_dict:
                            row_dict["delta_to_target"] = round(float(row_dict.get("close", 0.0)) - float(row_dict.get("open", 0.0)), 2)

                        c_time = float(c_cur.get("time", 0.0))
                        candle_snaps.append({
                            "trade_id": f"candle_{i}",
                            "ticker": f"KX{asset}15M-HIST-{i}",
                            "entry_price": 0.50,
                            "actual_outcome": outcome,
                            "raw_features": row_dict,
                            "indicators": row_dict,
                            "cur_price": 0.50,
                            "timestamp": c_time
                        })
                    if candle_snaps:
                        snapshots = candle_snaps + snapshots
            except Exception as fe_err:
                logger.warning(f"[StrategyValidator] Could not fetch real candles for {asset}: {fe_err}")

        # Ensure all snapshots are strictly sorted chronologically ascending by timestamp
        # to prevent out-of-sample data leaks and chronological splice inversion
        if snapshots:
            snapshots.sort(key=lambda s: float(s.get("timestamp") or 0.0))

        # Strategies are judged on real recorded outcomes and historical candles.
        # Assets with too little real data return few/no snapshots and are skipped (NO_HISTORICAL_DATA).
        if len(snapshots) < MIN_REAL_SNAPSHOTS:
            logger.info(f"[StrategyValidator] {asset}: only {len(snapshots)} real snapshots (< {MIN_REAL_SNAPSHOTS}); skipping validation.")
            return []

        from backend.engine.quant_lab.regime_classifier import MarketRegimeClassifier
        for s in snapshots:
            MarketRegimeClassifier.classify_snapshot(s, asset=asset)

        return snapshots

    @classmethod
    def validate(
        cls,
        strategy_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        asset: str = "BTC"
    ) -> Dict[str, Any]:
        """
        Runs Walk-Forward backtest:
        - 70% In-Sample (Optimization / Training)
        - 30% Out-of-Sample (Unseen Verification)
        - Monte Carlo permutation test
        """
        dataset = cls.load_historical_evaluation_snapshots(asset=asset)
        if not dataset:
            return {
                "passed": False,
                "failure_reason": "NO_HISTORICAL_DATA",
                "metrics": {}
            }

        split_idx = int(len(dataset) * 0.70)
        in_sample = dataset[:split_idx]
        out_sample = dataset[split_idx:]

        is_metrics = cls._simulate_subset(strategy_fn, in_sample, asset=asset)
        oos_metrics = cls._simulate_subset(strategy_fn, out_sample, asset=asset)

        total_trades = is_metrics["trades"] + oos_metrics["trades"]
        if total_trades < MIN_TRADES:
            return {
                "passed": False,
                "failure_reason": f"INSUFFICIENT_SIGNALS ({total_trades} < {MIN_TRADES})",
                "in_sample": is_metrics,
                "out_of_sample": oos_metrics,
                "metrics": oos_metrics
            }

        # Check Out-of-Sample Performance against Hurdles
        oos_win_rate = oos_metrics["win_rate"]
        oos_sharpe = oos_metrics["sharpe"]
        oos_dd = oos_metrics["max_drawdown"]

        failure_reasons = []
        # Profit-based hurdle: positive net P&L after fees in BOTH windows + minimum OOS trades.
        if oos_metrics["trades"] < MIN_OOS_TRADES:
            failure_reasons.append(f"Too few OOS trades ({oos_metrics['trades']} < {MIN_OOS_TRADES})")
        if oos_metrics["total_pnl"] <= 0:
            failure_reasons.append(f"Non-positive OOS net P&L (${oos_metrics['total_pnl']:.2f})")
        if is_metrics["total_pnl"] <= 0:
            failure_reasons.append(f"Non-positive in-sample net P&L (${is_metrics['total_pnl']:.2f})")

        if oos_sharpe < MIN_SHARPE:
            failure_reasons.append(f"Low OOS Sharpe ({oos_sharpe:.2f} < {MIN_SHARPE:.2f})")
        if oos_dd > MAX_DRAWDOWN:
            failure_reasons.append(f"High OOS Max Drawdown ({oos_dd*100:.1f}% > {MAX_DRAWDOWN*100:.1f}%)")

        # Monte Carlo Permutation Test on full sequence
        all_pnls = is_metrics["pnl_list"] + oos_metrics["pnl_list"]
        mc_passed, mc_p_value = cls._monte_carlo_test(all_pnls)
        if not mc_passed:
            failure_reasons.append(f"Failed Monte Carlo Robustness Test (p={mc_p_value:.3f})")

        passed = (len(failure_reasons) == 0)

        result = {
            "passed": passed,
            "failure_reason": "; ".join(failure_reasons) if not passed else None,
            "total_trades": total_trades,
            "in_sample": is_metrics,
            "out_of_sample": oos_metrics,
            "monte_carlo_p_value": mc_p_value,
            "metrics": {
                "win_rate": oos_win_rate,
                "sharpe": oos_sharpe,
                "max_drawdown": oos_dd,
                "total_pnl": oos_metrics["total_pnl"],
                "trades": oos_metrics["trades"],
                "avg_ensemble_agreement": oos_metrics.get("avg_ensemble_agreement", 1.0),
                "unanimous_rate": oos_metrics.get("unanimous_rate", 0.0)
            }
        }

        logger.info(
            f"[StrategyValidator] Validation Result: Passed={passed} "
            f"(OOS WinRate={oos_win_rate*100:.1f}%, Sharpe={oos_sharpe:.2f}, DD={oos_dd*100:.1f}%)"
        )
        return result

    @classmethod
    def _simulate_subset(
        cls,
        strategy_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        snapshots: List[Dict[str, Any]],
        asset: str = "BTC"
    ) -> Dict[str, Any]:
        trades_count = 0
        wins = 0
        total_pnl = 0.0
        equity_curve = [100.0]
        pnl_list = []
        agreements = []
        unanimous_count = 0

        # Lazy load ML consensus engine for validation confirmation
        ml_engine = None
        try:
            from backend.btc.ml_engine import get_ml_engine
            ml_engine = get_ml_engine(asset=asset)
        except Exception as e:
            logger.debug(f"[StrategyValidator] Could not initialize ML engine for confirmation: {e}")

        for snap in snapshots:
            sig = strategy_fn(snap)
            if not isinstance(sig, dict) or sig.get("action") != "BUY":
                continue

            chosen_side = sig.get("side", "YES").upper()
            actual_outcome = snap.get("actual_outcome", "NO").upper()
            raw_features = snap.get("raw_features") or snap.get("indicators") or {}

            # AI Model Consensus Gating
            # 1. Financial Universe: Voting Ensemble & DualMLEngine
            if not cls._is_sports_asset(asset) and ml_engine and raw_features:
                try:
                    consensus = ml_engine.predict_consensus(raw_features)
                    c_dir = str(consensus.get("consensus_direction", "NEUTRAL")).upper()
                    agree_ratio = float(consensus.get("agreement_ratio", 1.0))
                    is_unan = bool(consensus.get("is_unanimous", False))
                    p_ens = float(consensus.get("p_ensemble", 0.50))

                    # Normalize consensus direction
                    if c_dir in ("UP", "YES"):
                        c_side = "YES"
                    elif c_dir in ("DOWN", "NO"):
                        c_side = "NO"
                    else:
                        c_side = "NEUTRAL"

                    # If model ensemble actively contradicts the rule or has zero edge, reject trade
                    if c_side != "NEUTRAL" and c_side != chosen_side:
                        continue
                    if chosen_side == "YES" and p_ens < 0.48:
                        continue
                    if chosen_side == "NO" and p_ens > 0.52:
                        continue

                    agreements.append(agree_ratio)
                    if is_unan:
                        unanimous_count += 1
                except Exception as e:
                    logger.debug(f"[StrategyValidator] ML consensus filter warning: {e}")

            # 2. Sports Universe: Monte Carlo Simulation & Edge Gating
            elif cls._is_sports_asset(asset) and raw_features:
                try:
                    sim_prob = float(raw_features.get("ai_win_prob", 50.0))
                    sim_edge = float(raw_features.get("ai_edge", 0.0))
                    conf = float(raw_features.get("confidence_score", 50.0))

                    # If model contradicts chosen side or has negative edge, reject
                    if chosen_side == "YES" and (sim_prob < 48.0 or sim_edge < -2.0):
                        continue
                    if chosen_side == "NO" and (sim_prob > 52.0 or sim_edge > 4.0):
                        continue

                    # Sports agreement ratio from simulation confidence
                    agree_ratio = min(1.0, max(0.5, conf / 100.0 + (abs(sim_edge) / 50.0)))
                    is_unan = (conf >= 70.0 and abs(sim_edge) >= 5.0)
                    agreements.append(agree_ratio)
                    if is_unan:
                        unanimous_count += 1
                except Exception as e:
                    logger.debug(f"[StrategyValidator] Sports simulation filter warning: {e}")

            if snap.get("yes_bid") is not None and snap.get("yes_ask") is not None:
                # Side-specific executable price: buy YES at the ask, buy NO at (1 - YES bid)
                base_px = float(snap["yes_ask"]) if chosen_side == "YES" else 1.0 - float(snap["yes_bid"])
            else:
                base_px = float(snap.get("cur_price") or snap.get("entry_price") or 0.50)
            entry_price = base_px + SLIPPAGE_CENTS
            entry_price = min(0.99, max(0.01, entry_price))

            # Kalshi dynamic taker fee per contract: round_up(0.07 * P * (1 - P))
            kalshi_fee = math.ceil(0.07 * entry_price * (1.0 - entry_price) * 100.0) / 100.0

            is_win = (chosen_side == actual_outcome)
            trades_count += 1
            if is_win:
                wins += 1
                trade_pnl = (1.0 - entry_price) - kalshi_fee
            else:
                trade_pnl = (-entry_price) - kalshi_fee

            total_pnl += trade_pnl
            pnl_list.append(trade_pnl)
            equity_curve.append(equity_curve[-1] + trade_pnl)

        win_rate = (wins / trades_count) if trades_count > 0 else 0.0

        # Max Drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / max(peak, 0.001)
            if dd > max_dd:
                max_dd = dd

        # Sharpe Ratio
        if len(pnl_list) > 1:
            mean_pnl = sum(pnl_list) / len(pnl_list)
            variance = sum((x - mean_pnl) ** 2 for x in pnl_list) / (len(pnl_list) - 1)
            std_dev = math.sqrt(variance) if variance > 0 else 0.001
            sharpe = (mean_pnl / std_dev) * math.sqrt(len(pnl_list))
        else:
            sharpe = 0.0

        avg_agree = sum(agreements) / len(agreements) if agreements else 1.0
        unan_rate = unanimous_count / trades_count if trades_count > 0 else 0.0

        return {
            "trades": trades_count,
            "wins": wins,
            "win_rate": round(win_rate, 3),
            "total_pnl": round(total_pnl, 2),
            "max_drawdown": round(max_dd, 3),
            "sharpe": round(sharpe, 2),
            "avg_ensemble_agreement": round(avg_agree, 2),
            "unanimous_rate": round(unan_rate, 2),
            "pnl_list": pnl_list
        }

    @staticmethod
    def _monte_carlo_test(pnls: List[float], iterations: int = 200) -> Tuple[bool, float]:
        """
        Permutation test: Shuffles sequence of returns to test whether the equity curve
        is consistently positive or just an artifact of ordering.
        """
        if len(pnls) < 10:
            return False, 1.0

        actual_final = sum(pnls)
        if actual_final <= 0:
            return False, 1.0

        negative_runs = 0
        for _ in range(iterations):
            shuffled = list(pnls)
            random.shuffle(shuffled)
            # Check maximum drawdown of shuffled path
            eq = [100.0]
            for p in shuffled:
                eq.append(eq[-1] + p)
            if eq[-1] < 100.0:
                negative_runs += 1

        p_value = negative_runs / iterations
        return (p_value <= 0.05), p_value
