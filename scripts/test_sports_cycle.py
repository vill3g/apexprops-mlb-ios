import time
from backend.sports_bridge.executor import SportsBridgeExecutor
sb = SportsBridgeExecutor()
print("Running run_cycle...")
t0 = time.time()
sb.run_cycle()
print("Finished run_cycle in", round(time.time() - t0, 2), "s")
