import sys
import os
sys.path.append(os.getcwd())

from backend.engine.multi_asset_fetcher import fetch_asset_candles
from backend.btc.indicators import add_all_indicators

try:
    df_15m = fetch_asset_candles('BTC', '15m', limit=100)
    if df_15m is not None and not df_15m.empty:
        df_ind = add_all_indicators(df_15m)
        latest = df_ind.iloc[-1]
        
        c = float(latest.get('close', 0))
        atr = float(latest.get('atr', 0))
        atr_pct = float(latest.get('atr_percentile', 50.0))
        rsi = float(latest.get('rsi', 50.0))
        bb_u = float(latest.get('bb_upper', c * 1.01))
        bb_l = float(latest.get('bb_lower', c * 0.99))
        bb_w = ((bb_u - bb_l) / c * 100.0) if c > 0 else 0
        vol_surge = latest.get('vol_surge', False)
        
        print(f'Current Price: ${c:,.2f}')
        print(f'ATR: ${atr:,.2f} (Percentile: {atr_pct:.1f}%)')
        print(f'RSI: {rsi:.1f}')
        print(f'BB Width: {bb_w:.2f}%')
        print(f'Vol Surge: {vol_surge}')
except Exception as e:
    print('Error:', e)
