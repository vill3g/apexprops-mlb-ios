
import logging

logger = logging.getLogger(__name__)
import math
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    pass
import requests

from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract
from backend.btc.fees import kalshi_order_fee
from backend.btc.indicators import add_all_indicators, compute_atr
from backend.btc.kalshi_trader import filled_count as _filled_count
from backend.btc.kalshi_trader import kalshi_trader
from backend.btc.paper_balance import update_balance
from backend.btc.scalp_engine import scalp_engine
from backend.engine.multi_asset_fetcher import \
    fetch_asset_candles as fetch_candles
from backend.engine.multi_asset_fetcher import \
    get_asset_ticker as get_btc_ticker

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "trading_config.json")
from .shared import _history_lock


class StopManagerMixin:
        def _exit_open_trade(self, trade: Dict[str, Any], reason: str, estimated_exit_price: Optional[float] = None) -> Dict[str, Any]:
            """Close a recorded position at its current Kalshi bid.
    
            Paper trades use the same public bid as a simulated exit (or estimated_exit_price
            if off-hours/synthetic). Live trades submit a reduce-only IOC order, so a failed
            or unfilled order never changes the local trade record.
            """
            side = str(trade.get("side", "")).upper().strip()
            ticker = str(trade.get("ticker", "")).strip()
            try:
                count = float(trade.get("count", 0))
                entry_price = float(trade.get("entry_price", 0))
            except (TypeError, ValueError):
                return {"success": False, "error": "Trade has invalid price or contract count."}
            if side not in {"YES", "NO"} or not ticker or count <= 0:
                return {"success": False, "error": "Trade is missing a valid ticker, side, or contract count."}
    
            mode = str(trade.get("mode", self.mode)).upper()
            is_sim = str(trade.get("id", "")).startswith("sim_") or (mode == "PAPER")
            exit_res = kalshi_trader.close_position(
                ticker=ticker,
                purchased_side=side,
                count=count,
                dry_run=is_sim,
                estimated_exit_price=estimated_exit_price,
            )
            if not exit_res.get("success"):
                if exit_res.get("ambiguous"):
                    logger.error(
                        f"[AutoExecutor] CRITICAL: Position exit outcome ambiguous after timeout! "
                        f"Trade ID: '{trade.get('id')}', Ticker: '{ticker}', "
                        f"Client Order ID: '{exit_res.get('client_order_id')}'. "
                        f"Error: {exit_res.get('error')}. MANUAL VERIFICATION REQUIRED ON KALSHI."
                    )
                return exit_res
    
            filled_count = min(count, float(exit_res.get("filled_count") or 0))
            exit_price = float(exit_res.get("exit_price", 0) or 0)
            fee_paid = float(exit_res.get("fee_paid", 0) or 0)
            if filled_count <= 0 or not 0 < exit_price < 1:
                return {"success": False, "error": "Exit returned no valid fill; the trade remains open."}
            if fee_paid <= 0:
                # Paper fills and reconciled exits report no fee; use Kalshi's taker fee schedule
                fee_paid = kalshi_order_fee(exit_price, filled_count)
            entry_fee_share = kalshi_order_fee(entry_price, filled_count)
    
            previous_realized = float(trade.get("realized_pnl", 0) or 0)
            exit_pnl = round((exit_price - entry_price) * filled_count - fee_paid - entry_fee_share, 4)
            realized_pnl = round(previous_realized + exit_pnl, 4)
            remaining_count = max(0.0, round(count - filled_count, 4))
            closed_at = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
    
            trade["last_exit_price"] = exit_price
            trade["exit_fee_paid"] = round(float(trade.get("exit_fee_paid", 0) or 0) + fee_paid, 4)
            trade["exit_reason"] = reason
            trade["exit_source"] = exit_res.get("source", "kalshi_exit")
            trade["realized_pnl"] = realized_pnl
            trade["pnl"] = realized_pnl
            trade.setdefault("partial_exits", []).append({
                "time": closed_at,
                "count": filled_count,
                "price": exit_price,
                "fee_paid": fee_paid,
                "pnl": exit_pnl,
                "source": exit_res.get("source", "kalshi_exit"),
            })
    
            if mode == "PAPER":
                try:
                    update_balance(exit_price * filled_count - fee_paid, guest_id=getattr(self, '_guest_id', None))
                except Exception as ep:
                    logger.info(f"Failed to update paper balance: {ep}")
    
            if remaining_count <= 0:
                trade["status"] = "CLOSED"
                trade["result"] = "CLOSED_WIN" if realized_pnl > 0 else ("CLOSED_LOSS" if realized_pnl < 0 else "CLOSED_FLAT")
                trade["exit_price"] = exit_price
                trade["closed_at"] = closed_at
            else:
                trade["count"] = remaining_count
                trade["cost"] = round(entry_price * remaining_count, 4)
                trade["status"] = "OPEN"
                trade["result"] = "PARTIAL_EXIT"
    
            return {
                "success": True,
                "trade_id": trade.get("id"),
                "filled_count": filled_count,
                "remaining_count": remaining_count,
                "pnl": realized_pnl,
                "closed": remaining_count <= 0,
            }

        def close_specific_trade(self, trade_id: str, reason: str = "SCALP", estimated_exit_price: Optional[float] = None) -> Dict[str, Any]:
            """Close one tracked trade at its current contract bid."""
            with _history_lock:
                trades = self.get_trades_history()
                for trade in trades:
                    if trade.get("id") == trade_id and trade.get("status") == "OPEN":
                        result = self._exit_open_trade(trade, reason, estimated_exit_price=estimated_exit_price)
                        if not result.get("success"):
                            return result
                        self._save_trades_history(trades)
                        try:
                            with scalp_engine._trade_lock:
                                if hasattr(scalp_engine, "_active_positions") and trade_id in scalp_engine._active_positions:
                                    del scalp_engine._active_positions[trade_id]
                                if scalp_engine._active_trade and scalp_engine._active_trade.get("id") == trade_id:
                                    scalp_engine._active_trade.clear()
                        except Exception as e:
                            logger.warning(f"Swallowed exception: {e}")
                        return result
            return {"success": False, "error": f"Trade {trade_id} not found or not open"}

        def close_open_trades(self) -> Dict[str, Any]:
            """Close each open trade at its current contract bid.
    
            Unlike the prior implementation, live trades are only marked closed
            after their reduce-only Kalshi order receives a fill.
            """
            with _history_lock:
                trades = self.get_trades_history()
                open_trades = [trade for trade in trades if trade.get("status") == "OPEN"]
                if not open_trades:
                    return {"success": False, "error": "No open trades to close."}
    
                completed = 0
                partial = 0
                realized_pnl = 0.0
                failures = []
                for trade in open_trades:
                    # Dynamic realistic contract price estimation for paper/simulated fallback
                    strike = float(trade.get("strike", 0.0) or 0.0)
                    side = str(trade.get("side", "YES")).upper()
                    est_exit = None
                    if strike > 0:
                        try:
                            spot = float(get_btc_ticker(self.asset).get("price", 0.0))
                            if spot > 0:
                                diff = (spot - strike) if side == "YES" else (strike - spot)
                                prob = 1.0 / (1.0 + math.exp(-diff / 150.0))
                                est_exit = round(max(0.10, min(0.90, prob)), 2)  # Kalshi only quotes/fills in whole cents
                        except Exception as e:
                            logger.warning(f"Swallowed exception: {e}")
    
                    result = self._exit_open_trade(trade, "MANUAL_CLOSE", estimated_exit_price=est_exit)
                    if not result.get("success"):
                        failures.append({"trade_id": trade.get("id"), "error": result.get("error", "Close failed.")})
                        continue
                    realized_pnl += float(result.get("pnl", 0) or 0)
                    if result.get("closed"):
                        completed += 1
                    else:
                        partial += 1
    
                if completed or partial:
                    self._save_trades_history(trades)
    
            message = f"Closed {completed} position(s)"
            if partial:
                message += f"; {partial} partially filled"
            if failures:
                message += f"; {len(failures)} left open"
            return {
                "success": bool(completed or partial),
                "closed_count": completed,
                "partial_count": partial,
                "realized_pnl": round(realized_pnl, 2),
                "failures": failures,
                "message": f"{message} (realized P&L: ${realized_pnl:+.2f})",
            }

        def check_active_trades_stop_and_reversal(self) -> None:
            """
            Evaluates all open positions for:
            Option 1: Dynamic Early Stop-Loss (Bailout Guard)
              - If spot BTC moves against the strike target by >= stopLossMoveDollars within stopLossMaxMinutes,
                immediately exit early at executable market bid to rescue remaining contract capital.
            Option 2: Position Reversal (Selective Flip)
              - If stopped out and positionReversal is enabled, selectively enter the opposite contract
                if time remaining >= reversalMinMinutesLeft, opposite ask <= reversalMaxPriceCents,
                and confidence >= reversalMinConfidence.
            """
            dynamic_stop_enabled = bool(self.ai_settings.get("dynamic_stop_loss", self.ai_settings.get("dynamicStopLoss", True)))
            position_reversal_enabled = bool(self.ai_settings.get("position_reversal", self.ai_settings.get("positionReversal", False)))
            take_profit_enabled = bool(self.ai_settings.get("take_profit_enabled", self.ai_settings.get("takeProfitEnabled", True)))
            take_profit_percent = float(self.ai_settings.get("take_profit_pct", self.ai_settings.get("takeProfitPercent", 50.0)))

            if not dynamic_stop_enabled and not position_reversal_enabled and not take_profit_enabled:
                return
    
            trades = self.get_trades_history()
            open_trades = [t for t in trades if t.get("status") == "OPEN"]
            if not open_trades:
                return
    
            try:
                ticker_data = get_btc_ticker(self.asset)
                spot_price = float(ticker_data.get("price", 0.0) or 0.0)
            except (requests.exceptions.RequestException, ValueError, TypeError) as te:
                logger.debug(f"[AutoExecutor] Could not fetch spot price for stop/reversal check: {te}")
                return
    
            if spot_price <= 0:
                return
    
            stop_loss_move = float(self.ai_settings.get("stopLossMoveDollars", 140.0))
            atr_multiplier = float(self.ai_settings.get("atrStopMultiplier", 0.75))
            ema_21_val = 0.0
            cvd_val = 0.0
            try:
                # Fetch more candles to ensure EMA-21 calculation is valid
                recent_candles = fetch_candles(self.asset, timeframe="15m", limit=80)
                if recent_candles is not None and len(recent_candles) >= 30:
                    df_ind = add_all_indicators(recent_candles)
                    atr_val = float(df_ind["atr"].iloc[-1])
                    ema_21_val = float(df_ind["ema_21"].iloc[-1])
                    cvd_val = float(df_ind["cvd"].iloc[-1]) if "cvd" in df_ind.columns else 0.0
                    if atr_val > 0:
                        stop_loss_move = max(stop_loss_move, atr_val * atr_multiplier)
            except Exception as e:
                logger.warning(f"[AutoExecutor] Failed to compute dynamic stop indicators: {e}")
            stop_loss_max_minutes = float(self.ai_settings.get("stopLossMaxMinutes", 8.0))
            reversal_max_price = float(self.ai_settings.get("reversalMaxPriceCents", 65.0)) / 100.0
            reversal_min_minutes = float(self.ai_settings.get("reversalMinMinutesLeft", 6.0))
            reversal_min_conf = float(self.ai_settings.get("reversalMinConfidence", 75.0))
    
            now = time.time()
            for trade in open_trades:
                trade_id = trade.get("id")
                if not trade_id:
                    continue
                side = str(trade.get("side", "")).upper()
                strike = float(trade.get("strike", 0.0) or 0.0)
                entry_price = float(trade.get("entry_price", 0.50))
                btc_entry = float(trade.get("btc_price_at_entry") or trade.get("market_snapshot", {}).get("price") or spot_price)
                close_epoch = float(trade.get("close_epoch", 0.0))
    
                if close_epoch > 0:
                    time_remaining_sec = max(0.0, close_epoch - now)
                    time_elapsed_sec = max(0.0, 900.0 - time_remaining_sec)
                else:
                    time_remaining_sec = 900.0
                    time_elapsed_sec = 0.0
    
                minutes_elapsed = time_elapsed_sec / 60.0
                minutes_remaining = time_remaining_sec / 60.0
    
                if minutes_remaining >= 1.0:
                    ticker = trade.get("ticker")
                    bid_price = 0.0
                    if ticker and not ticker.endswith("_SYNTH") and self.mode == "LIVE":
                        try:
                            quote = kalshi_trader.get_market_quote(ticker)
                            if quote.get("success"):
                                bid_price = float(quote.get("yes_bid", 0.0)) if side == "YES" else float(quote.get("no_bid", 0.0))
                        except Exception as e:
                            logger.warning(f"[AutoExecutor] Take profit quote fetch failed: {e}")
                    elif self.mode == "PAPER":
                        # Paper trading: Use live Kalshi public orderbook if available, or realistic spot-based delta model
                        if ticker and not ticker.endswith("_SYNTH"):
                            try:
                                quote = kalshi_trader.get_market_quote(ticker)
                                if quote.get("success"):
                                    bid_price = float(quote.get("yes_bid", 0.0)) if side == "YES" else float(quote.get("no_bid", 0.0))
                            except Exception:
                                pass
                        if bid_price <= 0.0 and strike > 0:
                            diff = (spot_price - strike) if side == "YES" else (strike - spot_price)
                            prob = 1.0 / (1.0 + math.exp(-diff / 150.0))
                            bid_price = round(max(0.05, min(0.95, prob)), 2)  # Kalshi only quotes/fills in whole cents
    
                    if entry_price > 0 and bid_price > 0:
                        try:
                            profit_pct = ((bid_price - entry_price) / entry_price) * 100.0
                            
                            # Track Max Seen Bid for Trailing Stop
                            max_seen_bid = float(trade.get("max_seen_bid", entry_price))
                            min_seen_bid = float(trade.get("min_seen_bid", entry_price))
                            changed_max = False
                            changed_min = False
                            if bid_price > max_seen_bid:
                                max_seen_bid = bid_price
                                changed_max = True
                            if bid_price > 0 and bid_price < min_seen_bid:
                                min_seen_bid = bid_price
                                changed_min = True

                            if changed_max or changed_min:
                                # C1 FIX: Do NOT save the detached snapshot. Re-fetch fresh data under lock.
                                with _history_lock:
                                    fresh_trades = self.get_trades_history()
                                    for ft in fresh_trades:
                                        if ft.get("id") == trade_id:
                                            if changed_max:
                                                ft["max_seen_bid"] = bid_price
                                            if changed_min:
                                                ft["min_seen_bid"] = bid_price
                                            break
                                    self._save_trades_history(fresh_trades)
                                if changed_max:
                                    trade["max_seen_bid"] = bid_price
                                if changed_min:
                                    trade["min_seen_bid"] = bid_price
    
                            max_seen_profit_pct = ((max_seen_bid - entry_price) / entry_price) * 100.0
    
                            # 1. Hard Take-Profit Check
                            if take_profit_enabled and profit_pct >= take_profit_percent:
                                logger.info(
                                    f"[AutoExecutor] TAKE-PROFIT TRIGGERED for {trade_id} ({side}): "
                                    f"Current bid ${bid_price:.2f} is up {profit_pct:.1f}% from entry ${entry_price:.2f} "
                                    f"(Target: {take_profit_percent}%)."
                                )
                                close_res = self.close_specific_trade(trade_id, reason="TAKE_PROFIT", estimated_exit_price=bid_price)
                                if close_res.get("success"):
                                    logger.info(f"[AutoExecutor] Take profit executed for {trade_id}; realized P&L ${close_res.get('pnl', 0):.2f}")
                                    self._attempt_profit_reentry(trade, minutes_remaining, spot_price)
                                    continue
    
                            # 2. Dynamic Trailing Profit Stop (Locks in gains if they drop from peak)
                            ts_enabled = bool(self.ai_settings.get("trailing_stop_enabled", False))
                            ts_activation = float(self.ai_settings.get("trailing_stop_activation_pct", 35.0))
                            ts_distance = float(self.ai_settings.get("trailing_stop_distance_pct", 6.0)) / 100.0
                            
                            if ts_enabled and max_seen_profit_pct >= ts_activation:
                                # We trail the max seen bid by the configured distance (cents or percentage, whichever tightens first)
                                trail_threshold = max(max_seen_bid - ts_distance, max_seen_bid * (1.0 - ts_distance))
                                
                                # Ensure we don't accidentally trail into a loss (secure at least a small profit)
                                trail_threshold = max(trail_threshold, entry_price * 1.02)
    
                                if bid_price <= trail_threshold:
                                    logger.info(
                                        f"[AutoExecutor] DYNAMIC TRAILING PROFIT TRIGGERED for {trade_id} ({side}): "
                                        f"Max bid was ${max_seen_bid:.2f} (+{max_seen_profit_pct:.1f}%), now dropped to ${bid_price:.2f}. Securing gains."
                                    )
                                    close_res = self.close_specific_trade(trade_id, reason="TRAILING_TAKE_PROFIT", estimated_exit_price=bid_price)
                                    if close_res.get("success"):
                                        logger.info(f"[AutoExecutor] Trailing profit executed for {trade_id}; realized P&L ${close_res.get('pnl', 0):.2f}")
                                        self._attempt_profit_reentry(trade, minutes_remaining, spot_price)
                                        continue
                                        
                            # 3. Contract Price Stop Loss
                            stop_loss_pct = float(self.ai_settings.get("stop_loss_pct", self.ai_settings.get("stopLossPercent", 50.0)))
                            sl_enabled = bool(self.ai_settings.get("stop_loss_enabled", self.ai_settings.get("stopLossEnabled", 1)))
                            if sl_enabled and profit_pct <= -stop_loss_pct:
                                logger.info(
                                    f"[AutoExecutor] CONTRACT STOP-LOSS TRIGGERED for {trade_id} ({side}): "
                                    f"Current bid ${bid_price:.2f} is down {abs(profit_pct):.1f}% from entry ${entry_price:.2f} "
                                    f"(Target: {stop_loss_pct}%)."
                                )
                                close_res = self.close_specific_trade(trade_id, reason="CONTRACT_STOP_LOSS", estimated_exit_price=bid_price)
                                if close_res.get("success"):
                                    logger.info(f"[AutoExecutor] Contract stop loss executed for {trade_id}; realized P&L ${close_res.get('pnl', 0):.2f}")
                                    if bool(self.ai_settings.get("reentryAfterStopLoss", False)) or bool(self.ai_settings.get("reentry_after_stop_loss", False)):
                                        self._attempt_profit_reentry(trade, minutes_remaining, spot_price, is_stop_loss=True)
                                    continue
                        except Exception as e:
                            logger.warning(f"[AutoExecutor] Take profit check failed: {e}")
    
                if dynamic_stop_enabled:
                    # Pillar 5: Structural Spot Invalidation Stop-Loss
                    # Eliminates whipsaw bleeding by preventing exits on momentary synthetic bid noise.
                    is_adverse = False
                    deficit = 0.0
                    invalidation_reason = ""

                    if strike > 0:
                        if side == "YES" and spot_price < strike:
                            deficit = strike - spot_price
                        elif side == "NO" and spot_price >= strike:
                            deficit = spot_price - strike
                    
                    # Check 1: Late-candle terminal divergence
                    if minutes_remaining < 2.0 and deficit > 35.0:
                        is_adverse = True
                        invalidation_reason = f"Terminal Deficit: {minutes_remaining:.1f}m left and spot is ${deficit:.2f} away from strike."
                    
                    # Check 2: Early structural breakdown (Requires EMA-21 break AND volume expansion)
                    elif minutes_remaining >= 2.0 and ema_21_val > 0:
                        if side == "YES" and spot_price < ema_21_val and cvd_val < -10.0:
                            is_adverse = True
                            invalidation_reason = f"Structural Breakdown: Spot ${spot_price:,.2f} crossed under 15m EMA-21 (${ema_21_val:,.2f}) with negative CVD."
                        elif side == "NO" and spot_price > ema_21_val and cvd_val > 10.0:
                            is_adverse = True
                            invalidation_reason = f"Structural Breakdown: Spot ${spot_price:,.2f} crossed above 15m EMA-21 (${ema_21_val:,.2f}) with positive CVD."

                    if is_adverse:
                        logger.info(
                            f"[AutoExecutor] STRUCTURAL STOP-LOSS TRIGGERED for {trade_id} ({side}): "
                            f"{invalidation_reason} "
                            f"at {minutes_elapsed:.1f}m elapsed ({minutes_remaining:.1f}m left)."
                        )
                        # Realistic salvage exit price for simulation / paper fallback
                        est_exit = round(max(0.01, min(0.35, entry_price - 0.25)), 2)
                        close_res = self.close_specific_trade(trade_id, reason="DYNAMIC_STOP_LOSS", estimated_exit_price=est_exit)
                        if close_res.get("success"):
                            logger.info(f"[AutoExecutor] Structural stop executed for {trade_id}; realized P&L ${close_res.get('pnl', 0):.2f}")
                            if position_reversal_enabled and not trade.get("is_reversal"):
                                self._attempt_position_reversal(
                                    stopped_trade=trade,
                                    spot_price=spot_price,
                                    minutes_remaining=minutes_remaining,
                                    reversal_max_price=reversal_max_price,
                                    reversal_min_minutes=reversal_min_minutes,
                                    reversal_min_conf=reversal_min_conf
                                )
                            elif bool(self.ai_settings.get("reentryAfterStopLoss", False)) or bool(self.ai_settings.get("reentry_after_stop_loss", False)):
                                self._attempt_profit_reentry(trade, minutes_remaining, spot_price, is_stop_loss=True)

        def _attempt_position_reversal(
            self,
            stopped_trade: Dict[str, Any],
            spot_price: float,
            minutes_remaining: float,
            reversal_max_price: float,
            reversal_min_minutes: float,
            reversal_min_conf: float
        ) -> Optional[Dict[str, Any]]:
            """
            Executes a position reversal (flip) following an early stop-loss exit.
            Enforces strict safety guardrails:
            1. Time: minutes_remaining >= reversal_min_minutes.
            2. Single reversal per interval (no recursive flips).
            3. Price: opposite contract ask <= reversal_max_price (favorable risk/reward).
            4. Confidence: reversal direction confidence >= reversal_min_conf.
            """
            # Imported here: executor.py imports this mixin, so a module-level import would be circular.
            from .executor import normalize_prediction_direction
            stopped_side = str(stopped_trade.get("side", "")).upper()
            opposite_side = "NO" if stopped_side == "YES" else "YES"
            ticker = stopped_trade.get("ticker", "")
    
            # Guardrail 1: Time remaining
            if minutes_remaining < reversal_min_minutes:
                logger.info(
                    f"[AutoExecutor] Reversal rejected: {minutes_remaining:.1f}m remaining "
                    f"< min required {reversal_min_minutes:.1f}m."
                )
                return None
    
            # Guardrail 2: Max 1 reversal per interval
            interval_trades = self.get_trades_history()
            already_reversed = any(
                t.get("ticker") == ticker and t.get("is_reversal")
                for t in interval_trades
            )
            if already_reversed:
                logger.info(f"[AutoExecutor] Reversal rejected: Interval {ticker} already completed a reversal trade.")
                return None
    
            # Guardrail 3: Market quote on opposite contract
            opposite_ask = 0.50
            active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=(self.mode == "PAPER"))
            if active_m and (active_m.get("ticker") == ticker or not ticker):
                if opposite_side == "YES":
                    opposite_ask = float(active_m.get("yes_ask", 0.50) or 0.50)
                else:
                    opposite_ask = float(active_m.get("no_ask", 0.50) or 0.50)
    
            if opposite_ask > reversal_max_price:
                logger.info(
                    f"[AutoExecutor] Reversal rejected: Opposite {opposite_side} ask ${opposite_ask:.2f} "
                    f"> max allowed ${reversal_max_price:.2f}."
                )
                return None
    
            # Guardrail 4: Confidence & Directional Momentum
            # The model must (a) recommend the opposite direction and (b) clear the confidence bar.
            conf = None
            model_direction = None
            try:
                strike = float(stopped_trade.get("strike", 0.0) or (active_m.get("strike_price", 0.0) if active_m else 0.0))
                df_c = fetch_candles(self.asset, timeframe="15m", limit=30)
                if df_c is not None and not df_c.empty:
                    df_ind = add_all_indicators(df_c)
                    eval_res = evaluate_next_15m_contract(df_ind, target_price=strike, kalshi_m=active_m)
                    conf = float(eval_res.get("probability_percent", 0.0))
                    model_direction = normalize_prediction_direction(eval_res.get("recommendation", ""))
                # else: conf stays None â†’ rejected below
            except Exception as eg4:
                logger.warning(f"[AutoExecutor] Reversal Guardrail 4 evaluation failed: {eg4}")
                # conf stays None â†’ rejected below
    
            if conf is None:
                logger.info("[AutoExecutor] Reversal rejected: Could not evaluate momentum confidence (no candle data or error).")
                return None
    
            # normalize_prediction_direction maps YESâ†’ABOVE and NOâ†’BELOW; compute expected
            # from opposite_side the same way and compare.
            expected_direction = normalize_prediction_direction(opposite_side)
            if model_direction != expected_direction:
                logger.info(
                    f"[AutoExecutor] Reversal rejected: Model recommends {model_direction!r}, "
                    f"not the required opposite direction {expected_direction!r} (opposite of {stopped_side})."
                )
                return None
    
            if conf < reversal_min_conf:
                logger.info(
                    f"[AutoExecutor] Reversal rejected: Momentum confidence {conf:.1f}% "
                    f"< min required {reversal_min_conf:.1f}%."
                )
                return None
    
            # Guardrail 5: Risk Limit
            risk_blocked_reason = self.check_risk_budget()
            if risk_blocked_reason:
                logger.info(f"[AutoExecutor] Reversal rejected: {risk_blocked_reason}")
                return None
    
            # All guardrails passed! Place reversal order
            logger.info(
                f"[AutoExecutor] Executing POSITION REVERSAL: Flipping {stopped_side} -> {opposite_side} "
                f"on {ticker} @ ~${opposite_ask:.2f} ({minutes_remaining:.1f}m left, conf {conf:.1f}%)"
            )
    
            count = min(self.max_contracts, max(1, int(stopped_trade.get("count", 1))))
            dry_run = (self.mode == "PAPER") or bool(self.ai_settings.get("dryRun", False)) or (str(stopped_trade.get("mode", "")).upper() == "PAPER")
            trade_mode = "PAPER" if dry_run else "LIVE"
            try:
                order_res = kalshi_trader.place_order(
                    ticker=ticker,
                    side=opposite_side.lower(),
                    count=count,
                    limit_price_dollars=opposite_ask,
                    dry_run=dry_run
                )
                if order_res.get("success"):
                    # SaaS Broadcast (handled by saas multitenant)
                    # self._broadcast_trade_to_users(ticker, opposite_side.lower(), opposite_ask, {})
    
                    fill_price = float(order_res.get("filled_price", opposite_ask))
                    count = _filled_count(order_res, count)  # H1: record the real (possibly partial) fill
                    fill_cost = round(fill_price * count, 4)
                    fill_fee = kalshi_order_fee(fill_price, count)
                    reversal_record = {
                        "id": f"{'sim' if trade_mode == 'PAPER' else 'live'}_{uuid.uuid4().hex[:8]}",
                        "client_order_id": order_res.get("client_order_id") or order_res.get("order_id", str(uuid.uuid4())),
                        "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                        "interval_close_time": stopped_trade.get("interval_close_time"),
                        "close_epoch": stopped_trade.get("close_epoch"),
                        "ticker": ticker,
                        "title": f"Reversal Flip to {opposite_side}",
                        "market_snapshot": {
                            "price": spot_price,
                            "target": stopped_trade.get("strike", 0.0),
                            "confidence": conf,
                            "conviction_grade": "REVERSAL FLIP",
                            "primary_edge": f"Dynamic Reversal ({stopped_side} -> {opposite_side})"
                        },
                        "strike": stopped_trade.get("strike", 0.0),
                        "direction": opposite_side,
                        "recommendation": f"REVERSAL FLIP ({opposite_side})",
                        "conviction_grade": "REVERSAL FLIP",
                        "conviction_badge": f"ðŸ”„ REVERSAL ({int(conf)}%)",
                        "probability_percent": conf,
                        "trade_source": "SCALP",
                        "trading_style": "SCALP",
                        "side": opposite_side,
                        "entry_price": fill_price,
                        "count": count,
                        "cost": fill_cost,
                        "mode": trade_mode,
                        "status": "OPEN",
                        "result": "PENDING",
                        "pnl": 0.0,
                        "catalysts": [f"Early bailout stop on {stopped_side}; momentum reversed to {opposite_side}"],
                        "is_reversal": True,
                        "reversal_of": stopped_trade.get("id"),
                        "btc_price_at_entry": spot_price
                    }
                    with _history_lock:
                        trades_hist = self.get_trades_history()
                        trades_hist.append(reversal_record)
                        self._save_trades_history(trades_hist)
    
                    if trade_mode == "PAPER":
                        try:
                            update_balance(-(fill_cost + fill_fee), guest_id=getattr(self, '_guest_id', None))
                        except Exception as ep:
                            logger.warning(f"Failed to deduct paper balance for reversal: {ep}")
    
                    logger.info(f"[AutoExecutor] Successfully opened REVERSAL position {reversal_record['id']} ({opposite_side})")
                    return reversal_record
                else:
                    if order_res.get("ambiguous"):
                        logger.error(
                            f"[AutoExecutor] CRITICAL: Reversal order outcome ambiguous after timeout! "
                            f"Ticker: '{order_res.get('ticker', ticker)}', Client Order ID: '{order_res.get('client_order_id')}'. "
                            f"Error: {order_res.get('error')}. MANUAL VERIFICATION REQUIRED ON KALSHI."
                        )
                    else:
                        logger.error(f"[AutoExecutor] Reversal order placement failed: {order_res.get('error')}")
            except Exception as e:
                logger.error(f"[AutoExecutor] Exception executing reversal order: {e}", exc_info=True)
    
            return None

        def _attempt_profit_reentry(
            self,
            closed_trade: Dict[str, Any],
            minutes_remaining: float,
            spot_price: float,
            is_stop_loss: bool = False
        ) -> Optional[Dict[str, Any]]:
            """
            After securing a take-profit or getting stopped out (if re-entry enabled), evaluate
            if there is still enough time (>= 4.0 minutes) and conviction to enter a fresh contract.
            """
            if minutes_remaining < 0.25:
                logger.info(f"[AutoExecutor] Profit re-entry skipped: Only {minutes_remaining:.1f}m remaining in interval (< 15s minimum).")
                return None
    
            ticker = closed_trade.get("ticker", "")
            # Allow up to 2 re-entries per contract (3 total entries: initial + 2nd + 3rd entry) if time permits
            interval_trades = self.get_trades_history()
            reentry_count = sum(
                1 for t in interval_trades
                if t.get("ticker") == ticker and (
                    t.get("is_profit_reentry") or t.get("is_second_entry") or t.get("is_third_entry")
                )
            )
            max_reentries = int(self.ai_settings.get("maxProfitReentries", 2))
            if reentry_count >= max_reentries:
                logger.info(f"[AutoExecutor] Profit re-entry skipped: Interval {ticker} already reached max re-entries ({reentry_count}/{max_reentries}).")
                return None
    
            # Fetch active market and live analysis
            try:
    
                active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=(self.mode == "PAPER"), min_seconds_left=15)
                if not active_m:
                    logger.info("[AutoExecutor] Profit re-entry skipped: No active Kalshi contract found with >=15s remaining.")
                    return None
    
                strike = float(active_m.get("strike_price") or closed_trade.get("strike", 0.0))
                df_c = fetch_candles(self.asset, timeframe="15m", limit=60)
                if df_c is None or df_c.empty:
                    return None
    
                df_ind = add_all_indicators(df_c)
                forecast = evaluate_next_15m_contract(df_ind, target_price=strike, kalshi_m=active_m, trading_style=self.ai_settings.get("tradingStyle", "MOMENTUM_SURFER"), asset=self.asset)
    
                pred_dir = str(forecast.get("direction", "")).upper()
                if pred_dir == "PASS" or "PASS" in str(forecast.get("recommendation", "")):
                    # If Force Trade is enabled, check underlying pre-gate direction
                    if bool(self.ai_settings.get("ignorePass", False)):
                        pre_dir = str(forecast.get("pre_gate_direction", "")).upper()
                        if pre_dir in ["ABOVE", "YES", "UP"]:
                            direction = "ABOVE"
                            side = "yes"
                        elif pre_dir in ["BELOW", "NO", "DOWN"]:
                            direction = "BELOW"
                            side = "no"
                        else:
                            logger.info("[AutoExecutor] Profit re-entry: Setup is PASS even with Force Trade. Standing down.")
                            return None
                    else:
                        logger.info("[AutoExecutor] Profit re-entry: Fresh evaluation returned PASS. Preserving profits.")
                        return None
                elif pred_dir in ["ABOVE", "YES", "UP"]:
                    direction = "ABOVE"
                    side = "yes"
                else:
                    direction = "BELOW"
                    side = "no"
    
                conf = float(forecast.get("probability_percent", 50.0))

                closed_side = str(closed_trade.get("side", "")).lower()
                is_side_flipped = (side != closed_side)
                if not is_stop_loss and is_side_flipped:
                    logger.info(f"[AutoExecutor] Profit re-entry skipped: Model suggested {side.upper()} but original trade was {closed_side.upper()}. Only trend-aligned re-entries are permitted for take-profit exits.")
                    return None
                elif is_stop_loss and is_side_flipped:
                    logger.info(f"[AutoExecutor] Stop loss re-entry pivoted direction: original trade was {closed_side.upper()}, fresh model prediction is {side.upper()} ({conf:.1f}%). Entering {side.upper()}.")

                is_oversold_bounce = ("Absorption Hammer" in str(forecast.get("catalysts", [])) or "Oversold Spring" in str(forecast.get("catalysts", [])) or "Bullish Liquidity Sweep" in str(forecast.get("catalysts", [])))
                is_overbought_fade = ("Rejection Pin" in str(forecast.get("catalysts", [])) or "Overbought Exhaustion" in str(forecast.get("catalysts", [])) or "Bearish Liquidity Sweep" in str(forecast.get("catalysts", [])))

                last_candle = df_ind.iloc[-1]
                c_open = float(last_candle['open'])
                c_close = float(last_candle['close'])
                c_ema9 = float(last_candle.get("ema_9", c_close))
                c_ema21 = float(last_candle.get("ema_21", c_close))
                delta_strike = spot_price - strike
                
                chart_conflict = False
                if side == "no":
                    if ((delta_strike > 25.0 and (c_close > c_open) and (c_ema9 > c_ema21)) or (delta_strike > 40.0 and (c_close > c_open))) and not is_overbought_fade:
                        chart_conflict = True
                        logger.warning(f"[AutoExecutor] Re-entry chart conflict: Blocked NO entry because spot (${spot_price:.2f}) is ${delta_strike:.2f} above strike (${strike:.2f}) with green candle and EMA9 > EMA21.")
                elif side == "yes":
                    if ((delta_strike < -25.0 and (c_close < c_open) and (c_ema9 < c_ema21)) or (delta_strike < -40.0 and (c_close < c_open))) and not is_oversold_bounce:
                        chart_conflict = True
                        logger.warning(f"[AutoExecutor] Re-entry chart conflict: Blocked YES entry because spot (${spot_price:.2f}) is ${abs(delta_strike):.2f} below strike (${strike:.2f}) with red candle and EMA9 < EMA21.")
                    
                if chart_conflict:
                    if is_stop_loss:
                        side = "yes" if side == "no" else "no"
                        direction = "ABOVE" if side == "yes" else "BELOW"
                        min_conf = float(self.ai_settings.get("minConf", 60.0))
                        conf = max(60.0, min_conf)
                        is_side_flipped = (side != closed_side)
                        logger.warning(f"[AutoExecutor] Re-entry auto-pivot: Chart conflict detected on stop-loss. Auto-pivoting side to {side.upper()} to ride physical chart trend against ML advice (synthetic conf {conf}%).")
                    else:
                        return None

                min_conf = float(self.ai_settings.get("minConf", 60.0))
                if conf < min_conf and not bool(self.ai_settings.get("ignorePass", False)):
                    logger.info(f"[AutoExecutor] Profit re-entry: Model confidence {conf:.1f}% below minimum {min_conf}%. Standing down.")
                    return None
    
                # Check market price on chosen side
                market_price = float(active_m.get(f"{side}_ask", 0.50) or 0.50)
                max_reentry_ask = float(self.ai_settings.get("profitReentryMaxAsk", 0.75) or 0.75)
                if market_price >= max_reentry_ask:
                    logger.info(f"[AutoExecutor] Profit re-entry: {side.upper()} ask is ${market_price:.2f} >= ${max_reentry_ask:.2f} (too expensive/poor risk-reward). Standing down.")
                    return None

                last_exit_price = float(closed_trade.get("exit_price") or closed_trade.get("entry_price") or 0.50)
                if not is_stop_loss:
                    if market_price > (last_exit_price - 0.03):
                        logger.info(f"[AutoExecutor] Profit re-entry skipped: {side.upper()} ask ${market_price:.2f} has not pulled back >= 3Â¢ below scalp exit ${last_exit_price:.2f}")
                        return None
                else:
                    if not is_side_flipped:
                        initial_entry_price = float(closed_trade.get("entry_price") or 0.50)
                        if market_price > (initial_entry_price * 0.85):
                            logger.info(f"[AutoExecutor] Stop-loss DCA re-entry skipped: {side.upper()} ask ${market_price:.2f} is not discounted >= 15% from initial fill ${initial_entry_price:.2f}")
                            return None
    
                # Calculate contract count
                max_cap = float(self.ai_settings.get("maxCap", 0.0))
                unit_price_est = min(0.99, max(0.01, market_price + 0.04))
                if max_cap > 0:
                    contracts_to_buy = max(1, int(max_cap // unit_price_est))
                else:
                    contracts_to_buy = self.max_contracts
    
                dry_run = (self.mode == "PAPER") or bool(self.ai_settings.get("dryRun", False))
                trade_mode = "PAPER" if dry_run else "LIVE"
    
                risk_blocked_reason = self.check_risk_budget()
                if risk_blocked_reason:
                    logger.info(f"[AutoExecutor] Profit/Stop-Loss re-entry rejected: {risk_blocked_reason}")
                    return None

                reentry_label = f"POST-STOP-LOSS DIP RE-ENTRY #{reentry_count + 2}" if is_stop_loss else f"POST-TAKE-PROFIT RE-ENTRY #{reentry_count + 2}"
                logger.info(
                    f"[AutoExecutor] EXECUTING {reentry_label}: Buying {side.upper()} on {ticker} "
                    f"@ ${market_price:.2f} ({minutes_remaining:.1f}m left, Conf: {conf:.1f}%, Count: {contracts_to_buy})"
                )
    
                order_res = kalshi_trader.place_order(
                    ticker=ticker,
                    side=side,
                    count=contracts_to_buy,
                    limit_price_dollars=market_price,
                    dry_run=dry_run,
                    slippage_buffer_dollars=0.04
                )
    
                if order_res.get("success"):
                    # SaaS Broadcast (handled by saas multitenant)
                    # self._broadcast_trade_to_users(ticker, side, market_price, {})
    
                    fill_price = float(order_res.get("filled_price", market_price))
                    contracts_to_buy = _filled_count(order_res, contracts_to_buy)  # H1: record the real (possibly partial) fill
                    fill_cost = round(fill_price * contracts_to_buy, 4)
                    fill_fee = kalshi_order_fee(fill_price, contracts_to_buy)
                    entry_num = reentry_count + 2
                    style_tag = "THIRD_ENTRY" if entry_num == 3 else self.ai_settings.get("tradingStyle", "MOMENTUM_SURFER")
                    if is_stop_loss:
                        title_text = f"Pivoted Re-Entry #{entry_num} ({side.upper()})" if is_side_flipped else f"Dip Re-Entry #{entry_num} ({side.upper()})"
                        badge_icon = "ðŸ”„" if is_side_flipped else "ðŸ”‚"
                        catalyst_text = (
                            f"Stopped out on {closed_side.upper()}; fresh AI prediction pivoted to {side.upper()} ({conf:.1f}% conviction) with {minutes_remaining:.1f}m left"
                            if is_side_flipped else
                            f"Stopped out on pullback; fresh AI prediction confirmed {side.upper()} dip re-entry ({conf:.1f}% conviction) with {minutes_remaining:.1f}m left"
                        )
                    else:
                        title_text = f"Profit Re-Entry #{entry_num} ({side.upper()})"
                        badge_icon = "ðŸŽ¯"
                        catalyst_text = f"Secured take-profit; trend confirmed fresh {side.upper()} continuation (Entry #{entry_num}) with {minutes_remaining:.1f}m left"
                    reentry_record = {
                        "id": f"{'sim' if trade_mode == 'PAPER' else 'live'}_{uuid.uuid4().hex[:8]}",
                        "client_order_id": order_res.get("client_order_id") or order_res.get("order_id", str(uuid.uuid4())),
                        "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                        "interval_close_time": active_m.get("close_time", closed_trade.get("interval_close_time")),
                        "close_epoch": closed_trade.get("close_epoch"),
                        "ticker": ticker,
                        "title": title_text,
                        "market_snapshot": {
                            "price": spot_price,
                            "target": strike,
                            "confidence": conf,
                            "conviction_grade": f"{'DIP' if is_stop_loss else 'PROFIT'} RE-ENTRY #{entry_num}",
                            "primary_edge": "Stop-Loss Dip Re-Entry" if is_stop_loss else "Secured TP -> Fresh Trend Re-Entry",
                            "raw_features": forecast.get("raw_features", {})
                        },
                        "strike": strike,
                        "direction": direction,
                        "recommendation": f"{'DIP' if is_stop_loss else 'PROFIT'} RE-ENTRY #{entry_num} ({direction})",
                        "conviction_grade": f"GRADE A ({'DIP' if is_stop_loss else 'PROFIT'} RE-ENTRY #{entry_num})",
                        "conviction_badge": f"{badge_icon} RE-ENTRY #{entry_num} ({int(conf)}%)",
                        "probability_percent": conf,
                        "trade_source": "AUTO (STOP_LOSS_REENTRY)" if is_stop_loss else "AUTO (RE-ENTRY)",
                        "trading_style": style_tag,
                        "side": side.upper(),
                        "entry_price": fill_price,
                        "count": contracts_to_buy,
                        "cost": fill_cost,
                        "mode": trade_mode,
                        "status": "OPEN",
                        "result": "PENDING",
                        "pnl": 0.0,
                        "catalysts": [catalyst_text],
                        "is_profit_reentry": not is_stop_loss,
                        "is_stop_loss_reentry": is_stop_loss,
                        "is_second_entry": (entry_num == 2),
                        "is_third_entry": (entry_num == 3),
                        "reentry_index": entry_num,
                        "reentry_after": closed_trade.get("id"),
                        "btc_price_at_entry": spot_price
                    }
    
                    with _history_lock:
                        trades_hist = self.get_trades_history()
                        trades_hist.append(reentry_record)
                        self._save_trades_history(trades_hist)
    
                    if trade_mode == "PAPER":
                        try:
                            update_balance(-(fill_cost + fill_fee), guest_id=getattr(self, '_guest_id', None))
                        except Exception as ep:
                            logger.warning(f"Failed to deduct paper balance for re-entry: {ep}")
    
                    logger.info(f"[AutoExecutor] Successfully executed PROFIT RE-ENTRY #{entry_num} {reentry_record['id']} ({side.upper()})")
                    return reentry_record
                else:
                    logger.error(f"[AutoExecutor] Profit re-entry order placement failed: {order_res.get('error')}")
            except Exception as err:
                logger.error(f"[AutoExecutor] Error during profit re-entry evaluation: {err}", exc_info=True)
    
            return None



