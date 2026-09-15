import sys

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_reconcile = '''                        # Only auto-reconcile live markets. If it's expired, it's normal for it to be missing from active positions!
                        close_epoch = float(t.get("close_epoch") or float("inf"))
                        if time.time() > close_epoch:
                            continue
                            
                        # FIX: Kalshi NO positions have negative position_fp. Use abs() so we don't falsely close them!
                        val = kalshi_pos_map.get(ticker, 0.0)
                        is_sim = str(t.get("id", "")).startswith("sim_")
                        if abs(val) <= 0.001 or is_sim:
                            with open('reconcile_debug.log', 'a') as df:
                                df.write(f"Reconciling: ticker={ticker}, val={val}, is_sim={is_sim}, map={kalshi_pos_map}\\n")
                            logger.info(f"[AutoExecutor] Auto-reconciled flat Kalshi position for trade {t.get('id')} ({ticker}).")'''

new_reconcile = '''                        # Only auto-reconcile live markets. If it's expired, it's normal for it to be missing from active positions!
                        close_epoch = float(t.get("close_epoch") or float("inf"))
                        now_ts = time.time()
                        
                        if now_ts > close_epoch:
                            continue
                            
                        # FIX: Kalshi API has read-replica lag. A newly opened trade might not appear in get_positions for ~15 seconds!
                        # Add a 60 second grace period where we DO NOT auto-reconcile newly created trades.
                        trade_age = now_ts - float(t.get("close_epoch", now_ts) - 900) # close epoch is exactly +15m
                        # If we can parse timestamp precisely:
                        try:
                            from datetime import datetime
                            from zoneinfo import ZoneInfo
                            trade_dt = datetime.strptime(t.get("timestamp", ""), "%Y-%m-%d %I:%M:%S %p ET").replace(tzinfo=ZoneInfo("America/New_York"))
                            trade_age = now_ts - trade_dt.timestamp()
                        except:
                            trade_age = 61 # default to bypass grace period if parse fails
                            
                        if trade_age < 30.0:
                            continue
                            
                        # FIX: Kalshi NO positions have negative position_fp. Use abs() so we don't falsely close them!
                        val = kalshi_pos_map.get(ticker, 0.0)
                        is_sim = str(t.get("id", "")).startswith("sim_")
                        if abs(val) <= 0.001 or is_sim:
                            logger.info(f"[AutoExecutor] Auto-reconciled flat Kalshi position for trade {t.get('id')} ({ticker}).")'''

content = content.replace(old_reconcile, new_reconcile)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
