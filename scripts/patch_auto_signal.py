import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\analyzer\contract_eval.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Update iso_setting parsing block
old_block = """    if signal_isolation:
        iso_clean = str(signal_isolation).upper().strip()
        if iso_clean in ["AI_ONLY", "ML_ENSEMBLE", "ML", "RL_DQN", "RL", "DQN", "DEEP_Q_NETWORK"]:
            iso_setting = "AI_ONLY"
        elif iso_clean in ["CHART_ONLY", "TECHNICAL_ONLY", "TECHNICAL"]:
            iso_setting = "CHART_ONLY"
        else:
            iso_setting = "BLEND"
    else:
        try:
            iso_setting = get_auto_executor(asset).ai_settings.get("signalIsolation", "BLEND")
        except (ValueError, TypeError) as e:
            logger.warning(f"Auto executor get error: {e}")
            iso_setting = "BLEND" """

new_block = """    if signal_isolation:
        iso_clean = str(signal_isolation).upper().strip()
    else:
        try:
            iso_clean = get_auto_executor(asset).ai_settings.get("signalIsolation", "AUTO").upper().strip()
        except (ValueError, TypeError) as e:
            logger.warning(f"Auto executor get error: {e}")
            iso_clean = "AUTO"

    if iso_clean in ["AI_ONLY", "ML_ENSEMBLE", "ML", "RL_DQN", "RL", "DQN", "DEEP_Q_NETWORK"]:
        iso_setting = "AI_ONLY"
    elif iso_clean in ["CHART_ONLY", "TECHNICAL_ONLY", "TECHNICAL"]:
        iso_setting = "CHART_ONLY"
    elif iso_clean in ["BLEND", "CONFLUENCE"]:
        iso_setting = "BLEND"
    else:
        # AUTO (Dynamic Regime isolation)
        # Matches signal isolation specifically to the strengths of the active regime.
        if trading_style == "PREDICTION":
            # Noise is settled; trust the neural network directly
            iso_setting = "AI_ONLY"
        elif trading_style in ["MOMENTUM_SURFER", "AMBUSH"]:
            # Heavy physical order flow / expansions are purely technical tape reads
            iso_setting = "CHART_ONLY"
        else:
            # SNIPER, CAPITAL_GUARD, NORMAL_MARKET need full agreement
            iso_setting = "BLEND"
"""

if old_block in content:
    content = content.replace(old_block, new_block)
else:
    # Try regex fallback
    pattern = re.compile(r"    if signal_isolation:.*?iso_setting = \"BLEND\"", re.DOTALL)
    content = pattern.sub(new_block, content, count=1)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched contract_eval.py for AUTO regime signal sources.")
