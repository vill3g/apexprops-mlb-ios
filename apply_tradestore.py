import os
import re

def process_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    
    original = code
    for r in replacements:
        code = re.sub(r[0], r[1], code, flags=re.DOTALL)
        
    if code != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"Patched {filepath}")

# 1. Update saas_settler.py
saas_settler_reps = [
    (
        r'''            hist_path = os.path.join\(DATA_DIR, 'users', str\(user_id\), 'trades_history\.json'\)\s+if not os\.path\.exists\(hist_path\):\s+continue\s+with get_user_lock\(user_id\):\s+try:\s+with open\(hist_path, 'r'\) as f:\s+trades = json\.load\(f\)\s+except .*?continue''',
        '''            from backend.database.trade_store import TradeStore
            trades = TradeStore.get_open_trades(user_id)'''
    ),
    (
        r'''                        with open\(hist_path, 'w'\) as f:\s+json\.dump\(trades, f, indent=2\)\s+modified = True''',
        '''                        TradeStore.update_trade(t['id'], t)
                        modified = True'''
    ),
    (
        r'''                        with open\(hist_path, 'w'\) as f:\s+json\.dump\(trades, f, indent=2\)''',
        '''                        for t in new_trades_to_add:
                            TradeStore.insert_trade(user_id, t)'''
    ),
    (
        r'''            hist_path = os.path.join\(DATA_DIR, 'users', str\(user_id\), 'trades_history\.json'\)\s+with get_user_lock\(user_id\):\s+history = \[\]\s+if os\.path\.exists\(hist_path\):\s+try:\s+with open\(hist_path, 'r'\) as f:\s+history = json\.load\(f\)\s+except .*?\s+already_traded = any\(t\.get\('ticker'\) == ticker for t in history\)''',
        '''            from backend.database.trade_store import TradeStore
            history = TradeStore.get_recent_trades(user_id, limit=50)
            already_traded = any(t.get('ticker') == ticker for t in history)'''
    ),
    (
        r'''                  history\.append\(trade_rec\)\s+with open\(hist_path, 'w'\) as f:\s+json\.dump\(history, f, indent=2\)''',
        '''                  TradeStore.insert_trade(user_id, trade_rec)'''
    ),
    (
        r'''def archive_old_trades\(.*?\):.*?        except \(ValueError, TypeError\) as e:\s+pass\s+if len\(to_archive\) > 0:.*?json\.dump\(archive, f, indent=2\)\s+with open\(hist_path, "w"\) as f:\s+json\.dump\(keep, f, indent=2\)''',
        '''def archive_old_trades(max_age_days: int = 30) -> None:
    pass # Managed by SQLite'''
    )
]

