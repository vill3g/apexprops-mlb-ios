import re

with open('backend/btc/auto_executor.py', 'r') as f:
    content = f.read()

broadcast_method = '''
    def _broadcast_trade_to_users(self, ticker: str, side: str, limit_price_dollars: float, pred_info: dict = None):
        if self.mode != "LIVE":
            return
        
        try:
            from backend.database.models import get_all_active_users
            from backend.auth.security import decrypt_kalshi_key
            from backend.btc.kalshi_trader import KalshiTrader
            import concurrent.futures
            import json
            import os
            from datetime import datetime, timezone
            
            users = get_all_active_users()
            if not users:
                return
                
            logger.info(f"[SaaS Broadcast] Broadcasting {side} on {ticker} to {len(users)} active users.")
            
            def execute_for_user(user):
                try:
                    if not user.get('kalshi_key_id') or not user.get('kalshi_priv_key_encrypted'):
                        return
                    priv_key = decrypt_kalshi_key(user['kalshi_priv_key_encrypted'])
                    if not priv_key: return
                    
                    kt = KalshiTrader(key_id=user['kalshi_key_id'], private_key_pem=priv_key)
                    if not kt.is_authenticated():
                        return
                        
                    bal_res = kt.get_balance()
                    if not bal_res.get('success'): return
                    avail_bal = float(bal_res.get('balance_dollars', 0.0))
                    
                    if avail_bal < 1.0:
                        return
                        
                    # Risk 20% of the user's available balance
                    risk_amount = avail_bal * 0.20
                    contracts = max(1, int(risk_amount / max(0.01, limit_price_dollars)))
                    
                    res = kt.place_order(
                        ticker=ticker, 
                        side=side, 
                        count=contracts, 
                        limit_price_dollars=limit_price_dollars, 
                        dry_run=False, 
                        slippage_buffer_dollars=0.04
                    )
                    
                    if res.get('success'):
                        logger.info(f"[SaaS Broadcast] Successfully traded for User {user['username']} ({contracts} contracts)")
                        user_hist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'users', str(user['id']), 'trades_history.json')
                        if os.path.exists(user_hist_path):
                            with open(user_hist_path, 'r') as f:
                                history = json.load(f)
                            trade_record = {
                                "id": res.get("client_order_id", str(datetime.now().timestamp())),
                                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                                "ticker": ticker,
                                "direction": side.upper(),
                                "prediction_direction": side.upper(),
                                "probability_percent": pred_info.get('prob', 50) if pred_info else 50,
                                "entry_price": res.get("filled_price", limit_price_dollars),
                                "count": contracts,
                                "cost": res.get("filled_price", limit_price_dollars) * contracts,
                                "mode": "LIVE",
                                "status": "OPEN"
                            }
                            history.append(trade_record)
                            with open(user_hist_path, 'w') as f:
                                json.dump(history, f, indent=4)
                except Exception as e:
                    logger.error(f"[SaaS Broadcast] Error executing for user {user['username']}: {e}")
                    
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                executor.map(execute_for_user, users)
        except Exception as e:
            logger.error(f"[SaaS Broadcast] Critical error during broadcast: {e}")

'''

if '_broadcast_trade_to_users' not in content:
    content = content.replace('def get_trades_history(self) -> List[Dict[str, Any]]:', broadcast_method + '\n    def get_trades_history(self) -> List[Dict[str, Any]]:')
    with open('backend/btc/auto_executor.py', 'w') as f:
        f.write(content)
    print('Broadcast method injected.')
else:
    print('Already injected.')
