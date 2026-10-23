import re
import sys
import shutil

with open('backend/sports_bridge/executor.py', 'r') as f:
    code = f.read()

shutil.copy('backend/sports_bridge/executor.py', 'backend/sports_bridge/executor.py.bak')

# 1. Imports
if 'order_intents' not in code:
    code = code.replace('from backend.database import get_db', 'from backend.database import get_db\nfrom backend.database import order_intents\nfrom backend.btc.fees import kalshi_order_fee, net_pnl')

# 2. Add prefix and helpers
if 'SPORTS_INTENT_PREFIX' not in code:
    helpers = '''

SPORTS_INTENT_PREFIX = "sports:"
UNRESOLVED_MIN_AGE_SECONDS = 60          
UNRESOLVED_GIVE_UP_SECONDS = 15 * 60     

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

'''
    code = code.replace('def _generate_kalshi_market', helpers + 'def _generate_kalshi_market')

# 3. _process_user updates
code = code.replace('''        # 4. Kelly Criterion / edge-scaled sizing''', '''        try:
            self._reconcile_uncertain_sports_orders(user, kt)
        except Exception as rec_err:
            logger.error(f"[SportsBridge] Reconciling uncertain orders for user {uid} failed: {rec_err}")

        # 4. Kelly Criterion / edge-scaled sizing''')

sizing_old = '''            max_p = min(0.99, max(0.01, float(price) + 0.04))
            count = max(1, int(wager / max_p))
            cost = round(price * count, 2)'''
sizing_new = '''            count, worst_cost = _size_sports_order(wager, price)
            if count < 1:
                continue
            cost = round(price * count + kalshi_order_fee(price, count), 2)'''
if sizing_old in code:
    code = code.replace(sizing_old, sizing_new)

# Live execution wrapper
live_exec_old = '''                if avail_live_cash < cost:
                    logger.warning(f"[SportsBridge] User {uid} has insufficient live balance () for  sports trade on {ticker}")
                    continue

                if kt:
                    logger.info(f"[SportsBridge] Placing LIVE {mode} order for user {uid} on {ticker}...")
                    order_res = kt.place_sports_order(
                        ticker=ticker,
                        action="buy",
                        side="yes",
                        count=count,
                        yes_price=int(price * 100),
                        client_order_id=trade_id,
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
                    avail_live_cash -= actual_cost'''
live_exec_new = '''                if avail_live_cash < worst_cost:
                    logger.warning(f"[SportsBridge] User {uid} has insufficient live balance () for  worst-case cost on {ticker}")
                    continue

                if kt:
                    intent_key = order_intents.account_key_for_user(uid)
                    intent_ticker = _sports_intent_ticker(ticker)
                    if not order_intents.claim(intent_key, intent_ticker, "yes"):
                        continue
                        
                    logger.info(f"[SportsBridge] Placing LIVE {mode} order for user {uid} on {ticker}...")
                    order_res = kt.place_sports_order(
                        ticker=ticker,
                        action="buy",
                        side="yes",
                        count=count,
                        yes_price=int(price * 100),
                        client_order_id=trade_id,
                        dry_run=False,
                        slippage_buffer_dollars=0.04
                    )
                    outcome = order_intents.settle_outcome(intent_key, intent_ticker, order_res)
                    if not order_res.get("success"):
                        if outcome == "ambiguous":
                            logger.error(f"[SportsBridge] LIVE order outcome UNKNOWN for user {uid} on {ticker}. Not retrying; will reconcile.")
                            open_tickers.add(ticker)
                            open_sports_count += 1
                            daily_trades_count += 1
                            daily_risk_spent += worst_cost
                            avail_live_cash -= worst_cost
                        else:
                            logger.warning(f"[SportsBridge] Live order failed for user {uid} on {ticker}: {order_res.get('error')}")
                        continue

                    order_id = str(order_res.get("order_id") or order_res.get("client_order_id") or trade_id)
                    fill_price = float(order_res.get("filled_price") or price)
                    fill_count = int(float(order_res.get("count") or count))
                    actual_cost = round(fill_price * fill_count + kalshi_order_fee(fill_price, fill_count), 2)
                    avail_live_cash -= actual_cost'''

if live_exec_old in code:
    code = code.replace(live_exec_old, live_exec_new)


with open('backend/sports_bridge/executor.py', 'w') as f:
    f.write(code)

print("Applied parts 1, 2, and 3.")
