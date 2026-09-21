import sys
import pandas as pd
from backend.btc.data_fetcher import fetch_candles
from backend.btc.indicators import add_all_indicators
from backend.btc.chop_engine import evaluate_chop_contract
from backend.btc.analyzer import evaluate_next_15m_contract

df = fetch_candles(timeframe="15m", limit=3000)
df_ind = add_all_indicators(df)

chop_count = 0
chop_passed = 0
chop_traded = 0
sniper_traded_in_chop = 0

print("Evaluating CHOP regime on last 3000 15m candles...")

for i in range(100, len(df_ind)-1):
    curr = df_ind.iloc[i-1]
    
    vol_ratio = curr.get("vol_ratio", 1.0)
    bb_width = curr.get("bb_bandwidth", 1.0)
    
    if vol_ratio < 0.85 and bb_width < 0.005:
        chop_count += 1
        
        # We need to simulate the forecast
        # We can pass the df_ind up to i
        sub_df = df_ind.iloc[:i+1]
        
        target_price = float(df_ind.iloc[i].get('open'))
        
        # Chop engine
        forecast_chop = evaluate_chop_contract(sub_df, target_price=target_price, kalshi_m=None)
        
        # Sniper engine (what would have happened without chop engine)
        forecast_sniper = evaluate_next_15m_contract(sub_df, target_price=target_price, patterns=[], kalshi_m=None, trading_style="SNIPER")
        
        if "PASS" not in forecast_chop.get("direction", "PASS"):
            chop_traded += 1
        else:
            chop_passed += 1
            
        if "PASS" not in forecast_sniper.get("direction", "PASS"):
            sniper_traded_in_chop += 1

print(f"Total CHOP intervals: {chop_count}")
print(f"Trades taken by SNIPER if run in CHOP conditions: {sniper_traded_in_chop}")
print(f"Trades taken by CHOP engine: {chop_traded} (Passed: {chop_passed})")
