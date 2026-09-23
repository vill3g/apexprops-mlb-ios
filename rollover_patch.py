    def check_and_execute_rollover(self) -> Optional[Dict[str, Any]]:
        self._load_config()
        if not self._rollover_lock.acquire(blocking=False):
            logger.debug("[AutoExecutor] Rollover evaluation already in progress by another worker. Skipping concurrent execution.")
            return None

        lock_held = True
        try:
            now = time.time()
            if (now - self.last_check_time) < 4.0:
                return None
            self.last_check_time = now

            from backend.engine.multi_asset_fetcher import is_market_open, get_candle_countdown, fetch_asset_candles as fetch_candles
            if not is_market_open(self.asset):
                return None

            countdown_info = get_candle_countdown(timeframe="15m")
            sec_left = countdown_info.get("seconds_left", 900)
            sec_elapsed = 900 - sec_left

            is_rollover_window = sec_elapsed <= 60 or sec_left >= 840
            is_prediction_window = 30 <= sec_elapsed <= 55 or 845 <= sec_left <= 870
            
            # Since styles might need different windows, we will just allow evaluation if ANY group is valid
            window_valid = sec_left > 30 
            if not window_valid:
                return None

            # Fetch active Kalshi market
            active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=(self.mode == "PAPER"), min_seconds_left=45)
            if not active_m:
                return None

            current_interval_id = active_m.get("ticker") or active_m.get("event_ticker", "")
            if not current_interval_id or current_interval_id == self.last_traded_interval:
                return None

            trades = self.get_trades_history()
            if any(t.get("ticker") == current_interval_id for t in trades):
                self.last_traded_interval = current_interval_id
                return None

            try:
                strike = float(active_m.get("strike_price") or 0.0)
            except (TypeError, ValueError):
                strike = 0.0
            if strike <= 0:
                return None

            # --- MULTI-TENANT EVALUATION SETUP ---
            from backend.database.models import get_all_active_users
            users = get_all_active_users() or []
            active_users = [u for u in users if u.get('ai_enabled', 1)]
            
            # Master configuration
            master_style = str(self.ai_settings.get("tradingStyle", "SNIPER")).upper()
            master_source = str(self.ai_settings.get("signalIsolation", "BLEND")).upper()
            
            # Group configurations needed
            required_evaluations = {(master_style, master_source)}
            for u in active_users:
                u_style = str(u.get('trading_style', 'AUTO')).upper()
                u_source = str(u.get('signal_source', 'ML_ENSEMBLE')).upper()
                required_evaluations.add((u_style, u_source))
                
            logger.info(f"[AutoExecutor] Evaluating {len(required_evaluations)} distinct configuration styles for current interval.")

            # Base DataFrame (we'll fetch once and copy)
            df_base = fetch_candles(self.asset, timeframe="15m", limit=1000)
            df_ind_base = add_all_indicators(df_base)
            
            eval_results = {}
            
            for req_style, req_source in required_evaluations:
                try:
                    effective_style = req_style
                    if effective_style == "AUTO":
                        curr = df_ind_base.iloc[-1] if len(df_ind_base) > 0 else None
                        if curr is not None:
                            vr_raw = curr.get("vol_ratio", 1.0)
                            vol_ratio = float(vr_raw) if vr_raw is not None and not pd.isna(vr_raw) else 1.0
                            bb_raw = curr.get("bb_bandwidth", 1.0)
                            bb_width = float(bb_raw) if bb_raw is not None and not pd.isna(bb_raw) else 1.0
                            adx = float(curr.get("adx", 20.0))
                            liq_total = 0.0
                            if liq_total > 1_500_000 or (vol_ratio > 1.5 and adx > 25.0):
                                effective_style = "MOMENTUM_SURFER"
                            elif vol_ratio < 0.85 and bb_width < 0.015 and adx < 20.0:
                                effective_style = "CHOP"
                            elif vol_ratio > 1.1:
                                effective_style = "AMBUSH"
                            else:
                                effective_style = "SNIPER"
                        else:
                            effective_style = "SNIPER"

                    # For Momentum, we need 1m candles
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
                        # Strip ML probability and only use raw technical direction if confidence is somewhat neutral
                        forecast["conviction_grade"] = "TECHNICAL_ONLY"
                        if forecast.get("probability_percent", 50) > 50:
                            forecast["probability_percent"] = 75.0 # Forcing a pass threshold for technical
                        
                    eval_results[(req_style, req_source)] = (effective_style, forecast)
                except Exception as eval_err:
                    logger.error(f"[AutoExecutor] Evaluation error for {req_style}/{req_source}: {eval_err}")
                    eval_results[(req_style, req_source)] = (req_style, None)

            # --- ROUTING TRADES ---
            
            # 1. Master Account Trade
            master_eff_style, master_forecast = eval_results.get((master_style, master_source), (master_style, None))
            if master_forecast:
                direction = master_forecast.get("direction", "PASS")
                conf = master_forecast.get("probability_percent", 50.0)
                
                # Dynamic Confidence Minimums
                min_conf = 60.0
                if master_eff_style == "MOMENTUM_SURFER":
                    min_conf = 60.0 if sec_elapsed <= 60 else 75.0
                    conf = max(conf, 100.0 - conf)
                
                meets_conviction = (conf >= min_conf) and direction in ["BUY YES", "BUY NO"]
                
                if meets_conviction and self.mode == "LIVE":
                    self._execute_master_trade(direction, conf, strike, active_m, current_interval_id, master_eff_style, master_forecast)

            # 2. SaaS Users Trade
            from backend.auth.security import decrypt_kalshi_key
            import uuid
            from backend.database.models import update_user_paper_balance
            
            for user in active_users:
                u_style = str(user.get('trading_style', 'AUTO')).upper()
                u_source = str(user.get('signal_source', 'ML_ENSEMBLE')).upper()
                
                u_eff_style, u_forecast = eval_results.get((u_style, u_source), (u_style, None))
                if not u_forecast: continue
                
                direction = u_forecast.get("direction", "PASS")
                conf = u_forecast.get("probability_percent", 50.0)
                
                min_conf = 60.0
                if u_eff_style == "MOMENTUM_SURFER":
                    min_conf = 60.0 if sec_elapsed <= 60 else 75.0
                    conf = max(conf, 100.0 - conf)
                    
                if direction not in ["BUY YES", "BUY NO"] or conf < min_conf:
                    continue
                    
                # Passed! Execute for user
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
                        res = kt.place_order(
                            ticker=current_interval_id, side=side, count=contracts, 
                            limit_price_dollars=market_price, dry_run=False, slippage_buffer_dollars=0.04
                        )
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

                    logger.info(f'[SaaS Multitenant] Successfully traded {contracts} {side.upper()} for User {user["username"]} ({user_mode}) via {u_style}')
                    
                    import pytz
                    from datetime import datetime
                    est_tz = pytz.timezone('US/Eastern')
                    now_est = datetime.now(est_tz).strftime('%Y-%m-%d %I:%M:%S %p ET')
                    
                    user_hist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'users', str(user['id']), 'trades_history.json')
                    if os.path.exists(user_hist_path):
                        with open(user_hist_path, 'r') as f:
                            history = json.load(f)
                        trade_record = {
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
                            "reason": f"AI_COPY ({u_eff_style})"
                        }
                        history.append(trade_record)
                        with open(user_hist_path, 'w') as f:
                            json.dump(history, f, indent=4)
                            
                except Exception as user_e:
                    logger.error(f"[SaaS Multitenant] Error executing for user {user.get('username')}: {user_e}")

            self.last_traded_interval = current_interval_id
            return {"status": "Evaluated all groups"}
            
        finally:
            if lock_held:
                try:
                    self._rollover_lock.release()
                except Exception:
                    pass

    def _execute_master_trade(self, direction, conf, strike, active_m, current_interval_id, effective_style, forecast):
        import uuid
        import pytz
        from datetime import datetime
        side = "yes" if "YES" in direction else "no"
        market_price = float(active_m.get(f"{side}_ask", 0.50))
        contracts = min(self.max_contracts, int(self.max_daily_risk / max(0.01, market_price)))
        if contracts < 1: return
        res = kalshi_trader.place_order(ticker=current_interval_id, side=side, count=contracts, limit_price_dollars=market_price, dry_run=False, slippage_buffer_dollars=0.04)
        if res.get("success"):
            logger.info(f"[Master] Traded {direction} on {current_interval_id}")
            est_tz = pytz.timezone('US/Eastern')
            now_est = datetime.now(est_tz).strftime('%Y-%m-%d %I:%M:%S %p ET')
            trades = self.get_trades_history()
            trades.append({
                "id": res.get("client_order_id", str(uuid.uuid4())),
                "timestamp": now_est,
                "ticker": current_interval_id,
                "direction": side.upper(),
                "side": side.upper(),
                "entry_price": res.get("filled_price", market_price),
                "count": contracts,
                "status": "OPEN",
                "mode": "LIVE",
                "reason": f"MASTER ({effective_style})"
            })
            self._save_trades_history(trades)
