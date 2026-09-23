import json

try:
    with open('backend/data/trades_history.json', 'r') as f:
        d = json.load(f)
    
    closed = [t for t in d if t.get('status') in ['CLOSED', 'SETTLED']]
    
    # Analyze style performance
    styles = {}
    for t in closed:
        style = t.get('trading_style', 'UNKNOWN')
        if style not in styles:
            styles[style] = {'wins': 0, 'losses': 0, 'pnl': 0.0}
        
        pnl = float(t.get('pnl', 0) or 0)
        styles[style]['pnl'] += pnl
        if pnl > 0:
            styles[style]['wins'] += 1
        else:
            styles[style]['losses'] += 1
            
    print('--- PERFORMANCE BY STYLE ---')
    for s, data in styles.items():
        w = data['wins']
        l = data['losses']
        tot = w + l
        wr = (w / tot * 100) if tot > 0 else 0
        print(f"{s}: {tot} trades, Win Rate: {wr:.1f}%, PnL: ${data['pnl']:.2f}")

    # Get recent market condition
    last_trade = d[-1]
    raw = last_trade.get('market_snapshot', {}).get('raw_features', {})
    print('\n--- RECENT MARKET REGIME ---')
    print(f"RSI: {raw.get('rsi')}")
    print(f"Vol Percentile: {raw.get('vol_regime_percentile')}")
    print(f"Trend 1H: {raw.get('trend_1h')}")
    print(f"CVD Divergence: {raw.get('cvd_divergence')}")

except Exception as e:
    print('Error:', e)
