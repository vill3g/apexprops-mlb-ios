import re

df_fetcher_path = 'backend/btc/data_fetcher.py'
with open(df_fetcher_path, 'r', encoding='utf-8') as f:
    df_text = f.read()

# Introduce a global cache for the CSV
cache_code = """
_historical_15m_cache = None

def fetch_candles(timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
"""

# Replace the def line to inject the global variable
df_text = df_text.replace(
    'def fetch_candles(timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:',
    cache_code
)

csv_logic = """
                if timeframe.lower() == "15m":
                    global _historical_15m_cache
                    hist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "historical_candles_btc_15m.csv")
                    if os.path.exists(hist_path):
                        try:
                            if _historical_15m_cache is None:
                                _historical_15m_cache = pd.read_csv(hist_path)
                            
                            df_combined = pd.concat([_historical_15m_cache, df], ignore_index=True)
                            df_combined.drop_duplicates(subset=["time"], keep="last", inplace=True)
                            df_combined.sort_values("time", inplace=True)
                            
                            if len(df_combined) > 20000:
                                df_combined = df_combined.tail(20000)
                            
                            _historical_15m_cache = df_combined.copy() # update cache
                            df = df_combined.tail(limit).reset_index(drop=True)
"""

old_csv_logic = """
                if timeframe.lower() == "15m":
                    hist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "historical_candles_btc_15m.csv")
                    if os.path.exists(hist_path):
                        try:
                            df_hist = pd.read_csv(hist_path)
                            # Combine and drop duplicates based on 'time'
                            df_combined = pd.concat([df_hist, df], ignore_index=True)
                            df_combined.drop_duplicates(subset=["time"], keep="last", inplace=True)
                            df_combined.sort_values("time", inplace=True)
                            
                            # Trim to 20,000 candles to keep memory sane
                            if len(df_combined) > 20000:
                                df_combined = df_combined.tail(20000)
                                
                            df_combined.reset_index(drop=True, inplace=True)
                            df = df_combined
"""

df_text = df_text.replace(old_csv_logic, csv_logic)

with open(df_fetcher_path, 'w', encoding='utf-8') as f:
    f.write(df_text)

print("data_fetcher.py csv cache fixed")
