import sys
import os
import json

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    c = f.read()

new_func = """            def execute_for_user(user):
                try:
                    if not user.get('ai_enabled', 1): return
                    user_mode = user.get('trading_mode', 'PAPER')
                    
                    import uuid
                    import pytz
                    from datetime import datetime
                    
                    est_tz = pytz.timezone('US/Eastern')
                    now_est = datetime.now(est_tz).strftime('%Y-%m-%d %I:%M:%S %p ET')
                    
                    filled_price = limit_price_dollars
                    contracts = 0
                    trade_id = str(uuid.uuid4())
                    
                    if user_mode == 'LIVE':
                        if not user.get('kalshi_key_id') or not user.get('kalshi_priv_key_encrypted'): return
                        priv_key = decrypt_kalshi_key(user['kalshi_priv_key_encrypted'])
                        if not priv_key: return
                        kt = KalshiTrader(key_id=user['kalshi_key_id'], private_key_pem=priv_key)
                        if not kt.is_authenticated(): return
                        bal_res = kt.get_balance()
                        if not bal_res.get('success'): return
                        avail_bal = float(bal_res.get('balance_dollars', 0.0))
                        if avail_bal < 1.0: return
                        risk_amount = avail_bal * 0.20
                        contracts = max(1, int(risk_amount / max(0.01, limit_price_dollars)))
                        res = kt.place_order(
                            ticker=ticker, side=side, count=contracts, 
                            limit_price_dollars=limit_price_dollars, dry_run=False, slippage_buffer_dollars=0.04
                        )
                        if not res.get('success'): return
                        filled_price = res.get('filled_price', limit_price_dollars)
                        trade_id = res.get('client_order_id', trade_id)
                    else:
                        from backend.database.models import update_user_paper_balance
                        avail_bal = float(user.get('paper_balance', 500.0))
                        if avail_bal < 1.0: return
                        risk_amount = avail_bal * 0.20
                        contracts = max(1, int(risk_amount / max(0.01, limit_price_dollars)))
                        cost = contracts * filled_price
                        update_user_paper_balance(user['id'], avail_bal - cost)

                    logger.info(f'[SaaS Broadcast] Successfully traded for User {user["username"]} ({contracts} contracts in {user_mode})')
                    user_hist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'users', str(user['id']), 'trades_history.json')
                    if os.path.exists(user_hist_path):
                        with open(user_hist_path, 'r') as f:
                            history = json.load(f)
                        trade_record = {
                            "id": trade_id,
                            "timestamp": now_est,
                            "ticker": ticker,
                            "direction": side.upper(),
                            "side": side.upper(),
                            "prediction_direction": side.upper(),
                            "probability_percent": pred_info.get('prob', 50) if pred_info else 50,
                            "entry_price": filled_price,
                            "count": contracts,
                            "status": "OPEN",
                            "mode": user_mode,
                            "pnl": 0.0,
                            "reason": "AI_SIGNAL"
                        }
                        history.append(trade_record)
                        with open(user_hist_path, 'w') as f:
                            json.dump(history, f, indent=4)
                except Exception as e:
                    logger.error(f'[SaaS Broadcast] Error executing for user {user.get("username")}: {e}')"""

start_idx = c.find('def execute_for_user(user):')
end_idx = c.find('except Exception as e:', start_idx)
end_idx = c.find('\n', c.find('logger.error', end_idx))

c = c[:start_idx] + new_func + c[end_idx:]

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(c)
