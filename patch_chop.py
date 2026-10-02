import codecs
import re

with codecs.open('backend/btc/analyzer.py', 'r', 'utf-8') as f:
    text = f.read()

old = re.compile(r'if trading_style == .CHOP.:\s*# Mean Reversion Logic: Fade the Bollinger Bands\s*if c_close >= bb_upper:\s*# Overbought sideways -> Buy NO\s*pred = .PASS / BID NO \(CHOP FADE\).\s*prob = 100.0\s*grade = .GRADE A SETUP.\s*catalysts.insert\(0, .[^.]*Chop Mean-Reversion: Price hit Upper Bollinger Band in sideways regime. Fading the move \(BID NO\)..\)\s*elif c_close <= bb_lower:\s*# Oversold sideways -> Buy YES\s*pred = .PASS / BID YES \(CHOP FADE\).\s*prob = 100.0\s*grade = .GRADE A SETUP.\s*catalysts.insert\(0, .[^.]*Chop Mean-Reversion: Price hit Lower Bollinger Band in sideways regime. Fading the move \(BID YES\)..\)')

new = '''if trading_style == "CHOP":
        try:
            kalshi_yes_ask = float(kalshi_m.get("yes_ask", 0.50)) if kalshi_m else 0.50
            kalshi_no_ask = float(kalshi_m.get("no_ask", 0.50)) if kalshi_m else 0.50
        except Exception:
            kalshi_yes_ask, kalshi_no_ask = 0.50, 0.50

        if c_close >= bb_upper and rsi > 65:
            if 0.40 <= kalshi_no_ask <= 0.60:
                pred = "BID NO (CHOP FADE)"
                direction = "BELOW"
                prob = 100.0
                grade = "GRADE A SETUP"
                catalysts.insert(0, f"Chop FADE: Hit Upper BB with RSI {rsi:.1f}. Fading move (BID NO).")
            else:
                catalysts.insert(0, f"Chop Skip: BB Hit but NO Ask is {kalshi_no_ask*100:.0f}c (Outside 40-60c sweet spot).")
        elif c_close <= bb_lower and rsi < 35:
            if 0.40 <= kalshi_yes_ask <= 0.60:
                pred = "BID YES (CHOP FADE)"
                direction = "ABOVE"
                prob = 100.0
                grade = "GRADE A SETUP"
                catalysts.insert(0, f"Chop FADE: Hit Lower BB with RSI {rsi:.1f}. Fading move (BID YES).")
            else:
                catalysts.insert(0, f"Chop Skip: BB Hit but YES Ask is {kalshi_yes_ask*100:.0f}c (Outside 40-60c sweet spot).")'''

text, count = old.subn(new, text)
print('Replaced:', count)
with codecs.open('backend/btc/analyzer.py', 'w', 'utf-8') as f:
    f.write(text)
