import sys
import pandas as pd
import yfinance as yf
from backend.btc.indicators import add_all_indicators
from backend.btc.ml_engine import get_ml_engine

def force_train(asset):
    tickers = {'GOLD': 'GC=F'}
    sym = tickers.get(asset)
    
    print(f"Fetching 60d 15m data for {sym}...")
    try:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="60d", interval="15m")
    except Exception as e:
        print(f"Failed to fetch {sym}: {e}")
        return
        
    if hist.empty:
        print(f"No data for {sym}!")
        return
        
    hist = hist.reset_index()
    time_col = "Datetime" if "Datetime" in hist.columns else "Date"
    hist["time"] = pd.to_datetime(hist[time_col], utc=True).astype("int64") // 10**9
    hist = hist.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    
    df = hist[["time", "open", "high", "low", "close", "volume"]].sort_values("time").reset_index(drop=True)
    
    print(f"Adding indicators to {len(df)} candles...")
    df_ind = add_all_indicators(df)
    
    styles = ["SNIPER", "MOMENTUM_SURFER", "AMBUSH", "CHOP", "PREDICTION"]
    
    for st in styles:
        print(f"Training {st} for {asset}...")
        eng = get_ml_engine(trading_style=st, asset=asset)
        try:
            eng.self_train_on_historical_market(df_ind)
            print(f"Successfully trained {st} for {asset}.")
        except Exception as e:
            print(f"Failed to train {st} for {asset}: {e}")

force_train("GOLD")
