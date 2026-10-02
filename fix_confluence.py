import re

confluence_path = 'backend/btc/analyzer/confluence.py'
with open(confluence_path, 'r', encoding='utf-8') as f:
    conf_text = f.read()

# Fix 1: except Exception
conf_text = conf_text.replace(
    'except (ValueError, TypeError) as e:\n        logger.warning(f"MTF Macro Alignment Fetching failed: {e}")',
    'except Exception as e:\n        logger.warning(f"MTF Macro Alignment Fetching failed: {e}")'
)

# Fix 2: cb_ob = cb_ob or {}
conf_text = conf_text.replace(
    '        cb_ob = get_coinbase_orderbook_imbalance()\n        imb = cb_ob.get(\'imbalance\', 0.0)',
    '        cb_ob = get_coinbase_orderbook_imbalance() or {}\n        imb = cb_ob.get(\'imbalance\', 0.0)'
)

# Fix 3: Reduce TRAP DETECTED score to avoid artificial 100% inflation
conf_text = conf_text.replace(
    'score -= 15\n        bearish_reasons.append("TRAP DETECTED: Green candle with negative CVD (Short covering / Limit Selling absorption) (-15)")',
    'score -= 5\n        bearish_reasons.append("TRAP DETECTED: Green candle with negative CVD (Short covering / Limit Selling absorption) (-5)")'
)
conf_text = conf_text.replace(
    'score += 15\n        bullish_reasons.append("TRAP DETECTED: Red candle with positive CVD (Long liquidation / Limit Buying absorption) (+15)")',
    'score += 5\n        bullish_reasons.append("TRAP DETECTED: Red candle with positive CVD (Long liquidation / Limit Buying absorption) (+5)")'
)

with open(confluence_path, 'w', encoding='utf-8') as f:
    f.write(conf_text)

print("confluence.py fixed")
