import re

with open('backend/btc/pattern_detector.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_w = 'w = df.tail(12)'
new_w = '''w = df.tail(12)  # NOTE: 3hr window on 15m candles ? real triangle/H&S
                        # patterns often need longer to form. Known limitation,
                        # may cause missed patterns / false positives on noise.
                        # See audit bug #9. Widening requires backtest validation.'''
                        
content = content.replace(old_w, new_w)

with open('backend/btc/pattern_detector.py', 'w', encoding='utf-8') as f:
    f.write(content)
