import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\auto_executor\shared.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Auto 3.0 Classification Hierarchy update
old_classification = """    # Classification Hierarchy
    if is_liq_cascade or is_vol_momentum or is_mtf_aligned_momentum:
        style = "MOMENTUM_SURFER"
        regime = "STRONG_MOMENTUM"
        reason = f"High velocity trend / liquidation cascade (Vol: {vol_ratio:.2f}, ADX: {adx:.1f}, Liq: ${liq_total/1e6:.1f}M, 1H: {trend_1h})"
    elif is_squeeze_breakout or is_pure_breakout:
        style = "AMBUSH"
        regime = "SQUEEZE_BREAKOUT"
        reason = f"Squeeze breakout expansion (BBW: {bb_width:.4f}, Vol: {vol_ratio:.2f}, Range Exp: {candle_expansion})"
    elif is_chop_deadzone:
        style = "CAPITAL_GUARD"
        regime = "CHOP_DEADZONE"
        reason = f"Low-volatility compression deadzone (ADX: {adx:.1f} < 18, Vol: {vol_ratio:.2f} < 0.85, BBW: {bb_width:.4f}). Capital Guard active."
    elif is_trend_continuation:
        style = "SNIPER"
        regime = "TREND_CONTINUATION"
        reason = f"Directional trend continuation (ADX: {adx:.1f}, RSI: {rsi:.1f}, Vol: {vol_ratio:.2f})"
    else:
        style = "SNIPER"
        regime = "NORMAL_MARKET"
        reason = f"Standard market regime; routing to disciplined SNIPER confluence (ADX: {adx:.1f}, Vol: {vol_ratio:.2f})" """

new_classification = """    # Classification Hierarchy (Auto 3.0 God-Tier)
    is_noise_settled = (sec_left is not None and sec_left <= 810)  # 90s opening noise filtered
    
    if is_liq_cascade or is_vol_momentum or is_mtf_aligned_momentum:
        style = "MOMENTUM_SURFER"
        regime = "STRONG_MOMENTUM"
        reason = f"High velocity trend / liquidation cascade (Vol: {vol_ratio:.2f}, ADX: {adx:.1f}, Liq: ${liq_total/1e6:.1f}M, 1H: {trend_1h})"
    elif is_squeeze_breakout or is_pure_breakout:
        style = "AMBUSH"
        regime = "SQUEEZE_BREAKOUT"
        reason = f"Squeeze breakout expansion (BBW: {bb_width:.4f}, Vol: {vol_ratio:.2f}, Range Exp: {candle_expansion})"
    elif is_chop_deadzone:
        style = "CAPITAL_GUARD"
        regime = "CHOP_DEADZONE"
        reason = f"Low-volatility compression deadzone (ADX: {adx:.1f} < 18, Vol: {vol_ratio:.2f} < 0.85, BBW: {bb_width:.4f}). Capital Guard active."
    elif is_trend_continuation:
        if is_noise_settled:
            style = "PREDICTION"
            regime = "TREND_CONTINUATION"
            reason = f"Directional trend continuation & Noise Settled (ADX: {adx:.1f}, RSI: {rsi:.1f}, Vol: {vol_ratio:.2f})"
        else:
            style = "CAPITAL_GUARD" # Wait for 90s
            regime = "NOISE_SETTLING"
            reason = f"Waiting for 90s opening noise to settle before executing PREDICTION."
    else:
        style = "SNIPER"
        regime = "NORMAL_MARKET"
        reason = f"Standard market regime; routing to disciplined SNIPER confluence (ADX: {adx:.1f}, Vol: {vol_ratio:.2f})" """

content = content.replace(old_classification, new_classification)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched shared.py Auto 3.0 Regime successfully.")
