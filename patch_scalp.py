import sys

with open('backend/btc/scalp_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Optimize execution latency
old_fetch = '''                            try:
                                from backend.btc.data_fetcher import fetch_candles
                                from backend.btc.indicators import add_all_indicators
                                from backend.btc.analyzer import analyze_btc
                                _df = fetch_candles("15m", limit=200)
                                analysis = analyze_btc(add_all_indicators(_df))

                                next_forecast = analysis.get("target_benchmark", {}).get("next_contract_forecast", {})'''

new_fetch = '''                            try:
                                # Fetch from the fast cache instead of blocking the thread doing a 2s HTTP request
                                from backend.btc.auto_executor import auto_executor
                                _st = auto_executor.get_status()
                                analysis = _st.get("analyzer_status") or {}
                                next_forecast = analysis.get("target_benchmark", {}).get("next_contract_forecast", {})'''

content = content.replace(old_fetch, new_fetch)

# 2. Add smart trailing stop logic
old_while = '''        # Dynamic ATR-based Take Profit Target
        if take_profit_atr > 0 and entry_atr > 0 and btc_entry > 0:
            target_dollar_move = take_profit_atr * entry_atr
            profit_target = (target_dollar_move / btc_entry) * 100.0
            logger.info(f"[ScalpEngine] Dynamic Take-Profit Target active for {trade_id}: {take_profit_atr}x ATR (\ move, {profit_target:.3f}%)")

        while True:'''

new_while = '''        # Dynamic ATR-based Take Profit Target
        if take_profit_atr > 0 and entry_atr > 0 and btc_entry > 0:
            target_dollar_move = take_profit_atr * entry_atr
            profit_target = (target_dollar_move / btc_entry) * 100.0
            logger.info(f"[ScalpEngine] Dynamic Take-Profit Target active for {trade_id}: {take_profit_atr}x ATR (\ move, {profit_target:.3f}%)")

        highest_pnl_pct = 0.0
        trailing_activation = profit_target * 0.4  # activate trail at 40% of target

        while True:'''
content = content.replace(old_while, new_while)

old_exit = '''            # Convert BTC price move to a percentage
            rel = (btc_pnl / btc_entry) * 100.0 if btc_entry != 0 else 0
            
            if rel >= profit_target or rel <= -loss_target:
                reason = "SCALP_PROFIT_TARGET" if rel >= profit_target else "SCALP_STOP_LOSS"'''

new_exit = '''            # Convert BTC price move to a percentage
            rel = (btc_pnl / btc_entry) * 100.0 if btc_entry != 0 else 0
            
            # Smart Trailing Stop logic
            if rel > highest_pnl_pct:
                highest_pnl_pct = rel
                
            current_loss_target = loss_target
            if highest_pnl_pct >= trailing_activation:
                # Move to break-even once we reach 40% of our target
                current_loss_target = -(trailing_activation * 0.1)
                
                # Trail tightly if we get past 75% of target
                if highest_pnl_pct >= profit_target * 0.75:
                    current_loss_target = -(highest_pnl_pct - (profit_target * 0.25))

            if rel >= profit_target or rel <= -current_loss_target:
                if rel >= profit_target:
                    reason = "SCALP_PROFIT_TARGET"
                elif current_loss_target < loss_target:
                    reason = "SCALP_TRAILING_STOP"
                else:
                    reason = "SCALP_STOP_LOSS"'''
content = content.replace(old_exit, new_exit)

old_sleep = '''                trade["contract_count"] = close_res.get("remaining_count", trade.get("contract_count", 0))
                logger.info(f"[ScalpEngine] Partial exit for {trade['id']}; {trade['contract_count']} contracts remain.")
            time.sleep(1)'''

new_sleep = '''                trade["contract_count"] = close_res.get("remaining_count", trade.get("contract_count", 0))
                logger.info(f"[ScalpEngine] Partial exit for {trade['id']}; {trade['contract_count']} contracts remain.")
            time.sleep(0.3)  # Faster polling for less slippage'''
content = content.replace(old_sleep, new_sleep)

old_monitor_sleep = '''                            except Exception as e:
                                logger.info(f"[ScalpEngine] Analyzer check failed: {e}")
            except Exception as e:
                logger.error(f"[ScalpEngine] Monitoring error: {e}")
            time.sleep(1)'''

new_monitor_sleep = '''                            except Exception as e:
                                logger.info(f"[ScalpEngine] Analyzer check failed: {e}")
            except Exception as e:
                logger.error(f"[ScalpEngine] Monitoring error: {e}")
            time.sleep(0.5)  # Reduce latency for initial scalp trigger'''
content = content.replace(old_monitor_sleep, new_monitor_sleep)

with open('backend/btc/scalp_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done patching scalp_engine.py!')
