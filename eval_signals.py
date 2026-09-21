import sys
import pandas as pd
from backend.btc.data_fetcher import fetch_candles
from backend.btc.indicators import add_all_indicators
from backend.btc.analyzer import evaluate_next_15m_contract
from backend.btc.auto_executor import auto_executor

df = fetch_candles("15m", 1500)
df_ind = add_all_indicators(df)

results = {
    "AI_ONLY": {"wins": 0, "losses": 0, "trades": 0},
    "CHART_ONLY": {"wins": 0, "losses": 0, "trades": 0},
    "BLEND": {"wins": 0, "losses": 0, "trades": 0},
}

n_samples = min(200, len(df_ind) - 50)

for i in range(len(df_ind) - n_samples, len(df_ind) - 1):
    sub = df_ind.iloc[:i+1]
    curr = sub.iloc[-1]
    next_bar = df_ind.iloc[i+1]
    
    target = float(curr['open'])
    settle = float(next_bar['close'])
    actual = "ABOVE" if settle > target else "BELOW"
    
    for mode in ["AI_ONLY", "CHART_ONLY", "BLEND"]:
        auto_executor.ai_settings["signalIsolation"] = mode
        auto_executor.ai_settings["minConf"] = 55 # slightly lower so it takes trades
        
        res = evaluate_next_15m_contract(sub, target, patterns=[], kalshi_m={"strike_price": target}, trading_style="SNIPER")
        
        direction = res.get("direction", "PASS")
        if "PASS" not in direction:
            results[mode]["trades"] += 1
            if direction == actual:
                results[mode]["wins"] += 1
            else:
                results[mode]["losses"] += 1

print(f"\n--- PERFORMANCE (Last {n_samples} intervals) ---")
for mode, stats in results.items():
    wins = stats["wins"]
    trades = stats["trades"]
    wr = (wins / trades * 100) if trades else 0
    print(f"{mode}: {trades} trades | Win Rate: {wr:.1f}% ({wins}W - {stats['losses']}L)")
