from backend.engine.quant_lab.validator import StrategyValidator
for a in ("BTC", "ETH", "SOL", "NFL"):
    d = StrategyValidator.load_historical_evaluation_snapshots(asset=a)
    real = [s for s in d if not str(s["trade_id"]).startswith("sim")]
    print(a, "total", len(d), "real", len(real), "sample keys", sorted((real[0]["raw_features"] if real else {}).keys())[:8])
from backend.engine.quant_lab.orchestrator import QuantLabOrchestrator
r = QuantLabOrchestrator().run_research_cycle(asset="BTC", target_interval="15m")
print({k: r.get(k) for k in ("result", "name")}, str(r.get("metrics") or r.get("validation") or "")[:300])
