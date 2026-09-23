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

def settle_saas_trades():
    try:
        users = get_all_active_users()
        if not users:
            return
            
        market = get_kalshi_15m_market()
        for user in users:
            user_id = user['id']
            mode = user.get("trading_mode", "PAPER")
            hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
            
            if not os.path.exists(hist_path):
                continue
                
            try:
                with open(hist_path, 'r') as f:
                    trades = json.load(f)
            except Exception:
                continue
                
            modified = False
            for t in trades:
                if t.get("status") != "OPEN":
                    continue
                    
                ticker = t.get("ticker")
                side = t.get("side", "YES").lower()
                entry = float(t.get("entry_price", 0.0))
                count = int(t.get("count", 0))
                sl_pct = float(user.get("stop_loss_pct", 10.0)) / 100.0
                
                if not market or market.get("status") != "active" or market.get("ticker") != ticker:
                    from backend.btc.kalshi_trader import kalshi_trader
                    res = kalshi_trader.get_market_result(ticker)
                    ans = res.get("result", "").lower()
                    
                    exit_price = 0.0
                    if ans == "yes":
                        exit_price = 1.0 if side.upper() == "YES" else 0.0
                    elif ans == "no":
                        exit_price = 1.0 if side.upper() == "NO" else 0.0
                    else:
                        # Unresolved or synthetic. Try to fallback to probability just to close it out if it's super old, but for now we'll wait.
                        # Wait, we don't want to get stuck forever if synthetic.
                        if "SYNTH" in ticker.upper() or res.get("success") == False:
                            # Use synthetic resolution (just random fallback for now so it doesn't get stuck)
                            exit_price = 1.0 if float(t.get("probability_percent", 50)) > 50 else 0.0
                        else:
                            continue # Wait for official Kalshi resolution
                            
                    t["status"] = "CLOSED"
                    t["reason"] = "SETTLEMENT"
                    t["pnl"] = (exit_price - entry) * count
                    modified = True
                    
                    if mode == "PAPER":
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("SELECT paper_balance FROM users WHERE id = ?", (user_id,))
                        row = c.fetchone()
                        if row:
                            new_bal = row[0] + (count * exit_price)
                            c.execute("UPDATE users SET paper_balance = ? WHERE id = ?", (new_bal, user_id))
                            conn.commit()
                        conn.close()
                    continue

                tp_pct = float(user.get("take_profit_pct", 50.0)) / 100.0
                ts_enabled = bool(user.get("trailing_stop_enabled", 0))
                ts_activation = float(user.get("trailing_stop_activation_pct", 35.0)) / 100.0
                ts_distance = float(user.get("trailing_stop_distance_pct", 6.0)) / 100.0
                
                if market and market.get("ticker") == ticker:
                    curr_bid = market.get(f"{side}_bid", 0.0)
                    curr_ask = market.get(f"{side}_ask", 0.0)
                    if entry > 0:
                        # Use mid-price for trigger evaluation to avoid getting instantly stopped out by wide bid/ask spreads
                        mid_price = (curr_bid + curr_ask) / 2.0
                        if mid_price <= 0: mid_price = curr_bid
                        
                        profit_pct = (mid_price - entry) / entry
                        loss_pct = (entry - mid_price) / entry
                        
                        # But max seen is based on actual bid since that's what you'd sell for
                        max_seen_bid = float(t.get("max_seen_bid", curr_bid))
                        if curr_bid > max_seen_bid:
                            max_seen_bid = curr_bid
                            t["max_seen_bid"] = max_seen_bid
                            modified = True
                        
                        max_seen_profit_pct = (max_seen_bid - entry) / entry
                        
                        trigger_exit = False
                        reason = ""
                        
                        if ts_enabled and max_seen_profit_pct >= ts_activation:
                            trail_threshold = max(max_seen_bid - ts_distance, max_seen_bid * (1.0 - ts_distance))
                            trail_threshold = max(trail_threshold, entry * 1.02)
                            if curr_bid <= trail_threshold:
                                trigger_exit = True
                                reason = f"TRAILING_STOP (+{profit_pct*100:.1f}%)"
                        
                        if not trigger_exit:
                            if loss_pct >= sl_pct:
                                trigger_exit = True
                                reason = f"STOP_LOSS (-{loss_pct*100:.1f}%)"
                            elif profit_pct >= tp_pct:
                                trigger_exit = True
                                reason = f"TAKE_PROFIT (+{profit_pct*100:.1f}%)"
                            
                        if trigger_exit:
                            exit_price = curr_bid
                            if mode == "LIVE":
                                priv = decrypt_kalshi_key(user.get('kalshi_priv_key_encrypted', ''))
                                if priv:
                                    kt_live = KalshiTrader(key_id=user.get('kalshi_key_id'), private_key_pem=priv)
                                    kt_live.close_position(ticker=ticker, purchased_side=side, count=count, dry_run=False)
                            t["status"] = "CLOSED"
                            t["reason"] = reason
                            t["pnl"] = (exit_price - entry) * count
                            modified = True
                            
                            if mode == "PAPER":
                                conn = sqlite3.connect(DB_PATH)
                                c = conn.cursor()
                                c.execute("SELECT paper_balance FROM users WHERE id = ?", (user_id,))
                                row = c.fetchone()
                                if row:
                                    new_bal = row[0] + (count * exit_price)
                                    c.execute("UPDATE users SET paper_balance = ? WHERE id = ?", (new_bal, user_id))
                                    conn.commit()
                                conn.close()
            
            if modified:
                with open(hist_path, 'w') as f:
                    json.dump(trades, f, indent=4)
                    
    except Exception as e:
        logger.error(f"[SaaSSettler] Error: {e}")

