import re

with open('backend/sports_bridge/executor.py', 'r') as f:
    code = f.read()

# 1. Take Profit live close rewrite
patt_tp = r'if\s+kt_settle:.*?TradeStore\.update_trade\s*\(\s*t_id\s*,\s*\{.*?"exit_reason":\s*f"TAKE_PROFIT[^}]*\}\)'

new_tp = '''if kt_settle:
                            close_res = kt_settle.close_position(
                                ticker, "yes", cur_price,
                                count=contracts,
                                client_order_id=f"tp_{t_id}_{int(time.time())}"
                            )
                            if not close_res.get("success"):
                                if "Not enough positions" in str(close_res.get("error", "")):
                                    logger.info(f"[SportsBridge] Position on {ticker} already closed or not held on Kalshi.")
                                else:
                                    logger.warning(f"[SportsBridge] Live TP close failed for {t_id}: {close_res.get('error')}")
                                    continue
                            cur_price = float(close_res.get("exit_price") or cur_price)
                        else:
                            if t_mode == "LIVE": continue

                        pnl = net_pnl(entry_price, cur_price, contracts)
                        payout = round(cur_price * contracts, 2)
                        
                        closed_ok = TradeStore.close_if_open(uid, t, {
                            "exit_price": cur_price,
                            "pnl": pnl,
                            "exit_reason": f"TAKE_PROFIT (+{gain_pct:.1f}%)"
                        })
                        if not closed_ok:
                            continue
                            
                        if t_mode == "PAPER" and payout > 0:
                            credit_user_paper_balance(uid, payout - kalshi_order_fee(cur_price, contracts))'''
                            
code = re.sub(patt_tp, new_tp, code, flags=re.DOTALL)

# 2. Settlement rewrite
patt_settle = r'is_win\s*=\s*\(result\s*==\s*side\).*?TradeStore\.update_trade\s*\(\s*t_id\s*,\s*\{.*?"exit_reason":\s*"SETTLEMENT".*?\}\)'

new_settle = '''is_win = (result == side)
                exit_price = 1.0 if is_win else 0.0
                pnl = net_pnl(entry_price, exit_price, contracts)

                closed_ok = TradeStore.close_if_open(uid, t, {
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "exit_reason": "SETTLEMENT",
                    "settled_at": settled_at
                })
                if not closed_ok:
                    continue

                payout = round(exit_price * contracts, 2)
                if t_mode == "PAPER" and payout > 0:
                    credit_user_paper_balance(uid, payout - kalshi_order_fee(exit_price, contracts))'''

code = re.sub(patt_settle, new_settle, code, flags=re.DOTALL)

# 3. Timeout rewrite
patt_timeout = r'is_win\s*=\s*\(trade_conf\s*>=\s*55\.0\).*?TradeStore\.update_trade\s*\(\s*t_id\s*,\s*\{.*?"exit_reason":\s*"TIMEOUT".*?\}\)'

new_timeout = '''is_win = (trade_conf >= 55.0)
                exit_price = 1.0 if is_win else 0.0
                pnl = net_pnl(entry_price, exit_price, contracts)
                
                closed_ok = TradeStore.close_if_open(uid, t, {
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "exit_reason": "TIMEOUT",
                    "settled_at": time.time()
                })
                if not closed_ok:
                    continue
                    
                payout = round(exit_price * contracts, 2)
                if t_mode == "PAPER" and payout > 0:
                    credit_user_paper_balance(uid, payout - kalshi_order_fee(exit_price, contracts))'''
                    
code = re.sub(patt_timeout, new_timeout, code, flags=re.DOTALL)

with open('backend/sports_bridge/executor.py', 'w') as f:
    f.write(code)
