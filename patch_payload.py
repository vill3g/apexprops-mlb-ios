import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'r', encoding='utf-8') as f:
    content = f.read()

old_payload = '''                const payload = {
                    trade_size_dollars: size,
                    paper_trade_size_dollars: paperSize,
                    stop_loss_pct: sl,
                    take_profit_pct: tp,'''

new_payload = '''                const payload = {
                    trade_size_dollars: size,
                    paper_trade_size_dollars: paperSize,
                    stop_loss_pct: sl,
                    stop_loss_enabled: slEnabled,
                    take_profit_pct: tp,'''

if old_payload in content:
    content = content.replace(old_payload, new_payload)
    with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced payload!")
else:
    print("Could not find payload!")
