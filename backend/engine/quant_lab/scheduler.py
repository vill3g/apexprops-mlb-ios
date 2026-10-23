"""Background scheduler that keeps Quant Lab researching both trading universes."""
import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger("QuantLabScheduler")

# (asset, target_interval)
FINANCIAL_ASSETS = [
    ("BTC", "15m"), ("ETH", "15m"), ("SOL", "15m"), ("DOGE", "15m"), ("GOLD", "15m"),
]
SPORTS_ASSETS = [
    ("NFL", "GAME"), ("MLB", "GAME"), ("NHL", "GAME"), ("NBA", "GAME"), ("NCAAF", "GAME"),
    ("NPB", "GAME"), ("KBO", "GAME"), ("EPL", "GAME"), ("MLS", "GAME"), ("SOC", "GAME"),
    ("UFC", "GAME"), ("TEN", "GAME"),
]
# Metals markets are closed on weekends; skip them then.
WEEKEND_CLOSED = {"GOLD"}

DEFAULT_INTERVAL_SEC = 20 * 60


def _next_job(fin_idx: int, sp_idx: int, turn: int):
    """Alternate universes so both keep learning; rotate assets within each."""
    weekend = datetime.now(ZoneInfo("America/New_York")).weekday() >= 5
    if turn % 2 == 0:
        pool, idx = FINANCIAL_ASSETS, fin_idx
    else:
        pool, idx = SPORTS_ASSETS, sp_idx
    for _ in range(len(pool)):
        asset, interval = pool[idx % len(pool)]
        idx += 1
        if pool is FINANCIAL_ASSETS and weekend and asset in WEEKEND_CLOSED:
            continue
        return asset, interval, idx, pool is FINANCIAL_ASSETS
    return None, None, idx, pool is FINANCIAL_ASSETS


def start_quant_lab_scheduler(interval_sec: int = DEFAULT_INTERVAL_SEC) -> threading.Thread:
    def _loop():
        time.sleep(60)  # let the worker settle first
        from backend.engine.quant_lab.orchestrator import QuantLabOrchestrator
        orch = QuantLabOrchestrator()
        fin_idx = sp_idx = turn = 0
        while True:
            try:
                asset, interval, new_idx, is_fin = _next_job(fin_idx, sp_idx, turn)
                if is_fin:
                    fin_idx = new_idx
                else:
                    sp_idx = new_idx
                turn += 1
                if asset:
                    if not is_fin:
                        try:
                            from backend.engine.quant_lab.history_builder import build_history
                            build_history(asset)  # top up real settled-market history (capped, cached)
                        except Exception as _he:
                            logger.warning(f"[QuantLabScheduler] history top-up failed for {asset}: {_he}")
                    try:
                        from backend.engine.quant_lab.feedback import refresh, live_context
                        refresh()
                        _ctx = live_context(asset)
                        if _ctx:
                            logger.info(f"[QuantLabScheduler] {_ctx}")
                    except Exception as _fe:
                        logger.warning(f"[QuantLabScheduler] live feedback refresh failed: {_fe}")
                    logger.info(f"[QuantLabScheduler] Running scheduled cycle: {asset} ({interval})")
                    res = orch.run_research_cycle(asset=asset, target_interval=interval)
                    logger.info(f"[QuantLabScheduler] {asset} -> {res.get('result') or res.get('status')}")
            except Exception as e:
                logger.warning(f"[QuantLabScheduler] cycle error: {e}")
            time.sleep(interval_sec)

    t = threading.Thread(target=_loop, daemon=True, name="QuantLabScheduler")
    t.start()
    return t
