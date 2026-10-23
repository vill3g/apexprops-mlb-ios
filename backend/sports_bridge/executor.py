USE_KALSHI_BRIDGE = False
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
from backend.database import order_intents
from backend.btc.fees import kalshi_order_fee, net_pnl
from backend.database.models import (
    get_all_active_users,
    deduct_user_paper_balance,
    credit_user_paper_balance
)
from backend.routes.engine import _SPORTS_SERIES_MAP, _is_sports_asset
from backend.routes.engine_sports import (
    _SPORT_TEAM_MAP,
    _detect_game_segment,
    _execute_sports_paper_trade, _execute_sports_trade, _fetch_kalshi_series_events,
    extract_sports_event_date_and_time, parse_sports_market_details,
    normalize_sport_key as _normalize_sport
)

logger = logging.getLogger(__name__)

_vegas_veto_func = None

def _check_vegas_veto_safe(sport: str, pick_team_name: str, conf: float) -> bool:
    """Natively validates confidence thresholds and veto sanity without external HTTP calls."""
    try:
        if conf is not None and (float(conf) < 35.0 or float(conf) > 95.0):
            return True
        return False
    except Exception as e:
        logger.debug(f"[SportsBridge] Native veto check error for {sport} {pick_team_name}: {e}")
        return False

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
        "KXMMA", "KXCBB", "KXCFB", "KXMLS", "KXEPL", "KXUCL",
        "KXWTA", "KXATP", "KXBUNDESLIGA", "KXLALIGA", "KXSERIEA", "KXLIGUE1",
        "KXLIGAMX", "KXEFL", "KXUSL", "KXCONMEBOL", "KXARG", "KXDIMAYOR",
        "KXBRAS", "KXERED", "KXSAUDI", "KXSCOT", "KXUEL", "KXUECL",
        "KXMVE", "KXMVECROSSCATEGORY"
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


SPORTS_INTENT_PREFIX = "sports:"
UNRESOLVED_MIN_AGE_SECONDS = 60          
UNRESOLVED_GIVE_UP_SECONDS = 15 * 60     

MAX_FUTURE_START_WINDOW_SECONDS = 4 * 3600  # Strict 4-hour horizon limit for sports auto-trading (14,400s)

def _sports_intent_ticker(ticker: str) -> str:
    return f"{SPORTS_INTENT_PREFIX}{ticker}"

def _size_sports_order(wager: float, price: float) -> tuple:
    max_p = min(0.99, max(0.01, float(price) + 0.04))
    count = int(float(wager) / max_p) if max_p > 0 else 0
    while count > 0 and (count * max_p + kalshi_order_fee(max_p, count)) > float(wager):
        count -= 1
    if count < 1:
        return 0, 0.0
    return count, round(count * max_p + kalshi_order_fee(max_p, count), 2)

def _is_event_within_start_window(
    cand: dict,
    now_ts: float,
    max_future_seconds: float = MAX_FUTURE_START_WINDOW_SECONDS,
    allow_live: bool = False
) -> tuple[bool, str]:
    """
    Checks if a candidate event starts within the next `max_future_seconds` (default: 4 hours)
    or is currently live (if allow_live=True).
    Strictly prevents placing auto-trades for tomorrow night or games > 4 hours away,
    which blocks the queue and daily risk limits for imminent games.
    
    Returns: (is_eligible: bool, reason: str)
    """
    now_et = datetime.now(ZoneInfo("America/New_York"))
    today_et = now_et.date()

    ev_date = None
    ev_date_val = cand.get("event_date") or cand.get("date")
    if ev_date_val:
        try:
            if isinstance(ev_date_val, date):
                ev_date = ev_date_val
            elif isinstance(ev_date_val, str):
                clean_d = ev_date_val.split("T")[0].strip()
                parts = [int(p) for p in clean_d.split("-") if p.isdigit()]
                if len(parts) == 3:
                    ev_date = date(parts[0], parts[1], parts[2])
        except Exception:
            pass

    if ev_date is not None and ev_date > today_et:
        return False, f"Scheduled for future date {ev_date} (horizon limit: today only)"

    ep = cand.get("start_epoch")
    if ep is None:
        meta = cand.get("metadata") or {}
        tk = (
            cand.get("event_ticker")
            or cand.get("ticker")
            or cand.get("market_ticker")
            or meta.get("game_id")
            or meta.get("event_ticker")
            or meta.get("ticker")
            or ""
        )
        ex_date, ex_epoch = extract_sports_event_date_and_time(tk, metadata=meta, event_obj=cand)
        if ex_date is not None and ev_date is None:
            ev_date = ex_date
        if ex_epoch is not None:
            ep = float(ex_epoch)
            cand["start_epoch"] = ep

    if ev_date is not None and ev_date > today_et:
        return False, f"Scheduled for future date {ev_date} (horizon limit: today only)"

    if ep is None:
        # Start time unknown: reject from auto-trading to prevent trading games hours/days away
        return False, "Unknown start time (cannot verify within 4h window)"

    diff = ep - now_ts
    if diff > max_future_seconds:
        hours_away = diff / 3600.0
        return False, f"Starts in {hours_away:.1f}h (> 4.0h auto-trade horizon limit)"

    if diff < 0:
        elapsed = -diff
        if elapsed > 14400.0:
            return False, f"Concluded / started > 4h ago ({elapsed/3600.0:.1f}h ago)"
        is_really_live = bool(
            cand.get("is_live")
            or str(cand.get("status") or "").lower() in ("in_progress", "live", "active", "open")
            or str((cand.get("milestone") or {}).get("details", {}).get("status") or "").lower() in ("in_progress", "live")
        )
        # Grace window: matches frequently start 5-20m late (court delays, anthems, warmups)
        if elapsed <= 1200.0:
            if not allow_live and is_really_live:
                return False, "Live game (sports_include_live is disabled)"
            return True, f"Starting window active ({elapsed/60.0:.1f}m past scheduled start)"
        if not is_really_live and not allow_live:
            return False, f"Not active live in-progress ({elapsed/60.0:.1f}m past scheduled start)"
        if not allow_live:
            return False, "Live game (sports_include_live is disabled)"
        return True, "Live in-progress event within window"

    return True, f"Starts in {diff/3600.0:.1f}h (within 4h window)"

