from backend.btc.auto_executor import auto_executor
status = auto_executor.get_status()
print(f"Mode: {auto_executor.mode}")
print(f"Recent trades length: {len(status.get('recent_trades', []))}")
