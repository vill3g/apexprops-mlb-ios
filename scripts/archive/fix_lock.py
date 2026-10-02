import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the outer try/finally
content = content.replace("""        if not self._rollover_lock.acquire(blocking=False):
            logger.debug("[AutoExecutor] Rollover evaluation already in progress by another worker. Skipping concurrent execution.")
            return None

        try:""", """        if not self._rollover_lock.acquire(blocking=False):
            logger.debug("[AutoExecutor] Rollover evaluation already in progress by another worker. Skipping concurrent execution.")
            return None

        lock_held = True
        try:""")

content = content.replace("""            return None
        finally:
            self._rollover_lock.release()

    def execute_manual_trade""", """            return None
        finally:
            if lock_held:
                self._rollover_lock.release()

    def execute_manual_trade""")

# Replace the inner exec delay
content = content.replace("""                self._rollover_lock.release()
                try:
                    time.sleep(exec_delay)
                finally:
                    if not self._rollover_lock.acquire(blocking=True, timeout=10):
                        logger.error("[AutoExecutor] Could not re-acquire rollover lock after exec_delay sleep; aborting trade.")
                        return None""", """                self._rollover_lock.release()
                lock_held = False
                try:
                    time.sleep(exec_delay)
                finally:
                    lock_held = self._rollover_lock.acquire(blocking=True, timeout=10)
                    if not lock_held:
                        logger.error("[AutoExecutor] Could not re-acquire rollover lock after exec_delay sleep; aborting trade.")
                        return None""")

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
