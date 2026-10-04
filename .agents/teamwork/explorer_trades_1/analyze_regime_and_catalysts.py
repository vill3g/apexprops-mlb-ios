import os
import sys
import sqlite3
import json
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

conn = sqlite3.connect(f"file:{os.path.join(PROJECT_ROOT, 'backend', 'data', 'users.db')}?mode=ro", uri=True)
cur = conn.cursor()

cur.execute("""
    SELECT id, user_id, ticker, side, entry_price, pnl, exit_reason, trading_style, signal_source, timestamp, raw_json 
    FROM trades;
""")
rows = cur.fetchall()

print("=== REGIME, TREND ALIGNMENT, AND CATALYST AUDIT (users.db) ===")

catalyst_stats = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "pnl_list": []})
model_conflict_stats = {"conflict": {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0},
                        "aligned": {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0}}

prob_bins = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0})
style_stats = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0})
signal_stats = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0})
asset_stats = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "total_pnl": 0.0})

for r in rows:
    pnl = float(r[5]) if r[5] is not None else None
    if pnl is None:
        continue
    
    ticker = r[2]
    # Extract asset from ticker
    asset = "BTC"
    if "KXETH" in ticker:
        asset = "ETH"
    elif "KXGOLD" in ticker:
        asset = "GOLD"
    elif "KXSOL" in ticker:
        asset = "SOL"
    elif "KXDOGE" in ticker:
        asset = "DOGE"
    elif "KXEUR" in ticker or "EURUSD" in ticker:
        asset = "EURUSD"
    elif "KXGBP" in ticker or "GBPUSD" in ticker:
        asset = "GBPUSD"
    elif "KXNDQ" in ticker or "NDQ" in ticker:
        asset = "NDQ"
    elif "KXBTC" in ticker:
        asset = "BTC"
    else:
        asset = ticker.split("-")[0]
        
    style = r[7] or "UNKNOWN"
    signal = r[8] or "UNKNOWN"
    
    # Update style & signal & asset
    for stats_dict, key in [(style_stats, style), (signal_stats, signal), (asset_stats, asset)]:
        stats_dict[key]["count"] += 1
        stats_dict[key]["total_pnl"] += pnl
        if pnl > 0.0001: stats_dict[key]["wins"] += 1
        elif pnl < -0.0001: stats_dict[key]["losses"] += 1

    # Parse raw_json
    rj_str = r[10]
    prob = 50.0
    has_conflict = False
    catalysts = []
    
    if rj_str:
        try:
            rj = json.loads(rj_str)
            prob = float(rj.get("probability_percent") or 50.0)
            cats = rj.get("catalysts") or []
            if isinstance(cats, list):
                catalysts = cats
            elif isinstance(cats, str):
                try:
                    catalysts = json.loads(cats)
                except Exception:
                    catalysts = [cats]
        except Exception:
            pass
            
    # Probability Bins
    if prob < 52:
        p_bin = "50-51% (Neutral/Coinflip)"
    elif prob < 60:
        p_bin = "52-59% (Low Conviction)"
    elif prob < 70:
        p_bin = "60-69% (Moderate Conviction)"
    elif prob < 80:
        p_bin = "70-79% (High Conviction)"
    else:
        p_bin = "80%+ (Ultra Conviction)"
        
    prob_bins[p_bin]["count"] += 1
    prob_bins[p_bin]["total_pnl"] += pnl
    if pnl > 0.0001: prob_bins[p_bin]["wins"] += 1
    elif pnl < -0.0001: prob_bins[p_bin]["losses"] += 1

    # Check for Model Conflict in catalysts
    has_conflict = any("Model Conflict" in str(c) for c in catalysts)
    c_key = "conflict" if has_conflict else "aligned"
    model_conflict_stats[c_key]["count"] += 1
    model_conflict_stats[c_key]["total_pnl"] += pnl
    if pnl > 0.0001: model_conflict_stats[c_key]["wins"] += 1
    elif pnl < -0.0001: model_conflict_stats[c_key]["losses"] += 1

    # Catalyst Tagging
    for c in catalysts:
        c_clean = str(c).strip()
        # Simplify common catalyst categories
        tag = None
        if "Model Conflict" in c_clean:
            tag = "Model Conflict (Chart vs ML)"
        elif "Dual Green" in c_clean or "Dual Bullish" in c_clean:
            tag = "Dual Bullish Trend Alignment"
        elif "Dual Red" in c_clean or "Dual Bearish" in c_clean:
            tag = "Dual Bearish Trend Alignment"
        elif "Ascending Triangle" in c_clean:
            tag = "Ascending Triangle Breakout"
        elif "Descending Triangle" in c_clean:
            tag = "Descending Triangle Breakdown"
        elif "Overbought" in c_clean:
            tag = "Overbought (RSI/Oscillator)"
        elif "Oversold" in c_clean:
            tag = "Oversold (RSI/Oscillator)"
        elif "Mean Reversion" in c_clean:
            tag = "Mean Reversion"
        elif "Momentum" in c_clean:
            tag = "Momentum Surge"
        elif "Breakout" in c_clean:
            tag = "Breakout Pressure"
        elif "MACD" in c_clean:
            tag = "MACD Cross"
        elif "Volume" in c_clean:
            tag = "Volume Spike"
        if tag:
            catalyst_stats[tag]["count"] += 1
            catalyst_stats[tag]["total_pnl"] += pnl
            catalyst_stats[tag]["pnl_list"].append(pnl)
            if pnl > 0.0001: catalyst_stats[tag]["wins"] += 1
            elif pnl < -0.0001: catalyst_stats[tag]["losses"] += 1

