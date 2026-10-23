import logging, time
logging.basicConfig(level=logging.WARNING)
from backend.engine.quant_lab.history_builder import build_history, load_history_snapshots
from backend.engine.quant_lab.orchestrator import QuantLabOrchestrator
t = time.time()
for sp in ("NFL", "TEN"):
    d = load_history_snapshots(sp)
    yes = sum(1 for s in d if s["actual_outcome"] == "YES")
    print(sp, "snapshots", len(d), "YES rate", round(yes / max(1, len(d)), 3), "elapsed", round(time.time() - t, 1), "s")
    if d:
        print("  sample", d[-1]["ticker"], d[-1]["raw_features"])
o = QuantLabOrchestrator()
for sp in ("NFL", "TEN"):
    r = o.run_research_cycle(asset=sp, target_interval="GAME")
    m = r.get("metrics") or r.get("validation") or {}
    print(sp, r.get("result"), r.get("name"), str(m)[:260])
