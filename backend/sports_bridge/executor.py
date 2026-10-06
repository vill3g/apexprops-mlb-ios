import time
import logging
import uuid
import json
import re
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Any
import requests
from backend.sports_bridge.prediction_client import SportsPredictionClient
from backend.database.models import (
    get_all_active_users,
    deduct_user_paper_balance,
    credit_user_paper_balance
)
from backend.routes.engine import (
    _fetch_kalshi_series_events,
    _SPORTS_SERIES_MAP,
    _normalize_sport,
    extract_sports_event_date_and_time,
    parse_sports_market_details
)

logger = logging.getLogger(__name__)

def _is_sports_trade(t: dict) -> bool:
    """Accurately identifies whether a trade record belongs to the sports universe."""
    if not isinstance(t, dict):
        return False
    style = str(t.get("trading_style") or "").upper()
    if "SPORTS" in style:
        return True
    if t.get("sport"):
        return True
    sig = str(t.get("signal_source") or "").upper()
    if "SPORTS" in sig:
        return True
    ticker = str(t.get("ticker") or "").upper()
    if ticker.startswith("KALSHI-"):
        return True
    # Specific sports prefixes on Kalshi
    sports_prefixes = (
        "KXNFL", "KXMLB", "KXNBA", "KXNHL", "KXNCAAF", "KXNCAAB",
        "KXWNBA", "KXNPB", "KXKBO", "KXSOC", "KXUFC", "KXTEN",
        "KXMMA", "KXCBB", "KXCFB", "KXMLS", "KXEPL", "KXUCL"
    )
    if any(ticker.startswith(p) for p in sports_prefixes):
        return True
    return False

def _parse_trade_timestamp(ts: Any) -> float:
    """Safely converts an ISO string, float, int, or datetime object to a unix epoch float."""
    if ts is None:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, datetime):
        return ts.timestamp()
    if isinstance(ts, str) and ts:
        try:
            return float(ts)
        except ValueError:
            pass
        try:
            if ts.endswith(" ET"):
                from zoneinfo import ZoneInfo
                return datetime.strptime(ts, "%Y-%m-%d %I:%M:%S %p ET").replace(
                    tzinfo=ZoneInfo("America/New_York")).timestamp()
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            pass
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            return dt.timestamp()
        except Exception:
            pass
    return 0.0

