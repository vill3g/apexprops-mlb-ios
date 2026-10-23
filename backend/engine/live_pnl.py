import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("live_pnl")

SPORTS_PREFIXES = (
    "KXNFL", "KXMLB", "KXNBA", "KXNHL", "KXNCAAF", "KXNCAAB",
    "KXWNBA", "KXNPB", "KXKBO", "KXSOC", "KXUFC", "KXTEN",
    "KXMMA", "KXCBB", "KXCFB", "KXMLS", "KXEPL", "KXUCL",
    "KXWTA", "KXATP", "KXMVECROSSCATEGORY", "KXMVE"
)

def is_sports_trade(t: Dict[str, Any]) -> bool:
    """Accurately identifies whether a trade record belongs to the sports universe."""
    if not isinstance(t, dict):
        return False
    style = str(t.get("trading_style") or "").upper()
    if "SPORTS" in style or "COMBO" in style:
        return True
    sport_val = str(t.get("sport") or "").upper()
    if sport_val in ("SPORTS", "MULTIVARIATE_COMBO") or sport_val:
        return True
    sig = str(t.get("signal_source") or "").upper()
    if "SPORTS" in sig or "MVE" in sig or "COMBO" in sig:
        return True
    ticker = str(t.get("ticker") or "").upper()
    if ticker.startswith("KALSHI-"):
        return True
    return any(ticker.startswith(p) for p in SPORTS_PREFIXES)

# Backward compatibility alias
_is_sports_trade = is_sports_trade


import time

_parlay_quote_cache: Dict[str, Any] = {}

def _extract_leg_price_dollars(m: dict, prefix: str) -> float:
    """Safely extracts dollar quote (0.00 - 1.00) from a Kalshi market object."""
    d_val = m.get(f"{prefix}_dollars")
    if d_val is not None:
        try:
            f = float(d_val)
            return f / 100.0 if f > 1.0 else f
        except Exception:
            pass
    c_val = m.get(prefix)
    if c_val is not None:
        try:
            f = float(c_val)
            return f / 100.0 if f > 1.0 else f
        except Exception:
            pass
    return 0.0


