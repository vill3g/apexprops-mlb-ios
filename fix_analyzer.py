import re

with open('backend/btc/analyzer.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_analyzer_block = """    # 4. GRADE A SETUPS ? RSI + Bollinger secondary confirmation (upgrade only)
    # A Setup 1: Strong RSI Momentum Break (Bid YES) ? upgrade grade if already has direction
    if pred and rsi >= THRESHOLDS["rsi_bb_momentum_bull"] and c_close > bb_upper * 0.999:
        if "GRADE A+" not in grade:
            grade = "GRADE A SETUP"
            badge = "? 4-STAR A (72%)"
            prob = max(prob, 72) if "YES" in pred else 72
            pred = "BID YES (ABOVE TARGET)"
        catalysts.append(f"Overbought Expansion: High RSI ({rsi:.1f}) riding upper BB limit")

    # A Setup 2: Strong RSI Flush Break (Bid NO) ? upgrade grade only
    elif pred and rsi <= THRESHOLDS["rsi_bb_flush_bear"] and c_close < bb_lower * 1.001:
        if "GRADE A+" not in grade:
            grade = "GRADE A SETUP"
            badge = "? 4-STAR A (72%)"
            prob = max(prob, 72) if "NO" in pred else 72
            pred = "BID NO (BELOW TARGET)"
        catalysts.append(f"Oversold Flush: Low RSI ({rsi:.1f}) pressing lower BB limit")"""

new_analyzer_block = """    # 4. GRADE A SETUPS ? RSI + Bollinger secondary confirmation (upgrade only)
    # A Setup 1: Strong RSI Momentum Break (Bid YES) ? upgrade grade if already has direction
    if pred and "YES" in pred and rsi >= THRESHOLDS["rsi_bb_momentum_bull"] and c_close > bb_upper * 0.999:
        if "GRADE A+" not in grade:
            grade = "GRADE A SETUP"
            badge = "? 4-STAR A (72%)"
            prob = max(prob, 72) if "YES" in pred else 72
            pred = "BID YES (ABOVE TARGET)"
        catalysts.append(f"Overbought Expansion: High RSI ({rsi:.1f}) riding upper BB limit")

    # A Setup 2: Strong RSI Flush Break (Bid NO) ? upgrade grade only
    elif pred and "NO" in pred and rsi <= THRESHOLDS["rsi_bb_flush_bear"] and c_close < bb_lower * 1.001:
        if "GRADE A+" not in grade:
            grade = "GRADE A SETUP"
            badge = "? 4-STAR A (72%)"
            prob = max(prob, 72) if "NO" in pred else 72
            pred = "BID NO (BELOW TARGET)"
        catalysts.append(f"Oversold Flush: Low RSI ({rsi:.1f}) pressing lower BB limit")"""

content = content.replace(old_analyzer_block, new_analyzer_block)

with open('backend/btc/analyzer.py', 'w', encoding='utf-8') as f:
    f.write(content)

