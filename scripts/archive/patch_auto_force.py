import os
import json
import logging
import sqlite3
import uuid
import time
from backend.database.models import DATA_DIR, DB_PATH, get_all_active_users, update_user_paper_balance
from backend.auth.security import decrypt_kalshi_key
from backend.btc.kalshi_trader import KalshiTrader
from backend.btc.kalshi_client import get_kalshi_15m_market
from backend.main import get_cached_btc_analysis

logger = logging.getLogger(__name__)

def process_auto_force_trades():
    try:
        users = get_all_active_users()
        if not users: return
        
        # filter users who have auto_force_trade = 1
        force_users = [u for u in users if u.get('auto_force_trade') == 1]
        if not force_users: return
        
        market = get_kalshi_15m_market()
        if not market or market.get("status") != "active":
            return
            
        ticker = market.get("ticker")
        
        try:
            _, analysis = get_cached_btc_analysis(asset="BTC", timeframe="15m")
        except Exception:
            return
            
        signal = analysis.get("signal", "HOLD")
        if signal not in ["BUY", "SELL"]:
            return
            
        direction = "YES" if signal == "BUY" else "NO"
        price = market.get("yes_ask" if direction == "YES" else "no_ask")
        if not price or price <= 0:
            return

        for user in force_users:
            user_id = user['id']
            hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
            history = []
            if os.path.exists(hist_path):
                try:
                    with open(hist_path, 'r') as f:
                        history = json.load(f)
                except: pass
                
            # Check if already traded this ticker
            already_traded = any(t.get('ticker') == ticker for t in history)
            if already_traded:
                continue
                
            # Execute trade!
            mode = user.get("trading_mode", "PAPER")
            trade_size_pct = float(user.get("trade_size_pct", 20.0)) / 100.0
            trade_id = str(uuid.uuid4())
            count = 0
            
            if mode == "LIVE":
                if not user.get('kalshi_key_id') or not user.get('kalshi_priv_key_encrypted'):
                    continue
                priv = decrypt_kalshi_key(user['kalshi_priv_key_encrypted'])
                kt = KalshiTrader(key_id=user['kalshi_key_id'], private_key_pem=priv)
                if not kt.is_authenticated():
                    continue
                    
                bal_res = kt.get_balance()
                if not bal_res.get('success'):
                    continue
                avail_bal = float(bal_res.get('balance_dollars', 0.0))
                risk_amount = avail_bal * trade_size_pct
                count = max(1, int(risk_amount / max(0.01, price)))
                
                res = kt.place_order(
                    ticker=ticker,
                    side="yes" if direction=="YES" else "no",
                    count=count,
                    limit_price_dollars=price,
                    dry_run=False
                )
                if not res.get('success'):
                    continue
            else:
                avail_bal = float(user.get('paper_balance', 500.0))
                risk_amount = avail_bal * trade_size_pct
                count = max(1, int(risk_amount / max(0.01, price)))
                cost = count * price
                if cost > avail_bal:
                    continue
                update_user_paper_balance(user_id, avail_bal - cost)

            history.append({
                "id": trade_id,
                "ticker": ticker,
                "side": direction,
                "count": count,
                "entry_price": price,
                "status": "OPEN",
                "timestamp": time.time(),
                "mode": mode,
                "reason": "AUTO_FORCE_TRADE"
            })
            
            with open(hist_path, 'w') as f:
                json.dump(history, f, indent=4)
                
            logger.info(f"[AutoForceTrade] Executed {count} {direction} on {ticker} for user {user.get('username')}")
    except Exception as e:
        logger.error(f"[AutoForceTrade] Error: {e}")
