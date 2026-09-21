import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from backend.btc.analyzer import evaluate_next_15m_contract
from backend.btc.auto_executor import get_auto_executor

asset = "BTC"
ex = get_auto_executor(asset)
status = ex.get_status()

print("ENABLED:", status["enabled"])
print("RISK PAUSED:", status["is_risk_paused"], status["pause_reason"])
print("MODE:", status["mode"])
print("TODAY TRADES:", status["today_trade_count"], "/", status["max_daily_trades"])

print("\n--- ANALYZER OUTPUT ---")
res = evaluate_next_15m_contract(asset=asset, force_refresh=True)
print(json.dumps(res, indent=2))