def _calculate_parlay_synthetic_quotes(kt, legs: list, target_tk: str) -> tuple:
    """
    Calculates synthetic joint mark/ask probability across all underlying legs of a parlay.
    Uses a single batch HTTP request (`GET /trade-api/v2/markets?tickers=...`) for all legs,
    handles settled/determined legs (1.0 if won, 0.0 if lost), and groups same-game correlated
    legs by base matchup key so 28-leg bid-ask spreads do not compound into an artificial loss.
    Returns: (synth_mark, synth_ask, synth_status, leg_stats)
    """
    now = time.time()
    if target_tk and target_tk in _parlay_quote_cache:
        c_ts, c_data = _parlay_quote_cache[target_tk]
        if (now - c_ts) < 5.0:
            return c_data

    import requests as _req

    leg_tickers = [
        leg.get("market_ticker")
        for leg in legs
        if isinstance(leg, dict) and leg.get("market_ticker")
    ]
    if not leg_tickers:
        return (0.0, 1.0, "open", {})

    mkt_map = {}
    for i in range(0, len(leg_tickers), 100):
        chunk = leg_tickers[i:i + 100]
        try:
            resp = _req.get(
                "https://api.elections.kalshi.com/trade-api/v2/markets",
                params={"tickers": ",".join(chunk), "limit": 200},
                timeout=6,
            )
            if resp.status_code == 200:
                for m in resp.json().get("markets", []):
                    tk = m.get("ticker")
                    if tk:
                        mkt_map[tk] = m
        except Exception as e:
            logger.debug(f"[LivePnL] Batch leg fetch failed: {e}")

    # Fallback for any missing leg ticker
    for lt in leg_tickers:
        if lt not in mkt_map and kt is not None:
            try:
                lq = kt.get_market_quote(lt)
                lm = lq.get("market")
                if lm:
                    mkt_map[lt] = lm
            except Exception:
                pass

    any_lost = False
    all_won = True
    legs_evaluated = 0
    legs_won = 0
    legs_lost = 0
    legs_open = 0
    game_groups = {}
    leg_details = []

    for leg in legs:
        if not isinstance(leg, dict):
            continue
        lt = leg.get("market_ticker")
        side = str(leg.get("side") or "yes").lower()
        if not lt:
            continue

        lm = mkt_map.get(lt) or {}
        if not lm:
            continue

        legs_evaluated += 1
        res_str = str(lm.get("result") or "").lower()
        stat = str(lm.get("status") or "").lower()

        yb = _extract_leg_price_dollars(lm, "yes_bid")
        ya = _extract_leg_price_dollars(lm, "yes_ask")
        nb = _extract_leg_price_dollars(lm, "no_bid")
        na = _extract_leg_price_dollars(lm, "no_ask")
        lp = _extract_leg_price_dollars(lm, "last_price")

        if yb <= 0.0 and na > 0.0:
            yb = round(max(0.0, 1.0 - na), 4)
        if ya <= 0.0 and nb > 0.0:
            ya = round(max(0.0, 1.0 - nb), 4)
        if nb <= 0.0 and ya > 0.0:
            nb = round(max(0.0, 1.0 - ya), 4)
        if na <= 0.0 and yb > 0.0:
            na = round(max(0.0, 1.0 - yb), 4)

        leg_title = lm.get("yes_sub_title") or lm.get("title") or lt

        # 1. Explicitly settled or determined with result
        if res_str in ("yes", "no"):
            if res_str == side:
                legs_won += 1
                leg_details.append({"ticker": lt, "side": side, "status": "WON", "prob": 1.0, "title": leg_title})
                continue
            else:
                legs_lost += 1
                any_lost = True
                all_won = False
                leg_details.append({"ticker": lt, "side": side, "status": "LOST", "prob": 0.0, "title": leg_title})
                continue

        # 2. Closed/determined without result string yet: infer from 98c+ / 2c- quote
        if stat in ("determined", "settled", "closed", "finalized"):
            check_b = yb if side == "yes" else nb
            check_a = ya if side == "yes" else na
            check_lp = lp if side == "yes" else (1.0 - lp if lp > 0 else 0.0)
            if check_b >= 0.98 or check_lp >= 0.98:
                legs_won += 1
                leg_details.append({"ticker": lt, "side": side, "status": "WON", "prob": 1.0, "title": leg_title})
                continue
            elif (0.0 < check_a <= 0.02) or (0.0 < check_lp <= 0.02):
                legs_lost += 1
                any_lost = True
                all_won = False
                leg_details.append({"ticker": lt, "side": side, "status": "LOST", "prob": 0.0, "title": leg_title})
                continue

        # 3. Active / Open leg
        all_won = False
        legs_open += 1

        if side == "yes":
            leg_bid = yb if yb > 0 else (lp if lp > 0 else 0.5)
            leg_ask = ya if ya > 0 else (leg_bid if leg_bid > 0 else 0.5)
        else:
            leg_bid = nb if nb > 0 else (1.0 - lp if lp > 0 else 0.5)
            leg_ask = na if na > 0 else (leg_bid if leg_bid > 0 else 0.5)

        leg_mid = 0.5 * (leg_bid + leg_ask) if (leg_bid > 0 and leg_ask > 0) else (leg_bid or leg_ask or 0.5)
        ev_tk = lm.get("event_ticker") or lt
        game_key = re.sub(r"^KX[A-Z0-9]+-", "", ev_tk)
        if len(game_key) > 12:
            game_key = game_key[:12]

        game_groups.setdefault(game_key, []).append((leg_bid, leg_mid, leg_ask))
        leg_details.append({
            "ticker": lt,
            "side": side,
            "status": "OPEN",
            "prob": round(leg_mid, 4),
            "bid": round(leg_bid, 4),
            "ask": round(leg_ask, 4),
            "title": leg_title,
        })

    leg_stats = {
        "legs_total": len(leg_tickers),
        "legs_won": legs_won,
        "legs_lost": legs_lost,
        "legs_open": legs_open,
        "legs_details": leg_details,
    }

    if legs_evaluated == 0:
        res = (0.0, 1.0, "open", leg_stats)
    elif any_lost:
        res = (0.0, 0.0, "lost", leg_stats)
    elif all_won and legs_won == len(leg_tickers):
        res = (1.0, 1.0, "won", leg_stats)
    else:
        # Compute correlated game-grouped fair mark across remaining open legs
        synth_mark = 1.0
        synth_ask = 1.0
        for gk, probs in game_groups.items():
            probs_sorted = sorted(probs, key=lambda x: x[1])
            p_b, p_mid, p_a = probs_sorted[0]
            # Primary bottleneck leg in this game uses fair mid/ask blend
            game_mark = 0.35 * p_mid + 0.65 * p_a
            game_ask = p_a
            # Secondary correlated legs in the same game apply conditional residual factor
            for sb, smid, sa in probs_sorted[1:]:
                leg_fair = 0.35 * smid + 0.65 * sa
                game_mark *= (leg_fair ** 0.20)
                game_ask *= (sa ** 0.25)
            synth_mark *= game_mark
            synth_ask *= game_ask

        synth_mark = round(max(0.001, min(0.999, synth_mark)), 4)
        synth_ask = round(max(synth_mark, min(0.999, synth_ask)), 4)
        res = (synth_mark, synth_ask, "open", leg_stats)

    if target_tk:
        _parlay_quote_cache[target_tk] = (now, res)
    return res


