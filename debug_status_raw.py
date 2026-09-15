from backend.btc.auto_executor import auto_executor
import json
s = auto_executor.get_status()
for k, v in s.items():
    if k not in ['recent_trades', 'open_trades', 'active_market', 'prediction_accuracy', 'ai_settings', 'calibration_drift']:
        print(k, '=', repr(v))
