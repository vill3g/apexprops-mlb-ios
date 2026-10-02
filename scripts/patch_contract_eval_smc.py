import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\analyzer\contract_eval.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update signature
content = content.replace(
    'def evaluate_next_15m_contract(df_ind: pd.DataFrame, target_price: float = None, patterns: list = None, structure: dict = None, kalshi_m: dict = None, trading_style: str = "SNIPER", asset: str = "BTC", signal_isolation: str = None) -> dict:',
    'def evaluate_next_15m_contract(df_ind: pd.DataFrame, target_price: float = None, patterns: list = None, structure: dict = None, kalshi_m: dict = None, trading_style: str = "SNIPER", asset: str = "BTC", signal_isolation: str = None, fvgs: list = None, obs: list = None, sweeps: list = None, wicks: list = None) -> dict:'
)

# 2. Inject SMC Logic at the start of Heuristics Block
# We will find:
#     # 1. Check Advanced Descending & Ascending Chart Patterns (Secondary Override/Confluence)
# And insert our new God-Tier SMC block BEFORE it, so SMC has the highest priority over retail patterns.

smc_block = """    # 0. SMC GOD-TIER SETUPS (Institutional Order Flow)
    if not pred and sweeps and isinstance(sweeps, list):
        # 0a. Bearish Liquidity Sweep Sniping
        bear_sweeps = [s for s in sweeps if s.get('type') == 'BEARISH_SWEEP']
        if bear_sweeps:
            s = bear_sweeps[-1]
            has_bear_fvg = any(f.get('type') == 'BEARISH' for f in (fvgs or []))
            has_bear_ob = any(o.get('type') == 'BEARISH' for o in (obs or []))
            if has_bear_fvg or has_bear_ob:
                pred = "BID NO (BELOW TARGET)"
                grade = "GRADE A+ SETUP"
                badge = "⭐️ 5-STAR A+ (82%)"
                prob = 82
                catalysts.append(f"🐻 Bearish Liquidity Sweep: Retail trapped above {s.get('level_type', 'high')}.")
                if has_bear_fvg: catalysts.append("📉 Bearish FVG confirmation (Imbalance detected).")
                if has_bear_ob: catalysts.append("🧱 Bearish Order Block confirmation (Institutional defense).")

        # 0b. Bullish Liquidity Sweep Sniping
        bull_sweeps = [s for s in sweeps if s.get('type') == 'BULLISH_SWEEP']
        if not pred and bull_sweeps:
            s = bull_sweeps[-1]
            has_bull_fvg = any(f.get('type') == 'BULLISH' for f in (fvgs or []))
            has_bull_ob = any(o.get('type') == 'BULLISH' for o in (obs or []))
            if has_bull_fvg or has_bull_ob:
                pred = "BID YES (ABOVE TARGET)"
                grade = "GRADE A+ SETUP"
                badge = "⭐️ 5-STAR A+ (82%)"
                prob = 82
                catalysts.append(f"🐂 Bullish Liquidity Sweep: Sellers trapped below {s.get('level_type', 'low')}.")
                if has_bull_fvg: catalysts.append("📈 Bullish FVG confirmation (Imbalance detected).")
                if has_bull_ob: catalysts.append("🧱 Bullish Order Block confirmation (Institutional defense).")

    # 0c. Pure Order Block Defense
    if not pred and obs and isinstance(obs, list):
        for o in obs:
            dist = abs(c_close - o.get("price_level", 0.0))
            # Close proximity to OB and confirmed by wick absorption
            if dist <= atr * 0.5:
                if o.get("type") == "BULLISH" and c_close > o.get("price_level", 0.0) and lower_wick >= 0.35:
                    pred = "BID YES (ABOVE TARGET)"
                    grade = "GRADE A SETUP"
                    badge = "🟢 4-STAR A (75%)"
                    prob = 75
                    catalysts.append(f"🧱 Bullish Order Block Tap: Price rejected off ${o.get('price_level'):,.0f} OB.")
                    catalysts.append(f"🔨 Wick Absorption: {lower_wick*100:.0f}% lower wick signals strong limit bid absorption.")
                    break
                elif o.get("type") == "BEARISH" and c_close < o.get("price_level", 0.0) and upper_wick >= 0.35:
                    pred = "BID NO (BELOW TARGET)"
                    grade = "GRADE A SETUP"
                    badge = "🟢 4-STAR A (75%)"
                    prob = 75
                    catalysts.append(f"🧱 Bearish Order Block Tap: Price rejected off ${o.get('price_level'):,.0f} OB.")
                    catalysts.append(f"🔨 Wick Absorption: {upper_wick*100:.0f}% upper wick signals strong limit ask defense.")
                    break

"""

pattern_header = "    # 1. Check Advanced Descending & Ascending Chart Patterns (Secondary Override/Confluence)"
content = content.replace(pattern_header, smc_block + pattern_header)

# 3. Add CVD confirmation to the pattern breakout logic
old_bull_pattern = """        if eval_bullish_first and (asc_triangle or bull_flag):
            is_overbought_ceiling = (rsi > 68 and c_close >= bb_upper * 1.002)
            if not is_overbought_ceiling:
                if asc_triangle:"""

new_bull_pattern = """        if eval_bullish_first and (asc_triangle or bull_flag):
            is_overbought_ceiling = (rsi > 68 and c_close >= bb_upper * 1.002)
            if not is_overbought_ceiling:
                if cvd_val < 3.0:
                    catalysts.append("⛔ Warning: Bullish Chart Pattern detected, but CVD volume expansion is weak. Bypassing fakeout.")
                elif asc_triangle:"""
content = content.replace(old_bull_pattern, new_bull_pattern)

old_bear_pattern = """        elif eval_bearish_first and (desc_triangle or bear_flag or head_shoulders):
            is_oversold_floor = (rsi < 32 and c_close <= bb_lower * 0.998)
            if not is_oversold_floor:
                if desc_triangle:"""

new_bear_pattern = """        elif eval_bearish_first and (desc_triangle or bear_flag or head_shoulders):
            is_oversold_floor = (rsi < 32 and c_close <= bb_lower * 0.998)
            if not is_oversold_floor:
                if cvd_val > -3.0:
                    catalysts.append("⛔ Warning: Bearish Chart Pattern detected, but CVD seller expansion is weak. Bypassing fakeout.")
                elif desc_triangle:"""
content = content.replace(old_bear_pattern, new_bear_pattern)


# 4. Remove the naive "Liquidity Sweep" that was hardcoded in A+ setups previously
# Find the exact string for "A+ Setup 2: Liquidity Sweep Rejection (Turtle Soup)" and comment it out
# We can use regex to replace it entirely

import re
sweep_regex = re.compile(
    r"[ \t]*# A\+ Setup 2: Liquidity Sweep Rejection \(Turtle Soup\)\n"
    r"[ \t]*else:\n"
    r"[ \t]*low_4 = min\(float\(df_ind\.iloc\[j\]\[\"low\"\]\) for j in range\(max\(0, n-6\), n-2\)\)\n"
    r".*?Overhead Capping complete: Buyers trapped on spike\"\)\n",
    re.DOTALL
)
content = sweep_regex.sub("", content)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched contract_eval.py successfully.")
