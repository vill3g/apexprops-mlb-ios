import requests
import time
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
from typing import Dict, Any, List
from backend.database.models import get_all_active_users
from backend.database.trade_store import TradeStore

logger = logging.getLogger(__name__)

def get_predictions() -> List[Dict[str, Any]]:
    """Fetch current sports predictions from the bot-bridge."""
    try:
        resp = requests.get("http://127.0.0.1:8057/api/bot-bridge/predictions", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "predictions" in data:
            return data["predictions"]
        elif isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error(f"Failed to fetch sports predictions: {e}")
        return []

def _generate_kalshi_ticker(prediction: dict) -> str:
    """Dummy mapper to generate a unique string for the TradeStore."""
    sport = (prediction.get("sport") or "UNKNOWN").upper()
    team = (prediction.get("predicted_team") or "UNKNOWN").upper()
    meta = prediction.get("metadata") or {}
    date = meta.get("date") or "NODATE"
    if date == "NODATE":
        # Fallback to current date string if missing
        date = time.strftime("%y%m%d")
    return f"KALSHI-{sport}-{team}-{date}".replace(" ", "-")

def _check_kalshi_settlement(market_ticker: str) -> dict:
    """Dummy Kalshi API check function."""
    return {"status": "open", "result": None}

def run_sports_executor():
    """Main execution loop for sports."""
    predictions = get_predictions()
    if not predictions:
        logger.info("No sports predictions available.")
        return

    users = get_all_active_users()
    
    for user in users:
        user_id = user["id"]
        # Default configs if missing
        min_conf = float(user.get("min_sports_confidence", 70.0))
        min_edge = float(user.get("min_sports_edge", 0.0))
        max_wager = float(user.get("sports_trade_size_dollars") or user.get("sports_max_wager") or 10.0)
        include_live = bool(user.get("sports_include_live", False))
        mode = user.get("trading_mode", "PAPER").upper()

        if mode != "PAPER":
            # For now, only PAPER execution is supported based on requirements
            continue

        open_trades = TradeStore.get_open_trades(user_id)
        open_tickers = {t.get("ticker") for t in open_trades if t.get("ticker")}

        # 1. Evaluate and Execute
        for pred in predictions:
            conf = float(pred.get("confidence_pct") or 0.0)
            edge = float(pred.get("edge_pct") or 0.0)
            meta = pred.get("metadata") or {}
            is_upcoming = bool(meta.get("is_upcoming", True))
            status = str(pred.get("status") or "unknown").lower()

            # Filter logic
            if conf < min_conf or edge < min_edge:
                continue
            
            if not include_live:
                if not is_upcoming or status == "live":
                    continue
            
            market_ticker = _generate_kalshi_ticker(pred)
            
            # Paper execution check
            if market_ticker not in open_tickers:
                predicted_team = pred.get("predicted_team", "UNKNOWN")
                sport_tag = pred.get("sport", "SPORTS")
                # Derive a mock price from odds, e.g., 50 cents default
                entry_price = 0.50 
                cnt = int(max_wager / entry_price) if entry_price > 0 else 1
                
                trade = {
                    "id": f"sim_{int(time.time() * 1000)}_{user_id}_{market_ticker}",
                    "ticker": market_ticker,
                    "sport": sport_tag,
                    "asset": sport_tag,
                    "predicted_team": predicted_team,
                    "team": predicted_team,
                    "side": "YES",
                    "direction": "YES",
                    "entry_price": entry_price,
                    "count": cnt,
                    "cost": round(entry_price * cnt, 2),
                    "trade_size_dollars": max_wager,
                    "pnl": 0.0,
                    "status": "OPEN",
                    "mode": "PAPER",
                    "trading_style": "SPORTS_AI",
                    "reason": "SPORTS_PREDICTION",
                    "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "ml_reasoning": json.dumps({"confidence": conf, "sport": sport_tag, "team": predicted_team, "predicted_team": predicted_team})
                }
                
                logger.info(f"Opening sports trade for user {user_id}: {market_ticker}")
                TradeStore.insert_trade(user_id, trade)
                open_tickers.add(market_ticker)

        # 2. Settle OPEN trades
        open_trades = TradeStore.get_open_trades(user_id)
        for trade in open_trades:
            ticker = trade.get("ticker")
            if not ticker or not ticker.startswith("KALSHI-"):
                continue
                
            settlement = _check_kalshi_settlement(ticker)
            if settlement.get("status") == "determined":
                result = settlement.get("result")
                # dummy settlement logic
                if result == "YES":
                    exit_price = 1.0
                    pnl = (1.0 - float(trade.get("entry_price", 0.5))) * int(trade.get("count", 1))
                else:
                    exit_price = 0.0
                    pnl = -float(trade.get("entry_price", 0.5)) * int(trade.get("count", 1))
                    
                TradeStore.close_trade(
                    trade_id=trade["id"],
                    exit_price=exit_price,
                    pnl=pnl,
                    reason="SETTLEMENT",
                    settled_at=time.time()
                )
                logger.info(f"Settled sports trade {trade['id']} for {pnl}")

if __name__ == "__main__":
    run_sports_executor()
