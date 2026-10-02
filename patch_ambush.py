import codecs
import re

with codecs.open('backend/btc/analyzer.py', 'r', 'utf-8') as f:
    text = f.read()

old_block = r'''        if current_prob <= min_ev:
            catalysts.insert(0, f"â›” Negative EV Block: ML Prob ({current_prob*100:.1f}%) <= Kalshi Ask ({kalshi_ask*100:.0f}c) + 5% Edge.")
            pred = "PASS / NO BID (NEGATIVE EV)"
            direction = "PASS"
            grade = "PASS / POOR RISK REWARD"
            badge = "âšª PASS (NEGATIVE EV)"
            prob = 50.0'''

new_block = '''        if current_prob <= min_ev:
            catalysts.insert(0, f"â›” Negative EV Block: ML Prob ({current_prob*100:.1f}%) <= Kalshi Ask ({kalshi_ask*100:.0f}c) + 5% Edge.")
            pred = "PASS / NO BID (NEGATIVE EV)"
            direction = "PASS"
            grade = "PASS / POOR RISK REWARD"
            badge = "âšª PASS (NEGATIVE EV)"
            prob = 50.0

    if trading_style == "AMBUSH" and direction in ["ABOVE", "BELOW"]:
        try:
            is_fading_pump = (c_close > c_open) and direction == "BELOW"
            is_fading_dump = (c_close < c_open) and direction == "ABOVE"
            
            if is_fading_pump and trend_1h == "BULLISH":
                catalysts.insert(0, "🛑 AMBUSH Blocked: Attempted to fade a pump, but 1H Macro Trend is BULLISH.")
                pred = "PASS / NO BID (MACRO CONFLICT)"
                direction = "PASS"
                grade = "PASS / HIGH RISK"
                badge = "⚪ PASS (MACRO CONFLICT)"
                prob = 50.0
            elif is_fading_dump and trend_1h == "BEARISH":
                catalysts.insert(0, "🛑 AMBUSH Blocked: Attempted to fade a dump, but 1H Macro Trend is BEARISH.")
                pred = "PASS / NO BID (MACRO CONFLICT)"
                direction = "PASS"
                grade = "PASS / HIGH RISK"
                badge = "⚪ PASS (MACRO CONFLICT)"
                prob = 50.0
        except Exception:
            pass'''

# Handle the utf-8 characters correctly
old_block = old_block.replace("â›”", "⛔")
new_block = new_block.replace("â›”", "⛔").replace("âšª", "⚪")

text = text.replace(old_block, new_block)

# Sometimes powershell mangled characters, so let's try a regex without emoji
old_regex = re.compile(r'prob = 50\.0\s+return \{')
new_replacement = r'''prob = 50.0

    if trading_style == "AMBUSH" and direction in ["ABOVE", "BELOW"]:
        try:
            is_fading_pump = (c_close > c_open) and direction == "BELOW"
            is_fading_dump = (c_close < c_open) and direction == "ABOVE"
            
            if is_fading_pump and trend_1h == "BULLISH":
                catalysts.insert(0, "🛑 AMBUSH Blocked: Attempted to fade a pump, but 1H Macro Trend is BULLISH.")
                pred = "PASS / NO BID (MACRO CONFLICT)"
                direction = "PASS"
                grade = "PASS / HIGH RISK"
                badge = "⚪ PASS (MACRO CONFLICT)"
                prob = 50.0
            elif is_fading_dump and trend_1h == "BEARISH":
                catalysts.insert(0, "🛑 AMBUSH Blocked: Attempted to fade a dump, but 1H Macro Trend is BEARISH.")
                pred = "PASS / NO BID (MACRO CONFLICT)"
                direction = "PASS"
                grade = "PASS / HIGH RISK"
                badge = "⚪ PASS (MACRO CONFLICT)"
                prob = 50.0
        except Exception:
            pass

    return {'''

text, count = old_regex.subn(new_replacement, text)
print('Regex replaced:', count)

with codecs.open('backend/btc/analyzer.py', 'w', 'utf-8') as f:
    f.write(text)