def resolve_sports_market(trade: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Resolves the exact Kalshi market for a sports trade using the in-memory KalshiMarketCache.
    Handles direct market tickers, multivariate combo markets, event tickers, and strike detail matching.
    """
    tk = str(trade.get("ticker") or "").upper().strip()
    market_ticker = str(trade.get("market_ticker") or "").upper().strip()
    
    # 0. Check cache first
    try:
        from backend.engine.kalshi_market_cache import get_market_cache_instance
        cache = get_market_cache_instance()
    except Exception as e:
        logger.debug(f"[LivePnL] Could not import or get KalshiMarketCache: {e}")
        cache = None

    if cache:
        # 1. Direct market ticker stored on trade (if NOT an MVE parlay that needs synthetic pricing)
        if market_ticker and "MVE" not in market_ticker:
            m = cache.get_market(market_ticker)
            if m:
                return m

        # 2. Check primary ticker directly (if NOT an MVE parlay that needs synthetic pricing)
        if tk and "MVE" not in tk:
            m = cache.get_market(tk)
            if m:
                return m

    # 2b. Direct API quote lookup fallback & synthetic parlay leg pricing (especially for KXMVECROSSCATEGORY combo markets)
    target_tk = market_ticker or tk
    if target_tk and ("KXMVE" in target_tk or "KXMVECROSSCATEGORY" in target_tk):
        try:
            from backend.btc.kalshi_trader import KalshiTrader
            kt = KalshiTrader()
            q = kt.get_market_quote(target_tk)
            raw_mkt = (q or {}).get("market", {})
            if not raw_mkt:
                import requests as _req
                r = _req.get(f"https://api.elections.kalshi.com/trade-api/v2/markets/{target_tk}", timeout=5)
                if r.status_code == 200:
                    raw_mkt = r.json().get("market") or {}

            if raw_mkt or q:
                legs = raw_mkt.get("mve_selected_legs") or []

                raw_yes_bid = float((q or {}).get("yes_bid") or 0.0) / 100.0 if float((q or {}).get("yes_bid") or 0.0) > 1.0 else float((q or {}).get("yes_bid") or 0.0)
                raw_yes_ask = float((q or {}).get("yes_ask") or 0.0) / 100.0 if float((q or {}).get("yes_ask") or 0.0) > 1.0 else float((q or {}).get("yes_ask") or 0.0)
                raw_no_bid = float((q or {}).get("no_bid") or 0.0) / 100.0 if float((q or {}).get("no_bid") or 0.0) > 1.0 else float((q or {}).get("no_bid") or 0.0)
                raw_no_ask = float((q or {}).get("no_ask") or 0.0) / 100.0 if float((q or {}).get("no_ask") or 0.0) > 1.0 else float((q or {}).get("no_ask") or 0.0)
                raw_last = float((q or {}).get("last_price") or 0.0) / 100.0 if float((q or {}).get("last_price") or 0.0) > 1.0 else float((q or {}).get("last_price") or 0.0)

                leg_stats = {}
                # If this is a parlay/combo with underlying legs and no real market-maker bid on Kalshi (bid=0, ask=1.00),
                # compute synthetic fair-value live bid/ask from the underlying leg quotes!
                if legs and (raw_yes_bid <= 0.0 or raw_yes_ask >= 0.99):
                    synth_res = _calculate_parlay_synthetic_quotes(kt, legs, target_tk)
                    synth_bid, synth_ask, synth_status = synth_res[0], synth_res[1], synth_res[2]
                    leg_stats = synth_res[3] if len(synth_res) > 3 else {}
                    yes_bid_val = synth_bid
                    yes_ask_val = synth_ask
                    no_bid_val = round(1.0 - synth_ask, 4) if synth_ask > 0 else 0.0
                    no_ask_val = round(1.0 - synth_bid, 4) if synth_bid > 0 else 1.0
                    last_val = synth_bid
                    mkt_status = "closed" if synth_status in ("won", "lost") else "open"
                else:
                    yes_bid_val = raw_yes_bid
                    yes_ask_val = raw_yes_ask
                    no_bid_val = raw_no_bid
                    no_ask_val = raw_no_ask
                    last_val = raw_last
                    mkt_status = "open"

                clean_title = trade.get("predicted_team") or trade.get("title") or "Combo Market"
                if legs and len(legs) >= 2 and (len(str(clean_title)) > 60 or str(clean_title).lower().startswith("yes ") or str(clean_title).lower().startswith("no ")):
                    clean_title = f"{len(legs)}-Leg Master Combo"

                mkt_obj = {
                    "ticker": target_tk,
                    "title": clean_title,
                    "yes_bid": yes_bid_val,
                    "yes_ask": yes_ask_val,
                    "no_bid": no_bid_val,
                    "no_ask": no_ask_val,
                    "last_price": last_val,
                    "status": mkt_status,
                    "is_parlay": bool(legs),
                    "mve_leg_stats": leg_stats,
                }
                if cache:
                    try:
                        cache._markets[target_tk] = mkt_obj
                    except Exception:
                        pass
                return mkt_obj
        except Exception as e:
            logger.debug(f"[LivePnL] Direct quote lookup failed for {target_tk}: {e}")

    if not cache or not tk:
        return None

    # 3. Check event markets if tk is an event ticker (e.g. KXWTAMATCH-26OCT09KUDVOL, KXNHLGAME-26OCT09SEADET)
    ev_mkts = cache.get_markets_for_event(tk)
    if not ev_mkts:
        return None

    if len(ev_mkts) == 1:
        return ev_mkts[0]

    strike = str(trade.get("strike_details") or trade.get("title") or "").strip().lower()
    if strike:
        clean_target = re.sub(r"\b(wins|win|to win|winner)\b", "", strike).strip()
        # Pass 1: Exact team/player name or title match
        for em in ev_mkts:
            t_title = str(em.get("title") or "").lower()
            y_sub = str(em.get("yes_sub_title") or "").lower()
            if clean_target and (clean_target in t_title or clean_target in y_sub or t_title in clean_target or y_sub in clean_target):
                return em

        # Pass 2: Ticker suffix check (e.g. -VOL, -SEA, -WPG, -DET)
        for em in ev_mkts:
            suff = em.get("ticker", "").split("-")[-1].lower()
            if suff and suff in clean_target:
                return em

    return ev_mkts[0]


def annotate_trade_live_pnl(trade: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enriches a trade dictionary with real-time live PnL, exit bid, and current price.
    For sports trades in PAPER or LIVE mode, resolves live quotes from the in-memory WebSocket cache.
    """
    if not isinstance(trade, dict):
        return trade

    t = dict(trade)
    status = str(t.get("status") or "").upper()

    if status == "OPEN":
        if is_sports_trade(t):
            m = resolve_sports_market(t)
            entry = float(t.get("entry_price") or 0.5)
            count = float(t.get("count") or 1)
            side = str(t.get("side") or "YES").upper()

            if m:
                bid = float(m.get("yes_bid", 0.0) if side == "YES" else m.get("no_bid", 0.0))
                ask = float(m.get("yes_ask", 0.0) if side == "YES" else m.get("no_ask", 0.0))
                last = float(m.get("last_price", 0.0))
                if side == "NO" and last > 0:
                    last = round(1.0 - last, 4)

                if bid > 0:
                    mark_price = bid
                elif ask > 0.05:
                    mark_price = max(0.01, round(ask - 0.03, 4))
                elif last > 0:
                    mark_price = last
                else:
                    mark_price = entry

                live_pnl = round((mark_price - entry) * count, 2)
                live_pnl_pct = round(((mark_price - entry) / entry) * 100.0, 2) if entry > 0 else 0.0

                t["live_pnl"] = live_pnl
                t["live_pnl_pct"] = live_pnl_pct
                t["live_pnl_percent"] = live_pnl_pct
                t["cur_price"] = mark_price
                t["current_bid"] = mark_price
                t["current_price"] = mark_price
                t["exit_bid"] = mark_price
                # IMPORTANT: Never set exit_price on an OPEN trade (exit_price is strictly for settled/closed trades)
                t["exit_price"] = None
                if m.get("ticker"):
                    t["market_ticker"] = m.get("ticker")
                if m.get("title"):
                    t["market_title"] = m.get("title")
                if m.get("status"):
                    t["market_status"] = m.get("status")
                if m.get("mve_leg_stats"):
                    t["mve_leg_stats"] = m.get("mve_leg_stats")
            else:
                # Fallback if market cache has not loaded this event yet
                t["live_pnl"] = float(t.get("live_pnl") or 0.0)
                t["cur_price"] = float(t.get("cur_price") or entry)
                t["current_bid"] = float(t.get("current_bid") or entry)
                t["current_price"] = float(t.get("current_price") or entry)
                t["exit_bid"] = float(t.get("exit_bid") or entry)
                t["exit_price"] = None
        else:
            # Financial (crypto/forex) or investment contracts
            entry = float(t.get("entry_price") or 0.5)
            count = float(t.get("count") or 1)
            side = str(t.get("side") or "YES").upper()
            tk = str(t.get("ticker") or "").strip()

            mark_price = None
            if tk:
                try:
                    from backend.btc.kalshi_trader import KalshiTrader
                    kt = KalshiTrader()
                    quote = kt.get_market_quote(tk)
                    if quote and quote.get("success"):
                        yb = float(quote.get("yes_bid") or 0.0)
                        nb = float(quote.get("no_bid") or 0.0)
                        ya = float(quote.get("yes_ask") or 0.0)
                        na = float(quote.get("no_ask") or 0.0)
                        lp = float(quote.get("last_price") or 0.0)
                        if side == "YES":
                            if yb > 0:
                                mark_price = yb
                            elif na > 0 and (1.0 - na) > 0:
                                mark_price = round(1.0 - na, 4)
                            elif lp > 0:
                                mark_price = lp
                        else:  # NO
                            if nb > 0:
                                mark_price = nb
                            elif ya > 0 and (1.0 - ya) > 0:
                                mark_price = round(1.0 - ya, 4)
                            elif lp > 0:
                                mark_price = round(1.0 - lp, 4)
                    else:
                        # Check if finalized / determined via get_market_result
                        res = kt.get_market_result(tk)
                        if res and res.get("success"):
                            outcome = str(res.get("result") or "").lower()
                            if outcome in ("yes", "no"):
                                is_winner = (outcome == side.lower())
                                mark_price = 1.0 if is_winner else 0.0
                except Exception as e:
                    logger.debug(f"[LivePnL] Financial quote resolution error for {tk}: {e}")

            if mark_price is None:
                mark_price = float(t.get("cur_price") or t.get("current_price") or entry)

            live_pnl = round((mark_price - entry) * count, 2)
            live_pnl_pct = round(((mark_price - entry) / entry) * 100.0, 2) if entry > 0 else 0.0

            t["live_pnl"] = live_pnl
            t["live_pnl_pct"] = live_pnl_pct
            t["live_pnl_percent"] = live_pnl_pct
            t["cur_price"] = mark_price
            t["current_bid"] = mark_price
            t["current_price"] = mark_price
            t["exit_bid"] = mark_price
            t["exit_price"] = None
    else:
        # Closed or settled trade
        if "live_pnl" not in t:
            t["live_pnl"] = float(t.get("pnl_dollars") or t.get("pnl") or 0.0)

    return t

