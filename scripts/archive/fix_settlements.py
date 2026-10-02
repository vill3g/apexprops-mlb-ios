import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to find the `check_settlements` method block.
# We'll use a regex to replace it.
pattern = re.compile(r'(    def check_settlements\(self, trades: Optional\[List\[Dict\[str, Any\]\]\] = None\):\n.*?)(    def check_and_execute_rollover\(self\) -> Optional\[Dict\[str, Any\]\]:)', re.DOTALL)

replacement = """    def check_settlements(self, trades: Optional[List[Dict[str, Any]]] = None):
        \"\"\"
        Settle completed Kalshi trades from Kalshi's own YES/NO result, for both Master and SaaS users.
        \"\"\"
        now_ts = time.time()
        if (now_ts - getattr(self, "_last_settlement_check_ts", 0.0)) < 3.0:
            return
        self._last_settlement_check_ts = now_ts

        official_results: Dict[str, Dict[str, Any]] = {}
        
        def _settle_list(trades_list, user_id=None):
            modified = False
            newly_settled_count = 0
            settle_candles_df = None
            for t in trades_list:
                if t.get("status") != "OPEN":
                    continue
                close_epoch = t.get("close_epoch", 0)
                close_time_str = t.get("interval_close_time") or ""
                if not close_epoch and close_time_str:
                    try:
                        close_epoch = datetime.fromisoformat(close_time_str.replace("Z", "+00:00")).timestamp()
                    except (TypeError, ValueError):
                        continue
                if not close_epoch or now_ts <= float(close_epoch) + 2:
                    continue

                try:
                    ticker = str(t.get("ticker", "")).strip()
                    if ticker and ticker not in official_results:
                        official_results[ticker] = kalshi_trader.get_market_result(ticker)
                    official = official_results.get(ticker, {})
                    official_result = str(official.get("result", "")).upper()

                    if official.get("success") and official_result in {"YES", "NO"}:
                        side = str(t.get("side", "")).upper()
                        entry_price = float(t.get("entry_price", 0.50))
                        count = int(t.get("count", 1))
                        is_win = side == official_result
                        market = official.get("market") or {}
                        settle_price = market.get("settlement_value") or market.get("settlement_value_dollars")
                        try: settle_price = float(settle_price)
                        except: settle_price = None

                        t["status"] = "SETTLED"
                        t["result"] = "WIN" if is_win else "LOSS"
                        t["official_result"] = official_result
                        t["settlement_source"] = "kalshi_official"
                        if settle_price is not None and settle_price > 0:
                            t["settle_price"] = settle_price
                            
                        prior_realized_pnl = float(t.get("realized_pnl", 0.0))
                        settlement_pnl = round(((1.0 - entry_price) * count) if is_win else (-entry_price * count), 4)
                        t["pnl"] = round(prior_realized_pnl + settlement_pnl, 4)
                        t["settlement_pnl"] = settlement_pnl
                        t["settled_at"] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
                        modified = True
                        newly_settled_count += 1

                        if t.get("mode", self.mode).upper() == "PAPER":
                            if user_id:
                                try:
                                    from backend.database.models import get_all_active_users, update_user_paper_balance
                                    if is_win:
                                        users = get_all_active_users() or []
                                        u = next((x for x in users if x['id'] == user_id), None)
                                        if u:
                                            bal = float(u.get('paper_balance', 500.0))
                                            update_user_paper_balance(user_id, bal + float(count))
                                except Exception as ep:
                                    logger.info(f"Failed to update SaaS paper balance for user {user_id}: {ep}")
                            else:
                                try:
                                    from backend.btc.paper_balance import update_balance
                                    update_balance(float(count) if is_win else 0.0, guest_id=getattr(self, '_guest_id', None))
                                except Exception as ep:
                                    logger.info(f"Failed to update master paper balance: {ep}")
                        continue
                        
                    # Legacy fallback
                    if (t.get("prediction_kind") == "AUTO" or ticker.startswith("KX")) and not ticker.endswith("_SYNTH"):
                        if now_ts <= float(close_epoch) + 600:
                            continue

                    strike = float(t.get("strike", 0.0) or 0.0)
                    if strike <= 0: continue
                    if settle_candles_df is None:
                        try:
                            from backend.engine.multi_asset_fetcher import fetch_asset_candles as fetch_candles
                            settle_candles_df = fetch_candles(self.asset, timeframe="15m", limit=5)
                        except: settle_candles_df = None
                    if settle_candles_df is None or len(settle_candles_df) < 2: continue
                    settle_price = float(settle_candles_df.iloc[-2]["close"])
                    side = str(t.get("side", "")).upper()
                    entry_price = float(t.get("entry_price", 0.50))
                    count = int(t.get("count", 1))
                    is_win = (side == "YES" and settle_price >= strike) or (side == "NO" and settle_price < strike)
                    t.update({
                        "status": "SETTLED", "result": "WIN" if is_win else "LOSS",
                        "settlement_source": "legacy_exchange_candle", "settle_price": settle_price,
                        "pnl": round(((1.0 - entry_price) * count) if is_win else (-entry_price * count), 4),
                        "settled_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    })
                    modified = True
                    newly_settled_count += 1
                except Exception as e:
                    logger.error(f"[AutoExecutor] Error checking settlement for trade {t.get('id')}: {e}")
            return modified, newly_settled_count

        with _history_lock:
            if trades is None:
                trades = self.get_trades_history()

            modified, newly_settled = _settle_list(trades, user_id=None)
            if modified:
                try:
                    self._save_trades_history(trades)
                    self._settled_since_drift_check += newly_settled
                    if self._settled_since_drift_check >= 50:
                        self._settled_since_drift_check = 0
                        try: self.check_live_calibration_drift()
                        except Exception as cde: logger.warning(f"[AutoExecutor] Scheduled calibration drift check failed: {cde}")
                        try:
                            from backend.btc.ml_engine import get_ml_engine
                            ml_eng = get_ml_engine()
                            threading.Thread(target=ml_eng.train, daemon=True, name="MLRetrainThread").start()
                        except Exception as e:
                            logger.warning(f"[AutoExecutor] Post-settlement ML retrain launch failed: {e}")
                except Exception as e:
                    logger.error(f"[AutoExecutor] Error saving trades in check_settlements: {e}")

            # SaaS users settling
            try:
                import os, json
                from backend.database.models import get_all_active_users
                saas_users = get_all_active_users() or []
                for u in saas_users:
                    u_id = u['id']
                    u_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'users', str(u_id), 'trades_history.json')
                    if os.path.exists(u_path):
                        with open(u_path, 'r') as f:
                            u_hist = json.load(f)
                        u_mod, _ = _settle_list(u_hist, user_id=u_id)
                        if u_mod:
                            with open(u_path, 'w') as f:
                                json.dump(u_hist, f, indent=4)
            except Exception as e:
                logger.error(f"[AutoExecutor] Error settling SaaS trades: {e}")

        # Hook: RL Shadow Sandbox settlements
        try:
            from backend.btc.shadow_executor import update_shadow_settlements
            update_shadow_settlements(kalshi_trader, official_results)
        except Exception as e:
            logger.error(f"[ShadowExecutor Hook] Error: {e}")

"""

new_content = pattern.sub(replacement + r'\2', content)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Replacement successful!" if new_content != content else "Regex failed to match!")
