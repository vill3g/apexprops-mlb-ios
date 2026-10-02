import re

with open('backend/btc/scalp_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 3: market_price -> price in _monitor_position
old_stop_loss = """                    if reason == "SCALP_STOP_LOSS" and original_side and not is_rev:
                        rev_side = "no" if original_side == "yes" else "yes"
                        logger.info(f"[ScalpEngine] Stop loss hit! Reversing trade to {rev_side.upper()} at BTC ${market_price:.2f}")
                        # Delay slightly to allow settlement
                        threading.Timer(1.5, self._execute_trade, args=(rev_side, market_price, True)).start()"""

new_stop_loss = """                    if reason == "SCALP_STOP_LOSS" and original_side and not is_rev:
                        rev_side = "no" if original_side == "yes" else "yes"
                        logger.info(f"[ScalpEngine] Stop loss hit! Reversing trade to {rev_side.upper()} at BTC ${price:.2f}")
                        # Delay slightly to allow settlement
                        threading.Timer(1.5, self._execute_trade, args=(rev_side, price, True)).start()"""

content = content.replace(old_stop_loss, new_stop_loss)

# Fix 4a: fetch_candles -> fetch_asset_candles in _execute_trade
old_execute_atr = """            try:
                from backend.engine.multi_asset_fetcher import fetch_asset_candles
                from backend.btc.indicators import add_all_indicators
                df_c = fetch_candles("15m", limit=30)
                if df_c is not None and not df_c.empty:
                    df_ind = add_all_indicators(df_c)
                    if "atr" in df_ind.columns and len(df_ind["atr"]) > 0:
                        entry_atr = float(df_ind["atr"].iloc[-1])
            except Exception as e:
                logger.warning(f"[ScalpEngine] Could not fetch entry ATR, defaulting to 150.0: {e}")"""

new_execute_atr = """            try:
                from backend.engine.multi_asset_fetcher import fetch_asset_candles
                from backend.btc.indicators import add_all_indicators
                df_c = fetch_asset_candles(self.asset, timeframe="15m", limit=30)
                if df_c is not None and not df_c.empty:
                    df_ind = add_all_indicators(df_c)
                    if "atr" in df_ind.columns and len(df_ind["atr"]) > 0:
                        entry_atr = float(df_ind["atr"].iloc[-1])
            except Exception as e:
                logger.warning(f"[ScalpEngine] Could not fetch entry ATR, defaulting to 150.0: {e}")"""
                
content = content.replace(old_execute_atr, new_execute_atr)

# Fix 4b: fetch_candles -> fetch_asset_candles in register_position
old_register_atr = """        try:
            from backend.engine.multi_asset_fetcher import fetch_asset_candles
            from backend.btc.indicators import add_all_indicators
            df_c = fetch_candles("15m", limit=30)
            if df_c is not None and not df_c.empty:
                df_ind = add_all_indicators(df_c)
                if "atr" in df_ind.columns and len(df_ind["atr"]) > 0:
                    entry_atr = float(df_ind["atr"].iloc[-1])
        except Exception:
            pass"""

new_register_atr = """        try:
            from backend.engine.multi_asset_fetcher import fetch_asset_candles
            from backend.btc.indicators import add_all_indicators
            df_c = fetch_asset_candles(self.asset, timeframe="15m", limit=30)
            if df_c is not None and not df_c.empty:
                df_ind = add_all_indicators(df_c)
                if "atr" in df_ind.columns and len(df_ind["atr"]) > 0:
                    entry_atr = float(df_ind["atr"].iloc[-1])
        except Exception as e:
            logger.warning(f"[ScalpEngine] Could not fetch entry ATR in register_position, defaulting to 150.0: {e}")"""

content = content.replace(old_register_atr, new_register_atr)

with open('backend/btc/scalp_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

