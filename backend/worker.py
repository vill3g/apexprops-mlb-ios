import logging
from logging.handlers import RotatingFileHandler
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
import sys
import threading
import time
import traceback

# Add project root to sys.path
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

LOG_FILE = os.path.join(APP_DIR, "worker.log")
logger = logging.getLogger('worker')
if not logger.handlers:
    _fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")
    _fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(_fh)
    logger.setLevel(logging.INFO)
_worker_lock = None

from backend.core.registry import get_auto_executor
from backend.database.models import init_db
from backend.sports_bridge.executor import SportsBridgeExecutor
from backend.saas_settler import (archive_old_trades, fast_exit_check,
                                  settle_saas_trades)

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
    
    # Forex engine is retired/deprecated to focus resources on Crypto, Stocks & Sports
    # Forex background auto-executor loop intentionally disabled.
    
    # Fast stop-loss / take-profit watcher & settlement check.
    # Checks open trades across financial and sports universes every ~1.5 s
    # so exits and settlements fire immediately upon contract conclusion.
    sports_bridge = SportsBridgeExecutor()

    def _fast_exit_loop():
        while True:
            try:
                fast_exit_check()
            except Exception as e:
                logger.warning(f"[Worker] Fast exit check error: {e}")
            try:
                sports_bridge.settle_all_open_trades()
            except Exception as e:
                logger.debug(f"[Worker] Fast sports settlement check error: {e}")
            time.sleep(1.5)

    threading.Thread(target=_fast_exit_loop, daemon=True, name="FastExitWatcher").start()

    # Continuous Quant Lab research across both universes (alternating, rotating assets).
    try:
        from backend.engine.quant_lab.scheduler import start_quant_lab_scheduler
        start_quant_lab_scheduler()
    except Exception as e:
        logger.warning(f"[Worker] Quant Lab scheduler failed to start: {e}")

    # Sports Universe: Dedicated background execution thread so heavy network requests
    # across sports series never block or delay the 15-minute Financial candle loop.
    def _sports_cycle_loop():
        logger.info("[Worker] Sports Execution Loop initialized (continuous execution, no refresh throttling).")
        while True:
            try:
                sports_bridge.run_cycle()
            except Exception as e:
                logger.error(f"[Worker] Sports Bridge cycle error: {e}")
            time.sleep(4.0)

    threading.Thread(target=_sports_cycle_loop, daemon=True, name="SportsCycleLoop").start()

    # Investments Universe: Dedicated background execution thread for Robinhood US Stocks, ETFs & Options
    def _investments_cycle_loop():
        logger.info("[Worker] Investments Execution Loop initialized (Robinhood US Stocks, ETFs & Options).")
        try:
            from backend.investments.executor import InvestmentsExecutor
            inv_executor = InvestmentsExecutor()
        except Exception as e:
            logger.error(f"[Worker] Failed to initialize InvestmentsExecutor: {e}")
            return

        while True:
            try:
                inv_executor.run_cycle()
            except Exception as e:
                logger.error(f"[Worker] Investments cycle error: {e}")
            time.sleep(10.0)

    threading.Thread(target=_investments_cycle_loop, daemon=True, name="InvestmentsCycleLoop").start()

    # Financial Universe: Evaluates active financial assets, executes rollovers and SaaS trades
    financial_assets = ["BTC", "ETH", "GOLD", "SOL", "DOGE"]
    settle_tick = 0
    while True:
        try:
            if settle_tick % 30 == 0:
                logger.info(f"[Worker] Heartbeat: financial background worker running (cycle {settle_tick})")

            for asset in financial_assets:
                try:
                    logger.debug(f"[Worker] Running loop for {asset}")
                    ae = get_auto_executor(asset)
                    ae.check_and_execute_rollover()
                    ae.evaluate_and_execute_saas_users()
                    time.sleep(0.2)
                except Exception as e:
                    logger.error(f"[Worker] AutoExecutor error for {asset}: {e}")
                    traceback.print_exc()
            
            try:
                settle_saas_trades()
            except Exception as e:
                logger.error(f"[Worker] Settlement error: {e}")
                traceback.print_exc()
                
            settle_tick += 1
            if settle_tick % 30 == 0:  # Every 60 seconds
                try:
                    archive_old_trades()
                except Exception as e:
                    logger.error(f"[Worker] Archive error: {e}")
                    
        except Exception as e:
            logger.error(f"[Worker] Global financial loop error: {e}")

        time.sleep(1.0)

if __name__ == "__main__":
    run_worker()
