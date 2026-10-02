"""
Thread-safe analysis cache and JSON sanitization service.
Decouples the market analysis caching from the web application layer (main.py)
to eliminate circular import dependencies between API routes, trading executors,
and settlement services.
"""

import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import pandas as pd

from backend.btc.analyzer.confluence import analyze_btc
from backend.engine.multi_asset_fetcher import fetch_asset_candles

logger = logging.getLogger(__name__)

btc_timeframe_cache: Dict[str, Any] = {}
_btc_cache_lock = threading.Lock()


def get_cached_btc_analysis(asset: str = "BTC", timeframe: str = "15m", max_age_seconds: int = 10) -> Tuple[Any, Dict[str, Any]]:
    """Retrieve or compute BTC analysis with smart per-timeframe caching."""
    now = time.time()
    tf = timeframe.lower()
    cache_key = f"{asset}_{tf}"
    with _btc_cache_lock:
        if cache_key in btc_timeframe_cache and (now - btc_timeframe_cache[cache_key]["last_fetched"]) < max_age_seconds:
            if btc_timeframe_cache[cache_key].get("df") is not None:
                return btc_timeframe_cache[cache_key]["df"], btc_timeframe_cache[cache_key]["analysis"]

    try:
        df = fetch_asset_candles(asset, timeframe=tf, limit=1000)
        analysis = analyze_btc(df, asset=asset, timeframe=tf)
        analysis["generated_at"] = datetime.now(timezone.utc).isoformat()
        
        with _btc_cache_lock:
            btc_timeframe_cache[cache_key] = {
                "df": df,
                "analysis": analysis,
                "last_fetched": time.time()
            }
        return df, analysis
    except Exception as e:
        logger.error(f"Error fetching live BTC candles for {tf}: {e}")
        with _btc_cache_lock:
            if cache_key in btc_timeframe_cache and btc_timeframe_cache[cache_key].get("df") is not None:
                return btc_timeframe_cache[cache_key]["df"], btc_timeframe_cache[cache_key]["analysis"]
        raise e


def sanitize_btc_json(val: Any) -> Any:
    """Recursively convert NumPy scalars/types to standard Python types for JSON serialization.

    Also strips NaN/Infinity floats (-> 0.0), since Python's json module emits the
    non-standard `NaN`/`Infinity` tokens for these, which are NOT valid JSON and will
    throw a SyntaxError in the browser's JSON.parse().
    """
    if isinstance(val, dict):
        return {k: sanitize_btc_json(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [sanitize_btc_json(v) for v in val]
    elif hasattr(val, "item"):
        val = val.item()

    if isinstance(val, pd.Timestamp):
        return str(val)
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return 0.0
    return val
