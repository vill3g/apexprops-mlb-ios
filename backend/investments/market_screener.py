"""
Automated Dynamic Market Screener for US Equities & ETFs
Scans across the broader US equity market for intraday "in-play" stocks:
1. Day Gainers & Volume Leaders (Unusual Relative Volume)
2. Day Losers / Reversals (Oversold Bounce / Short Setups)
3. Most Active (Mega/Large-Cap institutional order flow)

Filters out:
- Micro-caps / OTC penny stocks (price < $5.00)
- Illiquid tickers (Volume < 500,000 shares)
- Leveraged warrants, warrants, and foreign share classes containing symbols like '.', '-', '^'
- Stale or untradeable symbols

Supports 3 Screener Modes:
- 'WATCHLIST_ONLY': Strictly scans the user's manual watchlist.
- 'DYNAMIC_SCREENER': Discovers the top 10-15 in-play stocks across the entire market.
- 'HYBRID': Retains the user's core anchor tickers (e.g. SPY, QQQ, NVDA) AND merges the top dynamic momentum runners.
"""

import logging
import time
from typing import Dict, List, Optional, Any
import requests

logger = logging.getLogger(__name__)

DEFAULT_ANCHORS = ["SPY", "QQQ", "NVDA", "TSLA"]


class DynamicMarketScreener:
    """Discovers high-liquidity, high-momentum intraday trade candidates across US equities."""

    _cache_ts: float = 0.0
    _cached_symbols: List[str] = []
    _cached_metadata: Dict[str, Dict[str, Any]] = {}
    CACHE_TTL_SECONDS: float = 60.0  # Refresh screener every 60 seconds

    @classmethod
    def discover_in_play_stocks(
        cls,
        min_price: float = 5.0,
        max_price: float = 1000.0,
        min_volume: int = 500_000,
        limit: int = 15,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Discovers top momentum and high-volume stocks currently in-play.
        Returns a list of dictionaries with symbol, price, change_pct, volume, and screener tag.
        """
        now = time.time()
        if not force_refresh and (now - cls._cache_ts) < cls.CACHE_TTL_SECONDS and cls._cached_symbols:
            return [cls._cached_metadata[s] for s in cls._cached_symbols if s in cls._cached_metadata][:limit]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        discovered: Dict[str, Dict[str, Any]] = {}

        # Screeners to query
        endpoints = [
            ("day_gainers", "🔥 TOP GAINER"),
            ("most_actives", "⚡ HIGH VOLUME"),
            ("day_losers", "📉 DIP REVERSAL")
        ]

        for scr_id, tag in endpoints:
            url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&scrIds={scr_id}&count=25"
            try:
                resp = requests.get(url, headers=headers, timeout=4.0)
                if resp.status_code == 200:
                    data = resp.json()
                    quotes = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
                    for q in quotes:
                        sym = str(q.get("symbol") or "").strip().upper()
                        if not sym:
                            continue
                        # Filter foreign classes, indices, futures, warrants
                        if any(c in sym for c in [".", "-", "=", "^", "/", "+"]):
                            continue
                        # Clean symbol length
                        if len(sym) > 5:
                            continue

                        px = float(q.get("regularMarketPrice") or 0.0)
                        chg_pct = float(q.get("regularMarketChangePercent") or 0.0)
                        vol = int(q.get("regularMarketVolume") or 0)

                        if px < min_price or px > max_price:
                            continue
                        if vol < min_volume:
                            continue

                        if sym not in discovered:
                            discovered[sym] = {
                                "symbol": sym,
                                "price": px,
                                "change_pct": round(chg_pct, 2),
                                "volume": vol,
                                "tag": tag,
                                "screener_source": scr_id
                            }
            except Exception as e:
                logger.debug(f"[DynamicMarketScreener] Error querying {scr_id}: {e}")

        # Rank candidates by a composite momentum score: |change_pct| * log10(volume)
        import math
        candidates = list(discovered.values())
        candidates.sort(
            key=lambda x: abs(x["change_pct"]) * math.log10(max(x["volume"], 1000)),
            reverse=True
        )

        top_candidates = candidates[:limit]
        cls._cache_ts = now
        cls._cached_symbols = [c["symbol"] for c in top_candidates]
        cls._cached_metadata = {c["symbol"]: c for c in top_candidates}

        return top_candidates

    @classmethod
    def resolve_tradeable_symbols(
        cls,
        user_config: Dict[str, Any],
        force_refresh: bool = False
    ) -> List[str]:
        """
        Resolves the final list of tradeable symbols based on user's screener mode setting:
        - 'WATCHLIST_ONLY': User's watchlist only
        - 'DYNAMIC_SCREENER': Discovered top in-play market movers only
        - 'HYBRID' (default): Core watchlist anchors + top in-play dynamic movers
        """
        screener_mode = str(user_config.get("investments_screener_mode") or "HYBRID").upper()
        raw_watchlist = str(user_config.get("investments_watchlist") or "SPY,QQQ,NVDA,TSLA,AAPL,META,AMD,AMZN,MSFT,IWM")
        watchlist_symbols = [s.strip().upper() for s in raw_watchlist.split(",") if s.strip()]

        if screener_mode == "WATCHLIST_ONLY":
            return watchlist_symbols

        try:
            in_play = cls.discover_in_play_stocks(limit=12, force_refresh=force_refresh)
            in_play_symbols = [item["symbol"] for item in in_play]
        except Exception as e:
            logger.warning(f"[DynamicMarketScreener] Screener discovery fallback to watchlist: {e}")
            return watchlist_symbols

        if screener_mode == "DYNAMIC_SCREENER":
            return in_play_symbols if in_play_symbols else watchlist_symbols

        # HYBRID mode: Combine core watchlist symbols with dynamic in-play runners (deduplicated preserving order)
        combined = []
        seen = set()

        for s in watchlist_symbols:
            if s not in seen:
                seen.add(s)
                combined.append(s)

        for s in in_play_symbols:
            if s not in seen and len(combined) < 20:
                seen.add(s)
                combined.append(s)

        return combined