def process_auto_force_trades():
    try:
        users = get_all_active_users()
        if not users: return
        
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

        for user in force_users:
            u_source = str(user.get("signal_source", "ML_ENSEMBLE")).upper()
            if u_source == "TECHNICAL_ONLY":
                signal = analysis.get("primary_bias", "HOLD")
            else:
                signal = analysis.get("signal", "HOLD")
                
            direction = "YES" if "BUY YES" in signal else ("NO" if "BUY NO" in signal else "HOLD")
            
            if direction not in ["YES", "NO"]:
                continue

            price = market.get("yes_ask" if direction == "YES" else "no_ask")
            if not price or price <= 0:
                continue

            user_id = user['id']
            hist_path = os.path.join(DATA_DIR, 'users', str(user_id), 'trades_history.json')
            history = []
            if os.path.exists(hist_path):
                try:
                    with open(hist_path, 'r') as f:
                        history = json.load(f)
                except: pass
                
            already_traded = any(t.get('ticker') == ticker for t in history)
            if already_traded:
                continue
                
            mode = user.get("trading_mode", "PAPER")
            risk_amount = float(user.get("trade_size_dollars", 50.0))
            count = max(1, int(risk_amount / max(0.01, price)))
            trade_id = str(uuid.uuid4())
            
            if mode == "LIVE":
                if not user.get('kalshi_key_id') or not user.get('kalshi_priv_key_encrypted'):
                    continue
                priv = decrypt_kalshi_key(user['kalshi_priv_key_encrypted'])
                kt = KalshiTrader(key_id=user['kalshi_key_id'], private_key_pem=priv)
                if not kt.is_authenticated():
                    continue
                    
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
                if risk_amount > avail_bal:
                    continue
                cost = count * price
                update_user_paper_balance(user_id, avail_bal - cost)

            import pytz
            from datetime import datetime
            est_tz = pytz.timezone('US/Eastern')
            now_est = datetime.now(est_tz).strftime('%Y-%m-%d %I:%M:%S %p ET')

            history.append({
                "id": trade_id,
                "ticker": ticker,
                "side": direction,
                "direction": direction,
                "prediction_direction": direction,
                "count": count,
                "entry_price": price,
                "status": "OPEN",
                "pnl": 0.0,
                "timestamp": now_est,
                "mode": mode,
                "reason": "AUTO_FORCE_TRADE"
            })
            
            with open(hist_path, 'w') as f:
                json.dump(history, f, indent=4)
                
            logger.info(f"[AutoForceTrade] Executed {count} {direction} on {ticker} for user {user.get('username')}")
    except Exception as e:
        logger.error(f"[AutoForceTrade] Error: {e}")
