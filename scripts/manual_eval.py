import logging, sys, time
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format="%(name)s %(levelname)s %(message)s")
for n in ("urllib3", "asyncio", "matplotlib", "websocket", "kalshi_market_cache", "backend.engine.quant_lab"):
    logging.getLogger(n).setLevel(logging.WARNING)
from backend.core.registry import get_auto_executor
ae = get_auto_executor("BTC")
print("broadcast_trades", getattr(ae, "broadcast_trades", None))
print("lock locked?", ae._saas_eval_lock.locked(), "last eval", time.time() - ae._last_saas_eval_time)
ae.evaluate_and_execute_saas_users()
print("done")
