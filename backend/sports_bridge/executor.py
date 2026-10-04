import time
import logging
import uuid
import json
import kalshi_python
from backend.sports_bridge.prediction_client import SportsPredictionClient
from backend.sports_bridge.kalshi_mapper import KalshiMapper
from backend.database.models import get_all_active_users, get_db_connection
from backend.btc.kalshi_trader import kalshi_trader

logger = logging.getLogger(__name__)

def _generate_kalshi_ticker(prediction: dict) -> str:
    """Uses Kalshi API to find the exact event ticker."""
    sport = (prediction.get("sport") or "UNKNOWN").upper()
    team = (prediction.get("predicted_team") or "UNKNOWN").upper()
    meta = prediction.get("metadata") or {}
    date = meta.get("date") or "NODATE"
    
    def get_dummy():
        d = date
        if d == "NODATE":
            d = time.strftime("%y%m%d")
        return f"KALSHI-{sport}-{team}-{d}".replace(" ", "-")

    try:
        config = kalshi_python.Configuration()
        config.host = 'https://api.elections.kalshi.com/trade-api/v2'
        api_client = kalshi_python.ApiClient(config)
        events_api = kalshi_python.EventsApi(api_client)
        
        response = events_api.get_events(series_ticker=sport, with_nested_markets=True)
        for event in getattr(response, 'events', []):
            title = getattr(event, 'title', '').lower()
            event_ticker = getattr(event, 'event_ticker', '').lower()
            if team.lower() in title or team.lower() in event_ticker:
                markets = getattr(event, 'markets', [])
                if markets:
                    return getattr(markets[0], 'ticker', getattr(event, 'event_ticker', get_dummy()))
                return getattr(event, 'event_ticker', get_dummy())
        
        return get_dummy()
    except Exception as e:
        if isinstance(e, kalshi_python.ApiException) and getattr(e, 'status', None) == 429:
            logger.warning("Kalshi API 429 Too Many Requests. Falling back to dummy ticker.")
        else:
            logger.error(f"Error fetching Kalshi ticker: {e}")
        return get_dummy()

def _check_kalshi_settlement(market_ticker: str) -> dict:
    """Uses Kalshi API to check if market is determined."""
    try:
        config = kalshi_python.Configuration()
        config.host = 'https://api.elections.kalshi.com/trade-api/v2'
        api_client = kalshi_python.ApiClient(config)
        markets_api = kalshi_python.MarketsApi(api_client)
        
        market_response = markets_api.get_market(market_ticker)
        market = getattr(market_response, 'market', market_response)
        
        status = getattr(market, 'status', 'open')
        result = getattr(market, 'result', None)
        return {"status": status, "result": result}
    except Exception as e:
        if isinstance(e, kalshi_python.ApiException) and getattr(e, 'status', None) == 429:
            logger.warning("Kalshi API 429 Too Many Requests during settlement check.")
        elif isinstance(e, kalshi_python.ApiException) and getattr(e, 'status', None) == 404:
            logger.warning(f"Market not found on Kalshi: {market_ticker}")
        else:
            logger.error(f"Error checking Kalshi settlement for {market_ticker}: {e}")
        return {"status": "open", "result": None}

class SportsBridgeExecutor:
    def __init__(self):
        self.client = SportsPredictionClient()
        self.last_check = 0
        
    def run_cycle(self):
        now = time.time()
        if now - self.last_check < 60:
            return
        self.last_check = now
        
        users = get_all_active_users()
        sports_users = [u for u in users if u.get("trading_universe") == "SPORTS"]
        if not sports_users:
            return
            
        logger.info(f"[SportsBridge] Found {len(sports_users)} active sports users. Fetching predictions...")
        picks = self.client.fetch_latest_picks()
        if not picks:
            return
            
        for u in sports_users:
            try:
                self._process_user(u, picks)
                self._settle_open_trades(u)
            except Exception as e:
                logger.error(f"[SportsBridge] Error processing user {u.get('id')}: {e}")

    def _process_user(self, user, picks):
        uid = user["id"]
        min_conf = float(user.get("min_sports_confidence") or 70.0)
        min_edge = float(user.get("min_sports_edge") or 0.0)
        max_wager = float(user.get("sports_max_wager") or 5.0)
        include_live = bool(user.get("sports_include_live") or False)
        mode = user.get("trading_mode") or "PAPER"
        
        if mode != "PAPER":
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all open tickers
        cursor.execute("SELECT market_ticker FROM trades WHERE user_id = ? AND status = 'open' AND asset = 'SPORTS'", (uid,))
        open_tickers = {row[0] for row in cursor.fetchall() if row[0]}
        
        for pred in picks:
            conf = float(pred.get("confidence_pct") or 0.0)
            edge = float(pred.get("edge_pct") or 0.0)
            meta = pred.get("metadata") or {}
            is_upcoming = bool(meta.get("is_upcoming", True))
            status = str(pred.get("status") or "unknown").lower()

            if conf < min_conf or edge < min_edge:
                continue
            
            if not include_live:
                if not is_upcoming or status == "live":
                    continue
            
            # For now use the dummy ticker since bridge is generating predictions without market_ticker
            # Later this uses KalshiMapper
            ticker = _generate_kalshi_ticker(pred)
            
            if ticker not in open_tickers:
                predicted_team = pred.get("predicted_team", "UNKNOWN")
                sport = pred.get("sport", "UNKNOWN")
                price = 0.50 
                
                trade_id = str(uuid.uuid4())
                
                logger.info(f"[SportsBridge] Executing {mode} trade for user {uid} on {ticker}")
                
                cursor.execute('''
                    INSERT INTO trades (
                        id, user_id, market_ticker, direction, mode, 
                        entry_price, contracts, status, initial_risk_amount,
                        asset, execution_time, details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade_id, uid, ticker, "YES", mode,
                    price, int(max_wager / max(price, 0.01)), "open", max_wager,
                    "SPORTS", time.time(), json.dumps({"confidence": conf, "sport": sport, "team": predicted_team})
                ))
                conn.commit()
                open_tickers.add(ticker)
        
        conn.close()

    def _settle_open_trades(self, user):
        uid = user["id"]
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, market_ticker, entry_price, contracts FROM trades WHERE user_id = ? AND status = 'open' AND asset = 'SPORTS'", (uid,))
        open_trades = cursor.fetchall()
        
        for row in open_trades:
            t_id, ticker, entry_price, contracts = row
            if not ticker or not ticker.startswith("KALSHI-"):
                continue
                
            settlement = _check_kalshi_settlement(ticker)
            if settlement.get("status") == "determined":
                result = settlement.get("result")
                if result == "YES":
                    exit_price = 1.0
                    pnl = (1.0 - float(entry_price or 0.5)) * int(contracts or 1)
                else:
                    exit_price = 0.0
                    pnl = -float(entry_price or 0.5) * int(contracts or 1)
                    
                cursor.execute("UPDATE trades SET status = 'closed', exit_price = ?, pnl = ?, closing_reason = ?, settled_at = ? WHERE id = ?",
                               (exit_price, pnl, "SETTLEMENT", time.time(), t_id))
                conn.commit()
                logger.info(f"[SportsBridge] Settled sports trade {t_id} for {pnl}")
        
        conn.close()
