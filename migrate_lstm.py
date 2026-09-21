import json
import pandas as pd
import numpy as np
import os
import datetime
from backend.btc.indicators import add_all_indicators

def migrate_trades():
    print("Loading trades...")
    with open('backend/data/trades_history.json', 'r', encoding='utf-8') as f:
        trades = json.load(f)
        
    print("Loading df_ind...")
    df = pd.read_csv('backend/data/historical_candles_btc_15m.csv')
    df['time'] = pd.to_numeric(df['time'])
    
    print("Adding indicators...")
    df = add_all_indicators(df)
    
    if "bb_percent_b" not in df.columns:
        bb_r = df["bb_upper"] - df["bb_lower"]
        df["bb_percent_b"] = np.where(bb_r > 0, (df["close"] - df["bb_lower"]) / bb_r, 0.5)
        
    if "volume_15m_ratio" not in df.columns:
        df["volume_15m_ratio"] = df["volume"] / df["volume"].rolling(288, min_periods=1).mean().clip(lower=1e-9)
        
    if "cvd_divergence" not in df.columns:
        df["cvd_divergence"] = df.get("cvd", 0.0) / (df["atr"] + 1e-5)
        
    SEQ_FEATURES = ["bb_percent_b", "rsi", "volume_15m_ratio", "roc_15m", "cvd_divergence"]
    
    migrated_count = 0
    for t in trades:
        # Find raw_features reference
        if "market_snapshot" in t and "raw_features" in t["market_snapshot"]:
            raw = t["market_snapshot"]["raw_features"]
        elif "raw_features" in t:
            raw = t["raw_features"]
        else:
            continue
            
        timestamp_str = t.get("timestamp")
        timestamp = 0
        if timestamp_str:
            try:
                dt_str = timestamp_str.replace(" ET", "").strip()
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %I:%M:%S %p")
                timestamp = int(dt.timestamp())
            except Exception:
                pass
                
        if not timestamp and "close_epoch" in t:
            timestamp = int(t["close_epoch"])
            
        if not timestamp:
            continue
            
        idx_matches = df[df["time"] <= timestamp].index
        if len(idx_matches) == 0:
            continue
            
        i = idx_matches[-1]
        p_idx = i - 1
        
        for step in range(4, -1, -1):
            curr_idx = p_idx - step
            for feat in SEQ_FEATURES:
                key = f"{feat}_lag_{step}"
                if curr_idx >= 0 and curr_idx < len(df) and feat in df.columns:
                    val = float(df[feat].iloc[curr_idx])
                else:
                    val = raw.get(feat, 0.0) if step == 0 else 0.5
                raw[key] = val
                
        migrated_count += 1
        
    print(f"Migrated {migrated_count} trades. Saving...")
    with open('backend/data/trades_history.json', 'w', encoding='utf-8') as f:
        json.dump(trades, f, indent=4)
    print("Migration complete!")

if __name__ == "__main__":
    migrate_trades()
