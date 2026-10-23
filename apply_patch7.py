import re

with open('backend/sports_bridge/executor.py', 'r') as f:
    code = f.read()

# Match the live block
patt = r'if avail_live_cash < cost:.*?continue\s+order_res = kt\.place_sports_order\(\s*ticker=ticker,\s*side="yes",\s*count=count,\s*limit_price_dollars=price,\s*dry_run=False,\s*slippage_buffer_dollars=0\.04\s*\)\s+if not order_res\.get\("success"\):\s*logger\.warning\(f"\[SportsBridge\] Live order failed for user \{uid\} on \{ticker\}: \{order_res\.get\(\'error\'\)\}"\)\s*continue\s+order_id = str\(order_res\.get\("order_id"\) or order_res\.get\("client_order_id"\) or trade_id\)\s*fill_price = float\(order_res\.get\("filled_price"\) or price\)\s*fill_count = int\(order_res\.get\("count"\) or count\)\s*actual_cost = round\(fill_price \* fill_count, 2\)\s*avail_live_cash -= actual_cost'

new_live = '''if avail_live_cash < worst_cost:
                        logger.warning(f"[SportsBridge] User {uid} has insufficient live balance () for  sports trade on {ticker}")
                        continue

                    intent_key = order_intents.account_key_for_user(uid)
                    intent_ticker = _sports_intent_ticker(ticker)
                    if not order_intents.claim(intent_key, intent_ticker, "yes"):
                        continue

                    order_res = kt.place_sports_order(
                        ticker=ticker,
                        side="yes",
                        count=count,
                        limit_price_dollars=price,
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

code = re.sub(patt, new_live, code, flags=re.DOTALL)

with open('backend/sports_bridge/executor.py', 'w') as f:
    f.write(code)