# 2. Update routes.py
routes_reps = [
    (
        r'''    hist_path = os\.path\.join\(DATA_DIR, 'users', str\(user_id\), 'trades_history\.json'\)\s+trades = \[\]\s+if os\.path\.exists\(hist_path\):\s+with get_user_lock\(user_id\):\s+try:\s+with open\(hist_path, 'r'\) as f:\s+trades = json\.load\(f\)\s+except .*?\s+trading_mode = current_user\.get\('trading_mode', 'PAPER'\)''',
        '''    from backend.database.trade_store import TradeStore
    trades = TradeStore.get_recent_trades(user_id, limit=100)
    
    trading_mode = current_user.get('trading_mode', 'PAPER')'''
    ),
    (
        r'''    hist_path = os\.path\.join\(DATA_DIR, 'users', str\(user_id\), 'trades_history\.json'\)\s+with get_user_lock\(user_id\):\s+trades = \[\]\s+if os\.path\.exists\(hist_path\):\s+try:\s+with open\(hist_path, 'r'\) as f:\s+trades = json\.load\(f\)\s+except .*?trades = \[\]\s+trades\.append\(trade_rec\)\s+with open\(hist_path, 'w'\) as f:\s+json\.dump\(trades, f, indent=2\)''',
        '''    from backend.database.trade_store import TradeStore
    TradeStore.insert_trade(user_id, trade_rec)'''
    ),
    (
        r'''    hist_path = os\.path\.join\(DATA_DIR, 'users', str\(user_id\), 'trades_history\.json'\)\s+market = get_kalshi_15m_market\(\)\s+closed_count = 0\s+with get_user_lock\(user_id\):\s+trades = \[\]\s+if os\.path\.exists\(hist_path\):\s+with open\(hist_path, 'r'\) as f:\s+try: trades = json\.load\(f\)\s+except .*?logger\.warning.*?''',
        '''    from backend.database.trade_store import TradeStore
    market = get_kalshi_15m_market()
    closed_count = 0
    trades = TradeStore.get_open_trades(user_id)'''
    ),
    (
        r'''                with open\(hist_path, 'w'\) as f:\s+json\.dump\(trades, f, indent=2\)''',
        '''                # Handled by TradeStore loop'''
    ),
    (
        r'''                    t\['status'\] = 'CLOSED'\s+t\['exit_price'\] = exit_price\s+t\['pnl'\] = pnl\s+t\['exit_reason'\] = 'MANUAL_CLOSE_ALL'\s+t\['settled_at'\] = time\.time\(\)\s+closed_count \+= 1''',
        '''                    TradeStore.close_trade(t['id'], exit_price, pnl, 'MANUAL_CLOSE_ALL', time.time())
                    closed_count += 1'''
    ),
    (
        r'''    hist_path = os\.path\.join\(DATA_DIR, 'users', str\(user_id\), 'trades_history\.json'\)\s+with get_user_lock\(user_id\):\s+trades = \[\]\s+if os\.path\.exists\(hist_path\):\s+with open\(hist_path, 'r'\) as f:\s+try: trades = json\.load\(f\)\s+except .*?target_trade = next\(\(t for t in trades if t\.get\('id'\) == trade_id and t\.get\('status'\) == 'OPEN'\), None\)''',
        '''    from backend.database.trade_store import TradeStore
    trades = TradeStore.get_open_trades(user_id)
    target_trade = next((t for t in trades if t.get('id') == trade_id and t.get('status') == 'OPEN'), None)'''
    ),
    (
        r'''        target_trade\['status'\] = 'CLOSED'\s+target_trade\['exit_price'\] = exit_price\s+target_trade\['pnl'\] = pnl\s+target_trade\['exit_reason'\] = 'MANUAL_CLOSE'\s+target_trade\['settled_at'\] = time\.time\(\)\s+with open\(hist_path, 'w'\) as f:\s+json\.dump\(trades, f, indent=2\)''',
        '''        TradeStore.close_trade(trade_id, exit_price, pnl, 'MANUAL_CLOSE', time.time())'''
    ),
    (
        r'''    hist_path = os\.path\.join\(DATA_DIR, 'users', str\(user_id\), 'trades_history\.json'\)\s+with get_user_lock\(user_id\):\s+history = \[\]\s+if os\.path\.exists\(hist_path\):\s+try:\s+with open\(hist_path, 'r'\) as f:\s+history = json\.load\(f\)\s+except .*?import pytz''',
        '''    from backend.database.trade_store import TradeStore
    import pytz'''
    ),
    (
        r'''        history\.append\(\{\s+"id": trade_id,.*?"raw_json": ""\s+\}\)\s+with open\(hist_path, 'w'\) as f:\s+json\.dump\(history, f, indent=2\)''',
        '''        TradeStore.insert_trade(user_id, {
            "id": trade_id,
            "ticker": market.get("ticker"),
            "side": direction,
            "count": count,
            "entry_price": price,
            "exit_price": 0.0,
            "pnl": 0.0,
            "status": "OPEN",
            "mode": mode,
            "reason": "MANUAL",
            "trading_style": "MANUAL",
            "timestamp": now_est,
            "settled_at": 0,
            "raw_json": ""
        })'''
    ),
    (
        r'''        hist_path = os\.path\.join\(DATA_DIR, "users", str\(uid\), "trades_history\.json"\)\s+trades = \[\]\s+if os\.path\.exists\(hist_path\):\s+with get_user_lock\(uid\):\s+try:\s+with open\(hist_path, "r", encoding="utf-8"\) as f:\s+trades = json\.load\(f\)\s+except .*?trades = \[\]\s+total_trades = len\(trades\)''',
        '''        from backend.database.trade_store import TradeStore
        trades = TradeStore.get_recent_trades(uid, limit=100)
        total_trades = len(trades)'''
    )
]

