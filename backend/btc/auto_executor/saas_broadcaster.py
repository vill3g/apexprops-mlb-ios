from backend.btc.data_fetcher import get_candle_countdown

import logging

from backend.btc.fees import entry_edge_cents, kalshi_order_fee, net_pnl

logger = logging.getLogger(__name__)
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np

try:
    pass
except ImportError:
    pass
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

from backend.auth.security import decrypt_kalshi_key
from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract
from backend.btc.chop_engine import evaluate_chop_contract
from backend.btc.indicators import add_all_indicators
from backend.btc.io_utils import atomic_json_write as _atomic_json_write
from backend.btc.kalshi_trader import PAPER_LATENCY_TAX_DOLLARS, KalshiTrader
from backend.btc.kalshi_trader import filled_count as _filled_count
from backend.btc.kalshi_trader import kalshi_trader
from backend.btc.pattern_detector import detect_candlestick_patterns
from backend.database import order_intents
from backend.database.models import (deduct_user_paper_balance,
                                     get_all_active_users, get_db_connection,
                                     get_user_lock)
from backend.engine.multi_asset_fetcher import \
    fetch_asset_candles as fetch_candles
from backend.engine.multi_asset_fetcher import (
                                                is_market_open)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "trading_config.json")
from .shared import (
    _SAAS_CANDLE_TTL,
    _SAAS_USERS_TTL,
    _saas_candle_cache,
    _saas_candle_cache_lock,
    _saas_users_cache,
    _saas_users_cache_lock,
    _user_last_traded_cache,
    _user_last_traded_lock,
    _user_trader_cache,
    _user_trader_cache_lock,
    classify_auto_regime,
)

# â”€â”€ Per-user signal snapshot (read by the dashboard's AI Intelligence panel) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# The worker evaluates each (trading_style, signal_source) combination that users run.
# The latest result per combination is saved so the web server can show every user the
# same forecast that will drive their own trades.
SIGNAL_SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                    "data", "signal_snapshot.json")
SIGNAL_SNAPSHOT_REFRESH_SEC = 15.0
_signal_snapshot: Dict[str, Any] = {}
_signal_snapshot_lock = threading.Lock()
_daily_limit_logged = set()   # (user_id, limit, date) already logged


def _order_flow(df, bars: int = 3):
    """Buy/sell pressure over the last few candles, -1 (all selling) .. +1 (all buying):
    the CVD proxy (volume signed by where each candle closed in its range) divided by volume."""
    try:
        tail = df.tail(bars)
        rng = (tail["high"] - tail["low"]).replace(0, float("nan"))
        signed = (tail["volume"] * (tail["close"] - tail["open"]) / rng).fillna(0).sum()
        vol = float(tail["volume"].sum())
        return round(max(-1.0, min(1.0, float(signed) / vol)), 3) if vol > 0 else 0.0
    except Exception:
        return None


def _snapshot_key(style, source) -> str:
    return f"{str(style).upper()}|{str(source).upper()}"


def _save_signal_snapshot(asset, ticker, strike, sec_left, results):
    """results: {(style, source): (effective_style, forecast, chart_row_dict)}"""
    now = time.time()
    with _signal_snapshot_lock:
        for (style, source), (eff_style, forecast, chart) in results.items():
            if not forecast:
                continue
            _signal_snapshot[_snapshot_key(style, source)] = {
                "ts": now,
                "asset": asset,
                "ticker": ticker,
                "strike": strike,
                "sec_left": sec_left,
                "effective_style": eff_style,
                "direction": forecast.get("direction", "PASS"),
                "probability_percent": forecast.get("probability_percent", 50.0),
                "ml_prob": forecast.get("ml_prob"),
                "conviction_grade": forecast.get("conviction_grade", ""),
                "pre_gate_direction": forecast.get("pre_gate_direction", ""),
                "pre_gate_prob": forecast.get("pre_gate_prob"),
                "pre_gate_grade": forecast.get("pre_gate_grade", ""),
                "catalysts": [str(c) for c in (forecast.get("catalysts") or [])][:6],
                "chart": chart,
            }
        # drop combinations nobody has refreshed for 10 minutes
        for k in [k for k, v in _signal_snapshot.items() if now - v.get("ts", 0) > 600]:
            _signal_snapshot.pop(k, None)
        data = {"updated": now, "results": dict(_signal_snapshot)}
    try:
        _atomic_json_write(SIGNAL_SNAPSHOT_PATH, data)
    except Exception as e:
        logger.debug(f"[SignalSnapshot] write failed: {e}")

def invalidate_saas_users_cache(user_id: Optional[int] = None):
    """Invalidate cached multi-tenant active-user list so modifications apply instantly."""
    with _saas_users_cache_lock:
        _saas_users_cache["ts"] = 0.0
        _saas_users_cache["users"] = None
    if user_id is not None:
        with _user_last_traded_lock:
            keys_to_del = [k for k in _user_last_traded_cache if k[0] == user_id]
            for k in keys_to_del:
                _user_last_traded_cache.pop(k, None)

def get_user_kalshi_trader(user: dict) -> Optional[Any]:
    """Retrieve or construct a cached KalshiTrader instance for a live user to reuse TLS connections."""
    uid = user.get("id")
    if not uid:
        return None
    key_id = user.get("kalshi_key_id")
    priv_enc = user.get("kalshi_priv_key_encrypted")
    if not key_id or not priv_enc:
        return None
    with _user_trader_cache_lock:
        if uid in _user_trader_cache:
            cached_kt, cached_enc = _user_trader_cache[uid]
            if cached_enc == priv_enc:
                return cached_kt
    try:
        priv_key = decrypt_kalshi_key(priv_enc)
        if not priv_key:
            return None
        kt = KalshiTrader(key_id=key_id, private_key_pem=priv_key)
        if not kt.is_authenticated():
            return None
        with _user_trader_cache_lock:
            _user_trader_cache[uid] = (kt, priv_enc)
        return kt
    except Exception as e:
        logger.error(f"[KalshiSessionCache] Error creating trader session for user #{uid}: {e}")
        return None