conn.close()

# 1. Model Conflict Impact
print("\n" + "="*80)
print("1. MODEL CONFLICT ANALYSIS (When Technical Chart Setup Disagreed with ML Model)")
print("="*80)
for k, s in model_conflict_stats.items():
    cnt = s["count"]
    wr = (s["wins"] / cnt * 100) if cnt else 0.0
    avg_p = s["total_pnl"] / cnt if cnt else 0.0
    print(f"  {k.upper():<12}: {cnt:<5} trades | Win Rate: {wr:>5.1f}% | Total PnL: ${s['total_pnl']:>8.2f} | Avg PnL: ${avg_p:>6.2f}")

# 2. Probability / Conviction Bins
print("\n" + "="*80)
print("2. CONVICTION / PROBABILITY PERCENT TIERS")
print("="*80)
print(f"{'Conviction Tier':<30} | {'Trades':<7} | {'Win%':<7} | {'Total PnL':<11} | {'Avg PnL':<9}")
print("-" * 75)
for p_bin in sorted(prob_bins.keys()):
    s = prob_bins[p_bin]
    cnt = s["count"]
    wr = (s["wins"] / cnt * 100) if cnt else 0.0
    avg_p = s["total_pnl"] / cnt if cnt else 0.0
    print(f"{p_bin:<30} | {cnt:<7} | {wr:>5.1f}% | ${s['total_pnl']:>9.2f} | ${avg_p:>7.2f}")

# 3. Catalyst Performance
print("\n" + "="*80)
print("3. REGIME & CATALYST PERFORMANCE")
print("="*80)
print(f"{'Catalyst / Pattern':<32} | {'Trades':<7} | {'Win%':<7} | {'Total PnL':<11} | {'Avg PnL':<9}")
print("-" * 75)
for tag, s in sorted(catalyst_stats.items(), key=lambda x: x[1]["count"], reverse=True):
    cnt = s["count"]
    wr = (s["wins"] / cnt * 100) if cnt else 0.0
    avg_p = s["total_pnl"] / cnt if cnt else 0.0
    print(f"{tag:<32} | {cnt:<7} | {wr:>5.1f}% | ${s['total_pnl']:>9.2f} | ${avg_p:>7.2f}")

# 4. Asset Performance
print("\n" + "="*80)
print("4. ASSET PERFORMANCE")
print("="*80)
print(f"{'Asset':<12} | {'Trades':<7} | {'Win%':<7} | {'Total PnL':<11} | {'Avg PnL':<9}")
print("-" * 60)
for asset, s in sorted(asset_stats.items(), key=lambda x: x[1]["count"], reverse=True):
    cnt = s["count"]
    wr = (s["wins"] / cnt * 100) if cnt else 0.0
    avg_p = s["total_pnl"] / cnt if cnt else 0.0
    print(f"{asset:<12} | {cnt:<7} | {wr:>5.1f}% | ${s['total_pnl']:>9.2f} | ${avg_p:>7.2f}")

# 5. Trading Style Performance
print("\n" + "="*80)
print("5. TRADING STYLE PERFORMANCE")
print("="*80)
print(f"{'Trading Style':<20} | {'Trades':<7} | {'Win%':<7} | {'Total PnL':<11} | {'Avg PnL':<9}")
print("-" * 65)
for style, s in sorted(style_stats.items(), key=lambda x: x[1]["count"], reverse=True):
    cnt = s["count"]
    wr = (s["wins"] / cnt * 100) if cnt else 0.0
    avg_p = s["total_pnl"] / cnt if cnt else 0.0
    print(f"{style:<20} | {cnt:<7} | {wr:>5.1f}% | ${s['total_pnl']:>9.2f} | ${avg_p:>7.2f}")

