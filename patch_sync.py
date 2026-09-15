import sys

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_reconcile = '''                    for t in list(open_trades):
                        ticker = t.get("ticker")
                        if kalshi_pos_map.get(ticker, 0.0) <= 0.0 or str(t.get("id", "")).startswith("sim_"):
                            logger.info(f"[AutoExecutor] Auto-reconciled flat Kalshi position for trade {t.get('id')} ({ticker}).")'''

new_reconcile = '''                    for t in list(open_trades):
                        ticker = t.get("ticker")
                        # FIX: Kalshi NO positions have negative position_fp. Use abs() so we don't falsely close them!
                        if abs(kalshi_pos_map.get(ticker, 0.0)) <= 0.001 or str(t.get("id", "")).startswith("sim_"):
                            logger.info(f"[AutoExecutor] Auto-reconciled flat Kalshi position for trade {t.get('id')} ({ticker}).")'''

content = content.replace(old_reconcile, new_reconcile)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
