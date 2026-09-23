    def check_and_execute_rollover(self) -> Optional[Dict[str, Any]]:
        self._load_config()
        """
        Core autonomous trigger:
        Evaluates at rollover (first 60 seconds of a new 15-minute contract interval).
        """
        # FIX #2: Acquire the lock FIRST so that the last_check_time read/write is
        # also serialized.  Previously both gates were outside the lock, creating a
        # narrow window where two threads could both pass the 4-second check and both
        # enter the expensive ML + network path.
        if not self._rollover_lock.acquire(blocking=False):
            logger.debug("[AutoExecutor] Rollover evaluation already in progress by another worker. Skipping concurrent execution.")
            return None

        lock_held = True
        try:
            now = time.time()
            if (now - self.last_check_time) < 4.0:
                return None
            self.last_check_time = now

            if not is_market_open(self.asset):
                logger.debug(f"[AutoExecutor] {self.asset} market is closed; skipping rollover evaluation.")
                return None

            countdown_info = get_candle_countdown(timeframe="15m")
            sec_left = countdown_info.get("seconds_left", 900)
            sec_elapsed = 900 - sec_left

            trading_style = str(self.ai_settings.get("tradingStyle", "SNIPER")).upper()
            is_rollover_window = sec_elapsed <= 60 or sec_left >= 840
            is_prediction_window = 30 <= sec_elapsed <= 55 or 845 <= sec_left <= 870
            
            if trading_style in ["MOMENTUM_SURFER", "AMBUSH", "AUTO"]:
                window_valid = sec_left > 30  # Allows mid-candle evaluation
            else:
                window_valid = is_prediction_window if self.prediction_mode else is_rollover_window

            if not window_valid:
                return None

            # Fetch active Kalshi KXBTC15M market (require at least 45s before close)
            active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=(self.mode == "PAPER"), min_seconds_left=45)
            if not active_m:
                logger.debug("[AutoExecutor] No active market")
                return None

            # Use market ticker for live orders if available; fallback to event_ticker
            current_interval_id = active_m.get("ticker") or active_m.get("event_ticker", "")
            if not current_interval_id or current_interval_id == self.last_traded_interval:
                logger.debug(f"[AutoExecutor] Skipping because interval is last_traded_interval: {current_interval_id}")
                return None

            # Check if already traded in history
            trades = self.get_trades_history()
            if any(t.get("ticker") == current_interval_id for t in trades):
                self.last_traded_interval = current_interval_id
                logger.debug(f"[AutoExecutor] Already traded interval {current_interval_id} in trades history")
                return None

            # Finding 4: Re-check last_traded_interval immediately before expensive ML & network calls
            if current_interval_id == self.last_traded_interval:
                return None

            # Regime penalty: after a string of recent losses (esp. false-breakout or
            # choppy-market losses), require higher confidence before trading again.
            # See loss_analyzer.calculate_regime_penalties() for the thresholds.
            regime = loss_analyzer.calculate_regime_penalties(trades)
            conviction_multiplier = float(regime.get("conviction_multiplier", 1.0))
            extra_conviction_cushion = float(regime.get("extra_min_rsi_cushion", 0.0))
            if conviction_multiplier < 1.0 or regime.get("chop_warning"):
                logger.info(f"[AutoExecutor] Regime penalty active: {regime}")

            # A prediction without the contract's official target must never create
            # an order; a zero target previously made NO trades settle incorrectly.
            try:
                strike = float(active_m.get("strike_price") or 0.0)
            except (TypeError, ValueError):
                strike = 0.0
            if strike <= 0:
                logger.error("[AutoExecutor] Active Kalshi market has no valid floor strike; skipping %s", current_interval_id)
                return None

            # Fetch technical indicator data based on Trading Style
            tf = "15m"
            df = fetch_candles(self.asset, timeframe=tf, limit=1000)
            df_ind = add_all_indicators(df)
            
            effective_style = trading_style
            if effective_style == "AUTO":
                curr = df_ind.iloc[-1] if len(df_ind) > 0 else None
                if curr is not None:
                    try:
                        vr_raw = curr.get("vol_ratio", 1.0)
                        vol_ratio = float(vr_raw) if vr_raw is not None and not pd.isna(vr_raw) else 1.0
                    except (ValueError, TypeError):
                        vol_ratio = 1.0
                    try:
                        bb_raw = curr.get("bb_bandwidth", 1.0)
                        bb_width = float(bb_raw) if bb_raw is not None and not pd.isna(bb_raw) else 1.0
                    except (ValueError, TypeError):
                        bb_width = 1.0
                        
                    adx = float(curr.get("adx", 20.0))
                    
                    try:
                        from backend.btc.liquidation_stream import get_liquidation_imbalance
                        liq = get_liquidation_imbalance()
                        liq_total = liq["short_liquidations_usd"] + liq["long_liquidations_usd"]
                    except Exception:
                        liq_total = 0.0

                    if liq_total > 1_500_000 or (vol_ratio > 1.5 and adx > 25.0):
                        effective_style = "MOMENTUM_SURFER"
                        logger.info(f"[AutoExecutor] AUTO Mode routed to MOMENTUM_SURFER (Vol: {vol_ratio:.2f}, ADX: {adx:.1f}, Liq: ${liq_total/1e6:.1f}M)")
                    elif vol_ratio < 0.85 and bb_width < 0.015 and adx < 20.0:
                        effective_style = "CHOP"
                        logger.info(f"[AutoExecutor] AUTO Mode routed to CHOP (Vol: {vol_ratio:.2f}, BBW: {bb_width:.4f}, ADX: {adx:.1f})")
                    elif vol_ratio > 1.1:
                        effective_style = "AMBUSH"
                        logger.info(f"[AutoExecutor] AUTO Mode routed to AMBUSH (Vol: {vol_ratio:.2f}, ADX: {adx:.1f})")
                    else:
                        effective_style = "SNIPER"
                        logger.info(f"[AutoExecutor] AUTO Mode routed to SNIPER (Vol: {vol_ratio:.2f}, ADX: {adx:.1f})")
                else:
                    effective_style = "SNIPER"

            # Inject historical market intervals directly into the ML Engine to train it instantly
            try:
                from backend.btc.ml_engine import get_ml_engine
                import os
                data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
                ml_engine = get_ml_engine(data_dir, effective_style)
                if not ml_engine.is_trained:
                    from backend.btc.data_fetcher import fetch_15m_candles_history, fetch_1m_candles_history
                    
                    if effective_style == "MOMENTUM_SURFER":
                        hist_df = fetch_1m_candles_history(days=15)
                    else:
                        hist_df = fetch_15m_candles_history(days=60)
                        
                    hist_df_ind = add_all_indicators(hist_df)
                    ml_engine.self_train_on_historical_market(hist_df_ind)
            except Exception as e:
                logger.error(f"[AutoExecutor] Failed to self-train ML Engine: {e}")

            # Detect advanced chart patterns (triangles, flags, head & shoulders)
            patterns = []
            if effective_style != "MOMENTUM_SURFER":
                try:
                    patterns = detect_candlestick_patterns(df_ind)
                except Exception as _pat_err:
                    logger.debug(f"[AutoExecutor] Pattern detector error: {_pat_err}")

            if effective_style == "CHOP":
                try:
                    from backend.btc.chop_engine import evaluate_chop_contract
                    forecast = evaluate_chop_contract(df_ind, target_price=strike, kalshi_m=active_m)
                except Exception as chop_err:
                    logger.error(
                        f"[AutoExecutor] chop_engine unavailable ({chop_err}); "
                        f"falling back to standard SNIPER evaluation for this cycle."
                    )
                    forecast = evaluate_next_15m_contract(
                        df_ind, target_price=strike, patterns=patterns, kalshi_m=active_m, trading_style="SNIPER"
                    )
            else:
                forecast = evaluate_next_15m_contract(
                    df_ind, target_price=strike, patterns=patterns, kalshi_m=active_m, trading_style=effective_style
                )

            # Hook: RL Shadow Sandbox execution
            try:
                from backend.btc.shadow_executor import execute_shadow_trade
                execute_shadow_trade(forecast, kalshi_market=active_m)
            except Exception as e:
                logger.error(f"[ShadowExecutor Hook] Error: {e}")

            raw_score = float(forecast.get("probability_percent", 50.0))
            edge_label = str(forecast.get("primary_edge", ""))
            rec = forecast.get("recommendation", "")
            grade = forecast.get("conviction_grade", "")
            badge = str(forecast.get("conviction_badge", ""))
            direction = normalize_prediction_direction(forecast.get("direction") or rec)

            pre_gate_dir = forecast.get("pre_gate_direction")
            pre_gate_grade = str(forecast.get("pre_gate_grade", ""))
            pre_gate_prob = float(forecast.get("pre_gate_prob", raw_score))
            raw_ml_prob = float(forecast.get("raw_ml_prob", forecast.get("ml_prob", 0.5)))
            ml_prob = float(forecast.get("ml_prob", 0.5))

            one_shot_ai = bool(self.ai_settings.get("oneShotAiStartTrade", False))
            ignore_pass = bool(self.ai_settings.get("ignorePass", False))
            ignore_pass_technical_only = bool(self.ai_settings.get("ignorePassTechnicalOnly", False))
            reverse_cvd = bool(self.ai_settings.get("reverseCvd", False))
            is_reverse = False
            is_forced_pass = False

            if ("PIN RISK" in badge or "PIN RISK" in rec) and not one_shot_ai:
                logger.info(f"[AutoExecutor] Strike Pin Risk active (price within $15 of strike target in low volatility). Sitting out to protect win rate.")
                return None

            if (one_shot_ai or ignore_pass):
                # 100% AI Prediction mode (until toggled off if ignore_pass, or 1-shot if one_shot_ai)
                # Use raw unmolested ML probability directly from the model
                ai_model_prob = raw_ml_prob
                if ai_model_prob != 0.50:
                    direction = "ABOVE" if ai_model_prob > 0.50 else "BELOW"
                    raw_score = max(51.0, ai_model_prob * 100.0) if ai_model_prob > 0.50 else max(51.0, (1.0 - ai_model_prob) * 100.0)
                else:
                    direction = pre_gate_dir if pre_gate_dir in ["ABOVE", "BELOW"] else "ABOVE"
                    raw_score = pre_gate_prob if pre_gate_prob else 51.0

                if pre_gate_prob and pre_gate_dir == direction and pre_gate_prob > raw_score:
                    raw_score = pre_gate_prob

                grade = "GRADE A+ (100% AI)"
                badge = f"🎯 100% AI ({raw_score:.0f}%)"
                rec = f"100% AI Prediction{' (Force Trade)' if ignore_pass else ' at Start'}: {'YES' if direction == 'ABOVE' else 'NO'}"
                is_forced_pass = True
                logger.info(
                    f"[AutoExecutor] [{'100% AI MODE (UNTIL TOGGLED OFF)' if ignore_pass else '1-SHOT AI MODE'}] Trading 100% on AI Prediction: "
                    f"{direction} ({raw_score:.1f}% Conf, Raw ML: {ai_model_prob*100:.1f}%). Technical and PASS filters bypassed."
                )
                if ignore_pass:
                    logger.warning(
                        "[AutoExecutor] 'Force Trade on PASS' is ENABLED — bypassing 1H-trend, "
                        "CVD, orderbook, and chop safety gates on this trade. This trades off "
                        "accuracy for frequency; verify this is intentional."
                    )
            elif ignore_pass_technical_only and direction == "PASS":
                # Only force trade if there was a real technical chart setup detected (not just ML fallback)
                if "ML MODEL" not in pre_gate_grade and pre_gate_dir in ["ABOVE", "BELOW"]:
                    direction = pre_gate_dir
                    raw_score = pre_gate_prob
                    grade = "GRADE A+ (TECH FORCE)"
                    badge = f"🎯 TECH FORCE ({raw_score:.0f}%)"
                    rec = f"Technical Force Trade: {'YES' if direction == 'ABOVE' else 'NO'}"
                    is_forced_pass = True
                    logger.info(f"[AutoExecutor] [TECHNICAL FORCE TRADE] Overriding PASS using Technical Setup: {direction} ({raw_score:.1f}% Conf). ML/Macro blockers bypassed.")
                else:
                    logger.info("[AutoExecutor] [TECHNICAL FORCE TRADE] Active, but no technical chart setup was present. Remaining PASS.")
                    return None
            # Handle PASS direction filtering or CVD Divergence
            elif direction == "PASS":
                # Determine best underlying direction from pre-gate analysis or ML model
                if pre_gate_dir in ["ABOVE", "BELOW"]:
                    best_underlying_dir = pre_gate_dir
                    best_underlying_prob = pre_gate_prob
                elif ml_prob != 0.5:
                    best_underlying_dir = "ABOVE" if ml_prob >= 0.5 else "BELOW"
                    best_underlying_prob = ml_prob * 100.0 if ml_prob >= 0.5 else (1.0 - ml_prob) * 100.0
                else:
                    best_underlying_dir = "ABOVE" if raw_score >= 50.0 else "BELOW"
                    best_underlying_prob = raw_score

                if reverse_cvd and "CVD DIVERGENCE" in badge:
                    original_dir = best_underlying_dir
                    direction = "BELOW" if original_dir == "ABOVE" else "ABOVE"
                    is_reverse = True
                    raw_score = best_underlying_prob
                    logger.info(f"[AutoExecutor] 'Reverse on CVD Divergence' enabled. Reversing {original_dir} trade to {direction} (Score: {raw_score:.1f}%).")
                else:
                    logger.debug("[AutoExecutor] Skipping because direction is PASS")
                    return None
            elif reverse_cvd and "CVD DIVERGENCE" in badge and raw_score > 0:
                original_dir = direction
                direction = "BELOW" if original_dir == "ABOVE" else "ABOVE"
                is_reverse = True
                logger.info(f"[AutoExecutor] 'Reverse on CVD Divergence' enabled. Reversing active {original_dir} trade to {direction}.")

            # Strict Filter 2: Conviction & Settings Thresholds
            meets_conviction = False
        
            # ML settings overrides
            min_conf = float(self.ai_settings.get("minConf", 0.0))
            edge_multiplier = float(self.ai_settings.get("edgeWeightFactor", 1.0)) if self.ai_settings.get("edgeWeightOn") else 1.0
        
            actual_conf = raw_score
            if "High Confluence" in edge_label:
                actual_conf = min(99.0, raw_score * edge_multiplier)

            # Dampen confidence after a rough recent stretch (see Step 2b above).
            # A multiplier < 1.0 makes both the min_conf check and the ML-fallback
            # gate below harder to satisfy, which is the intended effect.
            actual_conf = actual_conf * conviction_multiplier

            # Base threshold check against minConf
            applied_threshold = min_conf
            if one_shot_ai:
                meets_conviction = True
            elif is_forced_pass or is_reverse:
                # User explicitly requested Force Trade on PASS or Reverse on CVD Divergence
                meets_conviction = True
                logger.info(f"[AutoExecutor] Conviction check bypassed for forced/reversed trade ({direction} @ {actual_conf:.1f}%).")
            elif isinstance(self.ai_settings.get("minConfByGrade"), dict):
                floors = self.ai_settings["minConfByGrade"]
                if "A+" in grade:
                    applied_threshold = float(floors.get("A_PLUS", 70))
                elif "GRADE A " in grade or "GRADE A SETUP" in grade:
                    applied_threshold = float(floors.get("A", 65))
                elif "B SETUP" in grade:
                    applied_threshold = float(floors.get("B", 60))
                else:
                    applied_threshold = float(floors.get("ML_FALLBACK", 65))
                if actual_conf >= applied_threshold:
                    meets_conviction = True
            elif min_conf > 0:
                if actual_conf >= min_conf:
                    meets_conviction = True
            else:
                # Fallback to grade logic
                if self.prediction_mode:
                    meets_conviction = True
                else:
                    # A "GRADE C / ML MODEL" label is the fallback used when no real
                    # chart/technical setup fired; only let it satisfy a higher
                    # conviction bar when its own confidence is meaningfully away
                    # from a coin-flip (50%), never on the label text alone.
                    ml_fallback_hi = 65.0 + extra_conviction_cushion
                    ml_fallback_lo = 35.0 - extra_conviction_cushion
                    is_confident_ml_fallback = ("GRADE C" in grade and "ML MODEL" in grade) and (actual_conf >= ml_fallback_hi or actual_conf <= ml_fallback_lo)

                    if effective_style == "MOMENTUM_SURFER":
                        # Dynamic Confidence Minimums for Machine Gun Mode
                        min_conf = 60.0 if sec_elapsed <= 60 else 75.0
                        actual_win_conf = max(actual_conf, 100.0 - actual_conf)
                        meets_conviction = (actual_win_conf >= min_conf)
                    else:
                        if effective_style == "CHOP":
                            meets_conviction = ("CHOP" in grade) and (actual_conf >= min_conf)
                        elif self.min_conviction == "GRADE A+ SETUP" and "A+" in grade:
                            meets_conviction = True
                        elif self.min_conviction == "GRADE A SETUP" and ("A+" in grade or "GRADE A " in grade or is_confident_ml_fallback):
                            meets_conviction = True
                        elif self.min_conviction == "GRADE B+ SETUP" and ("A+" in grade or "GRADE A " in grade or "B+ SETUP" in grade or is_confident_ml_fallback):
                            meets_conviction = True
                        elif self.min_conviction == "GRADE B SETUP" and ("A+" in grade or "GRADE A " in grade or "B+ SETUP" in grade or "B SETUP" in grade or is_confident_ml_fallback):
                            meets_conviction = True

            if not meets_conviction:
                logger.debug(f"[AutoExecutor] Skipping because conviction not met: {actual_conf} < {applied_threshold} (Grade: {grade})")
                return None

            # If bot is disabled, do not execute
            if not self.enabled:
                logger.debug("[AutoExecutor] Skipping because bot is disabled")
                return None

            # Strict Filter 3: Enforce Max Daily Trades & Max Daily Risk (Finding 2)
            risk_blocked_reason = self.check_risk_budget(trades)
            if risk_blocked_reason:
                logger.info(f"[AutoExecutor] {risk_blocked_reason}. Skipping auto execution.")
                return None

            # Map signal to Kalshi contract side
            # "ABOVE" -> buy YES (anticipating price >= strike)
            # "BELOW" -> buy NO (anticipating price < strike)
            side = "yes" if direction == "ABOVE" else "no"
            market_price = active_m.get("yes_ask" if side == "yes" else "no_ask") or 0.50

            # Determine affordable contract count for live or paper
        
            # ML Settings Overrides: Use maxCap to size position
            max_cap = float(self.ai_settings.get("maxCap", 0.0))
            unit_price_est = min(0.99, max(0.01, float(market_price) + 0.04))
        
            # AUDIT FIX #3: Hard ceiling on contracts to prevent black-swan order sizes
            ABSOLUTE_MAX_CONTRACTS = 999999

            if max_cap > 0:
                contracts_to_buy = int(max_cap // unit_price_est)
                if contracts_to_buy < 1:
                    contracts_to_buy = 1
            else:
                contracts_to_buy = self.max_contracts
        
            contracts_to_buy = min(contracts_to_buy, ABSOLUTE_MAX_CONTRACTS)

            # 2. Dry Run
            dry_run = (self.mode == "PAPER")
            if self.ai_settings.get("dryRun", False):
                dry_run = True

            # 3. Execution Delay — FIX #4: release the lock while sleeping so the
            # background loop isn't stalled for the full delay duration.
            exec_delay = int(self.ai_settings.get("execDelay", 0))
            if exec_delay > 0:
                logger.info(f"[AutoExecutor] Delaying execution by {exec_delay}s (lock released during wait)...")
                self._rollover_lock.release()
                lock_held = False
                try:
                    time.sleep(exec_delay)
                finally:
                    lock_held = self._rollover_lock.acquire(blocking=True, timeout=10)
                    if not lock_held:
                        logger.error("[AutoExecutor] Could not re-acquire rollover lock after exec_delay sleep; aborting trade.")
                        return None
            

            if self.mode == "LIVE":

                bal_res = kalshi_trader.get_balance()
                if bal_res.get("success", False):
                    avail_bal = float(bal_res.get("balance_dollars", 0.0))
                    unit_price = min(0.99, max(0.01, float(market_price) + 0.04))
                    if unit_price > 0 and avail_bal < (unit_price * contracts_to_buy):
                        affordable = int(avail_bal // unit_price)
                        contracts_to_buy = affordable
            
            if contracts_to_buy < 1:
                logger.warning(f"Insufficient balance to execute trade. Skipping.")
                return None

            slippage_buffer = float(self.ai_settings.get("slippageBufferDollars", self.ai_settings.get("slippageBufferCents", 0.04)))

            # Execute Order (Paper or Live)
            order_res = kalshi_trader.place_order(
                ticker=current_interval_id,
                side=side,
                count=contracts_to_buy,
                limit_price_dollars=market_price,
                dry_run=dry_run,
                slippage_buffer_dollars=slippage_buffer
            )

            if order_res.get("success", False):
                # SaaS Broadcast
                self._broadcast_trade_to_users(current_interval_id, side, market_price, {"prob": float(analysis.get("probability_percent", 50))})

                # Finding 9: Verify order response ticker matches current_interval_id
                res_ticker = order_res.get("ticker") or (order_res.get("order") or {}).get("ticker")
                if res_ticker and str(res_ticker).strip() != str(current_interval_id).strip():
                    logger.error(
                        f"[AutoExecutor] Ticker mismatch! Expected interval '{current_interval_id}', "
                        f"order executed on '{res_ticker}'. Aborting trade record creation to prevent corrupted stats/ML training."
                    )
                    return None

                # H1 & H2: Record actual fill metrics and fix paper balance cost key
                fill_price = float(order_res.get("filled_price", market_price))
                fill_count = float(order_res.get("count", contracts_to_buy))
                fill_cost = float(order_res.get("total_cost", round(fill_price * fill_count, 4)))

                if self.mode == "PAPER":
                    try:
                        from backend.btc.paper_balance import update_balance
                        update_balance(-fill_cost, guest_id=getattr(self, '_guest_id', None))
                    except Exception as e:
                        logger.error(f"Paper deduction error: {e}")
                elif self.mode == "LIVE":
                    kalshi_trader.get_balance(force_refresh=True)

                self.last_traded_interval = current_interval_id
                # The prediction record is the single source carried from analyzer
                # to order to accuracy.  It deliberately uses a different ID from
                # Kalshi's order ID so retries cannot rewrite its identity.
                prediction_id = str(uuid.uuid4())
                prediction_generated_at = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
                close_time_str = active_m.get("close_time") or ""
                close_epoch = now + sec_left
                if close_time_str:
                    try:
                        close_epoch = datetime.fromisoformat(close_time_str.replace("Z", "+00:00")).timestamp()
                    except (TypeError, ValueError):
                        pass

                trade_record = {
                    "id": order_res.get("order_id", str(uuid.uuid4())[:8]),
                    "client_order_id": order_res.get("client_order_id", ""),
                    "timestamp": prediction_generated_at,
                    "prediction_id": prediction_id,
                    "prediction_kind": "AUTO",
                    "trade_source": f"AUTO ({effective_style})" if not is_reverse else f"AUTO ({effective_style}) - REVERSE",
                    "is_auto": True,
                    "is_reverse": is_reverse,
                    "is_forced_pass": is_forced_pass,
                    "is_scalp": False,
                    "trading_style": effective_style,
                    "prediction_direction": direction,
                    "prediction_generated_at": prediction_generated_at,
                    "accuracy_eligible": True,
                    "interval_close_time": close_time_str,
                    "close_epoch": close_epoch,
                    "ticker": current_interval_id,
                    "title": active_m.get("title", ""),
                    "market_snapshot": {
                        "price": float(df_ind.iloc[-1]["close"]) if len(df_ind) > 0 else float(strike),
                        "target": strike,
                        "confidence": int(raw_score) if (one_shot_ai or is_forced_pass or is_reverse) else forecast.get("probability_percent"),
                        "conviction_grade": forecast.get("conviction_grade"),
                        "primary_edge": forecast.get("primary_edge"),
                        "raw_features": forecast.get("raw_features", {})
                    },
                    "strike": strike,
                    "direction": direction,
                    "recommendation": rec,
                    "conviction_grade": grade,
                    "conviction_badge": badge if (one_shot_ai or ignore_pass) else forecast.get("conviction_badge", ""),
                    "probability_percent": int(raw_score) if (one_shot_ai or is_forced_pass or is_reverse) else forecast.get("probability_percent", 50),
                    "predicted_probability": round(float(raw_score) / 100.0, 4) if (one_shot_ai or is_forced_pass or is_reverse) else forecast.get("predicted_probability", round(float(forecast.get("probability_percent", 50)) / 100.0, 4)),
                    "ml_prob": round(float(raw_ml_prob if (one_shot_ai or ignore_pass) else ml_prob), 4),
                    "side": side.upper(),
                    "requested_price": market_price,
                    "entry_price": fill_price,
                    "requested_count": contracts_to_buy,
                    "count": fill_count,
                    "cost": fill_cost,
                    "slippage_cents": round(abs(fill_price - market_price), 4),
                    "slippage_buffer_used": slippage_buffer,
                    "mode": str(order_res.get("mode", self.mode)).upper(),
                    "status": "OPEN",
                    "result": "PENDING",
                    "pnl": 0.0,
                    "catalysts": [f"100% AI Prediction{' (Force Trade)' if ignore_pass else ' at Start'}: AI model predicted {raw_score:.1f}% {'UP' if direction == 'ABOVE' else 'DOWN'}"] + list(forecast.get("catalysts", [])) if (one_shot_ai or ignore_pass) else forecast.get("catalysts", [])
                }

                trades.append(trade_record)
                self._save_trades_history(trades)

                # Auto-reset oneShotAiStartTrade back to normal (OFF) after placing trade
                # Note: ignorePass (Force Trade on PASS) remains active continuously on every trade until explicitly toggled off by user
                if one_shot_ai and not ignore_pass:
                    self.ai_settings["oneShotAiStartTrade"] = False
                    self._save_config()
                    logger.info("[AutoExecutor] [1-SHOT AI MODE] Trade executed! Auto-resetting 'oneShotAiStartTrade' back to normal (OFF).")

                # Connect with scalp_engine for early profit exits if scalping is enabled
                try:
                    from backend.btc.scalp_engine import scalp_engine
                    if getattr(scalp_engine, "enabled", False):
                        scalp_engine.register_position(trade_record)
                except Exception as se_err:
                    logger.warning(f"[AutoExecutor] Could not register trade with ScalpEngine: {se_err}")

            else:
                if order_res.get("ambiguous"):
                    logger.error(
                        f"[AutoExecutor] CRITICAL: Rollover order outcome ambiguous after timeout! "
                        f"Interval: '{current_interval_id}', Ticker: '{order_res.get('ticker', current_interval_id)}', "
                        f"Client Order ID: '{order_res.get('client_order_id')}'. "
                        f"Error: {order_res.get('error')}. MANUAL VERIFICATION REQUIRED ON KALSHI."
                    )
                else:
                    logger.error(f"[AutoExecutor] Order failed: {order_res.get('error')}")

            return None
        finally:
            if lock_held:
                self._rollover_lock.release()

