from backend.btc.data_fetcher import get_candle_countdown

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── OVERSOLD / OVERBOUGHT MEAN-REVERSION GUARD ──────────────────────
# Block NO entries when RSI <= 32 (deep oversold = likely bounce) unless
# spot CVD confirms selling AND spot is below the target.
# Mirror for YES with RSI >= 68. Applies even when Gemini is authoritative.
RSI_OVERSOLD_THRESHOLD = 32.0
RSI_OVERBOUGHT_THRESHOLD = 68.0

def _rsi_mean_reversion_guard(direction: str, raw_features: dict, spot: float, target: float) -> str:
    """Returns block reason string if trade should be vetoed, empty string if allowed."""
    if not isinstance(raw_features, dict):
        return ""
    rsi_val = float(raw_features.get("rsi", 50.0))
    cvd_val = float(raw_features.get("cvd_value", 0.0))
    d = (direction or "").upper()
    if d == "NO" and rsi_val <= RSI_OVERSOLD_THRESHOLD:
        if cvd_val < 0 and spot < target:
            return ""
        return f"RSI_OVERSOLD_GUARD: NO blocked at RSI {rsi_val:.1f} (threshold {RSI_OVERSOLD_THRESHOLD}), CVD={cvd_val:.0f}, spot vs target {spot:.2f}/{target:.2f}"
    if d == "YES" and rsi_val >= RSI_OVERBOUGHT_THRESHOLD:
        if cvd_val > 0 and spot > target:
            return ""
        return f"RSI_OVERBOUGHT_GUARD: YES blocked at RSI {rsi_val:.1f} (threshold {RSI_OVERBOUGHT_THRESHOLD}), CVD={cvd_val:.0f}, spot vs target {spot:.2f}/{target:.2f}"
    return ""


import numpy as np

from backend.database.trade_store import TradeStore

try:
    pass
except ImportError:
    pass
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

from backend.auth.security import decrypt_kalshi_key
from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract
from backend.btc.chop_engine import evaluate_chop_contract
from backend.btc.fees import calculate_realized_edge_cents, kalshi_order_fee, net_pnl
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

