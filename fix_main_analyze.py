import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('analysis = analyze_btc(df, timeframe=tf)', 'analysis = analyze_btc(df, asset=asset, timeframe=tf)')

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
