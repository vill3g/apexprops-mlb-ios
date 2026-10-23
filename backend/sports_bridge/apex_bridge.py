"""
Direct In-Process ApexProps Sports AI Bridge.

Provides zero-latency, in-process access to the ApexProps sports prediction
engines and quantitative simulation modules, eliminating localhost HTTP roundtrip
latencies and socket timeout failures.
"""

import os
import sys
import json
import time
import logging
import threading
import importlib.util
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_APEX_DIR = os.getenv("APEXPROPS_DIR", r"C:\Users\Vill3\.gemini\antigravity\scratch\apexprops-mlb-ios")
_APEX_BACKEND = os.path.join(_APEX_DIR, "backend")
_APEX_ENGINE = os.path.join(_APEX_BACKEND, "engine")
_APEX_DATA = os.path.join(_APEX_BACKEND, "data")

_MEM_CACHE: Dict[str, Tuple[float, List[Dict]]] = {}
_MEM_LOCK = threading.Lock()
_CACHE_TTL = 60.0  # seconds

_PATHS_INITIALIZED = False
_INIT_LOCK = threading.Lock()


def ensure_apex_paths() -> bool:
    """Merges ApexProps backend, engine, and data directories into Python package paths."""
    global _PATHS_INITIALIZED
    if _PATHS_INITIALIZED:
        return True

    with _INIT_LOCK:
        if _PATHS_INITIALIZED:
            return True

        if not os.path.exists(_APEX_BACKEND):
            logger.warning(f"[ApexBridge] ApexProps backend directory not found at {_APEX_BACKEND}")
            return False

        try:
            import backend
            if hasattr(backend, "__path__") and _APEX_BACKEND not in backend.__path__:
                backend.__path__.append(_APEX_BACKEND)

            import backend.engine
            if hasattr(backend.engine, "__path__") and os.path.exists(_APEX_ENGINE):
                if _APEX_ENGINE not in backend.engine.__path__:
                    backend.engine.__path__.append(_APEX_ENGINE)

            import backend.data
            if hasattr(backend.data, "__path__") and os.path.exists(_APEX_DATA):
                if _APEX_DATA not in backend.data.__path__:
                    backend.data.__path__.append(_APEX_DATA)

            if _APEX_BACKEND not in sys.path:
                sys.path.append(_APEX_BACKEND)

            _PATHS_INITIALIZED = True
            logger.info("[ApexBridge] Successfully initialized direct in-process ApexProps engine paths.")
            return True
        except Exception as e:
            logger.error(f"[ApexBridge] Failed to merge ApexProps package paths: {e}")
            return False


_REFRESH_IN_PROGRESS = False
_REFRESH_LOCK = threading.Lock()


