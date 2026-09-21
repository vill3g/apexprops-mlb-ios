import re

with open('backend/btc/analyzer.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Make sure n_score is defined at the top of the function
if 'n_score = 0.0' not in code[:1000]:
    code = code.replace('def evaluate_next_15m_contract(asset: str = "BTC", now_dt=None) -> Dict[str, Any]:', 
                        'def evaluate_next_15m_contract(asset: str = "BTC", now_dt=None) -> Dict[str, Any]:\n    n_score = 0.0')

code = code.replace('"news_sentiment_score": 0.0,', '"news_sentiment_score": float(n_score),')

with open('backend/btc/analyzer.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched analyzer.py")
