import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\auto_executor\stop_manager.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update the setup of indicators before the loop to include EMA-21 and CVD.
old_setup = """            try:
                recent_candles = fetch_candles(self.asset, timeframe="15m", limit=30)
                if recent_candles is not None and len(recent_candles) >= 14:
                    atr_series = compute_atr(recent_candles)
                    atr_val = float(atr_series.iloc[-1])
                    if atr_val > 0:
                        stop_loss_move = max(stop_loss_move, atr_val * atr_multiplier)
            except Exception:
                pass"""

new_setup = """            ema_21_val = 0.0
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
                logger.warning(f"[AutoExecutor] Failed to compute dynamic stop indicators: {e}")"""

content = content.replace(old_setup, new_setup)

# 2. Update the actual dynamic stop-loss evaluation
# We want to replace everything from "if dynamic_stop_enabled:" down to the end of that if block.
# Since it's indented, we'll use a regex that matches the start of it to the end.

old_dynamic_stop = """            if dynamic_stop_enabled:
                # Early stop window check: first stop_loss_max_minutes and at least 90 seconds left
                if minutes_elapsed <= stop_loss_max_minutes and minutes_remaining >= 1.5:
                    is_adverse = False
                    deficit = 0.0

                    if strike > 0:
                        if side == "YES" and spot_price < strike:
                            deficit = strike - spot_price
                            if deficit >= stop_loss_move:
                                is_adverse = True
                        elif side == "NO" and spot_price >= strike:
                            deficit = spot_price - strike
                            if deficit >= stop_loss_move:
                                is_adverse = True
                    else:
                        if side == "YES" and spot_price < btc_entry:
                            deficit = btc_entry - spot_price
                            if deficit >= stop_loss_move:
                                is_adverse = True
                        elif side == "NO" and spot_price >= btc_entry:
                            deficit = spot_price - btc_entry
                            if deficit >= stop_loss_move:
                                is_adverse = True

                    if is_adverse:
                        logger.info(
                            f"[AutoExecutor] DYNAMIC STOP-LOSS TRIGGERED for {trade_id} ({side}): "
                            f"Spot ${spot_price:,.2f} adverse deficit ${deficit:.2f} >= ${stop_loss_move:.2f} "
                            f"at {minutes_elapsed:.1f}m elapsed ({minutes_remaining:.1f}m left)."
                        )
                        # Realistic salvage exit price for simulation / paper fallback
                        est_exit = round(max(0.10, min(0.40, entry_price - 0.25)), 2)  # Kalshi only quotes/fills in whole cents
                        close_res = self.close_specific_trade(trade_id, reason="DYNAMIC_STOP_LOSS", estimated_exit_price=est_exit)
                        if close_res.get("success"):
                            logger.info(f"[AutoExecutor] Early stop executed for {trade_id}; realized P&L ${close_res.get('pnl', 0):.2f}")
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
"""

new_dynamic_stop = """            if dynamic_stop_enabled:
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
"""

# Try a strict literal replace first
if old_dynamic_stop in content:
    content = content.replace(old_dynamic_stop, new_dynamic_stop)
else:
    # Use regex
    content = re.sub(r"            if dynamic_stop_enabled:.*?is_stop_loss=True\)\n", new_dynamic_stop, content, flags=re.DOTALL)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched stop_manager.py successfully.")
