import re

with open('backend/sports_bridge/executor.py', 'r') as f:
    code = f.read()

# 1. Take Profit settlement block
old_tp = '''                        if kt_settle:
                            close_res = kt_settle.close_position(
                                ticker, "yes", cur_price,
                                count=contracts,
                                client_order_id=f"tp_{t_id}_{int(time.time())}"
                            )
                            if not close_res.get("success"):
                                logger.warning(f"[SportsBridge] Live TP close failed for {t_id}: {close_res.get('error')}")
                                continue
                            cur_price = float(close_res.get("exit_price") or cur_price)
                            pnl = round((cur_price - entry_price) * contracts, 2)
                            payout = round(cur_price * contracts, 2)
                    elif payout > 0:
                        credit_user_paper_balance(uid, payout)
                    TradeStore.update_trade(t_id, {
                        "status": "CLOSED",
                        "exit_price": cur_price,
                        "pnl": pnl,
                        "exit_reason": f"TAKE_PROFIT (+{gain_pct:.1f}%)"
                    })'''

new_tp = '''                        if kt_settle:
                            close_res = kt_settle.close_position(
                                ticker, "yes", cur_price,
                                count=contracts,
                                client_order_id=f"tp_{t_id}_{int(time.time())}"
                            )
                            if not close_res.get("success"):
                                logger.warning(f"[SportsBridge] Live TP close failed for {t_id}: {close_res.get('error')}")
                                continue
                            cur_price = float(close_res.get("exit_price") or cur_price)
                        else:
                            continue
                            
                    pnl = net_pnl(entry_price, cur_price, contracts)
                    closed_ok = TradeStore.close_if_open(uid, t, {
                        "exit_price": cur_price,
                        "pnl": pnl,
                        "exit_reason": f"TAKE_PROFIT (+{gain_pct:.1f}%)"
                    })
                    if not closed_ok:
                        continue
                    payout = round(cur_price * contracts, 2)
                    if t_mode == "PAPER" and payout > 0:
                        credit_user_paper_balance(uid, payout - kalshi_order_fee(cur_price, contracts))'''
if old_tp in code:
    code = code.replace(old_tp, new_tp)

# 2. Final settlement (Win)
old_win = '''                is_win = (result == side)
                if is_win:
                    exit_price = 1.0
                    pnl = round((1.0 - entry_price) * contracts, 2)
                    payout = round(1.0 * contracts, 2)
                    # Credit winnings back to unified paper balance ONLY for PAPER trades
                    # (Live trades are settled and credited automatically by Kalshi into the user's cash portfolio)
                    if payout > 0 and t_mode == "PAPER":
                        credit_user_paper_balance(uid, payout)
                else:
                    exit_price = 0.0
                    pnl = round(-entry_price * contracts, 2)

                TradeStore.update_trade(t_id, {
                    "status": "CLOSED",
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "exit_reason": "SETTLEMENT",
                    "settled_at": settled_at
                })'''

new_win = '''                is_win = (result == side)
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
                if is_win and t_mode == "PAPER" and payout > 0:
                    credit_user_paper_balance(uid, payout - kalshi_order_fee(exit_price, contracts))'''

if old_win in code:
    code = code.replace(old_win, new_win)

with open('backend/sports_bridge/executor.py', 'w') as f:
    f.write(code)