# ── Per-user signal snapshot (read by the dashboard's AI Intelligence panel) ──────────
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
                        if not any(x in (user.get('trading_universe') or 'FINANCIAL').upper() for x in ('FINANCIAL', 'CRYPTO', 'BOTH', 'ALL')): return
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
                            # SAFEGUARD: Hard ceiling on trade size strictly clamped to user's setting
                            configured_cap = max(0.50, float(user.get("trade_size_dollars", 5.0) or 5.0))
                            risk_amount = min(configured_cap, avail_bal * 0.95)

                            # Pillar 6: True Binary Options Kelly Sizing with Consensus Amplification (User Opt-in Only)
                            is_unanimous = pred_info.get('is_unanimous') if pred_info else None
                            agreement_ratio = pred_info.get('agreement_ratio') if pred_info else None
                            use_kelly = False  # EV/Kelly removed: fixed trade size, focus on winning trades only
                            if use_kelly:
                                from backend.btc.fees import calculate_binary_kelly_position
                                p_win = float(pred_info.get('prob', 50.0)) / 100.0 if pred_info else 0.50
                                b_price = float(limit_price_dollars)
                                kelly_res = calculate_binary_kelly_position(
                                    win_prob=p_win,
                                    ask_price=b_price,
                                    available_capital=avail_bal,
                                    max_position_cap=risk_amount,
                                    is_unanimous=is_unanimous,
                                    agreement_ratio=agreement_ratio,
                                    slippage_buffer=0.04
                                )
                                if kelly_res.get("contracts", 0) <= 0:
                                    logger.info(f"[SaaS Broadcast] EV/Kelly Block: {user.get('username')} skipped trade @ ${b_price:.2f} (Reason: {kelly_res.get('reason')})")
                                    return
                                # Absolute clamp: Kelly can scale DOWN on uncertainty, but NEVER exceed user's configured trade size
                                risk_amount = min(configured_cap, max(0.50, float(kelly_res.get("allocated_dollars", risk_amount))))

                            # Include 0.04 slippage buffer in max cost estimation so we don't exceed Kalshi's balance check
                            max_cost_per_contract = min(limit_price_dollars + 0.04, 0.99)
                            contracts = int(risk_amount / max(0.01, max_cost_per_contract))
                            while contracts > 0 and (contracts * max_cost_per_contract + kalshi_order_fee(max_cost_per_contract, contracts)) > risk_amount:
                                contracts -= 1
                            # Absolute hard safety check: contracts * entry must never exceed configured_cap
                            if (contracts * limit_price_dollars) > configured_cap + 0.05:
                                contracts = int(configured_cap / max(0.01, limit_price_dollars))
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

                            # Pillar 6: True Binary Options Kelly Sizing with Consensus Amplification (User Opt-in Only)
                            is_unanimous = pred_info.get('is_unanimous') if pred_info else None
                            agreement_ratio = pred_info.get('agreement_ratio') if pred_info else None
                            use_kelly = False  # EV/Kelly removed: fixed trade size, focus on winning trades only
                            if use_kelly:
                                from backend.btc.fees import calculate_binary_kelly_position
                                p_win = float(pred_info.get('prob', 50.0)) / 100.0 if pred_info else 0.50
                                b_price = float(limit_price_dollars)
                                kelly_res = calculate_binary_kelly_position(
                                    win_prob=p_win,
                                    ask_price=b_price,
                                    available_capital=avail_bal,
                                    max_position_cap=risk_amount,
                                    is_unanimous=is_unanimous,
                                    agreement_ratio=agreement_ratio,
                                    slippage_buffer=0.04
                                )
                                if kelly_res.get("contracts", 0) <= 0:
                                    # PAPER only: no EV block so the model keeps generating outcomes to learn from;
                                    # trade at the user's own paper size. LIVE paths keep the EV/Kelly block.
                                    logger.info(f"[SaaS Broadcast] EV filter bypassed (PAPER): {user.get('username')} @ ${b_price:.2f} (Reason: {kelly_res.get('reason')})")
                                else:
                                    risk_amount = max(1.0, float(kelly_res.get("allocated_dollars", risk_amount)))

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
                
                if sec_left < 120:
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
    
                # ── P1: Cached active-users (15s TTL) — avoids new DB connection every 4s ──
                _now = time.time()
                with _saas_users_cache_lock:
                    if _saas_users_cache["users"] is None or (_now - _saas_users_cache["ts"]) > _SAAS_USERS_TTL:
                        _saas_users_cache["users"] = get_all_active_users() or []
                        _saas_users_cache["ts"] = _now
                    users = list(_saas_users_cache["users"])
    
                active_users = [
                    u for u in users
                    if u.get('ai_enabled', 1)
                    and any(x in (u.get('trading_universe') or 'FINANCIAL').upper() for x in ('FINANCIAL', 'CRYPTO', 'BOTH', 'ALL'))
                    and (self.asset.upper() in [x.strip() for x in u.get('target_asset', 'BTC').upper().split(',')]
                         or 'ALL' in [x.strip() for x in u.get('target_asset', 'BTC').upper().split(',')])
                ]
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
                                is_manual_close = ("MANUAL" in last_exit)
                                is_take_profit = ("TAKE_PROFIT" in last_exit) or ("TRAILING_STOP" in last_exit) or (float(last_t.get("pnl") or 0.0) > 0 and "STOP_LOSS" not in last_exit)
                                can_reenter = (not is_manual_close) and (is_take_profit or bool(u.get("second_entry_enabled", 0)))
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
    
                # ── P1: Cached 15m candle data (8s TTL per asset) — avoids Coinbase HTTP hit every 4s ──
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
                            auto_regime_info = classify_auto_regime(df_ind_base, sec_left=sec_left, asset=self.asset)
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
                                "conviction_badge": "🛡️ CAPITAL GUARD (PASS)",
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

                # Forward live financial market snapshot into Quant Lab PaperIncubator
                try:
                    from backend.engine.quant_lab.incubator import PaperIncubator
                    _first_fc = next((v[1] for v in eval_results.values() if isinstance(v[1], dict)), {})
                    _cur_p = (active_m.get("yes_bid") or 50) / 100.0 if (active_m.get("yes_bid") or 0) > 1 else (active_m.get("yes_bid") or 0.50)
                    _inc_snap = {
                        "ticker": current_interval_id,
                        "strike_price": strike,
                        "asset": self.asset,
                        "cur_price": _cur_p,
                        "yes_bid": _cur_p,
                        "yes_ask": (active_m.get("yes_ask") or 50) / 100.0 if (active_m.get("yes_ask") or 0) > 1 else (active_m.get("yes_ask") or 0.50),
                        "raw_features": _first_fc.get("raw_features") or {},
                        "indicators": df_ind_base.iloc[-1].to_dict() if df_ind_base is not None and not df_ind_base.empty else {},
                    }
                    PaperIncubator().evaluate_snapshot(self.asset, _inc_snap)
                except Exception as _inc_err:
                    logger.debug(f"[PaperIncubator] Broadcast eval warning: {_inc_err}")

                if not users_to_trade:
                    return

                # 3. Route to users in parallel for maximum execution speed and zero slippage
                def _execute_single_user_trade(user):
                    try:
                        # Fix A: a synthetic (_SYNTH) market has fabricated 50c prices and no real
                        # contract to settle against, so paper trades on it can't mirror live.
                        # Skip it in every mode, exactly like LIVE always has.
                        if active_m.get("is_synthetic") or "_SYNTH" in str(active_m.get("ticker", "")).upper():
                            return
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
                        is_auto_force = False
                        is_ignore_pass_tech = False
                        is_one_shot = False
                        is_test_market = bool("ADV-" in str(current_interval_id) or "TEST" in str(current_interval_id) or str(current_interval_id).endswith("_SYNTH") or (active_m and active_m.get("is_synthetic")))

                        # ── 65s OPENING DELAY & GEMINI MASTER DECISION ENGINE ─────────────────
                        # 1. Local AI gathers all stats (candles, opening drive, indicators, ML/Ensemble probs, orderbook).
                        # 2. Hold fire during the first 65 seconds of a new 15m contract (0-65s opening noise).
                        # 3. Starting at T+35s, prefetch Gemini's analysis in the background (0ms latency at T+65s).
                        # 4. At T+65s+, Gemini acts as Head Trader and makes the authoritative YES / NO / PASS call.
                        gemini_authoritative = False
                        c_eval_top = df_ind_base.iloc[-1]
                        c_close_top = float(c_eval_top["close"])
                        try:
                            from backend.engine.multi_asset_fetcher import get_multi_asset_ticker
                            live_tk = get_multi_asset_ticker(self.asset)
                            if live_tk and float(live_tk.get("price") or 0.0) > 0:
                                c_close_top = float(live_tk["price"])
                        except Exception:
                            pass

                        # Check if this is an initial entry or a 2nd/3rd re-entry on this contract
                        _user_sec_left = max(0, int(900 - sec_elapsed)) if 'sec_elapsed' in locals() else 450
                        sec_left = _user_sec_left
                        _prior_for_window = [
                            t for t in user_hist_cache.get(user['id'], (None, []))[1]
                            if t.get("ticker") == current_interval_id
                        ]
                        _is_initial_entry = (len(_prior_for_window) == 0)
                        # Always define live Kalshi quotes (previously only set in the RL_SCALPER branch -> UnboundLocalError in chop block)
                        yes_ask = float(active_m.get("yes_ask") or 0.0)
                        yes_bid = float(active_m.get("yes_bid") or 0.0)
                        no_ask = float(active_m.get("no_ask") or (1.0 - yes_bid))
                        no_bid = float(active_m.get("no_bid") or (1.0 - yes_ask))

                        if not is_one_shot and u_source != "RL_SCALPER":
                            from backend.btc.gemini_15m_gate import (
                                get_or_create_master_decision,
                                prefetch_master_decision_async,
                            )
                            is_gemini_every_interval = bool(user.get("gemini_every_interval_enabled", 0))

                            if sec_elapsed < 65 and not is_test_market:
                                if sec_elapsed >= 35:
                                    prefetch_master_decision_async(
                                        asset=self.asset,
                                        interval_id=current_interval_id,
                                        strike=strike,
                                        spot=c_close_top,
                                        sec_elapsed=sec_elapsed,
                                        active_m=active_m,
                                        forecast=forecast,
                                        df_ind=df_ind_base,
                                        allow_pass=not is_gemini_every_interval,
                                    )
                                logger.debug(
                                    f"[SaaS Multitenant] User {user.get('username')} holding for 65s opening confirmation "
                                    f"(sec_elapsed={sec_elapsed:.0f}s < 65s) on {current_interval_id}"
                                )
                                return

                            # Hard Opening Window Cutoff for initial 15m entries: never enter after 195s (3m15s) elapsed (bypassed if Every-Interval Force Mode is enabled)
                            if _is_initial_entry and sec_elapsed > 195 and not (is_auto_force or is_gemini_every_interval):
                                logger.debug(
                                    f"[SaaS Multitenant] User {user.get('username')} skipped late-candle initial entry "
                                    f"(sec_elapsed={sec_elapsed:.0f}s > 195s opening window) on {current_interval_id}"
                                )
                                return
                            gemini_decision = get_or_create_master_decision(
                                asset=self.asset,
                                interval_id=current_interval_id,
                                strike=strike,
                                spot=c_close_top,
                                sec_elapsed=sec_elapsed,
                                active_m=active_m,
                                forecast=forecast,
                                df_ind=df_ind_base,
                                sync_if_missing=(sec_elapsed <= 195 or is_gemini_every_interval),
                                allow_pass=not is_gemini_every_interval,
                            )
                            if gemini_decision and not gemini_decision.get("fallback"):
                                g_dir = str(gemini_decision.get("direction", "PASS")).upper().strip()
                                g_conf = float(gemini_decision.get("confidence", 50.0) or 50.0)
                                g_reason = str(gemini_decision.get("reason", ""))
                                g_model = str(gemini_decision.get("model", "gemini"))
                                # Check User's Regime Mode & Specialized Chop Engine Routing
                                u_regime_mode = str(user.get("regime_mode", "AUTO_ADAPTIVE") or "AUTO_ADAPTIVE").upper()
                                u_chop_enabled = bool(user.get("chop_engine_enabled", 1))

                                if g_dir == "PASS" and not (is_auto_force or is_gemini_every_interval):
                                    # If user is in AUTO_ADAPTIVE or CHOP_ONLY mode and Chop Engine is enabled, evaluate Specialized Chop Fade
                                    if u_chop_enabled and u_regime_mode in ("AUTO_ADAPTIVE", "CHOP_ONLY"):
                                        try:
                                            from backend.btc.chop_engine import evaluate_chop_trade
                                            sec_left = max(0, int(900 - sec_elapsed))
                                            c_eval_chop = df_ind_base.iloc[-1]
                                            c_rsi_1m = float(c_eval_chop.get("rsi_1m") or c_eval_chop.get("rsi") or 50.0)
                                            c_rsi_5m = float(c_eval_chop.get("rsi_5m") or c_eval_chop.get("rsi") or 50.0)
                                            c_bbu = float(c_eval_chop.get("bb_upper") or (c_close_top * 1.002))
                                            c_bbl = float(c_eval_chop.get("bb_lower") or (c_close_top * 0.998))
                                            c_bbm = float(c_eval_chop.get("bb_middle") or c_close_top)

                                            chop_setup = evaluate_chop_trade(
                                                asset=self.asset,
                                                spot_price=c_close_top,
                                                strike_price=strike,
                                                kalshi_yes_ask=float(yes_ask or 0.50),
                                                kalshi_no_ask=float(no_ask or 0.50),
                                                kalshi_yes_bid=float(yes_bid or 0.48),
                                                kalshi_no_bid=float(no_bid or 0.48),
                                                rsi_1m=c_rsi_1m,
                                                rsi_5m=c_rsi_5m,
                                                bb_upper_1m=c_bbu,
                                                bb_lower_1m=c_bbl,
                                                bb_middle_1m=c_bbm,
                                                seconds_to_expiry=sec_left,
                                            )
                                            if chop_setup:
                                                gemini_authoritative = True
                                                direction = chop_setup["side"]
                                                conf = float(chop_setup["confidence"])
                                                forecast = dict(forecast)
                                                forecast["direction"] = direction
                                                forecast["probability_percent"] = conf
                                                forecast["predicted_probability"] = (conf / 100.0) if direction == "YES" else ((100.0 - conf) / 100.0)
                                                forecast["is_chop_trade"] = True
                                                forecast["chop_take_profit_cents"] = float(user.get("chop_take_profit_cents", 12.0) or 12.0)
                                                forecast["catalysts"] = [f"Chop Engine: {chop_setup['reason']}"] + list(forecast.get("catalysts") or [])
                                                logger.info(
                                                    f"[SaaS Multitenant] 🧊 Specialized Chop Engine Triggered for {user.get('username')} "
                                                    f"on {current_interval_id}: {direction} @ ${chop_setup['target_price']:.2f} ({chop_setup['strategy']})"
                                                )
                                                g_dir = direction
                                        except Exception as e:
                                            logger.warning(f"[SaaS Multitenant] Chop evaluation error for {user.get('username')}: {e}")

                                    if g_dir == "PASS":
                                        logger.info(
                                            f"[SaaS Multitenant] 🛑 Gemini Master Decision PASS for {user.get('username')} "
                                            f"on {current_interval_id}: {g_reason} [model={g_model}]"
                                        )
                                        return
                                elif g_dir in ("YES", "NO"):
                                    gemini_authoritative = True
                                    direction = g_dir
                                    conf = g_conf
                                    forecast = dict(forecast)
                                    forecast["direction"] = g_dir
                                    forecast["probability_percent"] = g_conf
                                    forecast["predicted_probability"] = (
                                        (g_conf / 100.0) if g_dir == "YES" else ((100.0 - g_conf) / 100.0)
                                    )
                                    old_cats = list(forecast.get("catalysts") or [])
                                    forecast["catalysts"] = [
                                        f"Gemini Head Trader ({g_model}): {g_dir} ({g_conf:.0f}%) — {g_reason}"
                                    ] + old_cats
                                    if gemini_decision.get("is_unanimous") is not None:
                                        is_unanimous = bool(gemini_decision.get("is_unanimous"))
                                    # Calculate conviction grade (and dynamic Kelly scaling factor only if user opted into Kelly)
                                    try:
                                        from backend.btc.kelly_scaler import calculate_dynamic_kelly_size
                                        k_calc = calculate_dynamic_kelly_size(
                                            base_contracts=1,
                                            confidence=g_conf,
                                            is_snipe_opportunity=bool(gemini_decision.get("stale_snipe_active", False) or "Arbitrage" in g_reason),
                                            is_unanimous_debate=bool(gemini_decision.get("is_unanimous", True)),
                                        )
                                        if False:  # EV/Kelly removed: fixed trade size, focus on winning trades only
                                            forecast["dynamic_sizing_factor"] = k_calc.get("multiplier", 1.0)
                                        else:
                                            forecast["dynamic_sizing_factor"] = 1.0
                                        forecast["conviction_grade"] = k_calc.get("conviction_grade", "")
                                    except Exception:
                                        pass
                                    logger.info(
                                        f"[SaaS Multitenant] 🧠 Gemini Master Decision for {user.get('username')} "
                                        f"on {current_interval_id}: {g_dir} @ {g_conf:.1f}% — {g_reason} [model={g_model}]"
                                    )
                                elif is_gemini_every_interval and g_dir not in ("YES", "NO"):
                                    # Deterministic tie-breaker for Every-Interval mode when Gemini returned PASS
                                    _raw_ml = float(forecast.get("ml_prob", 0.50))
                                    _fallback_dir = "YES" if _raw_ml >= 0.50 else "NO"
                                    _fallback_conf = max(52.0, _raw_ml * 100.0 if _fallback_dir == "YES" else (1.0 - _raw_ml) * 100.0)
                                    gemini_authoritative = True
                                    direction = _fallback_dir
                                    conf = _fallback_conf
                                    forecast = dict(forecast)
                                    forecast["direction"] = _fallback_dir
                                    forecast["probability_percent"] = _fallback_conf
                                    forecast["predicted_probability"] = (
                                        (_fallback_conf / 100.0) if _fallback_dir == "YES" else ((100.0 - _fallback_conf) / 100.0)
                                    )
                                    old_cats = list(forecast.get("catalysts") or [])
                                    forecast["catalysts"] = [
                                        f"Gemini Every-Interval Fallback: {_fallback_dir} ({_fallback_conf:.0f}%) — ML/momentum resolution ({g_reason})"
                                    ] + old_cats
                                    logger.info(
                                        f"[SaaS Multitenant] 🧠 Gemini Every-Interval forced resolution for {user.get('username')} "
                                        f"on {current_interval_id}: {_fallback_dir} @ {_fallback_conf:.1f}%"
                                    )

                        min_conf = 60.0
                        if eff_style == "MOMENTUM_SURFER" and not is_user_rl:
                            if sec_left < 240 and not (is_auto_force or is_ignore_pass_tech or is_one_shot):
                                # Time Decay block (unless force trade is active)
                                return
                            # Opening window is 65s-150s (first 85s after 65s confirmation delay)
                            min_conf = 60.0 if sec_elapsed <= 150 else 72.0
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
    
                        # ── HARD RSI OVERSOLD / OVERBOUGHT MEAN-REVERSION GUARD ──
                        # Applies unconditionally across all trading modes, styles, and Gemini reasoning.
                        # Blocks NO entries when 15m RSI <= 32 (deep oversold) unless CVD confirms negative
                        # volume AND spot is already below target strike. Mirror for YES with RSI >= 68.
                        _ms_raw = forecast.get("raw_features", {}) if isinstance(forecast, dict) else {}
                        if not isinstance(_ms_raw, dict):
                            _ms_raw = {}
                        if not _ms_raw and c_eval_top is not None:
                            try:
                                _ms_raw = {
                                    "rsi": float(c_eval_top.get("rsi", 50.0) or 50.0),
                                    "cvd_value": float(c_eval_top.get("cvd_value", 0.0) or 0.0),
                                }
                            except Exception:
                                _ms_raw = {}
                        _cur_spot = float(c_eval_top["close"]) if (c_eval_top is not None and "close" in c_eval_top) else float(strike)
                        _cur_tgt = float(strike)
                        _guard_block = _rsi_mean_reversion_guard(side, _ms_raw, _cur_spot, _cur_tgt)
                        if _guard_block:
                            logger.info(f"[SaaS Broadcast] {_guard_block} — trade blocked for {user.get('username')} on {current_interval_id}")
                            return

                        consume_one_shot = False
                        # Check if the analyzer issued an explicit safety veto (ML Veto, Trend Alignment Block, Counter-Strike Block)
                        cats_joined = " ".join(str(c) for c in (forecast.get("catalysts") or []))
                        has_hard_safety_veto = any(
                            v in cats_joined
                            for v in (
                                "ML Veto",
                                "Trend Alignment Block",
                                "Sniper Counter-Strike Block",
                                "Momentum Surfer Counter-Strike Block",
                                "Sniper Longshot Block",
                                "Momentum Surfer Longshot Block",
                                "AMBUSH Longshot Block",
                                "Prediction Longshot Block",
                                "Chop Corridor Block",
                                "Capital Guard active",
                                "Dead zone filter",
                                "STRIKE PIN",
                                "No technical chart setup fired",
                                "Model edge too weak",
                                "Loss Guard Veto",
                                "PASS (LOSS GUARD)",
                            )
                        )

                        # Check user override preferences if market evaluation resulted in PASS
                        if not side:
                            if eff_style == "CAPITAL_GUARD" and not (is_one_shot or is_gemini_every_interval):
                                logger.info(f"[SaaS Broadcast] User {user.get('username')} skipping: CAPITAL GUARD strictly blocks trades in zero-edge chop.")
                                return
                            if has_hard_safety_veto and not (is_one_shot or is_auto_force or is_gemini_every_interval):
                                logger.info(f"[SaaS Broadcast] User {user.get('username')} skipping: Explicit safety veto active in catalysts ({cats_joined[:80]}).")
                                return
                            
                            if is_auto_force or is_one_shot or is_gemini_every_interval:
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
                                        c_eval = df_ind_target.iloc[-1]
                                        c_close = float(c_eval["close"])
                                        ema_9 = float(c_eval.get("ema_9", c_close))
                                        ema_21 = float(c_eval.get("ema_21", c_close))
                                        trend = str(c_eval.get("trend_1h", "FLAT")).upper()
                                        if trend in ["UP", "BULLISH"] or (ema_9 > ema_21 and ema_21 > 0):
                                            side = "yes"
                                        elif trend in ["DOWN", "BEARISH"] or (ema_9 < ema_21 and ema_21 > 0):
                                            side = "no"
                                        else:
                                            side = None  # Blocked by 60% conviction filter (Fix 5)
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
                                        c_eval = df_ind_target.iloc[-1]
                                        c_close = float(c_eval["close"])
                                        ema_9 = float(c_eval.get("ema_9", c_close))
                                        ema_21 = float(c_eval.get("ema_21", c_close))
                                        trend = str(c_eval.get("trend_1h", "FLAT")).upper()
                                        if trend in ["UP", "BULLISH"] or (ema_9 > ema_21 and ema_21 > 0):
                                            side = "yes"
                                        elif trend in ["DOWN", "BEARISH"] or (ema_9 < ema_21 and ema_21 > 0):
                                            side = "no"
                                        else:
                                            side = None  # Blocked by 60% conviction filter (Fix 5)
                                        conf = 55.0
                        if not side:
                            logger.info(f"[SaaS Broadcast] User {user.get('username')} skipping: direction is {direction} (conf: {conf}%)")
                            return
    
                        # Physical Chart Direction Guard & Strike-Pin Deadzone Guard for SaaS user trades
                        is_oversold_bounce = ("Absorption Hammer" in str(forecast.get("catalysts", [])) or "Oversold Spring" in str(forecast.get("catalysts", [])) or "Bullish Liquidity Sweep" in str(forecast.get("catalysts", [])))
                        is_overbought_fade = ("Rejection Pin" in str(forecast.get("catalysts", [])) or "Overbought Exhaustion" in str(forecast.get("catalysts", [])) or "Bearish Liquidity Sweep" in str(forecast.get("catalysts", [])))
                        c_eval = df_ind_base.iloc[-1]
                        c_open = float(c_eval["open"])
                        c_close = float(c_close_top)
                        c_ema9 = float(c_eval.get("ema_9", c_close))
                        c_ema21 = float(c_eval.get("ema_21", c_close))
                        c_atr = float(c_eval.get("atr", max(strike * 0.0015, 1e-4)) or max(strike * 0.0015, 1e-4))
                        delta_strike = c_close - strike

                        # Hard Strike-Pin Deadzone Gate ($15.00 BTC, $1.10 ETH, $0.08 SOL)
                        _asset_up = str(self.asset).upper()
                        if _asset_up == "BTC":
                            _dz_tol = 15.0
                        elif _asset_up == "ETH":
                            _dz_tol = 1.10
                        elif _asset_up == "SOL":
                            _dz_tol = 0.08
                        elif _asset_up == "DOGE":
                            _dz_tol = 0.0001
                        elif _asset_up in ("EURUSD", "GBPUSD", "AUDUSD"):
                            _dz_tol = 0.00008
                        elif _asset_up == "USDJPY":
                            _dz_tol = 0.015
                        else:
                            _dz_tol = max(strike * 0.00025, 0.0001)

                        if strike > 0 and abs(delta_strike) <= _dz_tol and not (is_auto_force or is_one_shot or is_test_market or is_gemini_every_interval):
                            logger.info(
                                f"[SaaS Multitenant] 🛑 User {user.get('username')} trade blocked by Strike-Pin Deadzone: "
                                f"{_asset_up} spot ${c_close:,.4f} vs strike ${strike:,.4f} (|delta|=${abs(delta_strike):.4f} <= ${_dz_tol:.4f})."
                            )
                            return

                        # Scale conflict thresholds proportionally for BTC, ETH, SOL, DOGE, GOLD, and Forex
                        moderate_conflict_tol = max(c_atr * 0.25, strike * (25.0 / 60000.0))
                        severe_conflict_tol = max(c_atr * 0.40, strike * (40.0 / 60000.0))
    
                        chart_conflict = False
                        if side == "yes":
                            if delta_strike < 0 and not is_oversold_bounce:
                                chart_conflict = True
                                conflict_reason = f"Spot ${c_close:,.4f} is ${abs(delta_strike):.4f} below strike ${strike:,.4f} when buying YES"
                            elif ((delta_strike < -moderate_conflict_tol and (c_close < c_open) and (c_ema9 < c_ema21)) or (delta_strike < -severe_conflict_tol and (c_close < c_open))) and not is_oversold_bounce:
                                chart_conflict = True
                                conflict_reason = f"Spot ${c_close:,.4f} is ${abs(delta_strike):.4f} below strike ${strike:,.4f} with red candle"
                        elif side == "no":
                            if delta_strike > 0 and not is_overbought_fade:
                                chart_conflict = True
                                conflict_reason = f"Spot ${c_close:,.4f} is ${delta_strike:.4f} above strike ${strike:,.4f} when buying NO"
                            elif ((delta_strike > moderate_conflict_tol and (c_close > c_open) and (c_ema9 > c_ema21)) or (delta_strike > severe_conflict_tol and (c_close > c_open))) and not is_overbought_fade:
                                chart_conflict = True
                                conflict_reason = f"Spot ${c_close:,.4f} is ${delta_strike:.4f} above strike ${strike:,.4f} with green candle"
    
                        if chart_conflict:
                            if is_ignore_pass_tech or is_auto_force or is_one_shot or is_gemini_every_interval:
                                logger.info(f"[SaaS Multitenant] [WARN] User {user.get('username')} bypassed chart conflict ({conflict_reason}) due to force_trade/gemini_every_interval setting.")
                            else:
                                logger.warning(
                                    f"[SaaS Multitenant] [BLOCKED] User {user.get('username')} trade blocked: Side {side.upper()} conflicts with physical chart trend ({conflict_reason})."
                                )
                                return

                        # ── COUNTER-TREND NO GATING & HIGHER CONVICTION ENFORCEMENT ──
                        # If market is in an established bullish uptrend, buying NO is fighting higher timeframe momentum.
                        # Enforce higher conviction threshold (>= 68%) or block the trade.
                        c_trend_1h = str(c_eval.get("trend_1h") or forecast.get("trend_1h", "FLAT")).upper()
                        is_bullish_uptrend = (c_trend_1h in ["UP", "BULLISH"]) or (c_ema9 > c_ema21 and c_ema21 > 0)
                        if side == "no" and is_bullish_uptrend:
                            NO_COUNTER_TREND_MIN_CONF = 68.0
                            if float(conf or 0) < NO_COUNTER_TREND_MIN_CONF and not (is_auto_force or is_one_shot or is_gemini_every_interval):
                                logger.warning(
                                    f"[SaaS Multitenant] 🛑 User {user.get('username')} counter-trend NO blocked: "
                                    f"Market in established bullish uptrend (1h={c_trend_1h}, EMA9={c_ema9:.2f} > EMA21={c_ema21:.2f}) "
                                    f"and conviction {float(conf or 0):.1f}% < {NO_COUNTER_TREND_MIN_CONF:.1f}% required."
                                )
                                return

                        # 3-Phase Time-Decay Engine Check: Pin Risk Veto in Phase 3
                        from backend.btc.time_phase_engine import classify_15m_time_phase
                        phase_info = classify_15m_time_phase(
                            sec_left=float(sec_left),
                            spot_price=c_close,
                            strike_price=strike,
                            atr=c_atr,
                            asset=self.asset
                        )
                        if phase_info.get("is_pin_risk") and not (is_ignore_pass_tech or is_auto_force or is_one_shot or is_test_market or is_gemini_every_interval):
                            logger.info(
                                f"[SaaS Multitenant] 🛑 User {user.get('username')} trade blocked: "
                                f"{phase_info.get('desc')} (Delta ${abs(delta_strike):.2f} too narrow for expiring candle)."
                            )
                            return

                        # Direction Prediction Enhancement: 3-Model Voting Ensemble Consensus Gating
                        # Only applies when Gemini Master Decision is on fallback; when Gemini is authoritative,
                        # Gemini has already ingested and weighed the Voting Ensemble telemetry in its dossier.
                        consensus_obj = forecast.get("consensus") if forecast else None
                        if not gemini_authoritative and consensus_obj and isinstance(consensus_obj, dict) and not (is_ignore_pass_tech or is_auto_force or is_one_shot or is_gemini_every_interval):
                            agree_r = float(consensus_obj.get("agreement_ratio", 1.0) or 1.0)
                            model_spread = float(consensus_obj.get("spread", 0.0) or 0.0)
                            cons_dir = str(consensus_obj.get("consensus_direction", "")).upper()
                            
                            # Disagreement veto: less than 2/3 agreement or extreme probability spread
                            if agree_r < 0.67 or model_spread > 0.25:
                                logger.info(
                                    f"[SaaS Multitenant] 🛑 User {user.get('username')} trade blocked: "
                                    f"Voting Ensemble consensus divergence (agreement: {agree_r*100:.0f}%, spread: {model_spread:.2f})."
                                )
                                return
                            # Direction clash veto: if ensemble consensus direction strongly contradicts candidate side
                            if cons_dir in ("DOWN", "BELOW", "NO") and side == "yes":
                                logger.info(
                                    f"[SaaS Multitenant] 🛑 User {user.get('username')} trade blocked: "
                                    f"Side YES contradicts Voting Ensemble consensus {cons_dir}."
                                )
                                return
                            elif cons_dir in ("UP", "ABOVE", "YES") and side == "no":
                                logger.info(
                                    f"[SaaS Multitenant] 🛑 User {user.get('username')} trade blocked: "
                                    f"Side NO contradicts Voting Ensemble consensus {cons_dir}."
                                )
                                return

                        # Volatility Squeeze Deadzone Veto
                        # When Bollinger Bands are compressing inside Keltner Channels (bb_squeeze is True)
                        # and ATR percentile is low (< 0.20), entering directional binary contracts is coin-flip chop.
                        # Veto directional entries unless trading style is specifically CHOP.
                        is_squeeze = bool(c_eval.get("bb_squeeze", False))
                        atr_pctile = float(c_eval.get("atr_percentile", 0.50) or 0.50)
                        if is_squeeze and atr_pctile < 0.20 and eff_style not in ["CHOP", "CAPITAL_GUARD"] and not (is_ignore_pass_tech or is_auto_force or is_one_shot or is_gemini_every_interval):
                            logger.info(
                                f"[SaaS Multitenant] 🛑 User {user.get('username')} trade blocked: "
                                f"Volatility squeeze deadzone active (bb_squeeze=True, atr_percentile={atr_pctile:.2f}). Capital preserved."
                            )
                            return
                            
                        raw_ask = active_m.get(f"{side}_ask")
                        market_price = float(raw_ask) if raw_ask is not None else 0.0

                        # ── EMPIRICAL ENTRY CORRIDOR ENFORCEMENT ──────────────────────────────
                        # Derived from forensic audit of 2,455 bot trades:
                        #   < 35¢  → 20.5% WR,  -$369 net PnL  (total anchor drag)
                        #   35–46¢ → 33.1% WR, -$1,341 net PnL  (biggest single loss pool)
                        #   46–55¢ → 37.8% WR,  -$480 net PnL  (edge of profitability)
                        #   56–65¢ → 49.9% WR,   -$49 net PnL  (near-breakeven)
                        #   ≥ 66¢  → 63.6% WR,   -$41 net PnL  (wins but fee drag kills it)
                        # HARD FLOOR: 0.46 default; 0.56 Strict Momentum for Users 4 (Prep109) & 5 (Mattroccett).
                        # HARD CEILING: $0.62 default cap to ensure favorable risk/reward asymmetry.
                        # Forbid buying contracts priced above $0.62 unless conviction is exceptional (>85% or Grade A+).
                        _uid = int(user.get("id") or 0)
                        is_chop_trade = bool(forecast.get("is_chop_trade", False))
                        # For Chop Engine discount fades: allow validated 0.15 - 0.35 entry corridor
                        if is_chop_trade:
                            EMPIRICAL_FLOOR = 0.15
                            EMPIRICAL_CEILING = 0.35
                        else:
                            EMPIRICAL_FLOOR = 0.56 if _uid in (4, 5) else 0.46
                            EMPIRICAL_CEILING = 0.62

                        # Exceptional conviction (>85% or Grade A+) allows widening ceiling up to 0.68 (or 0.74 for SNIPER)
                        is_grade_a_plus = "GRADE A+" in str(forecast.get("conviction_grade", ""))
                        is_exceptional_conviction = is_grade_a_plus or (conf is not None and float(conf) > 85.0)
                        if is_exceptional_conviction:
                            effective_ceiling = 0.74 if (eff_style == "SNIPER" and is_grade_a_plus) else 0.68
                        else:
                            effective_ceiling = EMPIRICAL_CEILING

                        if (market_price < EMPIRICAL_FLOOR or market_price > effective_ceiling) and not (is_auto_force or is_one_shot):
                            logger.warning(
                                f"[SaaS Multitenant] EMPIRICAL CORRIDOR BLOCK for {current_interval_id} (user={user.get('username')}): "
                                f"ask ${market_price:.2f} outside validated range "
                                f"[${EMPIRICAL_FLOOR:.2f}, ${effective_ceiling:.2f}] for {eff_style} "
                                f"(exceptional_conviction={is_exceptional_conviction})."
                            )
                            return

                        # ── BID-ASK SPREAD & ORDERBOOK LIQUIDITY GATE ─────────────────────────
                        # Prevents entering illiquid 15m contracts (e.g. AUDUSD/GOLD with a 53c spread)
                        # where a $0.57 ask sits above a $0.04 bid, causing an instant -89% mark-to-market stop-loss.
                        raw_bid = active_m.get(f"{side}_bid")
                        bid_price = float(raw_bid) if raw_bid is not None else 0.0
                        if bid_price <= 0.0:
                            other_ask = active_m.get("no_ask" if side == "yes" else "yes_ask")
                            if other_ask is not None and float(other_ask) > 0.0:
                                bid_price = round(1.0 - float(other_ask), 4)
                        book_spread = round(market_price - bid_price, 4) if bid_price > 0 else 0.99
                        MAX_ALLOWED_SPREAD = 0.12
                        if (bid_price < 0.15 or book_spread > MAX_ALLOWED_SPREAD) and not (is_auto_force or is_one_shot):
                            logger.warning(
                                f"[SaaS Multitenant] ILLIQUID SPREAD BLOCK for {current_interval_id} (user={user.get('username')}): "
                                f"{side.upper()} bid=${bid_price:.2f} / ask=${market_price:.2f} (spread=${book_spread:.2f} > ${MAX_ALLOWED_SPREAD:.2f} max)."
                            )
                            return

                        # Multi-entry / DCA Discipline Guard (for 2nd and 3rd entries on same contract)
                        prior_entries = [t for t in user_hist_cache.get(user['id'], (None, []))[1] if t.get("ticker") == current_interval_id]
                        entry_num = len(prior_entries) + 1
                        if entry_num > 1 and u_source != "RL_SCALPER":
                            reentry_max_ask = min(float(user.get("second_entry_max_ask", 0.62) or 0.62), effective_ceiling)
                            if market_price < EMPIRICAL_FLOOR or market_price > reentry_max_ask:
                                logger.info(f"[SaaS Multitenant] User {user.get('username')} skipped re-entry #{entry_num}: ask ${market_price:.2f} outside safe re-entry corridor [${EMPIRICAL_FLOOR:.2f}, ${reentry_max_ask:.2f}]")
                                return

                            if sec_left < 210 and not (is_auto_force or is_ignore_pass_tech or is_one_shot):
                                logger.info(f"[SaaS Multitenant] User {user.get('username')} skipped re-entry #{entry_num}: only {sec_left/60.0:.1f}m left in candle (< 3.5m min)")
                                return

                            last_trade = prior_entries[0]
                            last_exit_price = float(last_trade.get("exit_price") or last_trade.get("entry_price") or 0.50)
                            last_pnl = float(last_trade.get("pnl") or 0.0)
                            last_reason = str(last_trade.get("exit_reason") or last_trade.get("reason") or "").upper()
                            last_side = last_trade.get("side", "").upper()
                            
                            # Reversal check: if user manually closed or stopped out, only re-enter if AI has flipped its direction!
                            is_manual_or_stopped = "MANUAL" in last_reason or "SYNC_CLOSED" in last_reason or "STOP_LOSS" in last_reason
                            if is_manual_or_stopped:
                                if side.upper() == last_side:
                                    logger.info(f"[SaaS Multitenant] User {user.get('username')} skipped re-entry #{entry_num}: Prior {last_side} was stopped/closed. Not re-entering same direction.")
                                    return
                                else:
                                    logger.info(f"[SaaS Multitenant] User {user.get('username')} REVERSAL: Prior {last_side} was stopped/closed. Executing reversed forecast: {side.upper()}.")
                                    # Skip DCA logic since this is a fresh directional reversal
                                    pass
                            else:
                                # Normal DCA / Scalp pullback logic for SAME-SIDE re-entries
                                if side.upper() != last_side:
                                    pass # Reversal, skip DCA logic
                                else:
                                    was_profit = ("TAKE_PROFIT" in last_reason) or ("TRAILING_STOP" in last_reason) or (last_pnl > 0 and "STOP_LOSS" not in last_reason)
                                    if was_profit:
                                        if market_price > (last_exit_price - 0.03) and not (is_auto_force or is_one_shot):
                                            logger.info(f"[SaaS Multitenant] User {user.get('username')} skipped re-entry #{entry_num}: ask ${market_price:.2f} has not pulled back >= 3 cents below scalp exit ${last_exit_price:.2f}")
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

                        # Global Cross-Universe Circuit Breaker
                        from backend.engine.portfolio_governor import get_portfolio_governor
                        governor = get_portfolio_governor()
                        tripped, trip_reason = governor.check_global_circuit_breaker(user, mode=user.get('trading_mode', 'PAPER'))
                        if tripped:
                            _log_key = (user['id'], "GLOBAL_CIRCUIT_BREAKER", datetime.now().date())
                            if _log_key not in _daily_limit_logged:
                                _daily_limit_logged.add(_log_key)
                                logger.warning(f"[SaaS Multitenant] {user.get('username')}: Global Circuit Breaker Tripped ({trip_reason}). Halting all universe execution.")
                            return

                        # Edge Guard (per-user setting, on by default): only buy when the forecast
                        # probability beats the price after Kalshi's fee by more than the user's minimum.
                        # The RL scalper decides by action, not probability, so it is exempt.
                        if not is_auto_force and not is_one_shot and not is_gemini_every_interval and u_source != "RL_SCALPER" and False:  # EV edge gate removed: focus on winning trades only
                            min_edge = float(user.get("min_edge_cents", 0.0) or 0.0)
                            edge = calculate_realized_edge_cents(conf, market_price)
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
                            # High-performance non-blocking balance via Portfolio Governor
                            avail_bal = governor.get_effective_available_balance(user, kt=kt, max_cache_age=8.0)
                            target_ex = active_m.get('exchange_index') if active_m else None
                            # avail_bal stays the account TOTAL: place_order sweeps funds from other shards onto the
                            # market's shard, so clamping to one shard's balance wrongly blocked funded users.
                            if avail_bal < 0.50:
                                logger.warning(f"[SaaS Multitenant] User {user.get('username')} skipped LIVE: balance (${avail_bal:.2f} on ex {target_ex}) < $0.50 minimum")
                                return
                            # User configured trade size
                            risk_amount = min(float(user.get("trade_size_dollars", 5.0)), avail_bal * 0.95)
                            if side == "no" and is_bullish_uptrend:
                                risk_amount = max(0.50, risk_amount * 0.50)
                                logger.info(f"[SaaS Multitenant] Scaled down LIVE counter-trend NO risk to ${risk_amount:.2f} for {user.get('username')} (established bullish uptrend)")

                            order_limit_price = round(min(0.99, max(0.01, float(market_price))), 2)
                            is_maker = False

                            is_unanimous = forecast.get("is_unanimous") if forecast else None
                            agreement_ratio = forecast.get("agreement_ratio") if forecast else None
                            if consensus_obj := (forecast.get("consensus") if forecast else None):
                                if is_unanimous is None:
                                    is_unanimous = consensus_obj.get("is_unanimous")
                                if agreement_ratio is None:
                                    agreement_ratio = consensus_obj.get("agreement_ratio")

                            # Pillar 6: True Binary Options Kelly Sizing (Strictly User Opt-in)
                            use_kelly = False  # EV/Kelly removed: fixed trade size, focus on winning trades only
                            if use_kelly and not (is_auto_force or is_one_shot or is_gemini_every_interval):
                                from backend.btc.fees import calculate_binary_kelly_position
                                p_win = float(conf) / 100.0 if conf else 0.50
                                b_price = float(order_limit_price)
                                kelly_res = calculate_binary_kelly_position(
                                    win_prob=p_win,
                                    ask_price=b_price,
                                    available_capital=avail_bal,
                                    max_position_cap=risk_amount,
                                    is_unanimous=is_unanimous,
                                    agreement_ratio=agreement_ratio,
                                    slippage_buffer=0.04
                                )
                                if kelly_res.get("contracts", 0) <= 0:
                                    logger.info(f"[SaaS Broadcast] EV/Kelly Block: {user.get('username')} skipped trade @ ${b_price:.2f} (Reason: {kelly_res.get('reason')})")
                                    return
                                risk_amount = max(0.50, float(kelly_res.get("allocated_dollars", risk_amount)))
                            elif use_kelly and forecast and forecast.get("dynamic_sizing_factor") is not None:
                                try:
                                    sz_factor = float(forecast["dynamic_sizing_factor"])
                                    risk_amount = max(0.50, min(avail_bal * 0.95, risk_amount * sz_factor))
                                except (ValueError, TypeError):
                                    pass

                            # Include 0.04 slippage buffer for IOC execution
                            max_cost_per_contract = min(order_limit_price + 0.04, 0.99)
                            contracts = int(risk_amount / max(0.01, max_cost_per_contract))

                            dyn_contracts = forecast.get("dynamic_contracts") if forecast else None
                            if dyn_contracts is not None and not use_kelly:
                                try:
                                    dc = int(dyn_contracts)
                                    if dc >= 1:
                                        contracts = max(1, int(dc * 0.50)) if (side == "no" and is_bullish_uptrend) else dc
                                except (ValueError, TypeError):
                                    pass

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
                            # Cross-Universe Capital Reservation
                            res_id = f"fin_res_{user['id']}_{current_interval_id}_{uuid.uuid4().hex[:6]}"
                            governor.reserve_capital(user['id'], risk_amount, "FINANCIAL", current_interval_id, res_id)

                            logger.info(f"[SaaS Multitenant] Placing LIVE TAKER order for {user.get('username')}: ticker={current_interval_id}, side={side}, contracts={contracts}, price={order_limit_price}, risk_amount={risk_amount:.2f}, avail_bal={avail_bal:.2f}")
                            # Tell the Kalshi position sync this position is the bot's (see inflight_orders)
                            inflight_orders.mark_pending(user['id'], current_interval_id, side, {
                                "reason": f"AI_COPY ({eff_style})", "trading_style": eff_style,
                                "signal_source": u_source, "model_choice": user.get("model_choice", "RL_DQN"),
                                "strike": strike,
                            })
                            live_slip_buf = min(0.04, max(0.0, round(effective_ceiling - order_limit_price, 4)))
                            try:
                                res = kt.place_order(ticker=current_interval_id, side=side, count=contracts, limit_price_dollars=order_limit_price, dry_run=False, slippage_buffer_dollars=live_slip_buf, post_only=False)
                            except Exception as _pl_err:
                                governor.release_capital(res_id, actual_deducted_cost=0.0, user_id=user['id'])
                                raise _pl_err

                            if intent_key:
                                order_intents.settle_outcome(intent_key, intent_ticker, res)
                            if not res.get('success'):
                                err_msg = str(res.get('error', ''))
                                is_429 = '429' in err_msg or 'rate limit' in err_msg.lower()
                                is_rejected = 'rejected' in err_msg.lower() or 'not open' in err_msg.lower() or 'paused' in err_msg.lower()

                                if res.get('ambiguous'):
                                    inflight_orders.mark_ambiguous(user['id'], current_interval_id, side)
                                    # It may have filled: treat this interval as traded for this user.
                                    with _user_last_traded_lock:
                                        _user_last_traded_cache[(user['id'], self.asset)] = current_interval_id
                                    governor.release_capital(res_id, actual_deducted_cost=risk_amount, user_id=user['id'])
                                elif is_429 or is_rejected:
                                    inflight_orders.clear(user['id'], current_interval_id, side)
                                    # Prevent runaway loop on 429 or non-retryable rejection
                                    with _user_last_traded_lock:
                                        _user_last_traded_cache[(user['id'], self.asset)] = current_interval_id
                                    logger.warning(
                                        f"[SaaS Multitenant] User {user.get('username')} LIVE order failed (429/rejected): {res.get('error')}. "
                                        f"Recording interval as attempted to halt retry loop for {current_interval_id}."
                                    )
                                    governor.release_capital(res_id, actual_deducted_cost=0.0, user_id=user['id'])
                                else:
                                    inflight_orders.clear(user['id'], current_interval_id, side)
                                    governor.release_capital(res_id, actual_deducted_cost=0.0, user_id=user['id'])
                                logger.error(f"[SaaS Multitenant] User {user.get('username')} LIVE order rejected by Kalshi: {res.get('error')} | Payload was: contracts={contracts}, price={order_limit_price}, side={side}")
                                return
                            filled_price = res.get('filled_price', order_limit_price)
                            trade_id = res.get('client_order_id', trade_id)
                            # H1: an IOC order can partially fill - record what Kalshi actually
                            # filled, not what we asked for, so P&L and risk use the real size.
                            requested_contracts = contracts
                            contracts = _filled_count(res, contracts)
                            actual_deducted = round(filled_price * contracts + kalshi_order_fee(filled_price, contracts), 2)
                            governor.release_capital(res_id, actual_deducted_cost=actual_deducted, user_id=user['id'])
                            if contracts != requested_contracts:
                                logger.info(f"[SaaS Multitenant] User {user.get('username')} LIVE partial fill: {contracts}/{requested_contracts} {side.upper()} on {current_interval_id}")
                        else:
                            risk_amount = float(user.get("paper_trade_size_dollars", 50.0))
                            if side == "no" and is_bullish_uptrend:
                                risk_amount = max(1.0, risk_amount * 0.50)
                                logger.info(f"[SaaS Multitenant] Scaled down PAPER counter-trend NO risk to ${risk_amount:.2f} for {user.get('username')} (established bullish uptrend)")

                            from backend.btc.maker_engine import compute_maker_limit_price, get_execution_urgency
                            urgency = get_execution_urgency(forecast=forecast, sec_left=float(sec_left), regime=eff_style)
                            order_limit_price, is_maker = compute_maker_limit_price(
                                active_m=active_m,
                                side=side,
                                urgency=urgency,
                                target_limit_price=forecast.get("target_limit_price") if forecast else None
                            )
                            order_limit_price = round(max(EMPIRICAL_FLOOR, min(effective_ceiling, float(order_limit_price))), 2)

                            is_unanimous = forecast.get("is_unanimous") if forecast else None
                            agreement_ratio = forecast.get("agreement_ratio") if forecast else None
                            if consensus_obj := (forecast.get("consensus") if forecast else None):
                                if is_unanimous is None:
                                    is_unanimous = consensus_obj.get("is_unanimous")
                                if agreement_ratio is None:
                                    agreement_ratio = consensus_obj.get("agreement_ratio")

                            # Pillar 6: True Binary Options Kelly Sizing (Strictly User Opt-in)
                            use_kelly = False  # EV/Kelly removed: fixed trade size, focus on winning trades only
                            if use_kelly and not (is_auto_force or is_one_shot or is_gemini_every_interval):
                                from backend.btc.fees import calculate_binary_kelly_position
                                p_win = float(conf) / 100.0 if conf else 0.50
                                b_price = float(order_limit_price)
                                kelly_res = calculate_binary_kelly_position(
                                    win_prob=p_win,
                                    ask_price=b_price,
                                    available_capital=float(user.get('paper_balance', 500.0)),
                                    max_position_cap=risk_amount,
                                    is_unanimous=is_unanimous,
                                    agreement_ratio=agreement_ratio,
                                    slippage_buffer=0.04
                                )
                                if kelly_res.get("contracts", 0) <= 0:
                                    logger.info(
                                        f"[SaaS Broadcast] EV/Kelly Block (PAPER): {user.get('username')} skipped {side.upper()} @ ${b_price:.2f} "
                                        f"on {current_interval_id} (Reason: {kelly_res.get('reason')})"
                                    )
                                    return
                                risk_amount = max(1.0, float(kelly_res.get("allocated_dollars", risk_amount)))
                            elif use_kelly and forecast and forecast.get("dynamic_sizing_factor") is not None:
                                try:
                                    sz_factor = float(forecast["dynamic_sizing_factor"])
                                    risk_amount = max(1.0, risk_amount * sz_factor)
                                except (ValueError, TypeError):
                                    pass

                            paper_slip_buf = 0.0 if is_maker else min(0.04, max(0.0, round(effective_ceiling - order_limit_price, 4)))
                            # If maker, no slippage buffer needed; if taker, include capped buffer + latency tax
                            max_cost_per_contract = min(order_limit_price if is_maker else (order_limit_price + paper_slip_buf + PAPER_LATENCY_TAX_DOLLARS), effective_ceiling)
                            contracts = int(risk_amount / max(0.01, max_cost_per_contract))

                            dyn_contracts = forecast.get("dynamic_contracts") if forecast else None
                            if dyn_contracts is not None and not use_kelly:
                                try:
                                    dc = int(dyn_contracts)
                                    if dc >= 1:
                                        contracts = max(1, int(dc * 0.50)) if (side == "no" and is_bullish_uptrend) else dc
                                except (ValueError, TypeError):
                                    pass

                            while contracts > 0 and (contracts * max_cost_per_contract + kalshi_order_fee(max_cost_per_contract, contracts)) > risk_amount:
                                contracts -= 1
                            if contracts < 1:
                                return
                            res = kalshi_trader.place_order(
                                ticker=current_interval_id, side=side, count=contracts,
                                limit_price_dollars=order_limit_price, dry_run=True,
                                slippage_buffer_dollars=paper_slip_buf,
                                available_balance=user.get('paper_balance', 500.0),
                                post_only=is_maker,
                            )
                            if not res.get('success'):
                                logger.info(f"[SaaS Multitenant] User {user.get('username')} PAPER order not simulated: {res.get('error')}")
                                return
                            filled_price = res.get('filled_price', order_limit_price)
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
                                "raw_features": forecast.get("raw_features") if isinstance(forecast.get("raw_features"), dict) else {}
                            }

                        prior_entries = [t for t in user_hist_cache.get(user['id'], (None, []))[1] if t.get("ticker") == current_interval_id]
                        entry_num = len(prior_entries) + 1
                        is_second = (entry_num == 2)
                        is_third = (entry_num >= 3)
                        reason_str = f"GEMINI_REASONING ({eff_style})" if (is_gemini_every_interval or gemini_authoritative) else f"AI_COPY ({eff_style})"
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
                            "is_manual": False,
                            "is_second_entry": is_second,
                            "is_third_entry": is_third,
                            "is_profit_reentry": (is_second or is_third),
                            "reentry_index": entry_num,
                            "trading_style": eff_style,
                            "signal_source": "GEMINI_REASONING" if (is_gemini_every_interval or gemini_authoritative) else u_source,
                            "model_choice": "GEMINI_HIGH_REASONING" if (is_gemini_every_interval or gemini_authoritative) else user.get("model_choice", "RL_DQN"),
                            "catalysts": forecast.get("catalysts", []) if forecast else [],
                            "strike": strike,
                            "target_limit_price": order_limit_price,
                            "dynamic_contracts": dyn_contracts,
                            "is_unanimous": is_unanimous,
                            "market_snapshot": json.dumps(market_snapshot)
                        }

                        # ── PRIMARY: Insert into SQLite TradeStore so Recent Executions UI shows live trades ──
                        try:
                            from backend.database.trade_store import TradeStore
                            TradeStore.insert_trade(user['id'], trade_record)
                        except Exception as _ts_err:
                            logger.error(f"[SaaS Multitenant] TradeStore insert failed for {user.get('username')}: {_ts_err}")
                        finally:
                            if user_mode == 'LIVE':
                                inflight_orders.clear(user['id'], current_interval_id, side)

                        # ── SECONDARY: Also write to legacy JSON history file ──
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





