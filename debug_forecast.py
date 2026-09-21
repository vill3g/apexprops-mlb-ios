import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from backend.btc.auto_executor import get_auto_executor
from backend.btc.indicators import add_all_indicators
from backend.engine.multi_asset_fetcher import fetch_asset_candles
from backend.btc.pattern_detector import detect_candlestick_patterns
from backend.btc.analyzer import evaluate_next_15m_contract

ex = get_auto_executor("BTC")
from backend.btc.kalshi_trader import kalshi_trader
active_m = kalshi_trader.get_active_15m_market(force_refresh=True)

if not active_m:
    print("NO ACTIVE MARKET")
    sys.exit(0)

strike = float(active_m.get("strike_price", 0.0))
df_c = fetch_asset_candles("BTC", "15m", limit=30)
df_ind = add_all_indicators(df_c)
patterns = detect_candlestick_patterns(df_ind)
forecast = evaluate_next_15m_contract(df_ind, target_price=strike, patterns=patterns, kalshi_m=active_m, trading_style="AUTO")

print(json.dumps(forecast, indent=2))
