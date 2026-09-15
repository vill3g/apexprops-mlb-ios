import sys

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_reconcile = '''                        # FIX: Kalshi NO positions have negative position_fp. Use abs() so we don't falsely close them!
                        if abs(kalshi_pos_map.get(ticker, 0.0)) <= 0.001 or str(t.get("id", "")).startswith("sim_"):
                            logger.info(f"[AutoExecutor] Auto-reconciled flat Kalshi position for trade {t.get('id')} ({ticker}).")'''

new_reconcile = '''                        # FIX: Kalshi NO positions have negative position_fp. Use abs() so we don't falsely close them!
                        val = kalshi_pos_map.get(ticker, 0.0)
                        is_sim = str(t.get("id", "")).startswith("sim_")
                        if abs(val) <= 0.001 or is_sim:
                            with open('reconcile_debug.log', 'a') as df:
                                df.write(f"Reconciling: ticker={ticker}, val={val}, is_sim={is_sim}, map={kalshi_pos_map}\\n")
                            logger.info(f"[AutoExecutor] Auto-reconciled flat Kalshi position for trade {t.get('id')} ({ticker}).")'''

content = content.replace(old_reconcile, new_reconcile)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