def _generate_kalshi_market(prediction: dict, require_today: bool = True, max_horizon_seconds: float = MAX_FUTURE_START_WINDOW_SECONDS) -> tuple:
    """
    Matches a sport prediction to an actual Kalshi event/market ticker and ask price.
    Strictly filters for active, non-past Kalshi markets.
    If require_today is True, only matches events scheduled within max_horizon_seconds (default 4 hours).
    Returns: (ticker, entry_price, market_title) or (None, 0.0, None)
    """
    raw_sport = (prediction.get("sport") or "UNKNOWN").upper()
    sport = _normalize_sport(raw_sport)
    team = (prediction.get("predicted_team") or "UNKNOWN").strip()
    meta = prediction.get("metadata") or {}

    now_et = datetime.now(ZoneInfo("America/New_York"))
    today_et = now_et.date()
    now_ts = now_et.timestamp()

    # If prediction metadata specifies a date, ensure it's not in the past
    pred_date_str = meta.get("date")
    if pred_date_str and isinstance(pred_date_str, str):
        try:
            clean_d = pred_date_str.split("T")[0].strip()
            parts = [int(p) for p in clean_d.split("-") if p.isdigit()]
            if len(parts) == 3:
                p_date = date(parts[0], parts[1], parts[2])
                if p_date < today_et:
                    logger.debug(f"[SportsBridge] Skipping {team}: prediction date {pred_date_str} is in the past")
                    return None, 0.0, None, {}
                if require_today and p_date > today_et:
                    logger.debug(f"[SportsBridge] Skipping {team}: prediction date {pred_date_str} is tomorrow or future")
                    return None, 0.0, None, {}
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
        if require_today and ev_date is not None and ev_date > today_et:
            is_date_ok = False
        is_in_slate = (ev_date == today_et or (start_epoch is not None and (0 <= start_epoch - now_ts <= max_horizon_seconds)))
        if require_today and not is_in_slate:
            is_date_ok = False
        if ev_date and ev_date < today_et and not is_in_slate:
            is_date_ok = False
        if start_epoch and (start_epoch - now_ts > max_horizon_seconds):
            is_date_ok = False
        if start_epoch and (now_ts - start_epoch > 14400):
            is_date_ok = False

        if is_date_ok:
            team_tokens = {w for w in re.findall(r'[a-z0-9]+', team.lower()) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
            spread_team = re.sub(r'[\+\-]?\d+(\.\d+)?', '', team.lower()).strip()
            spread_tokens = {w for w in spread_team.split() if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
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
                if spread_tokens and (spread_tokens <= m_tokens):
                    matched_m = m
                    break
            if not matched_m:
                for first_m in pred_markets:
                    if str(first_m.get('status') or '').lower() not in ('closed', 'settled', 'determined'):
                        matched_m = first_m
                        break
            if matched_m:
                t = matched_m.get('ticker')
                ask = float(matched_m.get('yes_ask_dollars') or matched_m.get('last_price_dollars') or prediction.get('yes_ask') or 0.0)
                if not (0.01 <= ask <= 0.99):
                    return None, 0.0, None, {}
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
            base_s = list(_SPORTS_SERIES_MAP[sport])
            # Order series so GAME (moneyline) comes first for moneyline picks, SPREAD for spreads, TOTAL for totals
            p_mtype = str(prediction.get("market_type") or meta.get("market_type") or "").upper()
            if any(k in p_mtype for k in ("SPREAD", "PUCK LINE", "RUN LINE")):
                series_list = [s for s in base_s if "SPREAD" in s or "LINE" in s] + [s for s in base_s if "SPREAD" not in s and "LINE" not in s]
            elif any(k in p_mtype for k in ("TOTAL", "OVER", "UNDER", "O/U")):
                series_list = [s for s in base_s if "TOTAL" in s] + [s for s in base_s if "TOTAL" not in s]
            elif any(k in p_mtype for k in ("PROP", "PLAYER")):
                series_list = [s for s in base_s if any(p in s for p in ("TD", "PASS", "RUSH", "REC", "HRR", "PTS", "REB", "AST", "GOAL", "SAVE"))] + [s for s in base_s]
            else:
                # Default moneyline / game winner: GAME/MATCH/FIGHT first!
                series_list = [s for s in base_s if any(s.endswith(e) for e in ("GAME", "MATCH", "FIGHT", "WINS"))] + [s for s in base_s if not any(s.endswith(e) for e in ("GAME", "MATCH", "FIGHT", "WINS"))]
        else:
            series_list = [raw_sport]

        team_tokens = {w for w in re.findall(r'[a-z0-9]+', team.lower()) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
        pred_matchup = str(meta.get("matchup") or prediction.get("opponent") or "").lower()
        matchup_tokens = {w for w in re.findall(r'[a-z0-9]+', pred_matchup) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
        is_total = prediction.get("market_type") in ("TOTAL", "OVER/UNDER") or team.lower().startswith(("over ", "under "))
        spread_team = re.sub(r'[\+\-]?\d+(\.\d+)?', '', team.lower()).strip()
        spread_tokens = {w for w in spread_team.split() if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}

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

                if require_today and ev_date is not None and ev_date > today_et:
                    continue  # Calendar date is tomorrow or future

                # Strict 4-hour start horizon: only games starting within max_horizon_seconds (or live within last 4h)
                if start_epoch is not None:
                    if (start_epoch - now_ts) > max_horizon_seconds:
                        continue  # Starts > 4 hours away (prevents tomorrow night games)
                    if (now_ts - start_epoch) > 14400:
                        continue  # Concluded > 4h ago
                elif require_today:
                    if ev_date != today_et:
                        continue

                # Skip past events
                if ev_date and ev_date < today_et and (start_epoch is None or (now_ts - start_epoch > 14400)):
                    continue

                title = (event.get('title') or '').lower()
                event_ticker_l = event_ticker.lower()
                title_tokens = {w for w in re.findall(r'[a-z0-9]+', f"{title} {event_ticker_l}") if len(w) >= 3}

                # Check if this event involves the predicted team, spread, or total matchup
                matches_event = (
                    team.lower() in title or
                    team.lower() in event_ticker_l or
                    (team_tokens and team_tokens <= title_tokens) or
                    (is_total and matchup_tokens and len(matchup_tokens & title_tokens) >= 2) or
                    (spread_tokens and (spread_tokens <= title_tokens or bool(spread_tokens & title_tokens))) or
                    (matchup_tokens and len(matchup_tokens & title_tokens) >= 2)
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
                        if spread_tokens and (spread_tokens <= m_tokens):
                            matched_m = m
                            break

                    if matched_m:
                        t = matched_m.get('ticker')
                        ask = float(matched_m.get('yes_ask_dollars') or matched_m.get('last_price_dollars') or 0.0)
                        if not (0.01 <= ask <= 0.99):
                            return None, 0.0, None, {}
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
                                ask = float(first_m.get('yes_ask_dollars') or first_m.get('last_price_dollars') or 0.0)
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

def _check_kalshi_settlement(market_ticker: str, team_hint: str = "", user: dict = None) -> dict:
    """
    Uses Kalshi API to check if market or parent event is determined, settled, or closed.
    Supports:
    1. Child market tickers (e.g. KXWTAMATCH-26OCT10SHIRAK-RAK).
    2. Event tickers (e.g. KXWTAMATCH-26OCT09STESHI), matching against team_hint to determine winner.
    3. Fallback -MKT tickers.
    4. Signed Kalshi API headers when user keys are available to avoid 429 rate limits.
    """
    try:
        headers = {"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"}
        if user and user.get("kalshi_key_id"):
            try:
                from backend.btc.kalshi_trader import get_authenticated_trader_for_user
                kt = get_authenticated_trader_for_user(user)
                if kt and kt.is_authenticated():
                    headers = kt._sign_headers("GET", f"/trade-api/v2/markets/{market_ticker}")
            except Exception:
                pass

        # If it's a dummy or non-Kalshi ticker, cannot settle via Kalshi
        clean_ticker = str(market_ticker or "").strip()
        if clean_ticker.startswith("KALSHI-"):
            return {"status": "open", "result": None, "cur_price": 0.0}

        # Helper to query an event and inspect all its child markets
        def _inspect_event(ev_ticker: str):
            ev_headers = headers
            if user and user.get("kalshi_key_id"):
                try:
                    from backend.btc.kalshi_trader import get_authenticated_trader_for_user
                    kt = get_authenticated_trader_for_user(user)
                    if kt and kt.is_authenticated():
                        ev_headers = kt._sign_headers("GET", f"/trade-api/v2/events/{ev_ticker}")
                except Exception:
                    pass
            resp = requests.get(
                f"https://external-api.kalshi.com/trade-api/v2/events/{ev_ticker}",
                headers=ev_headers,
                timeout=5.0
            )
            if resp.status_code != 200:
                return {"status": "open", "result": None, "cur_price": 0.0}
            ev_data = resp.json()
            markets = ev_data.get("markets", [])
            if not markets:
                return {"status": "open", "result": None, "cur_price": 0.0}

            # If all markets are inactive/canceled/voided (e.g. match walkover / rain cancel)
            if any(m.get("status") in ("inactive", "canceled", "cancelled") for m in markets) and not any(m.get("status") == "active" for m in markets):
                return {"status": "voided", "result": "VOID", "cur_price": 0.0}

            # Check if any market matches team_hint
            if team_hint:
                th = team_hint.lower().strip()
                for m in markets:
                    sub = str(m.get("yes_sub_title") or "").lower().strip()
                    title = str(m.get("title") or "").lower().strip()
                    if th in sub or th in title or (len(th) > 3 and (sub in th or title in th)):
                        st = str(m.get("status") or "open").lower()
                        res = m.get("result", None)
                        price = float(m.get("yes_bid_dollars") or m.get("last_price_dollars") or 0.0)
                        return {"status": st, "result": res, "cur_price": price, "market_ticker": m.get("ticker")}
                # Surname check (e.g. "Peyton Stearns" -> "stearns")
                parts = [p for p in th.split() if len(p) > 2]
                for p in parts:
                    for m in markets:
                        sub = str(m.get("yes_sub_title") or "").lower().strip()
                        title = str(m.get("title") or "").lower().strip()
                        if p in sub or p in title:
                            st = str(m.get("status") or "open").lower()
                            res = m.get("result", None)
                            price = float(m.get("yes_bid_dollars") or m.get("last_price_dollars") or 0.0)
                            return {"status": st, "result": res, "cur_price": price, "market_ticker": m.get("ticker")}

            # If all markets finalized/determined, determine if any market won
            if all(m.get("status") in ("determined", "settled", "closed", "finalized") for m in markets):
                winning = next((m for m in markets if str(m.get("result") or "").lower() == "yes"), None)
                if winning:
                    return {"status": "determined", "result": "YES", "cur_price": 0.0, "market_ticker": winning.get("ticker")}
                return {"status": "determined", "result": "NO", "cur_price": 0.0, "market_ticker": markets[0].get("ticker")}

            return {"status": "open", "result": None, "cur_price": 0.0}

        # Case A: fallback -MKT ticker
        if clean_ticker.endswith("-MKT"):
            return _inspect_event(clean_ticker[:-4])

        # Case B: Event ticker with single hyphen (e.g. KXWTAMATCH-26OCT09STESHI)
        if clean_ticker.count("-") == 1 and clean_ticker.startswith("KX"):
            return _inspect_event(clean_ticker)

        # Case C: Standard market ticker
        r = requests.get(
            f"https://external-api.kalshi.com/trade-api/v2/markets/{clean_ticker}",
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
        elif r.status_code == 404:
            # Maybe the market ticker was truncated or is an event ticker without sub-market
            if clean_ticker.startswith("KX"):
                ev_res = _inspect_event(clean_ticker.split("-", 2)[0] + "-" + clean_ticker.split("-", 2)[1] if clean_ticker.count("-") >= 2 else clean_ticker)
                if ev_res.get("status") != "open":
                    return ev_res
            logger.debug(f"Market not found on Kalshi: {clean_ticker}")
        elif r.status_code == 429:
            logger.warning("Kalshi API 429 Too Many Requests during settlement check.")
        else:
            logger.error(f"Error checking Kalshi settlement for {clean_ticker}: status {r.status_code}")
        return {"status": "open", "result": None, "cur_price": 0.0}
    except Exception as e:
        logger.error(f"Error checking Kalshi settlement for {market_ticker}: {e}")
        return {"status": "open", "result": None, "cur_price": 0.0}

_LIVE_MID_SEEN = {}  # ticker -> (first_seen_ts, mid)


def _live_price_drift(ticker, mid, window_s=12 * 3600):
    """Mid-price change since this ticker was first seen (within window); 0.0 when new, matching the neutral default."""
    import time as _t
    if not ticker:
        return 0.0
    now = _t.time()
    first = _LIVE_MID_SEEN.get(ticker)
    if first is None or now - first[0] > window_s:
        _LIVE_MID_SEEN[ticker] = (now, mid)
        return 0.0
    return round(mid - first[1], 4)


def _candidate_priority_key(c: dict) -> tuple:
    """
    Computes a multi-tier sorting key ensuring that:
    1. Events scheduled for TODAY (ET) are prioritized (Tier 0).
    2. Soonest starting games come first within today's slate.
    3. Events scheduled for TOMORROW are secondary (Tier 1).
    4. Past / completed events are sorted to the end (Tier 999).
    Returns: (tier: int, start_time: float, -edge: float, -confidence: float)
    """
    now_et = datetime.now(ZoneInfo("America/New_York"))
    today_et = now_et.date()
    now_ts = now_et.timestamp()

    ep = c.get("start_epoch")
    ev_date = None
    ev_date_val = c.get("event_date") or c.get("date") or (c.get("metadata") or {}).get("date")
    if ev_date_val:
        try:
            if isinstance(ev_date_val, date):
                ev_date = ev_date_val
            elif isinstance(ev_date_val, str):
                clean_d = ev_date_val.split("T")[0].strip()
                parts = [int(p) for p in clean_d.split("-") if p.isdigit()]
                if len(parts) == 3:
                    ev_date = date(parts[0], parts[1], parts[2])
        except Exception:
            pass

    if ep is None or ev_date is None:
        tk = c.get("event_ticker") or c.get("ticker") or c.get("market_ticker") or ""
        meta = c.get("metadata") or {}
        ex_date, ex_epoch = extract_sports_event_date_and_time(tk, metadata=meta, event_obj=c)
        if ev_date is None and ex_date is not None:
            ev_date = ex_date
            c["event_date"] = str(ex_date)
        if ep is None and ex_epoch is not None:
            ep = float(ex_epoch)
            c["start_epoch"] = ep

    # If markets exist, check their expiration/close time for true date
    if (ep is None or ev_date is None) and c.get("markets"):
        for m in c["markets"]:
            exp = m.get("expected_expiration_time") or m.get("close_time")
            if exp and isinstance(exp, str):
                try:
                    dt = datetime.fromisoformat(exp.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
                    if ev_date is None:
                        ev_date = dt.date()
                        c["event_date"] = str(ev_date)
                    if ep is None:
                        ep = dt.timestamp()
                        c["start_epoch"] = ep
                    break
                except Exception:
                    pass

    # Check if event is within next 4 hours
    is_live = bool(c.get("is_live") or (ep is not None and ep <= now_ts and (now_ts - ep <= 14400)))
    is_within_4h = False
    if ep is not None and (0 <= (ep - now_ts) <= MAX_FUTURE_START_WINDOW_SECONDS):
        is_within_4h = True
    elif is_live:
        is_within_4h = True

    is_today = (ev_date == today_et) if ev_date is not None else bool(c.get("is_today"))
    c["is_today"] = is_today
    c["is_within_4h"] = is_within_4h

    # Past events check
    is_past = False
    if ev_date and ev_date < today_et and not is_live:
        is_past = True
    elif ep is not None and (now_ts - ep > 18000) and not is_live:
        is_past = True

    # Tier 0: Starts in next 4h or Live (imminent priority)
    # Tier 1: Scheduled > 4h away
    # Tier 999: Concluded / past
    tier = 999 if is_past else (0 if is_within_4h else 1)
    
    # Strategy Priority Ranking:
    # 0: FLOOR_TOTALS (Soccer O0.5, NHL O2.5) & MILESTONE_PROPS (Poisson 85-95% win prob)
    # 1: SPREAD / PUCK LINE / RUN LINE
    # 2: MONEYLINE / GAME (highest variance)
    strat_tag = str(c.get("strategy_tag") or "").upper()
    prop_type = str(c.get("market_type") or (c.get("metadata") or {}).get("type") or "").upper()
    title_str = str(c.get("title") or c.get("strike") or "").upper()
    
    if strat_tag in ("FLOOR_TOTALS", "MILESTONE_PROPS") or "TOTAL (O/U)" in prop_type or "OVER 0.5" in title_str or "OVER 2.5" in title_str or "1+" in title_str:
        strat_rank = 0
    elif "SPREAD" in prop_type or "PUCK LINE" in prop_type or "RUN LINE" in prop_type:
        strat_rank = 1
    else:
        strat_rank = 2

    start_time = float(ep) if ep is not None else 9999999999.0
    ai_p = c.get("ai_prediction") or {}
    conf = float(c.get("confidence_pct") or ai_p.get("confidence_pct") or 0.0)
    edge = float(c.get("edge_pct") or ai_p.get("edge_pct") or 0.0)

    return (tier, strat_rank, start_time, -edge, -conf)

class SportsBridgeExecutor:
    def __init__(self):
        self.client = SportsPredictionClient()
        self.last_check = 0
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=1)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    def settle_all_open_trades(self):
        """Immediately iterate through all active users and settle any concluded or resolved sports trades."""
        users = get_all_active_users() or []
        for u in users:
            try:
                self._settle_open_trades(u)
            except Exception as e:
                logger.error(f"[SportsBridge] Error settling open trades for user {u.get('id')}: {e}")

    def run_cycle(self):
        now = time.time()
        # Always run settlement check without throttling
        self.settle_all_open_trades()

        # No refresh cycle throttling - evaluate continuously on every cycle
        self.last_check = now

        users = get_all_active_users()

        # Strictly require trading_universe in ('SPORTS', 'BOTH', 'ALL') AND ai_enabled is True for auto-trading execution
        sports_users = [
            u for u in users
            if any(x in (u.get("trading_universe") or "").upper() for x in ("SPORTS", "BOTH", "ALL")) and bool(u.get("ai_enabled", 0))
        ]
        if not sports_users:
            return

        logger.info(f"[SportsBridge] Found {len(sports_users)} active auto-trading sports users. Gathering sports opportunities...")

        # Fast candidate gathering: query in-process cached events directly without self-HTTP roundtrips
        kalshi_today_events = []
        try:
            from backend.routes.engine_sports import fetch_sports_events_data
            kalshi_today_events = fetch_sports_events_data(query_filter="", user=None) or []
        except Exception as e:
            logger.debug(f"[SportsBridge] In-process fetch_sports_events_data fallback: {e}")

        picks = []
        if not kalshi_today_events:
            try:
                picks = self.client.fetch_latest_picks() or []
            except Exception as e:
                logger.debug(f"[SportsBridge] Could not fetch picks from client: {e}")

        # Combine candidates (giving priority to today's Kalshi events)
        all_candidates = list(kalshi_today_events)
        seen_keys = {(c.get("sport"), c.get("predicted_team"), c.get("ticker") or c.get("event_ticker")) for c in all_candidates}
        for p in picks:
            key = (p.get("sport"), p.get("predicted_team"), p.get("ticker") or p.get("event_ticker"))
            if key not in seen_keys:
                all_candidates.append(p)
                seen_keys.add(key)

        if not all_candidates:
            logger.info("[SportsBridge] No sports opportunities found for current cycle.")
            return

        now_ts = datetime.now(ZoneInfo("America/New_York")).timestamp()

        # Enforce strict 4-hour horizon limit for auto-trading:
        # Trade ONLY on the next 4 hours of events at a time to prevent placing trades
        # for tomorrow night and blocking up the queue and risk limits for games happening sooner.
        filtered_candidates = []
        for c in all_candidates:
            ok, reason = _is_event_within_start_window(
                c, now_ts, max_future_seconds=MAX_FUTURE_START_WINDOW_SECONDS, allow_live=True
            )
            if ok:
                filtered_candidates.append(c)
            else:
                logger.debug(f"[SportsBridge] Auto-trade pool excluding {c.get('ticker') or c.get('event_ticker')}: {reason}")

        all_candidates = filtered_candidates
        all_candidates.sort(key=_candidate_priority_key)
        
        # Forward live sports candidates into Quant Lab PaperIncubator
        try:
            from backend.engine.quant_lab.incubator import PaperIncubator
            incubator = PaperIncubator()
            for cand in all_candidates[:30]:
                c_sport = (cand.get("sport") or "SPORTS").upper()
                c_norm = _normalize_sport(c_sport)
                c_price = float(cand.get("market_ask") or cand.get("price") or 0.50)
                ai_p = cand.get("ai_prediction") or {}
                raw_feats = {
                    "ai_win_prob": float(cand.get("confidence_pct") or ai_p.get("confidence_pct") or 50.0),
                    "ai_edge": float(cand.get("edge_pct") or ai_p.get("edge_pct") or 0.0),
                    "confidence_score": float(cand.get("confidence_pct") or ai_p.get("confidence_pct") or 50.0),
                    "market_bid": float(cand.get("market_bid") or (c_price - 0.02)),
                    "market_ask": c_price,
                }
                try:
                    _bid = raw_feats["market_bid"]
                    _mid = round((_bid + c_price) / 2, 4)
                    raw_feats["market_mid"] = _mid
                    raw_feats["spread"] = round(c_price - _bid, 4)
                    raw_feats["price_drift"] = _live_price_drift(cand.get("ticker") or cand.get("event_ticker"), _mid)
                except Exception:
                    pass
                snap = {
                    "ticker": cand.get("ticker") or cand.get("event_ticker") or cand.get("kalshi_market_ticker"),
                    "cur_price": c_price,
                    "raw_features": raw_feats
                }
                # Check both normalized sport key and global 'SPORTS'
                for sp_key in {c_norm, c_sport, "SPORTS"}:
                    incubator.evaluate_snapshot(sp_key, snap)
        except Exception as inc_err:
            logger.debug(f"[SportsBridge] Incubator forward evaluation warning: {inc_err}")

        # Persistently log AI model predictions into Quant Lab sports_history
        try:
            from backend.engine.quant_lab.history_builder import record_sports_ai_prediction
            for cand in all_candidates[:50]:
                c_tk = cand.get("ticker") or cand.get("event_ticker") or cand.get("kalshi_market_ticker")
                if c_tk:
                    c_sp = (cand.get("sport") or "SPORTS").upper()
                    ai_p = cand.get("ai_prediction") or {}
                    c_prob = float(cand.get("confidence_pct") or ai_p.get("confidence_pct") or 50.0)
                    c_edge = float(cand.get("edge_pct") or ai_p.get("edge_pct") or 0.0)
                    c_nm = cand.get("predicted_team") or cand.get("name")
                    record_sports_ai_prediction(
                        ticker=str(c_tk),
                        sport=str(c_sp),
                        ai_win_prob=c_prob,
                        ai_edge=c_edge,
                        confidence_score=c_prob,
                        name=str(c_nm) if c_nm else None,
                    )
        except Exception as _re_err:
            logger.debug(f"[SportsBridge] Failed to record candidate predictions to quant lab: {_re_err}")

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

        from backend.engine.portfolio_governor import get_portfolio_governor
        governor = get_portfolio_governor()

        # Global Cross-Universe Circuit Breaker
        tripped, trip_reason = governor.check_global_circuit_breaker(user, mode=mode)
        if tripped:
            logger.warning(f"[SportsBridge] Global circuit breaker active for user {uid}: {trip_reason}. Skipping sports auto-trade.")
            return

        kt = None
        avail_live_cash = 0.0
        if mode == "LIVE":
            if USE_KALSHI_BRIDGE:
                avail_live_cash = 1000.0
                logger.info(f"[SportsBridge] Running in DRY-RUN mode for live user {uid} (simulated balance: ${avail_live_cash:.2f})")
            else:
                from backend.btc.kalshi_trader import get_authenticated_trader_for_user
                kt = get_authenticated_trader_for_user(user)
                if not kt or not kt.is_authenticated():
                    logger.warning(f"[SportsBridge] User {uid} is in LIVE mode but has no valid Kalshi credentials linked. Skipping auto-trade.")
                    return
                # High-performance non-blocking balance via Portfolio Governor
                avail_live_cash = governor.get_effective_available_balance(user, kt=kt, max_cache_age=8.0)
                if avail_live_cash <= 0.0:
                    logger.warning(f"[SportsBridge] User {uid} has zero or unverified available live cash. Skipping auto-trade.")
                    return
        elif mode != "PAPER":
            return

        # 1. Active leagues filter
        raw_leagues = user.get("sports_active_leagues") or 'NFL,MLB,NPB/KBO,SOC,UFC,TEN,NHL'
        active_leagues = {l.strip().upper() for l in raw_leagues.split(',') if l.strip()}

        # 2. Price corridor filter — EMPIRICAL FLOOR/CEILING ENFORCEMENT
        # Forensic trade audit shows: sports longshots (<35¢) = 12-17% WR (severe negative EV).
        # User DB setting respected, but clamped to empirically validated bounds.
        _user_min = float(user.get("sports_min_price") if user.get("sports_min_price") is not None else 0.46)
        _user_max = float(user.get("sports_max_price") if user.get("sports_max_price") is not None else 0.68)
        min_price = max(_user_min, 0.46)   # Hard floor: 0.46 — sub-46¢ = provably negative EV
        max_price = min(_user_max, 0.74)   # Hard ceiling: 0.74 — above = fee drag overwhelms wins

        # 3. Max daily sports wagers count and risk cap
        max_daily_trades = int(user.get("sports_max_daily_trades") if user.get("sports_max_daily_trades") is not None else 10)
        max_open_trades = int(user.get("sports_max_open_trades") if user.get("sports_max_open_trades") is not None else 15)
        max_daily_risk = float(user.get("sports_max_daily_risk") if user.get("sports_max_daily_risk") is not None else 100.0)

        try:
            self._reconcile_uncertain_sports_orders(user, kt)
        except Exception as rec_err:
            logger.error(f"[SportsBridge] Reconciling uncertain orders for user {uid} failed: {rec_err}")

        # 4. Kelly Criterion / edge-scaled sizing
        use_kelly = bool(user.get("sports_use_kelly", 0))

        # 5. Market types filter
        raw_market_types = user.get("sports_market_types") or 'GAME,SPREAD,TOTAL,PROP'
        allowed_market_types = {m.strip().upper() for m in raw_market_types.split(',') if m.strip()}

        # 6. Sports Betting Strategy & Parlay settings
        sports_strategy = str(user.get("sports_strategy") or "STANDARD").strip().upper()
        max_parlay_legs = int(user.get("sports_max_parlay_legs") or 2)

        from backend.database.trade_store import TradeStore
        all_open_trades = TradeStore.get_open_trades(uid)
        # Strictly isolate by user's current trading mode (LIVE vs PAPER)
        open_trades = [t for t in all_open_trades if (t.get("mode") or "PAPER").upper() == mode]
        open_tickers = {t.get("ticker") for t in open_trades if t.get("ticker")}
        
        # Enforce max open trades cap (only counting SPORTS trades in current mode)
        open_sports_count = sum(1 for t in open_trades if _is_sports_trade(t))
        if max_open_trades > 0 and open_sports_count >= max_open_trades:
            logger.info(f"[SportsBridge] User {uid} reached open {mode} sports trade limit ({open_sports_count}/{max_open_trades}). Skipping.")
            return

        # Evaluate rolling 24h trades for daily cap enforcement in current mode
        now_ts = time.time()
        day_ago = now_ts - 86400
        recent_trades = TradeStore.get_recent_trades(uid, limit=200)
        today_sports_trades = [
            t for t in recent_trades
            if _is_sports_trade(t)
            and (t.get("mode") or "PAPER").upper() == mode
            and _parse_trade_timestamp(t.get("timestamp")) >= day_ago
        ]
        daily_trades_count = len(today_sports_trades)
        daily_risk_spent = sum(float(t.get("cost") or t.get("trade_size_dollars") or 0.0) for t in today_sports_trades)

        traded_tickers = {t.get("ticker") for t in open_trades if t.get("ticker")}
        traded_tickers.update(t.get("ticker") for t in today_sports_trades if t.get("ticker"))

        if max_daily_trades > 0 and daily_trades_count >= max_daily_trades:
            logger.info(f"[SportsBridge] User {uid} reached daily {mode} sports trade limit ({daily_trades_count}/{max_daily_trades}). Skipping.")
            return

        if max_daily_risk > 0 and daily_risk_spent >= max_daily_risk:
            logger.info(f"[SportsBridge] User {uid} reached daily {mode} sports risk cap (${daily_risk_spent:.2f}/${max_daily_risk:.2f}). Skipping.")
            return


        sports_sport_config = None
        raw_sport_config = user.get("sports_sport_config")
        if raw_sport_config:
            try:
                sports_sport_config = json.loads(raw_sport_config)
            except Exception as e:
                logger.error(f"[SportsBridge] Failed to parse sports_sport_config for user {uid}: {e}")

        now_et = datetime.now(ZoneInfo("America/New_York"))
        today_et = now_et.date()
        now_ts = now_et.timestamp()

        # Enforce strict 4-hour horizon limit per user (honoring user's sports_include_live):
        user_picks = []
        for p in picks:
            ok, reason = _is_event_within_start_window(
                p, now_ts, max_future_seconds=MAX_FUTURE_START_WINDOW_SECONDS, allow_live=include_live
            )
            if ok:
                user_picks.append(p)
            else:
                p_meta = p.get("metadata") or {}
                p_label = p.get("ticker") or p.get("event_ticker") or p_meta.get("game_id") or p.get("predicted_team")
                logger.debug(f"[SportsBridge] User {uid} skipping {p_label}: {reason}")

        user_picks.sort(key=_candidate_priority_key)

        for pred in user_picks:
            if max_open_trades > 0 and open_sports_count >= max_open_trades:
                break
            if max_daily_trades > 0 and daily_trades_count >= max_daily_trades:
                break
            if max_daily_risk > 0 and daily_risk_spent >= max_daily_risk:
                break

            sport = (pred.get("sport") or "UNKNOWN").upper()
            norm_sport = _normalize_sport(sport)

            # Config Override
            current_allowed_markets = allowed_market_types
            current_allowed_props = None
            if sports_sport_config and norm_sport in sports_sport_config:
                sport_cfg = sports_sport_config[norm_sport]
                if not sport_cfg.get("on", False):
                    logger.debug(f"[SportsBridge] Skipping pick for user {uid}: sport {norm_sport} is turned off in per-sport config.")
                    continue
                current_allowed_markets = {m.strip().upper() for m in sport_cfg.get("markets", [])}
                current_allowed_props = {p.strip().upper() for p in sport_cfg.get("props", [])}
            else:
                # Fallback to global active leagues
                if norm_sport not in active_leagues and sport not in active_leagues:
                    continue

            ai_pred = pred.get("ai_prediction") or {}
            conf = float(pred.get("confidence_pct") or ai_pred.get("confidence_pct") or 0.0)
            meta = pred.get("metadata") or ai_pred.get("metadata") or {}
            is_upcoming = bool(meta.get("is_upcoming", True))
            status = str(pred.get("status") or "unknown").lower()

            # Veto simulation picks for auto-trader only if user explicitly opted out
            is_simulation_pick = (
                pred.get("ai_source") == "Simulation"
                or ai_pred.get("ai_source") == "Simulation"
                or meta.get("simulation") is True
                or pred.get("simulation") is True
                or meta.get("source") == "Simulation"
            )
            if is_simulation_pick and user.get("allow_simulation_trades") is False:
                logger.info(f"[SportsBridge] Skipping simulation pick for user {uid} on {pred.get('ticker') or pred.get('event_ticker')}: allow_simulation_trades is False")
                continue

            # Skip completed, past, postponed, suspended, or closed picks
            status_detail = str(meta.get("status_detail") or "").lower()
            if not is_upcoming or status in ("completed", "final", "closed", "ended", "post", "postponed", "canceled", "cancelled", "suspended") or any(w in status_detail for w in ("postponed", "canceled", "cancelled", "suspended", "rain delay")):
                continue

            # Secondary guard: Reject events scheduled for tomorrow or future dates
            pred_ev_ticker = pred.get("event_ticker") or pred.get("ticker") or pred.get("kalshi_market_ticker") or ""
            ev_date_val = pred.get("event_date") or pred.get("date") or meta.get("date")
            check_ev_date = None
            if ev_date_val:
                try:
                    if isinstance(ev_date_val, date):
                        check_ev_date = ev_date_val
                    elif isinstance(ev_date_val, str):
                        clean_d = ev_date_val.split("T")[0].strip()
                        parts = [int(p) for p in clean_d.split("-") if p.isdigit()]
                        if len(parts) == 3:
                            check_ev_date = date(parts[0], parts[1], parts[2])
                except Exception:
                    pass
            if check_ev_date is None and pred_ev_ticker:
                check_ev_date, _ = extract_sports_event_date_and_time(pred_ev_ticker, metadata=meta, event_obj=pred)
            if check_ev_date is not None and check_ev_date > today_et:
                logger.debug(f"[SportsBridge] User {uid} skipping {pred_ev_ticker}: scheduled for future date {check_ev_date} (horizon limit)")
                continue

            # Match only active, non-past Kalshi markets
            res = None
            ticker = pred.get("kalshi_market_ticker") or pred.get("market_ticker")

            # Check if ticker is a valid child market ticker or if we need to resolve it from the event
            is_valid_market_ticker = False
            if ticker and str(ticker).startswith("KX"):
                # Market tickers on Kalshi sports have at least 2 hyphens (Series-DateMatch-Outcome)
                # or end with -MKT / -YES / -NO
                if str(ticker).count("-") >= 2 or any(k in str(ticker) for k in ("-MKT", "-YES", "-NO")):
                    is_valid_market_ticker = True

            if not is_valid_market_ticker or pred.get("markets"):
                cand_tier = _candidate_priority_key(pred)[0]
                req_today = (cand_tier == 0) or (not bool(user.get("sports_include_live", 0)))
                res = _generate_kalshi_market(pred, require_today=req_today, max_horizon_seconds=MAX_FUTURE_START_WINDOW_SECONDS)
                if not res or not res[0]:
                    continue
                ticker, price, market_title = res[0], res[1], res[2]
                market_details = res[3] if len(res) > 3 and isinstance(res[3], dict) and res[3] else parse_sports_market_details(ticker or '', market_title or '', sport)
            else:
                raw_ask = float(pred.get("yes_ask_dollars") or pred.get("yes_ask") or 0.0)
                price = raw_ask / 100.0 if raw_ask > 1.0 else raw_ask
                market_title = pred.get("strike") or pred.get("title") or "Market"
                market_details = parse_sports_market_details(ticker or '', market_title or '', sport)

            if not ticker or not str(ticker).startswith("KX"):
                continue
            if ticker in traded_tickers:
                continue

            # --- PREVENT MARKET TYPE MISMATCHES ---
            m_prop_type = market_details.get("prop_type", "")
            pred_mtype = str(pred.get("market_type") or pred.get("metadata", {}).get("type") or "").upper()
            
            is_mismatch = False
            if m_prop_type in ("Player Prop", "PLAYER PROP") and not any(k in pred_mtype for k in ("PROP", "PLAYER")):
                is_mismatch = True
            elif m_prop_type == "Spread" and not any(k in pred_mtype for k in ("SPREAD", "PUCK LINE", "RUN LINE")):
                is_mismatch = True
            elif m_prop_type == "Total (O/U)" and not any(k in pred_mtype for k in ("TOTAL", "OVER", "UNDER", "O/U")):
                is_mismatch = True
            elif m_prop_type == "Moneyline" and any(k in pred_mtype for k in ("TOTAL", "SPREAD", "PROP", "OVER", "UNDER", "PUCK LINE", "RUN LINE", "PLAYER")):
                is_mismatch = True
                
            if is_mismatch:
                continue
            if m_prop_type == "Spread" and not any(k in pred_mtype for k in ("SPREAD", "PUCK LINE", "RUN LINE")):
                continue
            if m_prop_type == "Total (O/U)" and not any(k in pred_mtype for k in ("TOTAL", "OVER", "UNDER", "O/U")):
                continue

            # Enforce user sports strategy alignment
            strat_tag = str(pred.get("strategy_tag") or "").upper()
            if sports_strategy == "FLOOR_TOTALS":
                if m_prop_type != "Total (O/U)" and strat_tag != "FLOOR_TOTALS":
                    continue
            elif sports_strategy == "MILESTONE_PROPS":
                if m_prop_type not in ("Player Prop", "PLAYER PROP") and strat_tag != "MILESTONE_PROPS":
                    continue
            elif sports_strategy == "STANDARD":
                if m_prop_type not in ("Moneyline", "Spread") and not any(k in pred_mtype for k in ("GAME", "MONEYLINE", "SPREAD", "PUCK LINE", "RUN LINE")):
                    continue

            # --- PURE AI EDGE OVERRIDE ---
            # If the bridge lost its Vegas odds source, we calculate the Edge natively
            # here by comparing the AI's pure confidence directly against Kalshi's implied probability.
            kalshi_implied_prob = price * 100.0
            edge = round(conf - kalshi_implied_prob, 1)
            model_edge = float(pred.get("edge_pct") or ai_pred.get("edge_pct") or 0.0)
            if model_edge > 0.0:
                edge = model_edge
            
            # --- MASTER SPORTS CAPPER EVALUATION ---
            pick_team_name = str(pred.get("predicted_team") or pred.get("team") or pred.get("pick") or ai_pred.get("predicted_team") or "").strip()
            from backend.sports_engine.master_capper import MasterSportsCapper
            capper_eval = MasterSportsCapper.evaluate_capper_edge(
                sport=sport,
                matchup=market_title or pred.get("opponent", ""),
                pick_name=pick_team_name,
                market_type=m_prop_type or "Moneyline",
                model_win_prob=conf,
                kalshi_price_dollars=price,
                situational_factors=meta.get("factor_impacts", {}),
                bankroll=float(user.get("paper_balance") if (mode == "PAPER" and user.get("paper_balance") is not None) else (avail_live_cash if mode != "PAPER" else 1000.0))
            )
            net_ev_dollars = capper_eval.get("net_ev_dollars", 0.0)
            net_ev_pct = capper_eval.get("net_ev_pct", 0.0)
            capper_grade = capper_eval.get("grade", "B")
            capper_stars = capper_eval.get("stars", "⭐⭐⭐")
            capper_thesis = capper_eval.get("capper_thesis", "")

            # Capital Guard: Veto any negative net EV trade after Kalshi fees in both PAPER and LIVE modes
            if net_ev_dollars <= 0.0:
                logger.info(f"[SportsBridge] Capital Guard Veto on {ticker} ({mode}): Sub-threshold Net EV (${net_ev_dollars:.4f}) after Kalshi fees. Skipping.")
                continue

            # --- VEGAS CONSENSUS VETO ---
            if pick_team_name and _check_vegas_veto_safe(sport, pick_team_name, conf):
                logger.info(f"[SportsBridge] Skipping {ticker} ({mode}): Vetoed by Vegas Consensus Sharp Money Check.")
                continue

            if meta.get("is_live") and meta.get("pick_is_prematch"):
                logger.info(f"[SportsBridge] Skipping {ticker}: Event is live but pick is pre-match")
                continue

            if conf < min_conf or edge < min_edge:
                logger.debug(
                    f"[SportsBridge] Skipping {ticker} ({mode}): conf={conf:.1f}% (min {min_conf:.1f}%), edge={edge:.1f}% (min {min_edge:.1f}%)"
                )
                continue

            # Double-check scheduled date and start time with live event markets
            ev_date, start_epoch = extract_sports_event_date_and_time(ticker, metadata=meta, event_obj=pred)
            if start_epoch is not None:
                # Strictly enforce 4-hour start window limit:
                if (start_epoch - now_ts) > MAX_FUTURE_START_WINDOW_SECONDS:
                    logger.info(f"[SportsBridge] Skipping {ticker}: starts in {(start_epoch - now_ts)/3600:.1f}h (> 4.0h auto-trade horizon limit)")
                    continue
                if start_epoch < (now_ts - 300) and not include_live:
                    logger.info(f"[SportsBridge] Skipping {ticker}: event already started at {start_epoch} (include_live=False)")
                    continue
                if start_epoch < (now_ts - 14400):
                    logger.info(f"[SportsBridge] Skipping {ticker}: event started > 4 hours ago, already finished")
                    continue
            else:
                # If start_epoch is unknown, cannot verify it starts within 4 hours
                logger.info(f"[SportsBridge] Skipping {ticker}: start_epoch unknown, cannot verify within 4h window")
                continue

            # Price corridor check & strategy price cap
            strat_tag = str(pred.get("strategy_tag") or "").upper()
            is_floor_strategy = (sports_strategy in ("FLOOR_TOTALS", "POWER_COMBO", "ALL_ACTIVE") or strat_tag in ("FLOOR_TOTALS", "MILESTONE_PROPS"))
            effective_max_price = min(0.96, max(max_price, 0.96)) if is_floor_strategy else max_price
            if not (min_price <= price <= effective_max_price):
                logger.debug(f"[SportsBridge] Skipping {ticker}: price {price:.2f} outside corridor [{min_price:.2f}, {effective_max_price:.2f}]")
                continue

            # Hard safety price cap: Never pay above 0.96 (ensures positive EV after Kalshi fees)
            if price > 0.96:
                logger.info(f"[SportsBridge] Skipping {ticker}: price {price:.2f} exceeds 0.96 EV safety cap")
                continue

            # Price sanity & liquidity guard
            # Skip any market where yes_ask + no_ask < 0.9 or either price <= 0.01, unless it's a real longshot with a bid behind it.
            cached_mkt = None
            try:
                from backend.engine.kalshi_market_cache import get_market_cache_instance, USE_MARKET_CACHE
                if USE_MARKET_CACHE:
                    cached_mkt = get_market_cache_instance().get_market(ticker)
            except Exception:
                pass

            m_yes_ask = price
            m_no_ask = 0.0
            m_yes_bid = 0.0
            m_no_bid = 0.0
            if cached_mkt:
                m_yes_ask = float(cached_mkt.get("yes_ask") or price)
                m_no_ask = float(cached_mkt.get("no_ask") or 0.0)
                m_yes_bid = float(cached_mkt.get("yes_bid") or 0.0)
                m_no_bid = float(cached_mkt.get("no_bid") or 0.0)
                pick_side = pred.get("final_pick_side", "yes").lower()
                if pick_side == "no":
                    live_ask = m_no_ask if m_no_ask > 0.0 else (round(1.0 - m_yes_bid, 4) if m_yes_bid > 0.0 else 0.0)
                else:
                    live_ask = m_yes_ask if m_yes_ask > 0.0 else (round(1.0 - m_no_bid, 4) if m_no_bid > 0.0 else 0.0)
                if live_ask > 0.0:
                    price = live_ask
            elif pred:
                raw_ya = float(pred.get("yes_ask_dollars") or pred.get("yes_ask") or 0.0)
                raw_na = float(pred.get("no_ask_dollars") or pred.get("no_ask") or 0.0)
                m_yes_ask = (raw_ya / 100.0 if raw_ya > 1.0 else raw_ya) if raw_ya > 0.0 else price
                m_no_ask = (raw_na / 100.0 if raw_na > 1.0 else raw_na) if raw_na > 0.0 else (round(1.0 - price, 4) if price > 0.0 else 0.0)
                raw_yb = float(pred.get("yes_bid_dollars") or pred.get("yes_bid") or 0.0)
                raw_nb = float(pred.get("no_bid_dollars") or pred.get("no_bid") or 0.0)
                m_yes_bid = (raw_yb / 100.0 if raw_yb > 1.0 else raw_yb) if raw_yb > 0.0 else max(0.0, round(price - 0.02, 4))
                m_no_bid = (raw_nb / 100.0 if raw_nb > 1.0 else raw_nb) if raw_nb > 0.0 else max(0.0, round(1.0 - price - 0.02, 4))

            if m_yes_ask > 0 and m_no_ask > 0 and (m_yes_ask + m_no_ask < 0.90):
                logger.warning(f"[SportsBridge] Skipping {ticker}: Unhealthy market book sum (yes_ask={m_yes_ask:.4f}, no_ask={m_no_ask:.4f}) < 0.90")
                continue
            if (m_yes_ask <= 0.01 and m_yes_bid <= 0.0 and m_no_ask <= 0.01 and m_no_bid <= 0.0):
                logger.warning(f"[SportsBridge] Skipping {ticker}: Illiquid zero-bid extreme price (yes_ask={m_yes_ask}, yes_bid={m_yes_bid}, no_ask={m_no_ask}, no_bid={m_no_bid})")
                continue

            # Market type check (GAME, SPREAD, TOTAL, PROP)
            upper_tk = ticker.upper()
            upper_mt = market_title.upper()

            # Picks are full-game predictions. A 1st-period / first-5-innings / futures / derivative market is a
            # different bet, so the game confidence says nothing about it: skip.
            if (market_details.get("prop_type") in ("Period", "Futures", "Special") or market_details.get("segment")
                    or any(k in upper_tk for k in ("KXNHL1P", "KXNHL2P", "KXNHL3P", "KXNHLF10G", "KXNHLOT", "KXNHLTEAMTOTAL", "KXMLBF5", "KXNFLWINS"))):
                logger.info(f"[SportsBridge] Skipping {ticker}: part-of-game/futures/derivative market, no model for it (full-game pick {pred.get('predicted_team')})")
                continue

            m_type = "GAME"
            if market_details.get("prop_type") in ("Player Prop", "Special", "Period") or any(p in upper_tk for p in ("KXNHLGOAL", "KXNHLSHOT", "KXNHLF10G", "KXNHLOT", "KXMLBHRR", "KXMLBHIT", "KXMLBHR", "KXMLBKS", "KXMLBRBI", "KXMLBTB", "KXNFLTD", "PROP", "HRR")):
                m_type = "PROP"
            elif "SPREAD" in upper_tk or "SPREAD" in upper_mt:
                m_type = "SPREAD"
            elif any(w in upper_tk or w in upper_mt for w in ("TOTAL", "OVER", "UNDER", "O/U")):
                m_type = "TOTAL"

            pred_mtype = str(pred.get("market_type") or (pred.get("metadata") or {}).get("type") or "").upper()
            if not pred_mtype:
                pred_mtype = "GAME"
            if m_type == "SPREAD" and not any(k in pred_mtype for k in ("SPREAD", "PUCK LINE", "RUN LINE")):
                logger.info(f"[SportsBridge] Skipping {ticker}: spread market but pick is {pred_mtype}")
                continue
            if m_type == "TOTAL" and not any(k in pred_mtype for k in ("TOTAL", "OVER", "UNDER", "O/U")):
                logger.info(f"[SportsBridge] Skipping {ticker}: total market but pick is {pred_mtype}")
                continue
            if m_type == "PROP" and not any(k in pred_mtype for k in ("PROP", "PLAYER")):
                logger.info(f"[SportsBridge] Skipping {ticker}: prop market but pick is {pred_mtype}")
                continue
            if m_type == "GAME" and not any(k in pred_mtype for k in ("MONEYLINE", "MONEY LINE", "GAME", "WINNER")):
                logger.info(f"[SportsBridge] Skipping {ticker}: GAME market but pick is {pred_mtype}")
                continue

            if current_allowed_props is None:
                raw_active_props = user.get("sports_active_props") or "ANYTIME_TD,PASSING_YDS,RUSHING_YDS,RECEIVING_YDS,HOME_RUNS,STRIKEOUTS,HITS_RUNS_RBIS,TOTAL_BASES,OTHER"
                current_allowed_props = {p.strip().upper() for p in raw_active_props.split(',') if p.strip()}

            is_prop_allowed = m_type == "PROP" and any(p in current_allowed_markets for p in ("PROP", "PLAYER_PROP", "PROPS"))
            
            # If it is a prop, check if the specific prop type is enabled
            if is_prop_allowed:
                stat_name = str(market_details.get("stat_name") or market_details.get("prop_type") or "").upper()
                combined_mkt = f"{upper_tk} {upper_mt} {stat_name}"
                prop_category = "OTHER"
                # NFL
                if "FIRST TD" in combined_mkt or "FIRST TOUCHDOWN" in combined_mkt or "FIRSTTD" in upper_tk: prop_category = "FIRST_TD"
                elif "ANYTIME TD" in combined_mkt or "TOUCHDOWN" in combined_mkt or "KXNFLTD" in upper_tk: prop_category = "ANYTIME_TD"
                elif "PASSING" in combined_mkt or "KXNFLPASS" in upper_tk: prop_category = "PASSING_YDS"
                elif "RUSHING" in combined_mkt or "KXNFLRSH" in upper_tk: prop_category = "RUSHING_YDS"
                elif "RECEPTION" in combined_mkt or "KXNFLREC" in upper_tk and "RECYDS" not in upper_tk: prop_category = "RECEPTIONS"
                elif "RECEIVING" in combined_mkt or "KXNFLRECYDS" in upper_tk: prop_category = "RECEIVING_YDS"
                # MLB
                elif "HOME RUN" in combined_mkt or "HR" in stat_name or "KXMLBHR" in upper_tk: prop_category = "HOME_RUNS"
                elif "STRIKEOUT" in combined_mkt or "KXMLBKS" in upper_tk: prop_category = "STRIKEOUTS"
                elif "HIT" in stat_name and "RUN" in stat_name and "RBI" in stat_name or "HRR" in upper_tk: prop_category = "HITS_RUNS_RBIS"
                elif "TOTAL BASES" in combined_mkt or "TB" in stat_name or "KXMLBTB" in upper_tk: prop_category = "TOTAL_BASES"
                elif "KXMLBHIT" in upper_tk or " 1+ HITS" in combined_mkt: prop_category = "HITS"
                elif "KXMLBRBI" in upper_tk or " 1+ RBIS" in combined_mkt: prop_category = "RBIS"
                # NHL
                elif "FIRST GOAL" in combined_mkt or "FIRSTGOAL" in upper_tk: prop_category = "FIRST_GOAL"
                elif "KXNHLGOAL" in upper_tk or "GOAL" in stat_name: prop_category = "GOAL"
                elif "KXNHLPTS" in upper_tk or "POINTS" in stat_name: prop_category = "POINTS"
                elif "KXNHLAST" in upper_tk or "ASSIST" in stat_name: prop_category = "ASSISTS"
                elif "KXNHLSAVE" in upper_tk or "SAVE" in combined_mkt: prop_category = "SAVES"
                # Soccer
                elif "BTTS" in upper_tk or "BOTH TEAMS TO SCORE" in combined_mkt: prop_category = "BTTS"
                elif "CORNER" in upper_tk or "CORNERS" in combined_mkt: prop_category = "CORNERS"
                elif "FTTS" in upper_tk or "FIRST GOAL OF THE GAME" in combined_mkt: prop_category = "FTTS"
                elif "SCORE" in upper_tk or "FINAL SCORE" in combined_mkt: prop_category = "CORRECT_SCORE"
                # UFC
                elif "DISTANCE" in upper_tk or "DISTANCE" in combined_mkt: prop_category = "DISTANCE"
                elif "MOF" in upper_tk or "MOV" in upper_tk or any(k in combined_mkt for k in ("METHOD", "DECISION", "SUBMISSION", "KO", "TKO")): prop_category = "METHOD_OF_FINISH"
                elif "VICROUND" in upper_tk or "ROUND " in combined_mkt: prop_category = "ROUND_PROPS"
                # NBA
                elif "KXNBAPTS" in upper_tk or "POINTS" in stat_name: prop_category = "POINTS"
                elif "KXNBAREB" in upper_tk or "REBOUND" in stat_name: prop_category = "REBOUNDS"
                elif "KXNBAAST" in upper_tk or "ASSIST" in stat_name: prop_category = "ASSISTS"
                elif "THREE" in combined_mkt or "3PT" in upper_tk: prop_category = "THREES"
                elif "BLK" in upper_tk or "STL" in upper_tk or "BLOCK" in combined_mkt or "STEAL" in combined_mkt: prop_category = "BLOCKS_STEALS"
                
                if prop_category not in current_allowed_props:
                    logger.info(f"[SportsBridge] User {uid}: Skipping {ticker} per-sport rule: prop type {prop_category} not in {current_allowed_props}")
                    continue

            if m_type not in current_allowed_markets and not is_prop_allowed:
                logger.info(f"[SportsBridge] User {uid}: Skipping {ticker} per-sport rule: market type {m_type} not in {current_allowed_markets}")
                continue

            # Max wager safeguard from user settings
            max_wager_setting = float(user.get("sports_max_wager") or user.get("sports_trade_size_dollars") or 10.0)

            # Minimum edge safeguard for LIVE auto-trading (require at least 1.0% edge)
            if mode == "LIVE" and edge < max(min_edge, 1.0):
                continue

            if ticker not in traded_tickers:
                predicted_team = pred.get("predicted_team", "UNKNOWN")

                # Kelly Criterion Sizing calculation
                if use_kelly:
                    # Dynamically scales wager: e.g. 5% edge is standard 1.0x, range 0.3x to 1.2x
                    if mode == "PAPER" and edge <= 0:
                        wager = base_wager
                    else:
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
                count, worst_cost = _size_sports_order(wager, price)
                if count < 1:
                    continue
                cost = round(price * count + kalshi_order_fee(price, count), 2)

                order_id = trade_id
                fill_price = price
                fill_count = count
                actual_cost = cost

                if mode == "LIVE":
                    # Strictly require real Kalshi market ticker for live trades
                    if not ticker.startswith("KX") or ticker.endswith("-MKT") or ticker.startswith("KALSHI-"):
                        logger.debug(f"[SportsBridge] Skipping non-real Kalshi ticker {ticker} for live user {uid}")
                        continue

                    if avail_live_cash < worst_cost:
                        logger.warning(f"[SportsBridge] User {uid} has insufficient live balance (${avail_live_cash:.2f}) for ${worst_cost:.2f} sports trade on {ticker}")
                        continue

                    intent_key = order_intents.account_key_for_user(uid)
                    intent_ticker = _sports_intent_ticker(ticker)
                    if not order_intents.claim(intent_key, intent_ticker, pred.get("final_pick_side", "yes").lower()):
                        continue

                    # Reserve capital across universes
                    res_id = f"sports_res_{uid}_{ticker}_{uuid.uuid4().hex[:6]}"
                    governor.reserve_capital(uid, worst_cost, "SPORTS", ticker, res_id)

                    if USE_KALSHI_BRIDGE:
                        source_label = pred.get("ai_source") or ai_pred.get("ai_source") or "Sports AI"
                        logger.info(f"[DRY RUN - USE_KALSHI_BRIDGE] Would trade: user={uid} ticker={ticker} side={pred.get('final_pick_side', 'yes').lower()} pick_source={source_label} model_prob={conf:.1f}% price={price:.2f} edge={edge:.1f}% count={count} cost=${cost:.2f}")
                        open_tickers.add(ticker)
                        open_sports_count += 1
                        daily_trades_count += 1
                        daily_risk_spent += worst_cost
                        avail_live_cash -= worst_cost
                        governor.release_capital(res_id, actual_deducted_cost=worst_cost, user_id=uid)
                        continue

                    try:
                        order_res = kt.place_sports_order(
                            ticker=ticker,
                            side=pred.get("final_pick_side", "yes").lower(),
                            count=count,
                            limit_price_dollars=price,
                            dry_run=False,
                            slippage_buffer_dollars=0.04
                        )
                    except Exception as _pl_err:
                        governor.release_capital(res_id, actual_deducted_cost=0.0, user_id=uid)
                        raise _pl_err

                    outcome = order_intents.settle_outcome(intent_key, intent_ticker, order_res)
                    if not order_res.get("success"):
                        if outcome == "ambiguous":
                            logger.error(f"[SportsBridge] LIVE order outcome UNKNOWN for user {uid} on {ticker}. Not retrying; will reconcile.")
                            open_tickers.add(ticker)
                            open_sports_count += 1
                            daily_trades_count += 1
                            daily_risk_spent += worst_cost
                            avail_live_cash -= worst_cost
                            governor.release_capital(res_id, actual_deducted_cost=worst_cost, user_id=uid)
                        else:
                            logger.warning(f"[SportsBridge] Live order failed for user {uid} on {ticker}: {order_res.get('error')}")
                            governor.release_capital(res_id, actual_deducted_cost=0.0, user_id=uid)
                        continue

                    order_id = str(order_res.get("order_id") or order_res.get("client_order_id") or trade_id)
                    fill_price = float(order_res.get("filled_price") or price)
                    fill_count = int(float(order_res.get("count") or count))
                    actual_cost = round(fill_price * fill_count + kalshi_order_fee(fill_price, fill_count), 2)
                    avail_live_cash -= actual_cost
                    governor.release_capital(res_id, actual_deducted_cost=actual_cost, user_id=uid)
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
                    "reason": f"[{capper_grade} {capper_stars}] [{prop_type_val}] {line_val} | AI Edge: {predicted_team} (Conf: {conf:.1f}%, Edge: {edge:.1f}%, Net EV: {net_ev_pct:+.1f}%)",
                    "trading_style": "SPORTS_AI",
                    "signal_source": "Native Master Sports Capper",
                    "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "ml_reasoning": json.dumps({
                        "confidence": conf,
                        "edge": edge,
                        "net_ev_pct": net_ev_pct,
                        "capper_grade": capper_grade,
                        "capper_stars": capper_stars,
                        "capper_thesis": capper_thesis,
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
                        f"Master Capper: {capper_grade} {capper_stars}",
                        f"Net EV: {net_ev_pct:+.1f}% | Edge: {edge:.1f}%"
                    ]
                }
                _raw = dict(trade_dict)
                _raw["market_snapshot"] = {"indicators": {
                    "ai_win_prob": float(conf),
                    "ai_edge": float(edge),
                    "confidence_score": float(conf),
                    "market_bid": max(0.01, float(fill_price) - 0.02),
                    "market_ask": float(fill_price),
                }}
                trade_dict["raw_json"] = json.dumps(_raw)
                TradeStore.insert_trade(uid, trade_dict)
                traded_tickers.add(ticker)
                daily_trades_count += 1
                daily_risk_spent += actual_cost
                open_sports_count += 1


    def _reconcile_uncertain_sports_orders(self, user, kt):
        from backend.database.trade_store import TradeStore
        import json
        import uuid
        from datetime import datetime
        from zoneinfo import ZoneInfo
        import time

        uid = user["id"]
        key = order_intents.account_key_for_user(uid)
        pending = order_intents.list_unresolved(key, prefix=SPORTS_INTENT_PREFIX, min_age_seconds=UNRESOLVED_MIN_AGE_SECONDS)
        if not pending or not kt:
            return
        pos_res = kt.get_positions()
        if not pos_res or not pos_res.get("success"):
            return
        positions = {}
        for p in pos_res.get("positions", []) or []:
            if isinstance(p, dict):
                tk = str(p.get("ticker") or p.get("market_ticker") or "").strip()
                if tk:
                    positions[tk] = p
        known = {t.get("ticker") for t in TradeStore.get_open_trades(uid)}
        now = time.time()
        for row in pending:
            intent_ticker = row["ticker"]
            ticker = intent_ticker[len(SPORTS_INTENT_PREFIX):]
            held = kt._extract_side_position(positions.get(ticker, {}), "YES")
            if held > 0:
                if ticker not in known:
                    from backend.saas_settler import _position_avg_price
                    avg = _position_avg_price(positions[ticker], held)
                    if avg is None:
                        logger.error(f"[SportsBridge] User {uid}: found {held} YES on {ticker} from uncertain order, missing avg price. MANUAL VERIFICATION REQUIRED.")
                        continue
                    count = int(held)
                    trade_id = str(row.get("client_order_id") or f"sports_reconciled_{uuid.uuid4().hex[:8]}")
                    rec = {
                        "id": trade_id, "order_id": trade_id, "client_order_id": trade_id,
                        "user_id": uid, "ticker": ticker, "side": "YES", "direction": "YES",
                        "entry_price": avg, "count": count,
                        "cost": round(avg * count + kalshi_order_fee(avg, count), 2),
                        "pnl": 0.0, "status": "OPEN", "mode": "LIVE",
                        "trading_style": "SPORTS_AI", "signal_source": "Sports AI Bot Bridge",
                        "reason": "SPORTS_AI (reconciled after lost order response)",
                        "reconciled_from_ambiguous": True,
                        "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    }
                    rec["raw_json"] = json.dumps(rec)
                    TradeStore.insert_trade(uid, rec)
                    logger.warning(f"[SportsBridge] User {uid}: recorded {count} YES on {ticker} @ ${avg:.2f} from lost order.")
                order_intents.mark(key, intent_ticker, "filled_reconciled")
            elif now - float(row.get("created_at") or now) > UNRESOLVED_GIVE_UP_SECONDS:
                order_intents.mark(key, intent_ticker, "no_fill_found")
                logger.info(f"[SportsBridge] User {uid}: uncertain order on {ticker} never showed a position; treating as unfilled.")

    def _settle_open_trades(self, user):
        from backend.database.trade_store import TradeStore
        uid = user["id"]
        open_trades = TradeStore.get_open_trades(uid)
        if not open_trades:
            return

        tp_enabled = bool(user.get("sports_tp_enabled", 0))
        tp_pct = float(user.get("sports_tp_pct") if user.get("sports_tp_pct") is not None else 35.0)
        user_mode = (user.get("trading_mode") or "PAPER").upper()

        # If user is in LIVE mode or has Kalshi credentials, fetch positions and settlements
        kt = None
        kalshi_positions = {}
        kalshi_positions_loaded = False
        kalshi_settlements = {}
        if user_mode == "LIVE" or user.get("kalshi_key_id"):
            try:
                from backend.btc.kalshi_trader import get_authenticated_trader_for_user
                kt = get_authenticated_trader_for_user(user)
                if kt and kt.is_authenticated():
                    pos_resp = kt.get_positions(fail_fast=True)
                    if pos_resp.get("success") and isinstance(pos_resp.get("positions"), list):
                        kalshi_positions_loaded = True
                        for p in pos_resp.get("positions", []) or []:
                            tk = str(p.get("ticker") or p.get("market_ticker") or "").strip()
                            if tk:
                                kalshi_positions[tk] = p

                    settle_resp = kt.get_settlements(limit=100, fail_fast=True)
                    if settle_resp.get("success"):
                        for s in settle_resp.get("settlements", []) or []:
                            tk = str(s.get("ticker") or "").strip()
                            ev_tk = str(s.get("event_ticker") or "").strip()
                            if tk:
                                kalshi_settlements[tk] = s
                            if ev_tk and ev_tk not in kalshi_settlements:
                                kalshi_settlements[ev_tk] = s
            except Exception as e:
                logger.debug(f"[SportsBridge] Error fetching live portfolio state for user {uid}: {e}")

        for t in open_trades:
            ticker = t.get("ticker") or ""
            t_id = t.get("id")
            if not ticker:
                continue
            if not _is_sports_trade(t):
                continue

            t_mode = (t.get("mode") or "PAPER").upper()
            team_hint = str(t.get("team") or t.get("predicted_team") or "")
            entry_price = float(t.get("entry_price") or 0.5)
            contracts = float(t.get("count") or 1.0)

            # --- A. LIVE POSITION RECONCILIATION ---
            # If the user held this trade live on Kalshi, check if Kalshi already settled or closed it
            if t_mode == "LIVE" and kt and kalshi_positions_loaded:
                # 1. Did Kalshi officially settle this contract?
                s_record = kalshi_settlements.get(ticker)
                if not s_record and ticker.count("-") == 1:
                    # Check if event was settled
                    s_record = kalshi_settlements.get(ticker)

                if s_record:
                    m_res = str(s_record.get("market_result") or "").strip().upper()
                    side = str(t.get("side") or "YES").strip().upper()
                    is_win = (m_res == side)
                    rev = float(s_record.get("revenue") or 0.0) / 100.0 if s_record.get("revenue") is not None else (contracts * 1.0 if is_win else 0.0)
                    exit_price = 1.0 if is_win else 0.0
                    pnl = net_pnl(entry_price, exit_price, contracts)

                    closed_ok = TradeStore.close_if_open(uid, t, {
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "exit_reason": "SETTLEMENT",
                        "settled_at": time.time()
                    })
                    if closed_ok:
                        logger.info(f"[SportsBridge] Auto-settled LIVE trade {t_id} on {ticker} via Kalshi portfolio settlement (Result: {m_res}, PnL: ${pnl:.2f})")
                        continue

                # 2. Is this position no longer held on Kalshi (quantity == 0 or purged from positions)?
                held_qty = 0.0
                has_position_record = (ticker in kalshi_positions)
                if has_position_record:
                    p_entry = kalshi_positions[ticker]
                    held_qty = kt._extract_side_position(p_entry, t.get("side", "YES"))

                trade_age = time.time() - _parse_trade_timestamp(t.get("timestamp"))
                if held_qty <= 0.001 and (has_position_record or trade_age > 60):
                    # Check resting orders to make sure it's not waiting to fill
                    is_resting = False
                    try:
                        orders_resp = kt.get_orders(status="resting", ticker=ticker, fail_fast=True)
                        if orders_resp.get("success") and orders_resp.get("orders"):
                            is_resting = True
                    except Exception:
                        pass

                    if not is_resting:
                        # Position is flat on Kalshi! Check recent fills for exit price
                        exit_price = entry_price
                        try:
                            fills_resp = kt.get_fills(ticker=ticker, limit=20, fail_fast=True)
                            if fills_resp.get("success"):
                                for f in fills_resp.get("fills", []):
                                    if f.get("action") == "sell":
                                        p = float(f.get("yes_price_dollars") or f.get("price") or 0.0)
                                        if p > 0:
                                            exit_price = p
                                            break
                        except Exception:
                            pass

                        if exit_price == entry_price:
                            m_settle = _check_kalshi_settlement(ticker, team_hint=team_hint, user=user)
                            m_stat = str(m_settle.get("status") or "").lower()
                            if m_stat in ("determined", "settled", "closed", "finalized"):
                                res = str(m_settle.get("result") or "").strip().upper()
                                exit_price = 1.0 if res == str(t.get("side") or "YES").strip().upper() else 0.0

                        pnl = net_pnl(entry_price, exit_price, contracts)
                        closed_ok = TradeStore.close_if_open(uid, t, {
                            "exit_price": exit_price,
                            "pnl": pnl,
                            "exit_reason": "KALSHI_POSITION_RECONCILED",
                            "settled_at": time.time()
                        })
                        if closed_ok:
                            logger.info(f"[SportsBridge] Auto-reconciled flat Kalshi LIVE position for trade {t_id} ({ticker}, Exit: ${exit_price:.2f}, PnL: ${pnl:.2f})")
                            continue

            # --- B. KALSHI MARKET & EVENT SETTLEMENT QUERY ---
            settlement = _check_kalshi_settlement(ticker, team_hint=team_hint, user=user)
            status = str(settlement.get("status") or "").lower()

            # Handle Voided / Canceled / Walkover events
            if status in ("voided", "canceled", "cancelled"):
                cost = float(t.get("cost") or t.get("trade_size_dollars") or (entry_price * contracts))
                closed_ok = TradeStore.close_if_open(uid, t, {
                    "exit_price": entry_price,
                    "pnl": 0.0,
                    "exit_reason": "VOIDED_MATCH_CANCELED",
                    "settled_at": time.time()
                })
                if closed_ok:
                    if t_mode == "PAPER" and cost > 0:
                        credit_user_paper_balance(uid, cost)
                    logger.info(f"[SportsBridge] Refunded and closed voided/canceled sports trade {t_id} on {ticker}")
                    continue

            # 1. Check for Mid-Game Early Take-Profit if position is still open
            if status not in ("determined", "settled", "closed", "finalized"):
                cur_price = float(settlement.get("cur_price") or 0.0)
                if cur_price > entry_price:
                    gain_pct = ((cur_price - entry_price) / max(entry_price, 0.01)) * 100.0
                    
                    # Force auto-cashout at 99c to free queue, or if user's manual TP is hit
                    if cur_price >= 0.99 or (tp_enabled and gain_pct >= tp_pct):
                        pnl = round((cur_price - entry_price) * contracts, 2)
                        payout = round(cur_price * contracts, 2)
                        if t_mode == "LIVE":
                            if kt:
                                close_res = kt.close_position(
                                    ticker,
                                    purchased_side=t.get("side", "yes").lower(),
                                    count=contracts,
                                    dry_run=False,
                                    estimated_exit_price=cur_price
                                )
                                if not close_res.get("success"):
                                    if "Not enough positions" in str(close_res.get("error", "")):
                                        logger.info(f"[SportsBridge] Position on {ticker} already closed or not held on Kalshi.")
                                    else:
                                        logger.warning(f"[SportsBridge] Live TP close failed for {t_id}: {close_res.get('error')}")
                                        continue
                                cur_price = float(close_res.get("exit_price") or cur_price)
                            else:
                                continue

                            pnl = net_pnl(entry_price, cur_price, contracts)
                            payout = round(cur_price * contracts, 2)

                        closed_ok = TradeStore.close_if_open(uid, t, {
                            "exit_price": cur_price,
                            "pnl": pnl,
                            "exit_reason": f"TAKE_PROFIT (+{gain_pct:.1f}%)",
                            "settled_at": time.time()
                        })
                        if not closed_ok:
                            continue

                        if t_mode == "PAPER" and payout > 0:
                            credit_user_paper_balance(uid, payout - kalshi_order_fee(cur_price, contracts))
                        logger.info(f"[SportsBridge] Mid-game Take-Profit triggered for {t_id} ({t_mode}) at {cur_price:.2f} (+{gain_pct:.1f}% gain, PnL: ${pnl:.2f})")
                        continue

            # 2. Check for Final Settlement (Win/Loss)
            if status in ("determined", "settled", "closed", "finalized"):
                result = str(settlement.get("result") or "").strip().upper()
                side = str(t.get("side") or "YES").strip().upper()

                is_win = (result == side)
                exit_price = 1.0 if is_win else 0.0
                pnl = net_pnl(entry_price, exit_price, contracts)

                closed_ok = TradeStore.close_if_open(uid, t, {
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "exit_reason": "SETTLEMENT",
                    "settled_at": time.time()
                })
                if not closed_ok:
                    continue

                payout = round(exit_price * contracts, 2)
                if t_mode == "PAPER" and payout > 0:
                    credit_user_paper_balance(uid, payout - kalshi_order_fee(exit_price, contracts))
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
            elif t_mode == "PAPER":
                # For regular paper contracts, check parent event resolution immediately
                ev_ticker = ticker.split("-", 2)[0] + "-" + ticker.split("-", 2)[1] if ticker.count("-") >= 2 else ticker
                ev_res = _check_kalshi_settlement(ev_ticker, team_hint=team_hint, user=user)
                if ev_res.get("status") in ("determined", "settled", "closed", "finalized"):
                    res_val = str(ev_res.get("result") or "").strip().upper()
                    is_win = (res_val == str(t.get("side") or "YES").strip().upper())
                    exit_price = 1.0 if is_win else 0.0
                    pnl = net_pnl(entry_price, exit_price, contracts)
                    payout = round(exit_price * contracts, 2)
                    closed_ok = TradeStore.close_if_open(uid, t, {
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "exit_reason": "SETTLEMENT",
                        "settled_at": time.time()
                    })
                    if closed_ok:
                        if payout > 0:
                            credit_user_paper_balance(uid, payout - kalshi_order_fee(exit_price, contracts))
                        trade_age = time.time() - _parse_trade_timestamp(t.get("timestamp"))
                        logger.info(f"[SportsBridge] Concluded paper trade {t_id} via parent event after {trade_age/3600:.1f}h (Win: {is_win}, PnL: ${pnl:.2f})")
