import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''            def execute_for_user(user):
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
                    
                    if user_mode == 'LIVE':'''

new_block = '''            def execute_for_user(user):
                try:
                    if not user.get('ai_enabled', 1): return
                    user_mode = user.get('trading_mode', 'PAPER')
                    
                    import uuid
                    import pytz
                    import os
                    import json
                    from datetime import datetime
                    
                    est_tz = pytz.timezone('US/Eastern')
                    now_est = datetime.now(est_tz).strftime('%Y-%m-%d %I:%M:%S %p ET')
                    today_str = datetime.now(est_tz).strftime('%Y-%m-%d')
                    
                    # Check Daily Limits
                    user_hist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'users', str(user['id']), 'trades_history.json')
                    history = []
                    if os.path.exists(user_hist_path):
                        try:
                            with open(user_hist_path, 'r') as f:
                                history = json.load(f)
                        except: pass
                    
                    today_trades = [t for t in history if t.get("mode", "PAPER") == user_mode and str(t.get("timestamp", "")).startswith(today_str)]
                    max_trades = int(user.get("max_daily_trades", 10))
                    if len(today_trades) >= max_trades:
                        logger.info(f"[SaaS Broadcast] User {user['username']} skipped: Max daily trades reached ({max_trades})")
                        return
                        
                    max_risk = float(user.get("max_daily_risk", 50.0))
                    today_pnl = sum(float(t.get("pnl", 0.0)) for t in today_trades if t.get("status") in ["CLOSED", "SETTLED"])
                    today_open_cost = sum(float(t.get("entry_price", 0.0)) * int(t.get("count", 0)) for t in today_trades if t.get("status") == "OPEN")
                    effective_risk = today_pnl - today_open_cost
                    if effective_risk <= -abs(max_risk):
                        logger.info(f"[SaaS Broadcast] User {user['username']} skipped: Max daily risk reached (${max_risk})")
                        return
                    
                    filled_price = limit_price_dollars
                    contracts = 0
                    trade_id = str(uuid.uuid4())
                    
                    if user_mode == 'LIVE':'''

content = content.replace(old_block, new_block)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
