import os, re

path = 'backend/btc/auto_executor/saas_broadcaster.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(
    r"""\s+with get_user_lock\(user\['id'\]\):\s+# Create history if it doesn't exist\s+hist = \[\]\s+if os\.path\.exists\(user_hist_path\):\s+try:\s+with open\(user_hist_path, 'r'\) as f:\s+hist = json\.load\(f\)\s+except .*?trade_record = \{(.*?)\}\s+hist\.append\(trade_record\)\s+with open\(user_hist_path, 'w'\) as f:\s+json\.dump\(hist, f, indent=4\)""",
    r'''                        from backend.database.trade_store import TradeStore
                        trade_record = {\1}
                        TradeStore.insert_trade(user['id'], trade_record)''',
    code, flags=re.DOTALL
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)
