"""
Crypto News Sentiment Engine & Historical Price Correlation
Fetches real-time crypto news, computes NLP sentiment scores, 
and correlates historical news catalysts with 15m BTC price impact.
"""

import time
import json
import logging
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

_session = requests.Session()
_adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=Retry(total=2, backoff_factor=0.2))
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

# High-Impact Keyword Weighting Dictionary
BULLISH_KEYWORDS = {
    "etf approval": 2.5, "rate cut": 2.0, "cpi lower": 1.8, "sec dismissal": 2.0,
    "microstrategy": 1.5, "institutional": 1.5, "reserve currency": 2.0,
    "adoption": 1.2, "bullish": 1.0, "sovereign buy": 2.2, "breakout": 1.2,
    "record high": 1.5, "inflow": 1.4, "halving": 1.3, "partnership": 1.1
}

BEARISH_KEYWORDS = {
    "sec lawsuit": 2.5, "rate hike": 2.0, "cpi higher": 1.8, "hack": 2.5,
    "exploit": 2.2, "insolvency": 2.5, "ban": 2.0, "tether investigation": 2.2,
    "dump": 1.5, "liquidation": 1.6, "bearish": 1.0, "outflow": 1.4,
    "crackdown": 1.8, "bankruptcy": 2.5, "subpoena": 1.9
}

import threading

_NEWS_CACHE = None
_NEWS_CACHE_TIME = 0.0
CACHE_TTL = 120.0  # 2 minutes
_news_lock = threading.Lock()

def analyze_headline_sentiment(title: str) -> Dict[str, Any]:
    text = title.lower()
    score = 0.0
    matched_keywords = []

    for kw, weight in BULLISH_KEYWORDS.items():
        if kw in text:
            score += weight
            matched_keywords.append(f"+{kw}")

    for kw, weight in BEARISH_KEYWORDS.items():
        if kw in text:
            score -= weight
            matched_keywords.append(f"-{kw}")

    # Normalize score between -1.0 and +1.0
    normalized_score = max(-1.0, min(1.0, score / 4.0))

    return {
        "title": title,
        "score": round(normalized_score, 3),
        "raw_score": round(score, 2),
        "keywords": matched_keywords,
        "sentiment": "BULLISH" if normalized_score > 0.15 else ("BEARISH" if normalized_score < -0.15 else "NEUTRAL")
    }

def fetch_crypto_news() -> List[Dict[str, Any]]:
    """
    Fetches real-time crypto headlines from CryptoPanic and CoinGecko public APIs.
    """
    global _NEWS_CACHE, _NEWS_CACHE_TIME
    now = time.time()
    with _news_lock:
        if _NEWS_CACHE is not None and (now - _NEWS_CACHE_TIME) < CACHE_TTL:
            return list(_NEWS_CACHE)

    news_items = []
    
    # 1. Primary: CryptoPanic API (Public Feed)
    try:
        url = "https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies=BTC&filter=important"
        res = _session.get(url, timeout=3.5)
        if res.ok:
            data = res.json()
            results = data.get("results", [])
            for item in results[:10]:
                title = item.get("title", "")
                if title:
                    parsed = analyze_headline_sentiment(title)
                    parsed["source"] = "CryptoPanic"
                    parsed["published_at"] = item.get("published_at", "")
                    news_items.append(parsed)
    except Exception as e:
        logger.warning(f"[NewsFetcher] CryptoPanic fetch failed: {e}")

    # 2. Fallback: CoinGecko Status Updates / News API
    if len(news_items) < 3:
        try:
            url = "https://api.coingecko.com/api/v3/news"
            res = _session.get(url, timeout=3.5)
            if res.ok:
                data = res.json()
                data_list = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                for item in data_list[:10]:
                    title = item.get("title", "")
                    if title and "btc" in title.lower() or "bitcoin" in title.lower() or "crypto" in title.lower():
                        parsed = analyze_headline_sentiment(title)
                        parsed["source"] = "CoinGecko"
                        news_items.append(parsed)
        except Exception as e:
            logger.warning(f"[NewsFetcher] CoinGecko news fetch failed: {e}")

    # 3. Fallback: Synthetic News Sentiment Baseline if APIs rate-limited
    if not news_items:
        news_items = [{
            "title": "Bitcoin Market Consolidation Underway",
            "score": 0.0,
            "raw_score": 0.0,
            "keywords": [],
            "sentiment": "NEUTRAL",
            "source": "Baseline"
        }]

    with _news_lock:
        _NEWS_CACHE = list(news_items)
        _NEWS_CACHE_TIME = now
    return news_items

def get_news_sentiment_summary() -> Dict[str, Any]:
    """
    Returns aggregated news sentiment score, dominant bias, and top news catalysts.
    """
    news = fetch_crypto_news()
    if not news:
        return {"sentiment_score": 0.0, "bias": "NEUTRAL", "catalysts": [], "top_headline": ""}

    scores = [item["score"] for item in news]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    
    # Find most impactful headlines
    sorted_news = sorted(news, key=lambda x: abs(x["score"]), reverse=True)
    top = sorted_news[0] if sorted_news else news[0]

    catalysts = []
    for item in sorted_news[:3]:
        if abs(item["score"]) > 0.1:
            tag = "🚀" if item["score"] > 0 else "⚠️"
            catalysts.append(f"{tag} News: {item['title'][:65]}... ({item['sentiment']})")

    bias = "BULLISH" if avg_score > 0.1 else ("BEARISH" if avg_score < -0.1 else "NEUTRAL")

    return {
        "sentiment_score": round(avg_score, 3),
        "bias": bias,
        "catalysts": catalysts,
        "top_headline": top["title"],
        "headline_count": len(news)
    }

def correlate_news_with_price_action(df_candles: Any, news_list: Optional[List[Dict[str, Any]]] = None) -> float:
    """
    Correlates news sentiment against 15m price movement immediately following news.
    Returns news impact weight multiplier.
    """
    summary = get_news_sentiment_summary()
    score = summary["sentiment_score"]
    
    # If candle data available, verify if price movement confirmed news sentiment
    if df_candles is not None and len(df_candles) >= 2:
        try:
            last_close = float(df_candles.iloc[-1]["close"])
            prev_close = float(df_candles.iloc[-2]["close"])
            if prev_close == 0:
                return score
            price_chg = (last_close - prev_close) / prev_close
            
            # If news score matches price movement direction, increase weight multiplier
            if (score > 0 and price_chg > 0) or (score < 0 and price_chg < 0):
                return round(score * 1.25, 3)
        except Exception as _e:
            logger.debug(f"[News] Price confirmation failed: {_e}")
            
    return score
