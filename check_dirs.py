import json
try:
    d = json.load(open('backend/data/trades_history.json', 'r'))
    for t in d[-10:]:
        snap = t.get('market_snapshot', {}).get('raw_features', {})
        trend = snap.get('trend_1h', 'UNKNOWN')
        rsi = snap.get('rsi', 0)
        cvd = snap.get('cvd_divergence', 0)
        print(f"ID: {t.get('id')} | Dir: {t.get('direction')} | Conf: {t.get('probability_percent')}% | PnL: {t.get('pnl')} | Trend: {trend} | RSI: {rsi:.1f} | CVD: {cvd:.2f}")
except Exception as e:
    print('Error:', e)