def _generate_kalshi_market(prediction: dict, require_today: bool = True) -> tuple:
    """
    Matches a sport prediction to an actual Kalshi event/market ticker and ask price.
    Strictly filters for active, non-past Kalshi markets.
    If require_today is True, only matches events scheduled for the current ET date.
    Returns: (ticker, entry_price, market_title) or (None, 0.0, None)
    """
    raw_sport = (prediction.get("sport") or "UNKNOWN").upper()
    sport = _normalize_sport(raw_sport)
    team = (prediction.get("predicted_team") or "UNKNOWN").strip()
    meta = prediction.get("metadata") or {}

    now_et = datetime.now(ZoneInfo("America/New_York"))
    today_et = now_et.date()
    now_ts = now_et.timestamp()

    # If prediction metadata specifies a date, ensure it's today
    pred_date_str = meta.get("date")
    if pred_date_str and isinstance(pred_date_str, str):
        try:
            clean_d = pred_date_str.split("T")[0].strip()
            parts = [int(p) for p in clean_d.split("-") if p.isdigit()]
            if len(parts) == 3 and date(parts[0], parts[1], parts[2]) != today_et:
                logger.debug(f"[SportsBridge] Skipping {team}: prediction date {pred_date_str} is not today {today_et}")
                return None, 0.0, None
        except Exception:
            pass

    # If prediction is marked as not upcoming or completed, skip
    if meta.get("is_upcoming") is False or str(prediction.get("status") or "").lower() in ("completed", "final", "closed", "ended", "post"):
        logger.debug(f"[SportsBridge] Skipping {team}: prediction is not upcoming or already completed")
        return None, 0.0, None, {}

    # Fast path 1: If prediction object already includes active markets
    pred_markets = prediction.get("markets") or meta.get("markets")
    if pred_markets and isinstance(pred_markets, list):
        ev_ticker = (prediction.get("event_ticker") or prediction.get("ticker") or "").strip()
        ev_date, start_epoch = extract_sports_event_date_and_time(ev_ticker, event_obj=prediction)
        is_date_ok = True
        if require_today and (ev_date is None or ev_date != today_et):
            is_date_ok = False
        if ev_date and ev_date < today_et:
            is_date_ok = False
        if start_epoch and (now_ts - start_epoch > 14400):
            is_date_ok = False

        if is_date_ok:
            team_tokens = {w for w in re.findall(r'[a-z0-9]+', team.lower()) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
            matched_m = None
            for m in pred_markets:
                m_status = str(m.get('status') or '').lower()
                if m_status in ('closed', 'settled', 'determined'):
                    continue
                m_text = f"{m.get('title', '')} {m.get('yes_sub_title', '')}".lower()
                if team.lower() in m_text or (m.get('yes_sub_title', '').lower() in team.lower()):
                    matched_m = m
                    break
                m_tokens = {w for w in re.findall(r'[a-z0-9]+', m_text) if len(w) >= 3}
                if team_tokens and (team_tokens <= m_tokens):
                    matched_m = m
                    break
            if not matched_m:
                for first_m in pred_markets:
                    if str(first_m.get('status') or '').lower() not in ('closed', 'settled', 'determined'):
                        matched_m = first_m
                        break
            if matched_m:
                t = matched_m.get('ticker')
                ask = float(matched_m.get('yes_ask_dollars') or matched_m.get('last_price_dollars') or prediction.get('yes_ask') or 0.50)
                if not (0.01 <= ask <= 0.99):
                    ask = 0.50
                details = parse_sports_market_details(
                    ticker=t,
                    title=matched_m.get('title', ''),
                    series=prediction.get('series_ticker', ''),
                    markets=[matched_m],
                    sub_title=matched_m.get('yes_sub_title', ''),
                    event_obj=prediction
                )
                return t, ask, matched_m.get('title') or team, details

    try:
        # Determine series to check
        if sport == 'NPB/KBO':
            series_list = _SPORTS_SERIES_MAP.get("NPB", []) + _SPORTS_SERIES_MAP.get("KBO", [])
        elif sport in _SPORTS_SERIES_MAP:
            series_list = _SPORTS_SERIES_MAP[sport]
        else:
            series_list = [raw_sport]

        team_tokens = {w for w in re.findall(r'[a-z0-9]+', team.lower()) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}

        for s in series_list:
            events = _fetch_kalshi_series_events(s)
            if not events:
                continue

            for event in events:
                event_ticker = (event.get('event_ticker') or '').strip()
                if not event_ticker:
                    continue

                # Extract event date and start time
                ev_date, start_epoch = extract_sports_event_date_and_time(event_ticker, event_obj=event)

                # Strict current-day requirement: only trade current day's events
                if require_today and (ev_date is None or ev_date != today_et):
                    continue

                # Skip past events
                if ev_date and ev_date < today_et:
                    continue
                if start_epoch and (now_ts - start_epoch > 14400):
                    continue  # Concluded > 4h ago

                title = (event.get('title') or '').lower()
                event_ticker_l = event_ticker.lower()
                title_tokens = {w for w in re.findall(r'[a-z0-9]+', f"{title} {event_ticker_l}") if len(w) >= 3}

                # Check if this event involves the predicted team
                matches_event = (
                    team.lower() in title or
                    team.lower() in event_ticker_l or
                    (team_tokens and team_tokens <= title_tokens)
                )

                if matches_event:
                    markets = event.get('markets', [])
                    matched_m = None
                    for m in markets:
                        m_status = str(m.get('status') or '').lower()
                        if m_status in ('closed', 'settled', 'determined'):
                            continue

                        m_text = f"{m.get('title', '')} {m.get('yes_sub_title', '')}".lower()
                        if team.lower() in m_text or (m.get('yes_sub_title', '').lower() in team.lower()):
                            matched_m = m
                            break
                        m_tokens = {w for w in re.findall(r'[a-z0-9]+', m_text) if len(w) >= 3}
                        if team_tokens and (team_tokens <= m_tokens):
                            matched_m = m
                            break

                    if matched_m:
                        t = matched_m.get('ticker')
                        ask = float(matched_m.get('yes_ask_dollars') or matched_m.get('last_price_dollars') or 0.50)
                        if not (0.01 <= ask <= 0.99):
                            ask = 0.50
                        details = parse_sports_market_details(
                            ticker=t,
                            title=matched_m.get('title', ''),
                            series=event.get('series_ticker', ''),
                            markets=[matched_m],
                            sub_title=matched_m.get('yes_sub_title', ''),
                            event_obj=event
                        )
                        return t, ask, matched_m.get('title') or team, details

                    if markets:
                        for first_m in markets:
                            if str(first_m.get('status') or '').lower() not in ('closed', 'settled', 'determined'):
                                t = first_m.get('ticker') or event.get('event_ticker')
                                ask = float(first_m.get('yes_ask_dollars') or first_m.get('last_price_dollars') or 0.50)
                                details = parse_sports_market_details(
                                    ticker=t,
                                    title=first_m.get('title', ''),
                                    series=event.get('series_ticker', ''),
                                    markets=[first_m],
                                    sub_title=first_m.get('yes_sub_title', ''),
                                    event_obj=event
                                )
                                return t, ask, first_m.get('title') or event.get('title', team), details

        return None, 0.0, None, {}
    except Exception as e:
        logger.error(f"[SportsBridge] Error matching Kalshi market for {team}: {e}")
        return None, 0.0, None, {}

def _check_kalshi_settlement(market_ticker: str) -> dict:
    """Uses Kalshi API to check if market is determined."""
    try:
        headers = {"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"}
        # If it's a dummy or non-Kalshi ticker, cannot settle via Kalshi
        if market_ticker.startswith("KALSHI-"):
            return {"status": "open", "result": None}

        # If it's a fallback -MKT ticker, query the parent event
        lookup_ticker = market_ticker
        if lookup_ticker.endswith("-MKT"):
            ev_ticker = lookup_ticker[:-4]
            r = requests.get(
                f"https://external-api.kalshi.com/trade-api/v2/events/{ev_ticker}",
                headers=headers,
                timeout=5.0
            )
            if r.status_code == 200:
                ev = r.json().get('event', {})
                markets = ev.get('markets', [])
                if markets and all(m.get('status') in ('determined', 'settled', 'closed') for m in markets):
                    return {"status": "determined", "result": markets[0].get('result')}
            return {"status": "open", "result": None}

        r = requests.get(
            f"https://external-api.kalshi.com/trade-api/v2/markets/{market_ticker}",
            headers=headers,
            timeout=5.0
        )
        if r.status_code == 200:
            market = r.json().get('market', {})
            status = str(market.get('status', 'open')).lower()
            result = market.get('result', None)
            cur_price = float(market.get('yes_bid_dollars') or market.get('last_price_dollars') or 0.0)
            if not cur_price and market.get('yes_bid'):
                cur_price = float(market.get('yes_bid')) / 100.0
            return {"status": status, "result": result, "cur_price": cur_price}
        elif r.status_code == 429:
            logger.warning("Kalshi API 429 Too Many Requests during settlement check.")
        elif r.status_code == 404:
            logger.debug(f"Market not found on Kalshi: {market_ticker}")
        else:
            logger.error(f"Error checking Kalshi settlement for {market_ticker}: status {r.status_code}")
        return {"status": "open", "result": None, "cur_price": 0.0}
    except Exception as e:
        logger.error(f"Error checking Kalshi settlement for {market_ticker}: {e}")
        return {"status": "open", "result": None, "cur_price": 0.0}

class SportsBridgeExecutor:
    def __init__(self):
        self.client = SportsPredictionClient()
        self.last_check = 0

    def run_cycle(self):
        now = time.time()
        if now - self.last_check < 60:
            return
        self.last_check = now

        users = get_all_active_users()
        # Always settle open trades for all users (so open sports trades close/settle even if user toggled off auto-trading)
        for u in users:
            try:
                self._settle_open_trades(u)
            except Exception as e:
                logger.error(f"[SportsBridge] Error settling open trades for user {u.get('id')}: {e}")

        # Strictly require trading_universe in ('SPORTS', 'BOTH', 'ALL') AND ai_enabled is True for auto-trading execution
        sports_users = [
            u for u in users
            if (u.get("trading_universe") or "").upper() in ("SPORTS", "BOTH", "ALL") and bool(u.get("ai_enabled", 0))
        ]
        if not sports_users:
            return

        logger.info(f"[SportsBridge] Found {len(sports_users)} active auto-trading sports users. Gathering sports opportunities...")

        picks = []
        try:
            picks = self.client.fetch_latest_picks() or []
        except Exception as e:
            logger.debug(f"[SportsBridge] Could not fetch picks from client: {e}")

        # Fetch today's active Kalshi events with AI predictions
        kalshi_today_events = []
        try:
            r = requests.get("http://127.0.0.1:8058/api/engine/sports/events", timeout=5.0)
            if r.status_code == 200:
                ev_data = r.json().get("events", [])
                kalshi_today_events = [
                    e for e in ev_data
                    if e.get("is_today") and float(e.get("confidence_pct") or 0.0) > 0.0
                ]
        except Exception as e:
            logger.debug(f"[SportsBridge] Could not fetch events over HTTP: {e}")
            try:
                from backend.routes.engine import api_sports_events
                ev_data = api_sports_events().get("events", [])
                kalshi_today_events = [
                    e for e in ev_data
                    if e.get("is_today") and float(e.get("confidence_pct") or 0.0) > 0.0
                ]
            except Exception as e2:
                logger.error(f"[SportsBridge] Error calling api_sports_events in-process: {e2}")

        # Combine candidates (giving priority to today's Kalshi events)
        all_candidates = list(kalshi_today_events)
        seen_teams = {(c.get("sport"), c.get("predicted_team")) for c in all_candidates}
        for p in picks:
            pair = (p.get("sport"), p.get("predicted_team"))
            if pair not in seen_teams:
                all_candidates.append(p)
                seen_teams.add(pair)

        if not all_candidates:
            logger.info("[SportsBridge] No sports opportunities found for current cycle.")
            return

        logger.info(f"[SportsBridge] Evaluating {len(all_candidates)} candidates ({len(kalshi_today_events)} today Kalshi events, {len(picks)} bridge picks) across {len(sports_users)} active sports users...")

        for u in sports_users:
            try:
                self._process_user(u, all_candidates)
            except Exception as e:
                logger.error(f"[SportsBridge] Error processing user {u.get('id')}: {e}")

    def _process_user(self, user, picks):
        uid = user["id"]
        # Double check AI enabled
        if not user.get("ai_enabled"):
            return

        min_conf = float(user.get("min_sports_confidence") or 70.0)
        min_edge = float(user.get("min_sports_edge") or 0.0)
        base_wager = float(user.get("sports_trade_size_dollars") or user.get("sports_max_wager") or 10.0)
        include_live = bool(user.get("sports_include_live") or False)
        mode = (user.get("trading_mode") or "PAPER").upper()

        kt = None
        avail_live_cash = 0.0
        if mode == "LIVE":
            from backend.btc.kalshi_trader import get_authenticated_trader_for_user
            kt = get_authenticated_trader_for_user(user)
            if not kt or not kt.is_authenticated():
                logger.warning(f"[SportsBridge] User {uid} is in LIVE mode but has no valid Kalshi credentials linked. Skipping auto-trade.")
                return
            bal_res = kt.get_balance(force_refresh=True)
            if not bal_res.get("success"):
                logger.warning(f"[SportsBridge] Could not verify Kalshi live balance for user {uid}: {bal_res.get('error')}. Skipping auto-trade.")
                return
            avail_live_cash = float(bal_res.get("balance_dollars", 0.0))
        elif mode != "PAPER":
            return

        # 1. Active leagues filter
        raw_leagues = user.get("sports_active_leagues") or 'NFL,MLB,NPB/KBO,SOC,UFC,TEN,NHL'
        active_leagues = {l.strip().upper() for l in raw_leagues.split(',') if l.strip()}

        # 2. Price corridor filter (min/max price in dollars, e.g. 0.20 to 0.80)
        min_price = float(user.get("sports_min_price") if user.get("sports_min_price") is not None else 0.20)
        max_price = float(user.get("sports_max_price") if user.get("sports_max_price") is not None else 0.80)

        # 3. Max daily sports wagers count and risk cap
        max_daily_trades = int(user.get("sports_max_daily_trades") if user.get("sports_max_daily_trades") is not None else 10)
        max_open_trades = int(user.get("sports_max_open_trades") if user.get("sports_max_open_trades") is not None else 5)
        max_daily_risk = float(user.get("sports_max_daily_risk") if user.get("sports_max_daily_risk") is not None else 100.0)

        # 4. Kelly Criterion / edge-scaled sizing
        use_kelly = bool(user.get("sports_use_kelly", 0))

        # 5. Market types filter
        raw_market_types = user.get("sports_market_types") or 'GAME,SPREAD,TOTAL,PROP'
        allowed_market_types = {m.strip().upper() for m in raw_market_types.split(',') if m.strip()}

        from backend.database.trade_store import TradeStore
        open_trades = TradeStore.get_open_trades(uid)
        open_tickers = {t.get("ticker") for t in open_trades if t.get("ticker")}

        # Enforce max open trades cap
        if max_open_trades > 0 and len(open_trades) >= max_open_trades:
            logger.info(f"[SportsBridge] User {uid} reached open sports trade limit ({len(open_trades)}/{max_open_trades}). Skipping.")
            return

        # Evaluate rolling 24h trades for daily cap enforcement
        now_ts = time.time()
        day_ago = now_ts - 86400
        recent_trades = TradeStore.get_recent_trades(uid, limit=100)
        today_sports_trades = [
            t for t in recent_trades
            if _is_sports_trade(t)
            and _parse_trade_timestamp(t.get("timestamp")) >= day_ago
        ]
        daily_trades_count = len(today_sports_trades)
        daily_risk_spent = sum(float(t.get("cost") or t.get("trade_size_dollars") or 0.0) for t in today_sports_trades)

        if max_daily_trades > 0 and daily_trades_count >= max_daily_trades:
            logger.info(f"[SportsBridge] User {uid} reached daily sports trade limit ({daily_trades_count}/{max_daily_trades}). Skipping.")
            return

        if max_daily_risk > 0 and daily_risk_spent >= max_daily_risk:
            logger.info(f"[SportsBridge] User {uid} reached daily sports risk cap (${daily_risk_spent:.2f}/${max_daily_risk:.2f}). Skipping.")
            return

        now_et = datetime.now(ZoneInfo("America/New_York"))
        today_et = now_et.date()
        now_ts = now_et.timestamp()

        for pred in picks:
            if max_daily_trades > 0 and daily_trades_count >= max_daily_trades:
                break
            if max_daily_risk > 0 and daily_risk_spent >= max_daily_risk:
                break

            sport = (pred.get("sport") or "UNKNOWN").upper()
            norm_sport = _normalize_sport(sport)

            # League check
            if norm_sport not in active_leagues and sport not in active_leagues:
                continue

            conf = float(pred.get("confidence_pct") or 0.0)
            edge = float(pred.get("edge_pct") or 0.0)
            meta = pred.get("metadata") or {}
            is_upcoming = bool(meta.get("is_upcoming", True))
            status = str(pred.get("status") or "unknown").lower()

            if conf < min_conf or edge < min_edge:
                continue

            # Skip completed, past, or closed picks
            if not is_upcoming or status in ("completed", "final", "closed", "ended", "post"):
                continue

            # Match only active, non-past Kalshi markets scheduled strictly for today
            res = _generate_kalshi_market(pred, require_today=True)
            ticker, price, market_title = res[0], res[1], res[2]
            market_details = res[3] if len(res) > 3 and isinstance(res[3], dict) else parse_sports_market_details(ticker or '', market_title or '', sport)
            if not ticker or not ticker.startswith("KX"):
                continue

            # Double-check scheduled date and start time
            ev_date, start_epoch = extract_sports_event_date_and_time(ticker, metadata=meta)
            if ev_date != today_et:
                logger.info(f"[SportsBridge] Skipping {ticker}: event date {ev_date} is not current day {today_et}")
                continue

            if start_epoch is not None:
                if start_epoch < (now_ts - 300) and not include_live:
                    logger.info(f"[SportsBridge] Skipping {ticker}: event already started at {start_epoch} (include_live=False)")
                    continue
                if start_epoch < (now_ts - 14400):
                    logger.info(f"[SportsBridge] Skipping {ticker}: event started > 4 hours ago, already finished")
                    continue

            # Price corridor check
            if not (min_price <= price <= max_price):
                logger.debug(f"[SportsBridge] Skipping {ticker}: price {price:.2f} outside corridor [{min_price:.2f}, {max_price:.2f}]")
                continue

            # Market type check (GAME, SPREAD, TOTAL, PROP)
            upper_tk = ticker.upper()
            upper_mt = market_title.upper()
            m_type = "GAME"
            if market_details.get("prop_type") == "Player Prop" or any(p in upper_tk for p in ("KXNHLGOAL", "KXNHLSHOT", "KXMLBHRR", "KXMLBHIT", "KXMLBHR", "KXMLBKS", "KXMLBRBI", "KXMLBTB", "KXNFLTD", "PROP", "HRR")):
                m_type = "PROP"
            elif "SPREAD" in upper_tk or "SPREAD" in upper_mt:
                m_type = "SPREAD"
            elif any(w in upper_tk or w in upper_mt for w in ("TOTAL", "OVER", "UNDER", "O/U")):
                m_type = "TOTAL"

            is_prop_allowed = m_type == "PROP" and any(p in allowed_market_types for p in ("PROP", "PLAYER_PROP", "PROPS"))
            if m_type not in allowed_market_types and not is_prop_allowed:
                logger.debug(f"[SportsBridge] Skipping {ticker}: market type {m_type} not in allowed {allowed_market_types}")
                continue

            # Max wager safeguard from user settings
            max_wager_setting = float(user.get("sports_max_wager") or user.get("sports_trade_size_dollars") or 10.0)

            # Minimum edge safeguard for LIVE auto-trading (require at least 1.0% edge)
            if mode == "LIVE" and edge < max(min_edge, 1.0):
                continue

            if ticker not in open_tickers:
                predicted_team = pred.get("predicted_team", "UNKNOWN")

                # Kelly Criterion Sizing calculation
                if use_kelly:
                    # Dynamically scales wager: e.g. 5% edge is standard 1.0x, range 0.3x to 1.2x
                    kelly_factor = max(0.3, min(1.2, edge / 5.0))
                    wager = round(base_wager * kelly_factor, 2)
                else:
                    wager = base_wager

                # Ensure wager does not breach remaining daily risk cap or max wager setting
                if max_daily_risk > 0:
                    remaining_risk = max_daily_risk - daily_risk_spent
                    if remaining_risk <= 0:
                        break
                    wager = min(wager, remaining_risk, max_wager_setting)
                else:
                    wager = min(wager, max_wager_setting)
                if wager < 1.0:
                    continue

                trade_id = f"sports_auto_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                max_p = min(0.99, max(0.01, price + 0.04))
                count = max(1, int(wager / max_p))
                cost = round(price * count, 2)

                order_id = trade_id
                fill_price = price
                fill_count = count
                actual_cost = cost

                if mode == "LIVE":
                    # Strictly require real Kalshi market ticker for live trades
                    if not ticker.startswith("KX") or ticker.endswith("-MKT") or ticker.startswith("KALSHI-"):
                        logger.debug(f"[SportsBridge] Skipping non-real Kalshi ticker {ticker} for live user {uid}")
                        continue

                    if avail_live_cash < cost:
                        logger.warning(f"[SportsBridge] User {uid} has insufficient live balance (${avail_live_cash:.2f}) for ${cost:.2f} sports trade on {ticker}")
                        continue

                    order_res = kt.place_sports_order(
                        ticker=ticker,
                        side="yes",
                        count=count,
                        limit_price_dollars=price,
                        dry_run=False,
                        slippage_buffer_dollars=0.04
                    )
                    if not order_res.get("success"):
                        logger.warning(f"[SportsBridge] Live order failed for user {uid} on {ticker}: {order_res.get('error')}")
                        continue

                    order_id = str(order_res.get("order_id") or order_res.get("client_order_id") or trade_id)
                    fill_price = float(order_res.get("filled_price") or price)
                    fill_count = int(order_res.get("count") or count)
                    actual_cost = round(fill_price * fill_count, 2)
                    avail_live_cash -= actual_cost
                else:
                    # Deduct unified paper balance
                    if not deduct_user_paper_balance(uid, cost):
                        logger.warning(f"[SportsBridge] User {uid} has insufficient paper balance for ${cost:.2f} sports trade on {ticker}")
                        continue

                logger.info(f"[SportsBridge] Executed {mode} trade for user {uid} on {ticker} (${actual_cost:.2f}, Kelly: {use_kelly}, order_id: {order_id})")

                prop_type_val = market_details.get("prop_type", "Moneyline")
                line_val = market_details.get("line", "Moneyline")
                spread_amt_val = market_details.get("spread_amount")
                ou_amt_val = market_details.get("over_under_amount")
                strike_det_val = market_details.get("strike_details", "")
                num_line_val = market_details.get("numeric_line")
                if market_details.get("player_name"):
                    predicted_team = market_details["player_name"]

                trade_dict = {
                    "id": order_id,
                    "order_id": order_id,
                    "client_order_id": order_id,
                    "user_id": uid,
                    "ticker": ticker,
                    "sport": sport,
                    "asset": sport,
                    "predicted_team": predicted_team,
                    "team": predicted_team,
                    "trade_size_dollars": wager,
                    "side": "YES",
                    "direction": "YES",
                    "entry_price": fill_price,
                    "count": fill_count,
                    "cost": actual_cost,
                    "pnl": 0.0,
                    "status": "OPEN",
                    "mode": mode,
                    "prop_type": prop_type_val,
                    "line": line_val,
                    "spread_amount": spread_amt_val,
                    "over_under_amount": ou_amt_val,
                    "strike_details": strike_det_val,
                    "numeric_line": num_line_val,
                    "reason": f"[{prop_type_val}] {line_val} | AI Edge: {predicted_team} (Conf: {conf:.1f}%, Edge: {edge:.1f}%)",
                    "trading_style": "SPORTS_AI",
                    "signal_source": "Sports AI Bot Bridge",
                    "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "ml_reasoning": json.dumps({
                        "confidence": conf,
                        "edge": edge,
                        "sport": sport,
                        "team": predicted_team,
                        "predicted_team": predicted_team,
                        "market_title": market_title,
                        "kelly_scaled": use_kelly,
                        "market_type": m_type,
                        "prop_type": prop_type_val,
                        "line": line_val,
                        "spread_amount": spread_amt_val,
                        "over_under_amount": ou_amt_val,
                        "strike_details": strike_det_val,
                        "numeric_line": num_line_val,
                    }),
                    "catalysts": [
                        f"{sport} {prop_type_val}: {line_val}",
                        f"{sport} AI edge: {edge:.1f}%",
                        f"Model win prob: {conf:.1f}%"
                    ]
                }
                trade_dict["raw_json"] = json.dumps(trade_dict)
                TradeStore.insert_trade(uid, trade_dict)
                open_tickers.add(ticker)
                daily_trades_count += 1
                daily_risk_spent += actual_cost

    def _settle_open_trades(self, user):
        from backend.database.trade_store import TradeStore
        uid = user["id"]
        open_trades = TradeStore.get_open_trades(uid)

        tp_enabled = bool(user.get("sports_tp_enabled", 0))
        tp_pct = float(user.get("sports_tp_pct") if user.get("sports_tp_pct") is not None else 35.0)

        for t in open_trades:
            ticker = t.get("ticker") or ""
            t_id = t.get("id")
            if not ticker:
                continue
            if not _is_sports_trade(t):
                continue

            t_mode = (t.get("mode") or "PAPER").upper()
            settlement = _check_kalshi_settlement(ticker)
            status = str(settlement.get("status") or "").lower()
            entry_price = float(t.get("entry_price") or 0.5)
            contracts = int(t.get("count") or 1)

            # 1. Check for Mid-Game Early Take-Profit if position is still open
            if tp_enabled and status not in ("determined", "settled", "closed"):
                cur_price = float(settlement.get("cur_price") or 0.0)
                if cur_price > entry_price:
                    gain_pct = ((cur_price - entry_price) / max(entry_price, 0.01)) * 100.0
                    if gain_pct >= tp_pct:
                        pnl = round((cur_price - entry_price) * contracts, 2)
                        payout = round(cur_price * contracts, 2)
                        t_mode = (t.get("mode") or "PAPER").upper()
                        if t_mode == "LIVE":
                            from backend.btc.kalshi_trader import get_authenticated_trader_for_user
                            kt_settle = get_authenticated_trader_for_user(user)
                            if kt_settle:
                                close_res = kt_settle.close_position(
                                    ticker=ticker,
                                    purchased_side=str(t.get("side") or "YES").upper(),
                                    count=contracts,
                                    dry_run=False,
                                    estimated_exit_price=cur_price
                                )
                                if not close_res.get("success"):
                                    logger.warning(f"[SportsBridge] Live TP close failed for {t_id}: {close_res.get('error')}")
                                    continue
                                cur_price = float(close_res.get("exit_price") or cur_price)
                                pnl = round((cur_price - entry_price) * contracts, 2)
                                payout = round(cur_price * contracts, 2)
                        elif payout > 0:
                            credit_user_paper_balance(uid, payout)
                        TradeStore.update_trade(t_id, {
                            "status": "CLOSED",
                            "exit_price": cur_price,
                            "pnl": pnl,
                            "exit_reason": f"TAKE_PROFIT (+{gain_pct:.1f}%)",
                            "settled_at": time.time()
                        })
                        logger.info(f"[SportsBridge] Mid-game Take-Profit triggered for {t_id} ({t_mode}) at {cur_price:.2f} (+{gain_pct:.1f}% gain, PnL: ${pnl:.2f})")
                        continue

            # 2. Check for Final Settlement (Win/Loss)
            if status in ("determined", "settled", "closed"):
                result = str(settlement.get("result") or "").strip().upper()
                side = str(t.get("side") or "YES").strip().upper()
                t_mode = (t.get("mode") or "PAPER").upper()

                is_win = (result == side)
                if is_win:
                    exit_price = 1.0
                    pnl = round((1.0 - entry_price) * contracts, 2)
                    payout = round(1.0 * contracts, 2)
                    # Credit winnings back to unified paper balance ONLY for PAPER trades
                    # (Live trades are settled and credited automatically by Kalshi into the user's cash portfolio)
                    if payout > 0 and t_mode == "PAPER":
                        credit_user_paper_balance(uid, payout)
                else:
                    exit_price = 0.0
                    pnl = round(-entry_price * contracts, 2)

                TradeStore.update_trade(t_id, {
                    "status": "CLOSED",
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "exit_reason": "SETTLEMENT",
                    "settled_at": time.time()
                })
                logger.info(f"[SportsBridge] Settled sports trade {t_id} for ${pnl:.2f} (Win: {is_win})")
            elif t_mode == "PAPER" and ticker.startswith("KALSHI-"):
                # Clean up legacy phantom/dummy trades and refund paper balance immediately
                cost = float(t.get("cost") or t.get("trade_size_dollars") or 0.0)
                if cost > 0:
                    credit_user_paper_balance(uid, cost)
                TradeStore.update_trade(t_id, {
                    "status": "CLOSED",
                    "exit_price": entry_price,
                    "pnl": 0.0,
                    "exit_reason": "CANCELED_INVALID_DUMMY_TICKER",
                    "settled_at": time.time()
                })
                logger.info(f"[SportsBridge] Canceled and refunded dummy sports trade {t_id} on {ticker}")
            elif t_mode == "PAPER" and ticker.endswith("-MKT"):
                trade_age = time.time() - _parse_trade_timestamp(t.get("timestamp"))
                if trade_age > 14400:  # 4 hours
                    conf_match = re.search(r'Conf:\s*([\d\.]+)%', str(t.get("reason") or ""))
                    trade_conf = float(conf_match.group(1)) if conf_match else 60.0
                    is_win = (trade_conf >= 55.0)
                    exit_price = 1.0 if is_win else 0.0
                    pnl = round((exit_price - entry_price) * contracts, 2)
                    payout = round(exit_price * contracts, 2)
                    if payout > 0:
                        credit_user_paper_balance(uid, payout)
                    TradeStore.update_trade(t_id, {
                        "status": "CLOSED",
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "exit_reason": "SIMULATED_GAME_CONCLUDED",
                        "settled_at": time.time()
                    })
                    logger.info(f"[SportsBridge] Auto-settled simulated paper trade {t_id} after {trade_age/3600:.1f}h (Win: {is_win}, PnL: ${pnl:.2f})")
