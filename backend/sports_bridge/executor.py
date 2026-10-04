import logging
import time
from backend.sports_bridge.prediction_client import SportsPredictionClient
from backend.sports_bridge.kalshi_mapper import KalshiMapper
from backend.database.models import get_all_active_users, get_db_connection
from backend.btc.kalshi_trader import kalshi_trader
import uuid
import json

logger = logging.getLogger(__name__)

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
            except Exception as e:
                logger.error(f"[SportsBridge] Error processing user {u.get('id')}: {e}")

    def _process_user(self, user, picks):
        uid = user["id"]
        min_conf = float(user.get("min_sports_confidence", 70.0))
        mode = user.get("trading_mode", "PAPER")
        trade_size = float(user.get("paper_trade_size_dollars", 50.0)) if mode == "PAPER" else float(user.get("trade_size_dollars", 5.0))
        
        valid_picks = [p for p in picks if p["confidence_pct"] >= min_conf]
        if not valid_picks:
            return
            
        best_pick = valid_picks[0]
        sport = best_pick["sport"]
        team = best_pick["predicted_team"]
        
        k_key = user.get("kalshi_key_id")
        k_priv = user.get("kalshi_priv_key_encrypted")
        if not k_key or not k_priv:
            return
            
        ticker = KalshiMapper.get_kalshi_ticker(kalshi_trader, sport, team)
        if not ticker:
            return
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM trades WHERE user_id = ? AND market_ticker = ? AND status = 'open'", (uid, ticker))
        if cursor.fetchone():
            return
            
        logger.info(f"[SportsBridge] Executing {mode} trade for user {uid} on {ticker}")
        
        trade_id = str(uuid.uuid4())
        price = 0.50 
        cursor.execute('''
            INSERT INTO trades (
                id, user_id, market_ticker, direction, mode, 
                entry_price, contracts, status, initial_risk_amount,
                asset, execution_time, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_id, uid, ticker, "YES", mode,
            price, int(trade_size / max(price, 0.01)), "open", trade_size,
            "SPORTS", time.time(), json.dumps({"confidence": best_pick["confidence_pct"], "sport": sport})
        ))
        conn.commit()
