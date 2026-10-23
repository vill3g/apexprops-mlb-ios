import time
from backend.engine.quant_lab.history_builder import build_history, backfill_names
t = time.time()
print("names backfilled:", backfill_names("TEN"), flush=True)
for i in range(3):
    n = build_history("TEN", max_markets=120)
    print(f"build pass {i+1}: +{n} markets, elapsed {time.time()-t:.0f}s", flush=True)
    if n == 0:
        break
print("done", flush=True)
