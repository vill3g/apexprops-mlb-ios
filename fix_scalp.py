import sys

with open('backend/btc/scalp_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

broken_fetch = '''                            try:
                                # Fetch from the fast cache instead of blocking the thread doing a 2s HTTP request
                                from backend.btc.auto_executor import auto_executor
                                _st = auto_executor.get_status()
                                analysis = _st.get("analyzer_status") or {}
                                next_forecast = analysis.get("target_benchmark", {}).get("next_contract_forecast", {})'''

fixed_fetch = '''                            try:
                                # FIX: Use a much smaller limit (45) to drastically reduce HTTP latency for the spike monitor
                                from backend.btc.data_fetcher import fetch_candles
                                from backend.btc.indicators import add_all_indicators
                                from backend.btc.analyzer import analyze_btc
                                _df = fetch_candles(timeframe="15m", limit=45)
                                analysis = analyze_btc(add_all_indicators(_df))

                                next_forecast = analysis.get("target_benchmark", {}).get("next_contract_forecast", {})'''

content = content.replace(broken_fetch, fixed_fetch)

with open('backend/btc/scalp_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done fixing scalp_engine.py!')