def _sanitize_picks(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Recovers actual team name if predicted_team was accidentally populated with full matchup string."""
    cleaned = []
    for p in (picks or []):
        if not isinstance(p, dict):
            continue
        p_copy = dict(p)
        pt = str(p_copy.get("predicted_team") or "").strip()
        meta = p_copy.get("metadata") or {}
        if (" @ " in pt or " vs " in pt.lower()) and isinstance(meta, dict):
            real_team = (
                meta.get("team")
                or meta.get("ensemble_pick")
                or meta.get("best_pick_name")
                or meta.get("pick")
                or meta.get("predicted_team")
            )
            if real_team and " @ " not in str(real_team) and " vs " not in str(real_team).lower():
                p_copy["predicted_team"] = str(real_team).strip()
                meta_copy = dict(meta)
                meta_copy["name"] = str(real_team).strip()
                p_copy["metadata"] = meta_copy
        cleaned.append(p_copy)
    return cleaned


def _save_disk_cache(picks: List[Dict[str, Any]]) -> None:
    try:
        picks = _sanitize_picks(picks)
        os.makedirs(_APEX_DATA, exist_ok=True)
        disk_cache_file = os.path.join(_APEX_DATA, "latest_bot_predictions.json")
        tmp_file = disk_cache_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({"predictions": picks, "updated_at": time.time()}, f)
        os.replace(tmp_file, disk_cache_file)
    except Exception as e:
        logger.debug(f"[ApexBridge] Disk cache write exception: {e}")


def _fetch_predictions_sync(http_fallback_url: str, http_timeout: float = 6.0, allow_in_process: bool = True) -> List[Dict[str, Any]]:
    now = time.time()
    cache_key = "latest_sports_picks"
    ensure_apex_paths()

    # Path B: HTTP localhost request to running ApexProps server
    try:
        import requests
        resp = requests.get(http_fallback_url, timeout=http_timeout)
        if resp.status_code == 200:
            data = resp.json()
            picks = _sanitize_picks(data.get("predictions", []))
            if picks:
                with _MEM_LOCK:
                    _MEM_CACHE[cache_key] = (now, list(picks))
                _save_disk_cache(picks)
                _record_predictions_async(picks)
                return list(picks)
    except Exception as e:
        logger.debug(f"[ApexBridge] HTTP fetch to {http_fallback_url} skipped: {e}")

    if not allow_in_process:
        return []

    # Fallback Path C: Direct in-process execution of bot_bridge_router (background only)
    router_file = os.path.join(_APEX_BACKEND, "bot_bridge_router.py")
    if os.path.exists(router_file):
        try:
            if "apex_bot_bridge" not in sys.modules:
                spec = importlib.util.spec_from_file_location("apex_bot_bridge", router_file)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules["apex_bot_bridge"] = mod
                    spec.loader.exec_module(mod)
            else:
                mod = sys.modules["apex_bot_bridge"]

            if hasattr(mod, "get_bot_predictions"):
                res = mod.get_bot_predictions(include_live=False)
                picks = _sanitize_picks(res.get("predictions", []) if isinstance(res, dict) else [])
                if picks:
                    with _MEM_LOCK:
                        _MEM_CACHE[cache_key] = (time.time(), list(picks))
                    _save_disk_cache(picks)
                    _record_predictions_async(picks)
                    return list(picks)
        except Exception as e:
            logger.debug(f"[ApexBridge] Direct in-process execution failed: {e}")

    return []


def _trigger_bg_refresh(http_fallback_url: str) -> None:
    global _REFRESH_IN_PROGRESS
    with _REFRESH_LOCK:
        if _REFRESH_IN_PROGRESS:
            return
        _REFRESH_IN_PROGRESS = True

    def _bg():
        global _REFRESH_IN_PROGRESS
        try:
            _fetch_predictions_sync(http_fallback_url, http_timeout=8.0, allow_in_process=True)
        finally:
            with _REFRESH_LOCK:
                _REFRESH_IN_PROGRESS = False

    threading.Thread(target=_bg, daemon=True, name="ApexBridgeRefresh").start()


def get_sports_predictions(force_refresh: bool = False, http_fallback_url: str = "http://127.0.0.1:8057/api/bot-bridge/predictions") -> List[Dict[str, Any]]:
    """
    Retrieves latest sports predictions via high-speed, non-blocking paths:
    1. Memory cache (< 0.1ms)
    2. Shared disk cache file (< 2ms)
    3. Fast HTTP check (1.5s max) + asynchronous background refresh
    """
    now = time.time()
    cache_key = "latest_sports_picks"

    with _MEM_LOCK:
        if cache_key in _MEM_CACHE:
            cached_time, cached_data = _MEM_CACHE[cache_key]
            if not force_refresh and (now - cached_time < _CACHE_TTL):
                return list(cached_data)
            # Stale-while-revalidate: trigger background refresh and return cached immediately
            if cached_data:
                _trigger_bg_refresh(http_fallback_url)
                return list(cached_data)

    ensure_apex_paths()

    # Fast Path A: Shared disk cache file
    disk_cache_file = os.path.join(_APEX_DATA, "latest_bot_predictions.json")
    if os.path.exists(disk_cache_file):
        try:
            mtime = os.path.getmtime(disk_cache_file)
            with open(disk_cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            picks = _sanitize_picks(data.get("predictions", []))
            if picks:
                with _MEM_LOCK:
                    _MEM_CACHE[cache_key] = (now if (now - mtime < _CACHE_TTL) else mtime, list(picks))
                if force_refresh or (now - mtime >= _CACHE_TTL):
                    _trigger_bg_refresh(http_fallback_url)
                else:
                    _record_predictions_async(picks)
                return list(picks)
        except Exception as e:
            logger.debug(f"[ApexBridge] Disk cache read exception: {e}")

    # Cold start: try fast HTTP request (1.5s max), never block on in-process model execution
    picks = _fetch_predictions_sync(http_fallback_url, http_timeout=1.5, allow_in_process=False)
    if picks:
        return picks

    # Trigger background refresh (which can wait for 8057 or run in-process) and return immediately
    _trigger_bg_refresh(http_fallback_url)
    with _MEM_LOCK:
        if cache_key in _MEM_CACHE:
            return list(_MEM_CACHE[cache_key][1])
    return []


def _record_predictions_async(picks: List[Dict[str, Any]]) -> None:
    """Asynchronously archives model predictions into quant_lab.db sports_history."""
    def _worker():
        try:
            from backend.engine.quant_lab.history_builder import record_sports_ai_prediction
            for p in picks:
                meta = p.get("metadata") or {}
                ticker = meta.get("kalshi_ticker") or meta.get("ticker") or meta.get("game_id")
                if not ticker:
                    continue
                sport = p.get("sport") or meta.get("league") or "SPORTS"
                conf = float(p.get("confidence_pct") or meta.get("prob") or 50.0)
                edge = float(p.get("edge_pct") or meta.get("edge") or 0.0)
                score = float(meta.get("confidence_score") or conf)
                sim_score = float(meta.get("sim_score") or meta.get("sim_edge") or 0.0)
                name = p.get("predicted_team") or meta.get("name")
                record_sports_ai_prediction(
                    ticker=str(ticker),
                    sport=str(sport),
                    ai_win_prob=conf,
                    ai_edge=edge,
                    confidence_score=score,
                    sim_score=sim_score,
                    name=str(name) if name else None,
                )
        except Exception as e:
            logger.debug(f"[ApexBridge] Async prediction logging error: {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# ---------------- Direct In-Process Engine Simulators ----------------

def simulate_mlb_match(home_starter: str, away_starter: str, home_team: str, away_team: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Runs ApexProps God-Tier MLB simulation directly in-process."""
    ensure_apex_paths()
    try:
        from backend.engine.mlb_god_tier_sim import simulate_mlb_game
        return simulate_mlb_game(home_starter, away_starter, home_team, away_team, **kwargs)
    except Exception as e:
        logger.error(f"[ApexBridge] In-process MLB simulation error: {e}")
        return None


def simulate_nhl_match(home_team: str, away_team: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Runs ApexProps NHL Poisson/Negative Binomial simulation directly in-process."""
    ensure_apex_paths()
    try:
        from backend.engine.hockey_simulator import simulate_hockey_match
        return simulate_hockey_match(home_team, away_team, **kwargs)
    except Exception as e:
        logger.error(f"[ApexBridge] In-process NHL simulation error: {e}")
        return None


def simulate_nfl_match(home_team: str, away_team: str, spread: float = 0.0, total: float = 44.5, **kwargs) -> Optional[Dict[str, Any]]:
    """Runs ApexProps NFL Key Numbers & Poisson simulation directly in-process."""
    ensure_apex_paths()
    try:
        from backend.engine.nfl_simulator import simulate_nfl_matchup
        return simulate_nfl_matchup(home_team, away_team, spread=spread, total=total, **kwargs)
    except Exception as e:
        logger.error(f"[ApexBridge] In-process NFL simulation error: {e}")
        return None


def simulate_ufc_bout(fighter_a: str, fighter_b: str, division: str = "Welterweight", **kwargs) -> Optional[Dict[str, Any]]:
    """Runs ApexProps UFC Empirical simulation directly in-process."""
    ensure_apex_paths()
    try:
        from backend.engine.ufc_simulator import simulate_ufc_fight
        return simulate_ufc_fight(fighter_a, fighter_b, division=division, **kwargs)
    except Exception as e:
        logger.error(f"[ApexBridge] In-process UFC simulation error: {e}")
        return None


def get_apex_status() -> Dict[str, Any]:
    """Returns the operational status of the direct in-process ApexProps bridge."""
    return {
        "apex_dir": _APEX_DIR,
        "apex_backend_exists": os.path.exists(_APEX_BACKEND),
        "apex_engine_exists": os.path.exists(_APEX_ENGINE),
        "apex_data_exists": os.path.exists(_APEX_DATA),
        "paths_initialized": _PATHS_INITIALIZED,
        "cached_picks_count": len(_MEM_CACHE.get("latest_sports_picks", (0, []))[1]),
        "cache_ttl_sec": _CACHE_TTL,
    }
