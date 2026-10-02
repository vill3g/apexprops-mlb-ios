
import logging

logger = logging.getLogger(__name__)
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    pass

from backend.btc.fees import net_pnl
from backend.btc.kalshi_trader import kalshi_trader
from backend.btc.ml_engine import get_ml_engine
from backend.btc.paper_balance import update_balance
from backend.btc.shadow_executor import update_shadow_settlements
from backend.core.push_notifications import send_web_push
from backend.database.models import get_user_by_id
from backend.engine.multi_asset_fetcher import \
    fetch_asset_candles as fetch_candles

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "trading_config.json")
from .shared import _history_lock


class SettlementMixin:
        def check_settlements(self, trades: Optional[List[Dict[str, Any]]] = None):
            """
            Settle completed Kalshi trades from Kalshi's own YES/NO result, for both Master and SaaS users.
            """
            now_ts = time.time()
            if (now_ts - getattr(self, "_last_settlement_check_ts", 0.0)) < 3.0:
                return
            self._last_settlement_check_ts = now_ts
    
            official_results: Dict[str, Dict[str, Any]] = {}
            
            def _count_of(t):
                try:
                    c = float(t.get("count", 1))
                except (TypeError, ValueError):
                    c = 1.0
                return int(c) if c.is_integer() else c

            def _pay_out(t, user_id, is_win, count, pnl):
                """Runs exactly once per trade, right after it is marked SETTLED: the win push
                notification and the paper-balance credit (a win pays $1 per contract; the
                entry cost and fee were already deducted when the trade was opened)."""
                if is_win and user_id:
                    try:
                        u = get_user_by_id(user_id)
                        if u and u.get('notify_trade_results', 1):
                            send_web_push(user_id, 'Trade Won! 🚀', f'+${pnl:.2f} profit on {t.get("ticker", "Kalshi")}')
                    except Exception as pe:
                        logger.info(f"Win notification failed for user {user_id}: {pe}")
                if str(t.get("mode", self.mode)).upper() != "PAPER" or not is_win:
                    return
                try:
                    if user_id:
                        from backend.database.models import \
                            credit_user_paper_balance
                        credit_user_paper_balance(user_id, float(count))
                    else:
                        update_balance(float(count), guest_id=getattr(self, '_guest_id', None))
                except Exception as ep:
                    logger.error(f"Failed to credit paper payout for trade {t.get('id')} (user {user_id}): {ep}")

            def _settle_list(trades_list, user_id=None):
                # Audit M1: each trade's settlement is fully self-contained. Previously `is_win`
                # was only assigned inside the official-result branch but read outside it, so a
                # trade still waiting on Kalshi's result either crashed (NameError) or - with
                # several pending trades - reused the PREVIOUS trade's `is_win`: a false "Won"
                # push plus a paper credit while still OPEN, then a second credit at the real
                # settlement. An official LOSS also fell through into the candle fallback.
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
                            count = _count_of(t)
                            is_win = side == official_result
                            market = official.get("market") or {}
                            settle_price = market.get("settlement_value") or market.get("settlement_value_dollars")
                            try:
                                settle_price = float(settle_price) if settle_price is not None else None
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Error parsing settle_price: {e}")
                                settle_price = None
    
                            t["status"] = "SETTLED"
                            t["result"] = "WIN" if is_win else "LOSS"
                            t["official_result"] = official_result
                            t["settlement_source"] = "kalshi_official"
                            if settle_price is not None and settle_price > 0:
                                t["settle_price"] = settle_price
                                
                            prior_realized_pnl = float(t.get("realized_pnl", 0.0))
                            # Net of the Kalshi entry fee (no fee is charged at settlement)
                            settlement_pnl = net_pnl(entry_price, 1.0 if is_win else 0.0, count)
                            t["pnl"] = round(prior_realized_pnl + settlement_pnl, 4)
                            t["settlement_pnl"] = settlement_pnl
                            t["settled_at"] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
                            modified = True
                            newly_settled_count += 1
                            _pay_out(t, user_id, is_win, count, settlement_pnl)
                            continue  # Kalshi's official result is final - never fall through to the candle fallback

                        # No official result yet. Kalshi-listed markets wait for it (up to 10 min
                        # after close) before the legacy candle fallback is allowed to decide.
                        if (t.get("prediction_kind") == "AUTO" or ticker.startswith("KX")) and not ticker.endswith("_SYNTH"):
                            if now_ts <= float(close_epoch) + 600:
                                continue
    
                        strike = float(t.get("strike", 0.0) or 0.0)
                        if strike <= 0:
                            continue
                        if settle_candles_df is None:
                            try:
                                settle_candles_df = fetch_candles(self.asset, timeframe="15m", limit=5)
                            except Exception as e:
                                logger.warning(f"Error fetching settle candles: {e}")
                                settle_candles_df = None
                        if settle_candles_df is None or len(settle_candles_df) < 2:
                            continue
                        settle_price = float(settle_candles_df.iloc[-2]["close"])
                        side = str(t.get("side", "")).upper()
                        entry_price = float(t.get("entry_price", 0.50))
                        count = _count_of(t)
                        is_win = (side == "YES" and settle_price > strike) or (side == "NO" and settle_price <= strike)
                        fallback_pnl = net_pnl(entry_price, 1.0 if is_win else 0.0, count)
                        t.update({
                            "status": "SETTLED", "result": "WIN" if is_win else "LOSS",
                            "settlement_source": "legacy_exchange_candle", "settle_price": settle_price,
                            "pnl": fallback_pnl,
                            "settled_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                        })
                        modified = True
                        newly_settled_count += 1
                        _pay_out(t, user_id, is_win, count, fallback_pnl)
                    except Exception as e:
                        logger.error(f"[AutoExecutor] Error checking settlement for trade {t.get('id')}: {e}")
                return modified, newly_settled_count
    
            with _history_lock:
                # Audit H4: decide settlements on the history as it is on disk NOW, while
                # holding the cross-process lock - never on a list the caller read earlier,
                # which the other process (web server vs worker) may have settled already.
                caller_list = trades
                trades = self._read_history_from_disk() if hasattr(self, "_read_history_from_disk") else (trades or self.get_trades_history())
                if not trades and caller_list:
                    trades = caller_list
    
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
                                ml_eng = get_ml_engine()
                                threading.Thread(target=ml_eng.train, daemon=True, name="MLRetrainThread").start()
                            except Exception as e:
                                logger.warning(f"[AutoExecutor] Post-settlement ML retrain launch failed: {e}")
                    except Exception as e:
                        logger.error(f"[AutoExecutor] Error saving trades in check_settlements: {e}")
                if caller_list is not None and caller_list is not trades:
                    caller_list[:] = trades  # the caller (e.g. get_status) sees the settled state
    
                # Note: SaaS users are settled authoritatively by backend.saas_settler.settle_saas_trades
    
            # Hook: RL Shadow Sandbox settlements
            try:
                update_shadow_settlements(kalshi_trader, official_results)
            except Exception as e:
                logger.error(f"[ShadowExecutor Hook] Error: {e}")

