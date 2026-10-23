from dotenv import load_dotenv
load_dotenv()
from backend.engine.quant_lab.orchestrator import QuantLabOrchestrator

orch = QuantLabOrchestrator()
for asset in ["BTC", "SOL", "DOGE", "MLB", "TEN"]:
    res = orch.run_research_cycle(asset=asset, target_interval="15m")
    val = res.get("validation") or {}
    total_trades = val.get("total_trades", 0)
    passed = val.get("passed", False)
    fail_reason = val.get("failure_reason")
    print(f"Asset: {asset:<5} | Strategy: '{res.get('name')}'")
    print(f"       Result: {res.get('result')} | Total Trades: {total_trades} | Passed: {passed}")
    if not passed:
        print(f"       Failure Reason: {fail_reason}")
    print("-" * 70)
