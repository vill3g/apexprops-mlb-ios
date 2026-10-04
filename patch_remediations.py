import re
import os

base_dir = r"C:\Users\Vill3\Desktop\ShadowTraderAi\backend"

def apply_patch():
    # 1. stop_manager.py (Remediation 2 & 4 & 3)
    stop_mgr_path = os.path.join(base_dir, "btc", "auto_executor", "stop_manager.py")
    with open(stop_mgr_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Add import
    if "from backend.btc.auto_executor.remediations import evaluate_exit_discipline, calculate_anti_whipsaw_trailing_stop, is_reentry_permitted" not in content:
        content = content.replace("from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract",
                                  "from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract\nfrom backend.btc.auto_executor.remediations import evaluate_exit_discipline, calculate_anti_whipsaw_trailing_stop, is_reentry_permitted")

    # Rewrite loop body in check_active_trades_stop_and_reversal
    # We will replace from "# 1. Hard Take-Profit Check" to the end of the take profit check block.
    # Actually, it's safer to find the loop and replace the whole block.
    old_loop_block = """                            max_seen_profit_pct = ((max_seen_bid - entry_price) / entry_price) * 100.0
    
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
                                self._attempt_profit_reentry(trade, minutes_remaining, spot_price, is_stop_loss=True)"""
    new_loop_block = """                            max_seen_profit_pct = ((max_seen_bid - entry_price) / entry_price) * 100.0

                            # Remediation 2 & 4: Evaluate Exit Discipline and Anti-Whipsaw Trailing Stop
                            # 1. Anti-Whipsaw Trailing Stop
                            ts_res = calculate_anti_whipsaw_trailing_stop(entry_price, max_seen_bid, bid_price)
                            if ts_res.get("should_exit"):
                                logger.info(f"[AutoExecutor] {ts_res['reason']} for {trade_id} ({side}).")
                                close_res = self.close_specific_trade(trade_id, reason="TRAILING_TAKE_PROFIT", estimated_exit_price=bid_price)
                                if close_res.get("success"):
                                    self._attempt_profit_reentry(trade, minutes_remaining, spot_price)
                                continue

                            # 2. Exit Discipline
                            exit_res = evaluate_exit_discipline(trade, bid_price, spot_price, strike, time_remaining_sec)
                            if exit_res.get("should_close"):
                                logger.info(f"[AutoExecutor] EXIT DISCIPLINE: {exit_res['reason']} for {trade_id}.")
                                reason_str = "TAKE_PROFIT" if "PROFIT" in exit_res['reason'] else "DYNAMIC_STOP_LOSS"
                                close_res = self.close_specific_trade(trade_id, reason=reason_str, estimated_exit_price=exit_res["exit_price"])
                                if close_res.get("success"):
                                    if reason_str == "TAKE_PROFIT":
                                        self._attempt_profit_reentry(trade, minutes_remaining, spot_price)
                                continue

                        except Exception as e:
                            logger.warning(f"[AutoExecutor] Take profit check failed: {e}")"""
    
    if old_loop_block in content:
        content = content.replace(old_loop_block, new_loop_block)
        print("Patched check_active_trades_stop_and_reversal in stop_manager.py")
    else:
        print("Failed to find old loop block in stop_manager.py")

    # Replace _attempt_profit_reentry's start to use is_reentry_permitted (Remediation 3)
    old_reentry_start = """        def _attempt_profit_reentry(
            self,
            closed_trade: Dict[str, Any],
            minutes_remaining: float,
            spot_price: float,
            is_stop_loss: bool = False
        ) -> Optional[Dict[str, Any]]:
            \"\"\"
            After securing a take-profit or getting stopped out (if re-entry enabled), evaluate
            if there is still enough time (>= 4.0 minutes) and conviction to enter a fresh contract.
            \"\"\"
            if minutes_remaining < 0.25:
                logger.info(f"[AutoExecutor] Profit re-entry skipped: Only {minutes_remaining:.1f}m remaining in interval (< 15s minimum).")
                return None"""
    new_reentry_start = """        def _attempt_profit_reentry(
            self,
            closed_trade: Dict[str, Any],
            minutes_remaining: float,
            spot_price: float,
            is_stop_loss: bool = False
        ) -> Optional[Dict[str, Any]]:
            if not is_reentry_permitted(self.get_trades_history(), closed_trade.get("ticker", ""), closed_trade.get("exit_reason", ""), minutes_remaining * 60):
                return None"""
    
    if old_reentry_start in content:
        content = content.replace(old_reentry_start, new_reentry_start)
        print("Patched _attempt_profit_reentry in stop_manager.py")
    
    with open(stop_mgr_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 2. saas_broadcaster.py (Remediation 5 & 8)
    # Wait, the prompt says remediations 2, 3, 4, 7, 8, 9. 
    # Remediation 7 is in contract_eval.py
    # Remediation 8 is terminal gamma gate in saas_broadcaster.py
    # Remediation 9 is in risk_manager.py
    
    saas_b_path = os.path.join(base_dir, "btc", "auto_executor", "saas_broadcaster.py")
    with open(saas_b_path, "r", encoding="utf-8") as f:
        sb_content = f.read()

    # Rem 8: Terminal Gamma Guardrail
    old_gamma = """                # Expiration Safety Guard: Never enter brand new trades within 180s (3 minutes) of expiration
                if sec_left < 15:
                    return"""
    new_gamma = """                # Terminal Gamma Gate and Timing Filter (Remediation 8)
                if sec_left < 210:
                    return
                minute_elapsed = sec_elapsed // 60
                if 3 <= minute_elapsed <= 6:
                    return"""
    if old_gamma in sb_content:
        sb_content = sb_content.replace(old_gamma, new_gamma)
        print("Patched saas_broadcaster.py (Terminal Gamma)")

    with open(saas_b_path, "w", encoding="utf-8") as f:
        f.write(sb_content)

    # 3. contract_eval.py (Remediation 7)
    ce_path = os.path.join(base_dir, "btc", "analyzer", "contract_eval.py")
    with open(ce_path, "r", encoding="utf-8") as f:
        ce_content = f.read()

    old_ce = """    if kalshi_m and "GRADE A" not in grade:
        k_yes = float(kalshi_m.get("yes_ask", 50) if kalshi_m.get("yes_ask") else 50)
        k_no = float(kalshi_m.get("no_ask", 50) if kalshi_m.get("no_ask") else 50)
        imbalance = float(kalshi_m.get("book_imbalance", 0.0) if kalshi_m.get("book_imbalance") else 0.0)

        if k_yes >= THRESHOLDS["kalshi_override_yes"] or imbalance >= THRESHOLDS["kalshi_imbalance_threshold"]:"""
    new_ce = """    if kalshi_m and "GRADE A" not in grade:
        k_yes = float(kalshi_m.get("yes_ask", 0.50) if kalshi_m.get("yes_ask") else 0.50)
        k_no = float(kalshi_m.get("no_ask", 0.50) if kalshi_m.get("no_ask") else 0.50)
        
        # Remediation 7: Dollar to cent normalization
        k_yes_cents = k_yes * 100.0 if k_yes <= 1.0 else k_yes
        k_no_cents = k_no * 100.0 if k_no <= 1.0 else k_no
        imbalance = float(kalshi_m.get("book_imbalance", 0.0) if kalshi_m.get("book_imbalance") else 0.0)

        if k_yes_cents >= THRESHOLDS["kalshi_override_yes"] or imbalance >= THRESHOLDS["kalshi_imbalance_threshold"]:"""
    
    if old_ce in ce_content:
        ce_content = ce_content.replace(old_ce, new_ce)
        print("Patched contract_eval.py (Remediation 7)")
    else:
        print("contract_eval.py old text not found")

    with open(ce_path, "w", encoding="utf-8") as f:
        f.write(ce_content)

    # 4. risk_manager.py (Remediation 9)
    rm_path = os.path.join(base_dir, "btc", "auto_executor", "risk_manager.py")
    with open(rm_path, "r", encoding="utf-8") as f:
        rm_content = f.read()

    # Look for the streak logic
    old_rm = """        # Optional Circuit Breaker: Max Consecutive Losses
        max_consecutive_losses = int(self.ai_settings.get("max_consecutive_losses", 3))
        if max_consecutive_losses > 0:
            consecutive_losses = 0
            for trade in sorted_today:
                res = str(trade.get("result", "")).upper()
                if "LOSS" in res:
                    consecutive_losses += 1
                elif "WIN" in res:
                    consecutive_losses = 0
            if consecutive_losses >= max_consecutive_losses:
                return f"Circuit breaker tripped: {consecutive_losses} consecutive losses reached."
"""
    new_rm = """        # Remediation 9: Grouped Interval Risk Budget & Multi-Entry Circuit Breaker
        max_consecutive_losses = int(self.ai_settings.get("max_consecutive_losses", 3))
        if max_consecutive_losses > 0:
            interval_pnl_map = {}
            for trade in sorted_today:
                if trade.get("status") in ["SETTLED", "CLOSED"]:
                    ticker = trade.get("ticker", "")
                    interval_pnl_map.setdefault(ticker, []).append(float(trade.get("pnl", 0.0)))
            
            consecutive_losses = 0
            for ticker in reversed(list(interval_pnl_map.keys())):
                net_interval_pnl = sum(interval_pnl_map[ticker])
                if net_interval_pnl < 0.0:
                    consecutive_losses += 1
                    if consecutive_losses >= max_consecutive_losses:
                        return f"Circuit breaker tripped: {consecutive_losses} consecutive interval losses reached."
                else:
                    break
"""
    if old_rm in rm_content:
        rm_content = rm_content.replace(old_rm, new_rm)
        print("Patched risk_manager.py (Remediation 9)")
    else:
        print("risk_manager.py old text not found")

    with open(rm_path, "w", encoding="utf-8") as f:
        f.write(rm_content)

if __name__ == "__main__":
    apply_patch()
