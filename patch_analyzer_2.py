import re

with open('backend/btc/analyzer.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('"news_sentiment_score": float(n_score),', '"news_sentiment_score": float(n_score) if "n_score" in locals() else 0.0,')

with open('backend/btc/analyzer.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched analyzer.py again")
