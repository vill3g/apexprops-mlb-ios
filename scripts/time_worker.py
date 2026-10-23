import logging, time, sys
logging.disable(logging.CRITICAL)
from backend.core.registry import get_auto_executor
from backend.saas_settler import settle_saas_trades
from backend.sports_bridge.executor import SportsBridgeExecutor
t0 = time.time()
tot = {}
for a in ["BTC", "ETH", "GOLD", "SOL", "DOGE", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NDQ"]:
    s = time.time()
    ae = get_auto_executor(a)
    ae.check_and_execute_rollover()
    s2 = time.time()
    ae.evaluate_and_execute_saas_users()
    print(f"{a}: rollover {s2-s:.1f}s eval {time.time()-s2:.1f}s", flush=True)
s = time.time(); settle_saas_trades(); print(f"settle_saas_trades {time.time()-s:.1f}s", flush=True)
sb = SportsBridgeExecutor()
s = time.time(); sb.settle_all_open_trades(); print(f"sports settle_all {time.time()-s:.1f}s", flush=True)
s = time.time(); sb.run_cycle(); print(f"sports run_cycle(total incl settle) {time.time()-s:.1f}s", flush=True)
print(f"TOTAL {time.time()-t0:.1f}s")
