import os
import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    c = f.read()

saas_func = """
    def evaluate_and_execute_saas_users(self) -> None:
        '''
        Isolated multi-tenant orchestrator for SaaS users.
        Runs concurrently alongside the Master bot.
        '''
        if not self._rollover_lock.acquire(blocking=False):
            return
        
        lock_held = True
        try:
            from backend.engine.multi_asset_fetcher import is_market_open, get_candle_countdown, fetch_asset_candles as fetch_candles
            from backend.database.models import get_all_active_users, update_user_paper_balance
            from backend.btc.kalshi_trader import kalshi_trader, KalshiTrader
            from backend.auth.security import decrypt_kalshi_key
            import uuid
            import json
            import pytz
            from datetime import datetime
            import pandas as pd
            from backend.btc.indicators import add_all_indicators
            
            if not is_market_open(self.asset):
                return
                
            countdown_info = get_candle_countdown(timeframe="15m")
            sec_left = countdown_info.get("seconds_left", 900)
            sec_elapsed = 900 - sec_left
            
            if sec_left < 30:
                return
                
            active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=(self.mode == "PAPER"), min_seconds_left=45)
            if not active_m: return
            
            current_interval_id = active_m.get("ticker") or active_m.get("event_ticker", "")
            if not current_interval_id: return
            
            try:
                strike = float(active_m.get("strike_price") or 0.0)
            except: strike = 0.0
            if strike <= 0: return
            
            users = get_all_active_users() or []
            active_users = [u for u in users if u.get('ai_enabled', 1)]
            if not active_users: return
            
            # 1. Filter out users who have ALREADY traded this interval
            users_to_trade = []
            for u in active_users:
                user_hist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'users', str(u['id']), 'trades_history.json')
                has_traded = False
                if os.path.exists(user_hist_path):
                    try:
                        with open(user_hist_path, 'r') as f:
                            hist = json.load(f)
                        if any(t.get("ticker") == current_interval_id for t in hist):
                            has_traded = True
                    except: pass
                if not has_traded:
                    users_to_trade.append(u)
                    
            if not users_to_trade:
                return
                
            # 2. Group by configurations
            required_evals = set()
            for u in users_to_trade:
                u_style = str(u.get('trading_style', 'AUTO')).upper()
                u_source = str(u.get('signal_source', 'ML_ENSEMBLE')).upper()
                required_evals.add((u_style, u_source))
                
            df_base = fetch_candles(self.asset, timeframe="15m", limit=1000)
            df_ind_base = add_all_indicators(df_base)
            
            eval_results = {}
            for req_style, req_source in required_evals:
                try:
                    effective_style = req_style
                    if effective_style == "AUTO":
                        curr = df_ind_base.iloc[-1] if len(df_ind_base) > 0 else None
                        if curr is not None:
                            vr_raw = curr.get("vol_ratio", 1.0)
                            vol_ratio = float(vr_raw) if pd.notna(vr_raw) else 1.0
                            bb_raw = curr.get("bb_bandwidth", 1.0)
                            bb_width = float(bb_raw) if pd.notna(bb_raw) else 1.0
                            adx = float(curr.get("adx", 20.0))
                            if (vol_ratio > 1.5 and adx > 25.0):
                                effective_style = "MOMENTUM_SURFER"
                            elif vol_ratio < 0.85 and bb_width < 0.015 and adx < 20.0:
                                effective_style = "CHOP"
                            elif vol_ratio > 1.1:
                                effective_style = "AMBUSH"
                            else:
                                effective_style = "SNIPER"
                        else:
                            effective_style = "SNIPER"
                            
                    if effective_style == "MOMENTUM_SURFER":
                        df_target = fetch_candles(self.asset, timeframe="1m", limit=1000)
                        df_ind_target = add_all_indicators(df_target)
                    else:
                        df_ind_target = df_ind_base
                        
                    patterns = []
                    if effective_style != "MOMENTUM_SURFER":
                        try:
                            from backend.btc.pattern_scanner import detect_candlestick_patterns
                            patterns = detect_candlestick_patterns(df_ind_target)
                        except: pass
                        
                    if effective_style == "CHOP":
                        from backend.btc.chop_engine import evaluate_chop_contract
                        forecast = evaluate_chop_contract(df_ind_target, target_price=strike, kalshi_m=active_m)
                    else:
                        from backend.btc.analyzer import evaluate_next_15m_contract
                        forecast = evaluate_next_15m_contract(
                            df_ind_target, target_price=strike, patterns=patterns, kalshi_m=active_m, trading_style=effective_style
                        )
                        
                    if req_source == "TECHNICAL_ONLY":
                        forecast["conviction_grade"] = "TECHNICAL_ONLY"
                        if forecast.get("probability_percent", 50) > 50:
                            forecast["probability_percent"] = 75.0
                            
                    eval_results[(req_style, req_source)] = (effective_style, forecast)
                except Exception as e:
                    logger.error(f"[SaaS Eval] Error evaluating {req_style}/{req_source}: {e}")
                    eval_results[(req_style, req_source)] = (req_style, None)
                    
            # 3. Route to users
            for user in users_to_trade:
                u_style = str(user.get('trading_style', 'AUTO')).upper()
                u_source = str(user.get('signal_source', 'ML_ENSEMBLE')).upper()
                
                eff_style, forecast = eval_results.get((u_style, u_source), (u_style, None))
                if not forecast: continue
                
                direction = forecast.get("direction", "PASS")
                conf = forecast.get("probability_percent", 50.0)
                
                min_conf = 60.0
                if eff_style == "MOMENTUM_SURFER":
                    min_conf = 60.0 if sec_elapsed <= 60 else 75.0
                    conf = max(conf, 100.0 - conf)
                    
                if direction not in ["BUY YES", "BUY NO"] or conf < min_conf:
                    continue
                    
                side = "yes" if "YES" in direction else "no"
                market_price = float(active_m.get(f"{side}_ask", 0.50))
                user_mode = user.get('trading_mode', 'PAPER')
                trade_id = str(uuid.uuid4())
                filled_price = market_price
                contracts = 0
                
                try:
                    if user_mode == 'LIVE':
                        if not user.get('kalshi_key_id') or not user.get('kalshi_priv_key_encrypted'): continue
                        priv_key = decrypt_kalshi_key(user['kalshi_priv_key_encrypted'])
                        if not priv_key: continue
                        kt = KalshiTrader(key_id=user['kalshi_key_id'], private_key_pem=priv_key)
                        if not kt.is_authenticated(): continue
                        bal_res = kt.get_balance()
                        if not bal_res.get('success'): continue
                        avail_bal = float(bal_res.get('balance_dollars', 0.0))
                        if avail_bal < 1.0: continue
                        risk_amount = float(user.get("trade_size_dollars", 50.0))
                        contracts = max(1, int(risk_amount / max(0.01, market_price)))
                        res = kt.place_order(ticker=current_interval_id, side=side, count=contracts, limit_price_dollars=market_price, dry_run=False, slippage_buffer_dollars=0.04)
                        if not res.get('success'): continue
                        filled_price = res.get('filled_price', market_price)
                        trade_id = res.get('client_order_id', trade_id)
                    else:
                        avail_bal = float(user.get('paper_balance', 500.0))
                        if avail_bal < 1.0: continue
                        risk_amount = float(user.get("trade_size_dollars", 50.0))
                        contracts = max(1, int(risk_amount / max(0.01, market_price)))
                        cost = contracts * filled_price
                        update_user_paper_balance(user['id'], avail_bal - cost)

                    logger.info(f'[SaaS Multitenant] Traded {contracts} {side.upper()} for User {user["username"]} ({user_mode}) via {eff_style}')
                    
                    est_tz = pytz.timezone('US/Eastern')
                    now_est = datetime.now(est_tz).strftime('%Y-%m-%d %I:%M:%S %p ET')
                    user_hist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'users', str(user['id']), 'trades_history.json')
                    if os.path.exists(user_hist_path):
                        with open(user_hist_path, 'r') as f:
                            hist = json.load(f)
                        hist.append({
                            "id": trade_id,
                            "timestamp": now_est,
                            "ticker": current_interval_id,
                            "direction": side.upper(),
                            "side": side.upper(),
                            "prediction_direction": side.upper(),
                            "probability_percent": conf,
                            "entry_price": filled_price,
                            "count": contracts,
                            "status": "OPEN",
                            "mode": user_mode,
                            "reason": f"AI_COPY ({eff_style})"
                        })
                        with open(user_hist_path, 'w') as f:
                            json.dump(hist, f, indent=4)
                except Exception as e:
                    logger.error(f"[SaaS Multitenant] Error executing for user {user.get('username')}: {e}")
                    
        finally:
            if lock_held:
                try:
                    self._rollover_lock.release()
                except Exception:
                    pass
"""

# Inject saas_func right before execute_manual_trade
c = c.replace("    def execute_manual_trade(self, direction: str) -> Dict[str, Any]:", saas_func + "\n    def execute_manual_trade(self, direction: str) -> Dict[str, Any]:")

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(c)

# Now, we also need to disable the old broadcast logic inside check_and_execute_rollover
with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    c = f.read()
    
# Remove the call to _broadcast_trade_to_users in check_and_execute_rollover
c = re.sub(
    r'self\._broadcast_trade_to_users\(current_interval_id, side, market_price, pred_info=forecast\)',
    r'# SaaS broadcasting is now handled concurrently by evaluate_and_execute_saas_users()',
    c
)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(c)
