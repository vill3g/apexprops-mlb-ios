from backend.btc.auto_executor import auto_executor
import json

status = auto_executor.get_status()
print(f"Mode: {auto_executor.mode}")
print(f"Open trades found in status: {len(status.get('open_trades', []))}")
for t in status.get('open_trades', []):
    print(t.get('ticker'), t.get('status'))