class SaasBroadcasterMixin:
        def _broadcast_trade_to_users(self, ticker: str, side: str, limit_price_dollars: float, pred_info: dict = None):
            if not getattr(self, "broadcast_trades", True):
                logger.info("[SaaS Broadcast] Broadcast disabled via Admin toggle. Skipping trade copy.")
                return
    
            try:
                
                users = get_all_active_users()
                if not users:
                    return
                    
                logger.info(f"[SaaS Broadcast] Broadcasting {side} on {ticker} to {len(users)} active users.")
                
                def execute_for_user(user):
                    try:
                        if not user.get('ai_enabled', 1): return
                        user_mode = user.get('trading_mode', 'PAPER')
                        
                        
                        from zoneinfo import ZoneInfo
                        _et_tz = ZoneInfo("America/New_York")
                        _now_dt = datetime.now(_et_tz)
                        now_est = _now_dt.isoformat()
                        today_str = _now_dt.strftime('%Y-%m-%d')
                        from backend.database.trade_store import TradeStore
                        history = TradeStore.get_recent_trades(user['id'], limit=100)
                        today_trades = [t for t in history if t.get("mode", "PAPER") == user_mode and str(t.get("timestamp", "")).startswith(today_str)]
                        max_trades = int(user.get("max_daily_trades", 10))
                        if len(today_trades) >= max_trades:
                            logger.info(f"[SaaS Broadcast] User {user['username']} skipped: Max daily trades reached ({max_trades})")
                            return
                        
                        max_risk = float(user.get("max_daily_risk", 50.0))
                        today_pnl = sum(float(t.get("pnl", 0.0)) for t in today_trades if t.get("status") in ["CLOSED", "SETTLED"])
                        today_open_cost = sum(float(t.get("entry_price", 0.0)) * int(t.get("count", 0)) for t in today_trades if t.get("status") == "OPEN")
                        effective_risk = today_pnl - today_open_cost
                        if effective_risk <= -abs(max_risk):
                            logger.info(f"[SaaS Broadcast] User {user['username']} skipped: Max daily risk reached (${max_risk})")
                            return
                        
                        filled_price = limit_price_dollars
                        contracts = 0
                        trade_id = str(uuid.uuid4())
                        
                        if user_mode == 'LIVE':
                            if not user.get('kalshi_key_id') or not user.get('kalshi_priv_key_encrypted'):
                                logger.info(f"[SaaS Broadcast] User {user['username']} skipped LIVE: missing Kalshi credentials")
                                return
                            priv_key = decrypt_kalshi_key(user['kalshi_priv_key_encrypted'])
                            if not priv_key:
                                logger.info(f"[SaaS Broadcast] User {user['username']} skipped LIVE: could not decrypt credentials")
                                return
                            kt = KalshiTrader(key_id=user['kalshi_key_id'], private_key_pem=priv_key)
                            if not kt.is_authenticated():
                                logger.info(f"[SaaS Broadcast] User {user['username']} skipped LIVE: Kalshi authentication failed")
                                return
                            bal_res = kt.get_balance()
                            if not bal_res.get('success'):
                                logger.info(f"[SaaS Broadcast] User {user['username']} skipped LIVE: could not fetch balance")
                                return
                            avail_bal = float(bal_res.get('balance_dollars', 0.0))
                            if avail_bal < 0.50:
                                logger.info(f"[SaaS Broadcast] User {user['username']} skipped LIVE: balance (${avail_bal:.2f}) < $0.50 minimum")
                                return
                            # Leave 5% buffer for Kalshi fees when using max available balance
                            risk_amount = min(float(user.get("trade_size_dollars", 5.0)), avail_bal * 0.95)

                            # Pillar 6: True Binary Options Half-Kelly Sizing
                            if bool(user.get('use_kelly_criterion', 0)):
                                p_win = float(pred_info.get('prob', 50.0)) / 100.0 if pred_info else 0.50
                                b_price = float(limit_price_dollars)
                                if p_win <= b_price:
                                    logger.info(f"[SaaS Broadcast] EV/Kelly Block: {user.get('username')} skipped trade @ ${b_price:.2f} (win prob {p_win*100:.1f}% <= ask)")
                                    return
                                f_star = (p_win - b_price) / (1.0 - b_price) if b_price < 1.0 else 0.0
                                kelly_frac = min(1.25, max(0.25, 0.50 * f_star))
                                risk_amount = max(0.50, risk_amount * kelly_frac)

                            # Include 0.04 slippage buffer in max cost estimation so we don't exceed Kalshi's balance check
                            max_cost_per_contract = min(limit_price_dollars + 0.04, 0.99)
                            contracts = int(risk_amount / max(0.01, max_cost_per_contract))
                            while contracts > 0 and (contracts * max_cost_per_contract + kalshi_order_fee(max_cost_per_contract, contracts)) > risk_amount:
                                contracts -= 1
                            if contracts < 1:
                                logger.info(f"[SaaS Broadcast] User {user['username']} skipped LIVE: balance (${avail_bal:.2f}) or trade size (${risk_amount:.2f}) insufficient for 1 contract at max cost ${max_cost_per_contract:.2f}")
                                return
                            res = kt.place_order(
                                ticker=ticker, side=side, count=contracts, 
                                limit_price_dollars=limit_price_dollars, dry_run=False, slippage_buffer_dollars=0.04
                            )
                            if not res.get('success'):
                                logger.error(f"[SaaS Broadcast] User {user['username']} LIVE order rejected by Kalshi: {res.get('error')}")
                                return
                            filled_price = res.get('filled_price', limit_price_dollars)
                            trade_id = res.get('client_order_id', trade_id)
                            contracts = _filled_count(res, contracts)  # H1: record the real fill size
                        else:
                            avail_bal = float(user.get('paper_balance', 500.0))
                            if avail_bal < 1.0: return
                            risk_amount = float(user.get("paper_trade_size_dollars", 50.0))

                            # Pillar 6: True Binary Options Half-Kelly Sizing
                            if bool(user.get('use_kelly_criterion', 0)):
                                p_win = float(pred_info.get('prob', 50.0)) / 100.0 if pred_info else 0.50
                                b_price = float(limit_price_dollars)
                                if p_win <= b_price:
                                    logger.info(f"[SaaS Broadcast] EV/Kelly Block: {user.get('username')} skipped trade @ ${b_price:.2f} (win prob {p_win*100:.1f}% <= ask)")
                                    return
                                f_star = (p_win - b_price) / (1.0 - b_price) if b_price < 1.0 else 0.0
                                kelly_frac = min(1.25, max(0.25, 0.50 * f_star))
                                risk_amount = max(1.0, risk_amount * kelly_frac)

                            max_cost_per_contract = min(limit_price_dollars + 0.04 + PAPER_LATENCY_TAX_DOLLARS, 0.99)
                            contracts = int(risk_amount / max(0.01, max_cost_per_contract))
                            while contracts > 0 and (contracts * max_cost_per_contract + kalshi_order_fee(max_cost_per_contract, contracts)) > risk_amount:
                                contracts -= 1
                            if contracts < 1:
                                return
                            res = kalshi_trader.place_order(
                                ticker=ticker, side=side, count=contracts,
                                limit_price_dollars=limit_price_dollars, dry_run=True, slippage_buffer_dollars=0.04,
                                available_balance=avail_bal,
                            )
                            if not res.get('success'):
                                logger.info(f"[SaaS Broadcast] User {user['username']} PAPER order not simulated: {res.get('error')}")
                                return
                            filled_price = res.get('filled_price', limit_price_dollars)
                            contracts = int(res.get('count', contracts))
                            trade_id = res.get('client_order_id', trade_id)
                            # total_cost excludes the exchange fee; add it, same as the main SaaS path.
                            cost = float(res.get('total_cost', contracts * filled_price)) + kalshi_order_fee(filled_price, contracts)
                            # Atomic deduction (was a read-modify-write that could lose updates)
                            if not deduct_user_paper_balance(user['id'], cost):
                                return
    
                        logger.info(f'[SaaS Broadcast] Successfully traded for User {user["username"]} ({contracts} contracts in {user_mode})')
                        import json

                        from backend.database.trade_store import TradeStore
                        market_snapshot = {}
                        if pred_info and isinstance(pred_info, dict):
                            market_snapshot = pred_info.get("market_snapshot", {
                                "price": pred_info.get("spot", 0),
                                "target": pred_info.get("strike", 0)
                            })
                        
                        trade_record = {
                                "id": trade_id,
                                "timestamp": now_est,
                                "ticker": ticker,
                                "direction": side.upper(),
                                "side": side.upper(),
                                "prediction_direction": side.upper(),
                                "probability_percent": pred_info.get('prob', 50) if pred_info else 50,
                                "entry_price": filled_price,
                                "count": contracts,
                                "status": "OPEN",
                                "mode": user_mode,
                                "pnl": 0.0,
                                "reason": "AI_SIGNAL",
                                "trading_style": user.get('trading_style', 'AUTO'),
                                "signal_source": user.get('signal_source', 'BLEND'),
                                "strike": pred_info.get("strike", 0) if pred_info else 0.0,
                                "market_snapshot": json.dumps(market_snapshot)
                            }
                        TradeStore.insert_trade(user['id'], trade_record)
                    except Exception as e:
                        logger.error(f'[SaaS Broadcast] Error executing for user {user.get("username")}: {e}')
                        
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    executor.map(execute_for_user, users)
            except Exception as e:
                logger.error(f"[SaaS Broadcast] Critical error during broadcast: {e}")

        def evaluate_and_execute_saas_users(self) -> None:
            '''
            Isolated multi-tenant orchestrator for SaaS users.
            Runs concurrently alongside the Master bot.
            '''
            if not getattr(self, "broadcast_trades", True):
                return
    
            if not self._saas_eval_lock.acquire(blocking=False):
                return
            
            lock_held = True
            try:
                now_ts = time.time()
                if (now_ts - self._last_saas_eval_time) < 4.0:
                    return
                self._last_saas_eval_time = now_ts
    
                
                if not is_market_open(self.asset):
                    return
                    
                countdown_info = get_candle_countdown(timeframe="15m")
                sec_left = countdown_info.get("seconds_left", 900)
                sec_elapsed = 900 - sec_left
                
                # Expiration Safety Guard: Never enter brand new trades within 180s (3 minutes) of expiration
                if sec_left < 15:
                    return
                    
                # Allow synthetic markets so PAPER trading works for ETH and GOLD
                active_m = kalshi_trader.get_active_15m_market(series_ticker=f"KX{self.asset}15M", allow_synthetic=True, min_seconds_left=15)
                if not active_m: return
                
                current_interval_id = active_m.get("ticker") or active_m.get("event_ticker", "")
                if not current_interval_id: return
                
                try:
                    strike = float(active_m.get("strike_price") or 0.0)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing strike: {e}")
                    strike = 0.0
                if strike <= 0: return
    
                # â”€â”€ P1: Cached active-users (15s TTL) â€” avoids new DB connection every 4s â”€â”€
                _now = time.time()
                with _saas_users_cache_lock:
                    if _saas_users_cache["users"] is None or (_now - _saas_users_cache["ts"]) > _SAAS_USERS_TTL:
                        _saas_users_cache["users"] = get_all_active_users() or []
                        _saas_users_cache["ts"] = _now
                    users = list(_saas_users_cache["users"])
    
                active_users = [u for u in users if u.get('ai_enabled', 1) and self.asset.upper() in [x.strip() for x in u.get('target_asset', 'BTC').upper().split(',')]]
                if not users: return  # users with AUTO off still get a dashboard forecast (no trades)
    
                # 1. Filter out users who have ALREADY traded this interval.
                #    Fast in-memory cache check avoids repeated disk I/O every 4s.
                users_to_trade = []
                user_hist_cache: dict = {}  # uid -> (path, hist_list)
                from backend.btc import inflight_orders
                for u in active_users:
                    uid = u['id']
                    u_source = str(u.get('signal_source', '')).upper().strip()
                    is_scalper = (u_source == "RL_SCALPER")
                    
                    with _user_last_traded_lock:
                        if not is_scalper and _user_last_traded_cache.get((uid, self.asset)) == current_interval_id:
                            continue
                    from backend.database.trade_store import TradeStore
                    loaded_hist = TradeStore.get_recent_trades(uid, limit=50)
                    has_traded = False
                    
                    # Check if user has traded or is currently trading this interval
                    if not is_scalper:
                        if inflight_orders.has_inflight(uid, current_interval_id):
                            has_traded = True
                        else:
                            interval_trades = [t for t in loaded_hist if t.get("ticker") == current_interval_id]
                            if any(str(t.get("status", "")).upper() == "OPEN" for t in interval_trades):
                                # An active position is currently open on this contract
                                has_traded = True
                            elif len(interval_trades) >= 3:
                                # Maximum 3 entries per 15-minute candle reached
                                has_traded = True
                                with _user_last_traded_lock:
                                    _user_last_traded_cache[(uid, self.asset)] = current_interval_id
                            elif interval_trades:
                                # All trades on this contract are closed and len < 3. Check newest closed trade:
                                last_t = interval_trades[0]
                                last_exit = str(last_t.get("exit_reason") or last_t.get("reason") or "").upper()
                                is_take_profit = ("TAKE_PROFIT" in last_exit) or ("TRAILING_STOP" in last_exit) or (float(last_t.get("pnl") or 0.0) > 0 and "STOP_LOSS" not in last_exit)
                                can_reenter = is_take_profit or bool(u.get("second_entry_enabled", 0))
                                if can_reenter:
                                    has_traded = False  # Bot is allowed to re-enter!
                                else:
                                    has_traded = True
                                    with _user_last_traded_lock:
                                        _user_last_traded_cache[(uid, self.asset)] = current_interval_id

                    user_hist_cache[uid] = (None, loaded_hist)
                    if is_scalper or not has_traded:
                        users_to_trade.append(u)
    
                # Combinations whose dashboard snapshot is getting old are re-evaluated even
                # if no user needs to trade them right now (e.g. everyone already traded).
                _now_snap = time.time()
                with _signal_snapshot_lock:
                    snapshot_combos = set()
                    for u in users:
                        combo = (str(u.get('trading_style', 'AUTO')).upper(), str(u.get('signal_source', 'RL_DQN')).upper())
                        snap = _signal_snapshot.get(_snapshot_key(*combo))
                        if not snap or snap.get("ticker") != current_interval_id or _now_snap - snap.get("ts", 0) > SIGNAL_SNAPSHOT_REFRESH_SEC:
                            snapshot_combos.add(combo)

                if users_to_trade:
                    logger.info(f"===> Users in users_to_trade: {[u['username'] for u in users_to_trade]}")
                else:
                    logger.info(f"===> users_to_trade is EMPTY!")
                if not users_to_trade and not snapshot_combos:
                    return
    
                # 2. Group by configurations
                required_evals = set()
                for u in users_to_trade:
                    u_style = str(u.get('trading_style', 'AUTO')).upper()
                    u_source = str(u.get('signal_source', 'RL_DQN')).upper()
                    required_evals.add((u_style, u_source))
                required_evals |= snapshot_combos
    
                # â”€â”€ P1: Cached 15m candle data (8s TTL per asset) â€” avoids Coinbase HTTP hit every 4s â”€â”€
                _now2 = time.time()
                with _saas_candle_cache_lock:
                    entry = _saas_candle_cache.get(self.asset)
                    if entry is None or (_now2 - entry["ts"]) > _SAAS_CANDLE_TTL:
                        try:
                            _df_fresh = fetch_candles(self.asset, timeframe="15m", limit=350)
                            _df_ind_fresh = add_all_indicators(_df_fresh)
                            _saas_candle_cache[self.asset] = {
                                "df": _df_fresh,
                                "df_ind": _df_ind_fresh,
                                "ts": _now2
                            }
                        except Exception as _candle_err:
                            logger.error(f"[SaaS Broadcast] Candle fetch/indicator failed for {self.asset}, skipping cycle: {_candle_err}")
                            return
                    df_base = _saas_candle_cache[self.asset]["df"]
                    df_ind_base = _saas_candle_cache[self.asset]["df_ind"]
    
                if df_base is None or df_ind_base is None:
                    return
    
    
                eval_results = {}
                _chart_rows = {}
                for req_style, req_source in required_evals:
                    try:
                        effective_style = req_style
                        auto_regime_info = None
                        is_pure_rl = str(req_source).upper().strip() in ["RL_DQN", "RL", "DQN", "DEEP_Q_NETWORK"]

                        if effective_style == "AUTO":
                            auto_regime_info = classify_auto_regime(df_ind_base, sec_left=sec_left)
                            effective_style = auto_regime_info["style"]
                            logger.info(
                                f"[SaaS Broadcast] Auto 2.0 Regime: {auto_regime_info['regime']} -> Routed to {effective_style} "
                                f"({auto_regime_info['reason']})"
                            )
                                
                        if effective_style == "MOMENTUM_SURFER":
                            df_target = fetch_candles(self.asset, timeframe="1m", limit=350)
                            df_ind_target = add_all_indicators(df_target)
                        else:
                            df_ind_target = df_ind_base
                            
                        patterns = []
                        if effective_style not in ["MOMENTUM_SURFER", "CAPITAL_GUARD"]:
                            try:
                                patterns = detect_candlestick_patterns(df_ind_target)
                            except Exception as e:
                                logger.warning(f"Error detecting candlestick patterns: {e}")
                                patterns = []
                            
                        if effective_style == "CAPITAL_GUARD":
                            forecast = {
                                "recommendation": "PASS / CHOP DEADZONE (CAPITAL GUARD)",
                                "direction": "PASS",
                                "action_type": "PASS",
                                "probability_percent": 50.0,
                                "predicted_probability": 0.5,
                                "ml_prob": 0.5,
                                "pre_gate_direction": "PASS",
                                "pre_gate_prob": 50.0,
                                "pre_gate_grade": "GRADE C / PASS",
                                "conviction_grade": "PASS / CHOP DEADZONE (CAPITAL GUARD)",
                                "conviction_badge": "ðŸ›¡ï¸ CAPITAL GUARD (PASS)",
                                "target_settlement_zone": "--",
                                "primary_edge": "Low-volatility compression deadzone (ADX < 18, Vol < 0.85). Preserving capital for high-edge expansion.",
                                "catalysts": ["Capital Guard active: zero edge detected"],
                                "raw_features": {},
                                "auto_regime": auto_regime_info,
                            }
                        elif not is_pure_rl and effective_style == "CHOP":
                            forecast = evaluate_chop_contract(df_ind_target, target_price=strike, kalshi_m=active_m)
                        else:
                            forecast = evaluate_next_15m_contract(
                                df_ind_target, target_price=strike, patterns=patterns, kalshi_m=active_m, trading_style=effective_style, signal_isolation=req_source, asset=self.asset
                            )
                            if auto_regime_info:
                                forecast["auto_regime"] = auto_regime_info
                            
                        if req_source == "TECHNICAL_ONLY":
                            forecast["conviction_grade"] = "TECHNICAL_ONLY"
                            if forecast.get("probability_percent", 50) > 50:
                                forecast["probability_percent"] = 75.0
                                
                        eval_results[(req_style, req_source)] = (effective_style, forecast)
                        try:
                            _last = df_ind_target.iloc[-1]
                            _chart_rows[(req_style, req_source)] = {
                                "open": float(_last["open"]), "close": float(_last["close"]),
                                "ema9": float(_last.get("ema_9", _last["close"])), "ema21": float(_last.get("ema_21", _last["close"])),
                                "flow": _order_flow(df_ind_target),
                            }
                        except Exception:
                            _chart_rows[(req_style, req_source)] = None
                    except Exception as e:
                        logger.error(f"[SaaS Eval] Error evaluating {req_style}/{req_source}: {e}")
                        eval_results[(req_style, req_source)] = (req_style, None)
                        
                try:
                    _save_signal_snapshot(self.asset, current_interval_id, strike, sec_left,
                                          {k: (v[0], v[1], _chart_rows.get(k)) for k, v in eval_results.items()})
                except Exception as _snap_err:
                    logger.debug(f"[SignalSnapshot] {_snap_err}")
                if not users_to_trade:
                    return

                # 3. Route to users in parallel for maximum execution speed and zero slippage
                def _execute_single_user_trade(user):
                    try:
                        u_style = str(user.get('trading_style', 'AUTO')).upper()
                        u_source = str(user.get('signal_source', 'RL_DQN')).upper()

                        if u_source == "RL_SCALPER":
                            # The scalper places orders only when a training run validated it on
                            # held-out markets. Until then RL_SCALPER users get NO trades (it used to
                            # fall through to the generic signal with no once-per-market limit).
                            try:
                                from backend.btc.rl_scalper import (
                                    get_rl_scalper, scalper_live_enabled)
                                if not scalper_live_enabled():
                                    return
                                # Trained only on the first 4 minutes of each market (see train_rl_scalper.py);
                                # later positions are held to settlement / normal stop-loss & take-profit.
                                if (900 - float(sec_left)) > 240:
                                    logger.info(f"[SaaS Scalper] User {user.get('username')} skipped: sec_elapsed={900 - float(sec_left):.0f} > 240s limit")
                                    return
                                from backend.btc.rl_priced import (
                                    _interval_index, kalshi_fee,
                                    market_features)
                                from backend.database.models import \
                                    credit_user_paper_balance
                                from backend.database.trade_store import \
                                    TradeStore

                                agent = get_rl_scalper()
                                user_mode = str(user.get('trading_mode', 'PAPER')).upper()
                                uid = user['id']

                                history = TradeStore.get_recent_trades(uid, limit=50)
                                this_market = [t for t in history if t.get("ticker") == current_interval_id]
                                open_trade = next((t for t in this_market if t.get("status") == "OPEN"
                                                   and str(t.get("mode", "PAPER")).upper() == user_mode), None)
                                pos_type, entry_price = 0.0, 0.0
                                if open_trade:
                                    pos_type = 1.0 if str(open_trade.get("side", "")).upper() == "YES" else -1.0
                                    entry_price = float(open_trade.get("entry_price", 0.0) or 0.0)

                                # Kalshi prices are already in dollars (0.52), not cents
                                yes_ask = float(active_m.get("yes_ask") or 0.0)
                                yes_bid = float(active_m.get("yes_bid") or 0.0)
                                no_ask = float(active_m.get("no_ask") or (1.0 - yes_bid))
                                no_bid = float(active_m.get("no_bid") or (1.0 - yes_ask))
                                if not (0.0 < yes_bid < yes_ask < 1.0):
                                    return

                                unrealized_pnl = 0.0
                                if pos_type == 1.0:
                                    unrealized_pnl = yes_bid - entry_price - kalshi_fee(yes_bid)
                                elif pos_type == -1.0:
                                    unrealized_pnl = no_bid - entry_price - kalshi_fee(no_bid)

                                # Same feature construction as training: the candle that opens this
                                # interval, with windows ending before it (index -1 made the "24h"
                                # windows span the whole candle history).
                                interval_start = int(time.time() // 900 * 900)
                                df_feat, fi = _interval_index(df_ind_base, interval_start)
                                if fi is None or fi < 300:
                                    return
                                base_feats = market_features(df_feat, fi)
                                keys = sorted(base_feats.keys())
                                vec = [base_feats[k] for k in keys]
                                vec.extend([pos_type, unrealized_pnl, yes_ask, yes_bid, no_ask, no_bid, float(sec_left)])
                                state = np.array(vec, dtype=np.float32)
                                if agent.state_dim != len(state):
                                    logger.warning(f"[SaaS Scalper] Model expects {agent.state_dim} inputs, got {len(state)}; no trade.")
                                    return
                                valid = [0, 3] if pos_type != 0.0 else [0, 1, 2]
                                action = agent.select_action(state, exploit=True, valid_actions=valid)
                                logger.info(f"[SaaS Scalper] {user.get('username')} pos={pos_type:+.0f} pnl={unrealized_pnl:+.3f} action={action}")

                                if action == 0:
                                    return
                                if action == 3:
                                    side_l = "yes" if pos_type == 1.0 else "no"
                                    count = float(open_trade.get("count", 0) or 0)
                                    exit_price = yes_bid if pos_type == 1.0 else no_bid
                                    if user_mode == "LIVE":
                                        kt = get_user_kalshi_trader(user)
                                        if not kt:
                                            return
                                        c_res = kt.close_position(ticker=current_interval_id, purchased_side=side_l,
                                                                  count=count, dry_run=False)
                                        if not c_res.get("success"):
                                            logger.error(f"[SaaS Scalper] LIVE close failed for {user.get('username')}: {c_res.get('error')}")
                                            return
                                        exit_price = float(c_res.get("exit_price", exit_price))
                                        count = float(c_res.get("filled_count", count) or count)
                                    closed = TradeStore.close_if_open(uid, open_trade, {
                                        "exit_reason": "SCALPER_CLOSE",
                                        "exit_price": round(exit_price, 4),
                                        "pnl": net_pnl(entry_price, exit_price, count),
                                        "settled_at": time.time(),
                                    })
                                    if closed and user_mode == "PAPER":
                                        credit_user_paper_balance(uid, count * exit_price - kalshi_order_fee(exit_price, count))
                                    return
                                # Entries: never while a position is open, at most 3 per market
                                if open_trade is not None or len(this_market) >= 3:
                                    return
                                forecast = {"direction": "yes" if action == 1 else "no", "probability_percent": 50.0,
                                            "catalysts": ["RL scalper entry"], "raw_features": []}
                                eff_style = "SCALPER"
                            except Exception as scale_err:
                                logger.error(f"[SaaS Scalper] Error: {scale_err}")
                                return
                        
                        if u_source != "RL_SCALPER":
                            eff_style, forecast = eval_results.get((u_style, u_source), (u_style, None))
                        if not forecast: return
                        
                        direction = forecast.get("direction", "PASS")
                        conf = forecast.get("probability_percent", 50.0)
                        
                        is_user_rl = str(u_source).upper().strip() in ["RL_DQN", "RL", "DQN", "DEEP_Q_NETWORK"]
                        is_auto_force = bool(user.get("auto_force_trade", 0))
                        is_ignore_pass_tech = bool(user.get("ignore_pass_technical", 0))
                        is_one_shot = bool(user.get("one_shot_ai", 0))

                        min_conf = 60.0
                        if eff_style == "MOMENTUM_SURFER" and not is_user_rl:
                            if sec_left < 240:
                                # Time Decay block
                                return
                            min_conf = 60.0 if sec_elapsed <= 60 else 75.0
                            conf = max(conf, 100.0 - conf)
                            if conf < min_conf and not (is_auto_force or is_ignore_pass_tech or is_one_shot):
                                return
                        elif eff_style == "PREDICTION":
                            # Wait up to 1m 30s (90s) from interval open so it does not enter blindly
                            if sec_elapsed < 90 and not (is_auto_force or is_ignore_pass_tech or is_one_shot):
                                logger.debug(f"[SaaS Broadcast] User {user.get('username')} PREDICTION waiting for 1m 30s open (sec_elapsed={sec_elapsed:.0f}s < 90s)")
                                return
                            if sec_left < 15:
                                return
                            actual_win_conf = max(conf, 100.0 - conf)
                            if actual_win_conf < 58.0 and not (is_auto_force or is_ignore_pass_tech or is_one_shot):
                                logger.debug(f"[SaaS Broadcast] User {user.get('username')} PREDICTION skipped: conf {actual_win_conf:.1f}% < 58.0%")
                                return
                            
                        dir_clean = str(direction).upper().strip()
                        if dir_clean in ["ABOVE", "UP", "YES", "BUY YES", "BID YES", "STRONG BULLISH (UP)", "BULLISH (UP)"]:
                            side = "yes"
                        elif dir_clean in ["BELOW", "DOWN", "NO", "BUY NO", "BID NO", "STRONG BEARISH (DOWN)", "BEARISH (DOWN)"]:
                            side = "no"
                        else:
                            side = None
    
                        consume_one_shot = False
                        # Check user override preferences if market evaluation resulted in PASS
                        if not side:
                            if eff_style == "CAPITAL_GUARD":
                                logger.info(f"[SaaS Broadcast] User {user.get('username')} skipping: CAPITAL GUARD strictly blocks overrides.")
                                return
                            
                            if is_auto_force or is_one_shot:
                                raw_ml_prob = float(forecast.get("ml_prob", 0.50))
                                if raw_ml_prob > 0.50:
                                    side = "yes"
                                    conf = max(51.0, raw_ml_prob * 100.0)
                                elif raw_ml_prob < 0.50:
                                    side = "no"
                                    conf = max(51.0, (1.0 - raw_ml_prob) * 100.0)
                                else:
                                    pg_dir = str(forecast.get("pre_gate_direction", "")).upper()
                                    if pg_dir in ["ABOVE", "YES"]:
                                        side = "yes"
                                        conf = float(forecast.get("pre_gate_prob", 51.0))
                                    elif pg_dir in ["BELOW", "NO"]:
                                        side = "no"
                                        conf = float(forecast.get("pre_gate_prob", 51.0))
                                    else:
                                        # Extreme fallback: look at physical chart trend and short-term momentum
                                        trend = str(forecast.get("raw_features", {}).get("trend_1h", "UP")).upper()
                                        ema_9 = float(forecast.get("raw_features", {}).get("ema_9", 0))
                                        ema_21 = float(forecast.get("raw_features", {}).get("ema_21", 0))
                                        if trend in ["UP", "BULLISH"] or (ema_9 > ema_21 and ema_21 > 0):
                                            side = "yes"
                                        else:
                                            side = "no"
                                        conf = 51.0
                                        
                                # The 1-shot is used up just before the order, once every check has passed
                                consume_one_shot = bool(is_one_shot and side)
                                        
                            elif is_ignore_pass_tech:
                                pg_dir = str(forecast.get("pre_gate_direction", "")).upper()
                                if pg_dir in ["ABOVE", "YES"]:
                                    side = "yes"
                                    conf = float(forecast.get("pre_gate_prob", 60.0))
                                elif pg_dir in ["BELOW", "NO"]:
                                    side = "no"
                                    conf = float(forecast.get("pre_gate_prob", 60.0))
                                else:
                                    raw_ml_prob = float(forecast.get("ml_prob", 0.50))
                                    if raw_ml_prob > 0.50:
                                        side = "yes"
                                        conf = max(55.0, raw_ml_prob * 100.0)
                                    elif raw_ml_prob < 0.50:
                                        side = "no"
                                        conf = max(55.0, (1.0 - raw_ml_prob) * 100.0)
                                    else:
                                        trend = str(forecast.get("raw_features", {}).get("trend_1h", "UP")).upper()
                                        side = "yes" if trend in ["UP", "BULLISH"] else "no"
                                        conf = 55.0
                        if not side:
                            logger.info(f"[SaaS Broadcast] User {user.get('username')} skipping: direction is {direction} (conf: {conf}%)")
                            return
    
                        # Physical Chart Direction Guard for SaaS user trades
                        is_oversold_bounce = ("Absorption Hammer" in str(forecast.get("catalysts", [])) or "Oversold Spring" in str(forecast.get("catalysts", [])) or "Bullish Liquidity Sweep" in str(forecast.get("catalysts", [])))
                        is_overbought_fade = ("Rejection Pin" in str(forecast.get("catalysts", [])) or "Overbought Exhaustion" in str(forecast.get("catalysts", [])) or "Bearish Liquidity Sweep" in str(forecast.get("catalysts", [])))
                        c_eval = df_ind_target.iloc[-1]
                        c_open = float(c_eval["open"])
                        c_close = float(c_eval["close"])
                        c_ema9 = float(c_eval.get("ema_9", c_close))
                        c_ema21 = float(c_eval.get("ema_21", c_close))
                        delta_strike = c_close - strike
    
                        chart_conflict = False
                        if side == "yes":
                            if ((delta_strike < -25.0 and (c_close < c_open) and (c_ema9 < c_ema21)) or (delta_strike < -40.0 and (c_close < c_open))) and not is_oversold_bounce:
                                chart_conflict = True
                                conflict_reason = f"Spot ${c_close:,.2f} is ${abs(delta_strike):.2f} below strike ${strike:,.2f} with red candle"
                        elif side == "no":
                            if ((delta_strike > 25.0 and (c_close > c_open) and (c_ema9 > c_ema21)) or (delta_strike > 40.0 and (c_close > c_open))) and not is_overbought_fade:
                                chart_conflict = True
                                conflict_reason = f"Spot ${c_close:,.2f} is ${delta_strike:.2f} above strike ${strike:,.2f} with green candle"
    
                        if chart_conflict:
                            if is_ignore_pass_tech or is_auto_force or is_one_shot:
                                logger.info(f"[SaaS Multitenant] âš ï¸ User {user.get('username')} bypassed chart conflict ({conflict_reason}) due to force_trade setting.")
                            else:
                                logger.warning(
                                    f"[SaaS Multitenant] ðŸ›‘ User {user.get('username')} trade blocked: Side {side.upper()} conflicts with physical chart trend ({conflict_reason})."
                                )
                                return
                            
                        raw_ask = active_m.get(f"{side}_ask")
                        market_price = float(raw_ask) if raw_ask is not None else 0.0
                        if market_price < 0.15 or market_price > 0.85:
                            logger.warning(f"[SaaS Multitenant] Skipping trade for {current_interval_id}: ask price ${market_price:.2f} outside safe entry corridor ($0.15 - $0.85)")
                            return

                        # Multi-entry / DCA Discipline Guard (for 2nd and 3rd entries on same contract)
                        prior_entries = [t for t in user_hist_cache.get(user['id'], (None, []))[1] if t.get("ticker") == current_interval_id]
                        entry_num = len(prior_entries) + 1
                        if entry_num > 1 and u_source != "RL_SCALPER":
                            reentry_max_ask = float(user.get("second_entry_max_ask", 0.75) or 0.75)
                            if market_price > reentry_max_ask:
                                logger.info(f"[SaaS Multitenant] User {user.get('username')} skipped re-entry #{entry_num}: ask ${market_price:.2f} exceeds re-entry cap ${reentry_max_ask:.2f}")
                                return

                            if sec_left < 210:
                                logger.info(f"[SaaS Multitenant] User {user.get('username')} skipped re-entry #{entry_num}: only {sec_left/60.0:.1f}m left in candle (< 3.5m min)")
                                return

                            last_trade = prior_entries[0]
                            last_exit_price = float(last_trade.get("exit_price") or last_trade.get("entry_price") or 0.50)
                            last_pnl = float(last_trade.get("pnl") or 0.0)
                            last_reason = str(last_trade.get("exit_reason") or last_trade.get("reason") or "").upper()
                            was_profit = ("TAKE_PROFIT" in last_reason) or ("TRAILING_STOP" in last_reason) or (last_pnl > 0 and "STOP_LOSS" not in last_reason)

                            if was_profit:
                                if market_price > (last_exit_price - 0.03):
                                    logger.info(f"[SaaS Multitenant] User {user.get('username')} skipped re-entry #{entry_num}: ask ${market_price:.2f} has not pulled back >= 3Â¢ below scalp exit ${last_exit_price:.2f}")
                                    return
                            else:
                                initial_entry_price = float(prior_entries[-1].get("entry_price") or 0.50)
                                dca_target_max = initial_entry_price * 0.85
                                if market_price > dca_target_max:
                                    logger.info(f"[SaaS Multitenant] User {user.get('username')} skipped DCA re-entry #{entry_num}: ask ${market_price:.2f} is not discounted >= 15% from initial entry ${initial_entry_price:.2f} (max ${dca_target_max:.2f})")
                                    return

                        # Daily limits (user settings max_daily_trades / max_daily_risk)
                        from backend.database.trade_store import \
                            daily_limit_reason
                        limit_reason = daily_limit_reason(user, user.get('trading_mode', 'PAPER'))
                        if limit_reason:
                            _log_key = (user['id'], limit_reason.split(' (')[0], datetime.now().date())
                            if _log_key not in _daily_limit_logged:
                                _daily_limit_logged.add(_log_key)
                                logger.info(f"[SaaS Multitenant] {user.get('username')}: {limit_reason}. No more bot trades today.")
                            return

                        # Edge Guard (per-user setting, on by default): only buy when the forecast
                        # probability beats the price after Kalshi's fee by more than the user's minimum.
                        # The RL scalper decides by action, not probability, so it is exempt.
                        if not is_auto_force and not is_one_shot and u_source != "RL_SCALPER" and bool(user.get("edge_gate_enabled", 1)):
                            min_edge = float(user.get("min_edge_cents", 0.0) or 0.0)
                            edge = entry_edge_cents(conf, market_price)
                            if edge <= min_edge:
                                logger.info(
                                    f"[SaaS Multitenant] Edge Guard: {user.get('username')} skipped {side.upper()} @ {market_price:.2f} "
                                    f"on {current_interval_id} (prob {float(conf):.1f}%, edge {edge:+.1f}c <= min {min_edge:.1f}c)")
                                return

                        if consume_one_shot:
                            try:
                                with get_db_connection() as c_db:
                                    c_db.execute("UPDATE users SET one_shot_ai = 0 WHERE id = ?", (user['id'],))
                                    c_db.commit()
                            except Exception as oe:
                                logger.debug(f"[SaaS Multitenant] Reset one_shot_ai error: {oe}")

                        user_mode = user.get('trading_mode', 'PAPER')
                        trade_id = str(uuid.uuid4())
                        filled_price = market_price
                        contracts = 0
                        requested_contracts = 0
                        
                        if user_mode == 'LIVE':
                            if active_m.get("is_synthetic") or str(active_m.get("ticker", "")).endswith("_SYNTH"):
                                logger.info(f"[SaaS Multitenant] User {user.get('username')} skipped LIVE: {self.asset} is a synthetic market (PAPER only).")
                                return
                            
                            kt = get_user_kalshi_trader(user)
                            if not kt:
                                logger.warning(f"[SaaS Multitenant] User {user.get('username')} skipped LIVE: could not create Kalshi session")
                                return
                            bal_res = kt.get_balance()
                            if not bal_res.get('success'):
                                logger.warning(f"[SaaS Multitenant] User {user.get('username')} skipped LIVE: failed to fetch balance")
                                return
                            avail_bal = float(bal_res.get('balance_dollars', 0.0))
                            target_ex = active_m.get('exchange_index') if active_m else None
                            if target_ex is not None:
                                for b_item in bal_res.get('raw', {}).get('balance_breakdown', []):
                                    if b_item.get('exchange_index') == target_ex:
                                        avail_bal = min(avail_bal, float(b_item.get('balance', avail_bal)))
                                        break
                            if avail_bal < 0.50:
                                logger.warning(f"[SaaS Multitenant] User {user.get('username')} skipped LIVE: balance (${avail_bal:.2f} on ex {target_ex}) < $0.50 minimum")
                                return
                            # Leave 5% buffer for Kalshi fees when using max available balance
                            risk_amount = min(float(user.get("trade_size_dollars", 5.0)), avail_bal * 0.95)
                            # Pillar 6: True Binary Options Half-Kelly Sizing
                            if bool(user.get('use_kelly_criterion', 0)):
                                p_win = float(conf) / 100.0 if conf else 0.50
                                b_price = float(market_price)
                                if p_win <= b_price:
                                    logger.info(f"[SaaS Broadcast] EV/Kelly Block: {user.get('username')} skipped trade @ ${b_price:.2f} (win prob {p_win*100:.1f}% <= ask)")
                                    return
                                f_star = (p_win - b_price) / (1.0 - b_price) if b_price < 1.0 else 0.0
                                kelly_frac = min(1.25, max(0.25, 0.50 * f_star))
                                risk_amount = max(0.50, risk_amount * kelly_frac)

                            # Include 0.04 slippage buffer in max cost estimation so we don't exceed Kalshi's balance check
                            max_cost_per_contract = min(market_price + 0.04, 0.99)
                            contracts = int(risk_amount / max(0.01, max_cost_per_contract))
                            while contracts > 0 and (contracts * max_cost_per_contract + kalshi_order_fee(max_cost_per_contract, contracts)) > risk_amount:
                                contracts -= 1
                            if contracts < 1:
                                logger.warning(f"[SaaS Multitenant] User {user.get('username')} skipped LIVE: balance (${avail_bal:.2f}) or trade size (${risk_amount:.2f}) insufficient for 1 contract at max cost ${max_cost_per_contract:.2f}")
                                return
                            # M-DUP: one automated LIVE entry per user per market, enforced in users.db
                            # (survives restarts and holds across processes - see order_intents.py).
                            # The RL scalper intentionally trades the same market repeatedly, so it's exempt.
                            intent_key = None
                            intent_ticker = current_interval_id
                            if u_source != "RL_SCALPER":
                                intent_key = order_intents.account_key_for_user(user['id'])
                                prior_entries = [t for t in user_hist_cache.get(user['id'], (None, []))[1] if t.get("ticker") == current_interval_id]
                                entry_num = len(prior_entries) + 1
                                intent_ticker = f"{current_interval_id}#entry_{entry_num}" if entry_num > 1 else current_interval_id
                                if not order_intents.claim(intent_key, intent_ticker, side):
                                    logger.warning(f"[SaaS Multitenant] User {user.get('username')} skipped LIVE: an entry was already attempted on {intent_ticker} (order_intents)")
                                    with _user_last_traded_lock:
                                        _user_last_traded_cache[(user['id'], self.asset)] = current_interval_id
                                    return
                            logger.info(f"[SaaS Multitenant] Placing LIVE order for {user.get('username')}: ticker={current_interval_id}, side={side}, contracts={contracts}, price={market_price}, risk_amount={risk_amount:.2f}, avail_bal={avail_bal:.2f}")
                            # Tell the Kalshi position sync this position is the bot's (see inflight_orders)
                            inflight_orders.mark_pending(user['id'], current_interval_id, side, {
                                "reason": f"AI_COPY ({eff_style})", "trading_style": eff_style,
                                "signal_source": u_source, "model_choice": user.get("model_choice", "RL_DQN"),
                                "strike": strike,
                            })
                            res = kt.place_order(ticker=current_interval_id, side=side, count=contracts, limit_price_dollars=market_price, dry_run=False, slippage_buffer_dollars=0.04)
                            if intent_key:
                                order_intents.settle_outcome(intent_key, intent_ticker, res)
                            if not res.get('success'):
                                if res.get('ambiguous'):
                                    inflight_orders.mark_ambiguous(user['id'], current_interval_id, side)
                                    # It may have filled: treat this interval as traded for this user.
                                    with _user_last_traded_lock:
                                        _user_last_traded_cache[(user['id'], self.asset)] = current_interval_id
                                else:
                                    inflight_orders.clear(user['id'], current_interval_id, side)
                                logger.error(f"[SaaS Multitenant] User {user.get('username')} LIVE order rejected by Kalshi: {res.get('error')} | Payload was: contracts={contracts}, price={market_price}, side={side}")
                                return
                            filled_price = res.get('filled_price', market_price)
                            trade_id = res.get('client_order_id', trade_id)
                            # H1: an IOC order can partially fill - record what Kalshi actually
                            # filled, not what we asked for, so P&L and risk use the real size.
                            requested_contracts = contracts
                            contracts = _filled_count(res, contracts)
                            if contracts != requested_contracts:
                                logger.info(f"[SaaS Multitenant] User {user.get('username')} LIVE partial fill: {contracts}/{requested_contracts} {side.upper()} on {current_interval_id}")
                        else:
                            risk_amount = float(user.get("paper_trade_size_dollars", 50.0))

                            # Pillar 6: True Binary Options Half-Kelly Sizing
                            if bool(user.get('use_kelly_criterion', 0)):
                                p_win = float(conf) / 100.0 if conf else 0.50
                                b_price = float(market_price)
                                if p_win <= b_price:
                                    logger.info(f"[SaaS Broadcast] EV/Kelly Block: {user.get('username')} skipped trade @ ${b_price:.2f} (win prob {p_win*100:.1f}% <= ask)")
                                    return
                                f_star = (p_win - b_price) / (1.0 - b_price) if b_price < 1.0 else 0.0
                                kelly_frac = min(1.25, max(0.25, 0.50 * f_star))
                                risk_amount = max(1.0, risk_amount * kelly_frac)

                            max_cost_per_contract = min(market_price + 0.04 + PAPER_LATENCY_TAX_DOLLARS, 0.99)
                            contracts = int(risk_amount / max(0.01, max_cost_per_contract))
                            while contracts > 0 and (contracts * max_cost_per_contract + kalshi_order_fee(max_cost_per_contract, contracts)) > risk_amount:
                                contracts -= 1
                            if contracts < 1:
                                return
                            res = kalshi_trader.place_order(
                                ticker=current_interval_id, side=side, count=contracts,
                                limit_price_dollars=market_price, dry_run=True, slippage_buffer_dollars=0.04,
                                available_balance=user.get('paper_balance', 500.0),
                            )
                            if not res.get('success'):
                                logger.info(f"[SaaS Multitenant] User {user.get('username')} PAPER order not simulated: {res.get('error')}")
                                return
                            filled_price = res.get('filled_price', market_price)
                            contracts = int(res.get('count', contracts))
                            trade_id = res.get('client_order_id', trade_id)
                            # FIX: kalshi_trader returns `total_cost` without exchange fees. We must explicitly add it.
                            raw_cost = float(res.get('total_cost', contracts * filled_price))
                            cost = raw_cost + kalshi_order_fee(filled_price, contracts)
                            if not deduct_user_paper_balance(user['id'], cost):
                                return

                        logger.info(f'[SaaS Multitenant] Traded {contracts} {side.upper()} for User {user["username"]} ({user_mode}) via {eff_style}')
    
                        from zoneinfo import ZoneInfo
                        _et = ZoneInfo("America/New_York")
                        now_dt = datetime.now(_et)
                        now_est = now_dt.isoformat()  # ISO 8601 for correct UI timezone display
                        now_est_str = now_dt.strftime('%Y-%m-%d %I:%M:%S %p ET')  # Human-readable for JSON file
    
                        import json
                        market_snapshot = {}
                        if forecast and isinstance(forecast, dict):
                            market_snapshot = {
                                "price": float(df_ind_base.iloc[-1]["close"]) if df_ind_base is not None and len(df_ind_base) > 0 else float(strike),
                                "target": strike,
                                "confidence": conf,
                                "conviction_grade": forecast.get("conviction_grade"),
                                "primary_edge": forecast.get("primary_edge"),
                                "raw_features": forecast.get("raw_features", {})
                            }

                        prior_entries = [t for t in user_hist_cache.get(user['id'], (None, []))[1] if t.get("ticker") == current_interval_id]
                        entry_num = len(prior_entries) + 1
                        is_second = (entry_num == 2)
                        is_third = (entry_num >= 3)
                        reason_str = f"AI_COPY ({eff_style})"
                        if is_second:
                            reason_str = f"SECOND_ENTRY_SCALP ({eff_style})"
                        elif is_third:
                            reason_str = f"THIRD_ENTRY_SCALP ({eff_style})"

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
                            "requested_count": requested_contracts or contracts,
                            "status": "OPEN",
                            "mode": user_mode,
                            "pnl": 0.0,
                            "reason": reason_str,
                            "is_second_entry": is_second,
                            "is_third_entry": is_third,
                            "is_profit_reentry": (is_second or is_third),
                            "reentry_index": entry_num,
                            "trading_style": eff_style,
                            "signal_source": u_source,
                            "model_choice": user.get("model_choice", "RL_DQN"),
                            "catalysts": forecast.get("catalysts", []) if forecast else [],
                            "strike": strike,
                            "market_snapshot": json.dumps(market_snapshot)
                        }

                        # â”€â”€ PRIMARY: Insert into SQLite TradeStore so Recent Executions UI shows live trades â”€â”€
                        try:
                            from backend.database.trade_store import TradeStore
                            TradeStore.insert_trade(user['id'], trade_record)
                        except Exception as _ts_err:
                            logger.error(f"[SaaS Multitenant] TradeStore insert failed for {user.get('username')}: {_ts_err}")
                        finally:
                            if user_mode == 'LIVE':
                                inflight_orders.clear(user['id'], current_interval_id, side)

                        # â”€â”€ SECONDARY: Also write to legacy JSON history file â”€â”€
                        _hist_path = os.path.join(DATA_DIR, 'users', str(user['id']), 'trades_history.json')
                        with get_user_lock(user['id']):
                            hist = []
                            if os.path.exists(_hist_path):
                                try:
                                    with open(_hist_path, 'r') as f:
                                        hist = json.load(f)
                                except Exception:
                                    pass
                            json_record = dict(trade_record)
                            json_record["timestamp"] = now_est_str  # human-readable for JSON file
                            hist.append(json_record)
                            os.makedirs(os.path.dirname(_hist_path), exist_ok=True)
                            with open(_hist_path, 'w') as f:
                                json.dump(hist, f, indent=4)
    
                        with _user_last_traded_lock:
                            _user_last_traded_cache[(user['id'], self.asset)] = current_interval_id
    
                    except Exception as e:
                        import traceback
                        logger.error(f"[SaaS Multitenant] Error executing for user {user.get('username')}: {e}\n{traceback.format_exc()}")
    
                max_workers = min(16, max(1, len(users_to_trade)))
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    list(executor.map(_execute_single_user_trade, users_to_trade))
                        
            finally:
                if lock_held:
                    try:
                        self._saas_eval_lock.release()
                    except Exception:
                        pass




