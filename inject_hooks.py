import re

with open('backend/btc/auto_executor.py', 'r') as f:
    content = f.read()

# For the main rollover execution
content = re.sub(
    r'(order_res = kalshi_trader\.place_order\(\s*ticker=current_interval_id,\s*side=side,\s*count=contracts_to_buy,\s*limit_price_dollars=market_price,\s*dry_run=dry_run,\s*slippage_buffer_dollars=slippage_buffer\s*\)\s*if order_res\.get\("success", False\):)',
    r'\1\n                # SaaS Broadcast\n                self._broadcast_trade_to_users(current_interval_id, side, market_price, {"prob": float(analysis.get("probability_percent", 50))})\n',
    content
)

# For Forced execution
content = re.sub(
    r'(order_res = kalshi_trader\.place_order\(\s*ticker=active_m\.get\("ticker", ""\),\s*side=side,\s*count=contracts_to_buy,\s*limit_price_dollars=market_price,\s*dry_run=dry_run,\s*slippage_buffer_dollars=slippage_buffer\s*\)\s*if order_res\.get\("success", False\):)',
    r'\1\n            # SaaS Broadcast\n            self._broadcast_trade_to_users(active_m.get("ticker", ""), side, market_price, {})\n',
    content
)

# For reversal
content = re.sub(
    r'(order_res = kalshi_trader\.place_order\(\s*ticker=ticker,\s*side=opposite_side\.lower\(\),\s*count=count,\s*limit_price_dollars=opposite_ask,\s*dry_run=dry_run\s*\)\s*if order_res\.get\("success"\):)',
    r'\1\n                # SaaS Broadcast\n                self._broadcast_trade_to_users(ticker, opposite_side.lower(), opposite_ask, {})\n',
    content
)

# For profit re-entry
content = re.sub(
    r'(order_res = kalshi_trader\.place_order\(\s*ticker=ticker,\s*side=side,\s*count=contracts_to_buy,\s*limit_price_dollars=market_price,\s*dry_run=dry_run,\s*slippage_buffer_dollars=0\.04\s*\)\s*if order_res\.get\("success"\):)',
    r'\1\n                # SaaS Broadcast\n                self._broadcast_trade_to_users(ticker, side, market_price, {})\n',
    content
)

with open('backend/btc/auto_executor.py', 'w') as f:
    f.write(content)
print('Patched auto_executor.py with broadcast hooks.')
