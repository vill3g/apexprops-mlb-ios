import re
import sys
import shutil

with open('backend/sports_bridge/executor.py', 'r') as f:
    code = f.read()

# Part 4: _reconcile_uncertain_sports_orders
if '_reconcile_uncertain_sports_orders' not in code or 'def _reconcile_uncertain_sports_orders' not in code:
    recon_code = '''
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
        if not pending:
            return
        pos_res = kt.get_positions()
        if not pos_res.get("success"):
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
                    logger.warning(f"[SportsBridge] User {uid}: recorded {count} YES on {ticker} @  from lost order.")
                order_intents.mark(key, intent_ticker, "filled_reconciled")
            elif now - float(row.get("created_at") or now) > UNRESOLVED_GIVE_UP_SECONDS:
                order_intents.mark(key, intent_ticker, "no_fill_found")
                logger.info(f"[SportsBridge] User {uid}: uncertain order on {ticker} never showed a position; treating as unfilled.")

    def _settle_open_trades'''
    code = code.replace('    def _settle_open_trades', recon_code)


# Part 5: _settle_open_trades fixes
settle_old_1 = '''                        if kt:
                            close_res = kt.close_position(ticker, "yes", cur_price)
                            if not close_res.get("success"):
                                if "Not enough positions" in str(close_res.get("error", "")):
                                    logger.info(f"[SportsBridge] Position on {ticker} already closed or not held on Kalshi.")
                                else:
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
                            "exit_reason": f"TAKE_PROFIT (+{gain_pct:.1f}%)"
                        })'''

settle_new_1 = '''                        if kt:
                            close_res = kt.close_position(ticker, "yes", cur_price)
                            if not close_res.get("success"):
                                if "Not enough positions" in str(close_res.get("error", "")):
                                    logger.info(f"[SportsBridge] Position on {ticker} already closed or not held on Kalshi.")
                                else:
                                    logger.warning(f"[SportsBridge] Live TP close failed for {t_id}: {close_res.get('error')}")
                                    continue
                                cur_price = float(close_res.get("exit_price") or cur_price)
                        else:
                            # if live but no kt, skip
                            if t_mode == "LIVE":
                                continue

                        pnl = net_pnl(entry_price, cur_price, contracts)
                        payout = round(cur_price * contracts, 2)
                        
                        closed_ok = TradeStore.close_if_open(uid, t, {
                            "exit_price": cur_price,
                            "pnl": pnl,
                            "exit_reason": f"TAKE_PROFIT (+{gain_pct:.1f}%)"
                        })
                        if not closed_ok:
                            continue
                            
                        if t_mode == "PAPER" and payout > 0:
                            credit_user_paper_balance(uid, payout - kalshi_order_fee(cur_price, contracts))'''
if settle_old_1 in code:
    code = code.replace(settle_old_1, settle_new_1)

settle_old_2 = '''                    pnl = round((exit_price - entry_price) * contracts, 2)
                    payout = round(exit_price * contracts, 2)
                    if payout > 0 and t_mode == "PAPER":
                        credit_user_paper_balance(uid, payout)

                    TradeStore.update_trade(t_id, {
                        "status": "CLOSED",
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "exit_reason": "SETTLEMENT",
                        "settled_at": settled_at
                    })'''

settle_new_2 = '''                    pnl = net_pnl(entry_price, exit_price, contracts)
                    closed_ok = TradeStore.close_if_open(uid, t, {
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "exit_reason": "SETTLEMENT",
                        "settled_at": settled_at
                    })
                    if not closed_ok:
                        continue
                    payout = round(exit_price * contracts, 2)
                    if payout > 0 and t_mode == "PAPER":
                        credit_user_paper_balance(uid, payout)'''
if settle_old_2 in code:
    code = code.replace(settle_old_2, settle_new_2)

with open('backend/sports_bridge/executor.py', 'w') as f:
    f.write(code)

print("Applied parts 4 and 5.")
