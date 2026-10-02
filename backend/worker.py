import logging
import os
import sys
import time
import traceback

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.registry import get_auto_executor
from backend.database.models import init_db
from backend.forex.auto_executor import start_forex_executor
from backend.saas_settler import (archive_old_trades, fast_exit_check,
                                  settle_saas_trades)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('worker')
_worker_lock = None

def run_worker():
    logger.info("================================================================")
    logger.info("   KALSHI AI TRADER - STANDALONE BACKGROUND WORKER STARTED      ")
    logger.info("================================================================")
    
    # Single instance: two workers would each place the same orders (duplicate LIVE trades).
    from backend.database.models import CrossProcessLock
    global _worker_lock
    _worker_lock = CrossProcessLock("worker_singleton", timeout=0)
    try:
        _worker_lock.acquire()
    except TimeoutError:
        logger.error("[Worker] Another worker is already running. Exiting to avoid duplicate orders.")
        return

    # Ensure database is initialized
    init_db()
    
    # Start Forex
    try:
        start_forex_executor()
        logger.info("[Worker] Forex Engine Started.")
    except Exception as e:
        logger.error(f"[Worker] Failed to start Forex engine: {e}")
    
    # Fast stop-loss / take-profit watcher. The main loop below also evaluates every
    # asset, which takes ~10 s per round; this thread checks open trades every 1.5 s
    # so exits fire close to the user's stop level.
    import threading

    def _fast_exit_loop():
        while True:
            try:
                fast_exit_check()
            except Exception as e:
                logger.warning(f"[Worker] Fast exit check error: {e}")
            time.sleep(1.5)

    threading.Thread(target=_fast_exit_loop, daemon=True, name="FastExitWatcher").start()

    settle_tick = 0
    while True:
        try:
            for asset in ["BTC", "ETH", "GOLD"]:
                try:
                    logger.info(f"[Worker] Running loop for {asset}")
                    ae = get_auto_executor(asset)
                    ae.check_and_execute_rollover()
                    ae.evaluate_and_execute_saas_users()
                except Exception as e:
                    logger.error(f"[Worker] AutoExecutor error for {asset}: {e}")
                    traceback.print_exc()
            
            try:
                settle_saas_trades()
            except Exception as e:
                logger.error(f"[Worker] Settlement error: {e}")
                traceback.print_exc()
                
            settle_tick += 1
            if settle_tick % 60 == 0:  # Every 60 seconds
                try:
                    archive_old_trades()
                except Exception as e:
                    logger.error(f"[Worker] Archive error: {e}")
                    
        except Exception as e:
            logger.error(f"[Worker] Global loop error: {e}")
            
        time.sleep(1)

if __name__ == "__main__":
    run_worker()