# 3. auto_executor/saas_broadcaster.py
saas_broadcast_reps = [
    (
        r'''                        user_hist_path = os\.path\.join.*?with get_user_lock\(user\['id'\]\):\s+user_history = \[\]\s+if os\.path\.exists\(user_hist_path\):\s+try:\s+with open\(user_hist_path, 'r'\) as f:\s+user_history = json\.load\(f\)\s+except .*?already_traded = any\(t\.get\('ticker'\) == active_ticker for t in user_history\)''',
        '''                        from backend.database.trade_store import TradeStore
                        user_history = TradeStore.get_recent_trades(user['id'], limit=50)
                        already_traded = any(t.get('ticker') == active_ticker for t in user_history)'''
    ),
    (
        r'''                        user_history\.append\(user_trade\)\s+with open\(user_hist_path, 'w'\) as f:\s+json\.dump\(user_history, f, indent=2\)''',
        '''                        TradeStore.insert_trade(user['id'], user_trade)'''
    ),
    (
        r'''                    user_hist_path = os\.path\.join.*?with get_user_lock\(uid\):\s+u_history = \[\]\s+if os\.path\.exists\(user_hist_path\):\s+try:\s+with open\(user_hist_path, 'r'\) as f:\s+u_history = json\.load\(f\)\s+except .*?target_trade = next\(\(t for t in u_history if t\.get\("ticker"\) == active_ticker and t\.get\("status"\) == "OPEN"\), None\)''',
        '''                    from backend.database.trade_store import TradeStore
                    u_history = TradeStore.get_open_trades(uid)
                    target_trade = next((t for t in u_history if t.get("ticker") == active_ticker and t.get("status") == "OPEN"), None)'''
    ),
    (
        r'''                        target_trade\.update\(updates\)\s+with open\(user_hist_path, 'w'\) as f:\s+json\.dump\(u_history, f, indent=2\)''',
        '''                        TradeStore.update_trade(target_trade['id'], updates)'''
    ),
    (
        r'''                        _hist_path = _cached_path or os\.path\.join.*?with get_user_lock\(user\['id'\]\):\s+u_history = \[\]\s+if os\.path\.exists\(_hist_path\):\s+try:\s+with open\(_hist_path, 'r'\) as f:\s+u_history = json\.load\(f\)\s+except .*?target_trade = next\(\(t for t in u_history if t\.get\("ticker"\) == ticker and t\.get\("status"\) == "OPEN"\), None\)''',
        '''                        from backend.database.trade_store import TradeStore
                        u_history = TradeStore.get_open_trades(user['id'])
                        target_trade = next((t for t in u_history if t.get("ticker") == ticker and t.get("status") == "OPEN"), None)'''
    ),
    (
        r'''                            target_trade\.update\(updates\)\s+with open\(_hist_path, 'w'\) as f:\s+json\.dump\(u_history, f, indent=2\)''',
        '''                            TradeStore.update_trade(target_trade['id'], updates)'''
    )
]

process_file('backend/saas_settler.py', saas_settler_reps)
process_file('backend/auth/routes.py', routes_reps)
process_file('backend/btc/auto_executor/saas_broadcaster.py', saas_broadcast_reps)

