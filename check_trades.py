import json
from datetime import datetime

try:
    with open('data/users/7/trades_history.json', 'r') as f:
        trades = json.load(f)
    print(f"Total trades for Vill3.G: {len(trades)}")
    
    # Last 10 trades
    for i, t in enumerate(trades[-10:]):
        ts_val = t.get('timestamp')
        if isinstance(ts_val, (int, float)):
            ts = datetime.fromtimestamp(ts_val).strftime('%m-%d %H:%M')
        else:
            ts = str(ts_val)[:16]
            
        ml = t.get('ml_reasoning', '')
        if len(ml) > 100: ml = ml[:100] + '...'
        
        print(f"#{i+1} [{ts}] Side: {t.get('side')} | Status: {t.get('status')} | PnL: {t.get('pnl')}")
        print(f"  Ticker: {t.get('ticker')} | Style: {t.get('trading_style')} | Source: {t.get('signal_source')}")
        print(f"  Reason: {t.get('reason')}")
        print(f"  Confidence: {t.get('confidence')} / Prob: {t.get('probability_percent')}")
        if ml: print(f"  ML Reasoning: {ml}")
        
        # Check market snapshot
        ms = t.get('market_snapshot', {})
        if isinstance(ms, str):
            try:
                ms = json.loads(ms)
            except:
                pass
        if isinstance(ms, dict):
            print(f"  Snapshot -> RSI: {ms.get('rsi')}, EMA Fast: {ms.get('ema_fast')}, EMA Slow: {ms.get('ema_slow')}, ADX: {ms.get('adx')}")
        print("-" * 60)
except Exception as e:
    print(f"Error: {e}")
