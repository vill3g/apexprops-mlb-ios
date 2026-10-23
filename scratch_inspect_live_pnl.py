import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('backend/engine/live_pnl.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos = text.find('def annotate_trade_live_pnl')
print(text[pos:pos+2500])
