import re

# 1. Patch executor.py
with open("backend/btc/auto_executor/executor.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace window_valid for PREDICTION
old_block1 = """                elif trading_style == "PREDICTION":
                    # Only focuses on making a trade at the contract open (first 120 seconds)
                    window_valid = sec_elapsed <= 120"""

new_block1 = """                elif trading_style == "PREDICTION":
                    # Wait up to 3 minutes (180s) for opening noise/chop to settle, then enter before the 3m expiry cutoff
                    window_valid = (sec_elapsed >= 180 and sec_left >= 180)
                    if not window_valid and sec_elapsed < 180:
                        logger.debug(f"[AutoExecutor] [PREDICTION] Waiting up to 3 minutes for opening candle noise to settle ({sec_elapsed:.0f}s elapsed < 180s).")"""

# Replace meets_conviction for PREDICTION
old_block2 = """                        elif effective_style == "PREDICTION":
                            # Prediction style trades at open regardless of chart pattern strictness
                            meets_conviction = True"""

new_block2 = """                        elif effective_style == "PREDICTION":
                            # Prediction style waits 3m for opening noise to settle; requires conviction >= 55%
                            actual_win_conf = max(actual_conf, 100.0 - actual_conf)
                            min_pred_conf = max(55.0, min_conf)
                            meets_conviction = (actual_win_conf >= min_pred_conf)
                            if not meets_conviction:
                                logger.info(f"[AutoExecutor] [PREDICTION] Skipped: confidence {actual_win_conf:.1f}% below minimum {min_pred_conf:.1f}%")"""

assert old_block1 in content, "old_block1 not found in executor.py"
assert old_block2 in content, "old_block2 not found in executor.py"

content = content.replace(old_block1, new_block1, 1)
content = content.replace(old_block2, new_block2, 1)

with open("backend/btc/auto_executor/executor.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Successfully patched backend/btc/auto_executor/executor.py")

# 2. Patch saas_broadcaster.py
with open("backend/btc/auto_executor/saas_broadcaster.py", "r", encoding="utf-8") as f:
    sb_content = f.read()

old_sb = """                        min_conf = 60.0
                        if eff_style == "MOMENTUM_SURFER" and not is_user_rl:
                            if sec_left < 240:
                                # Time Decay block
                                return
                            min_conf = 60.0 if sec_elapsed <= 60 else 75.0
                            conf = max(conf, 100.0 - conf)
                            if conf < min_conf:
                                return"""

new_sb = """                        min_conf = 60.0
                        if eff_style == "MOMENTUM_SURFER" and not is_user_rl:
                            if sec_left < 240:
                                # Time Decay block
                                return
                            min_conf = 60.0 if sec_elapsed <= 60 else 75.0
                            conf = max(conf, 100.0 - conf)
                            if conf < min_conf:
                                return
                        elif eff_style == "PREDICTION":
                            # Wait up to 3 minutes (180s) from interval open so it does not enter blindly
                            if sec_elapsed < 180:
                                logger.debug(f"[SaaS Broadcast] User {user.get('username')} PREDICTION waiting for 3m open (sec_elapsed={sec_elapsed:.0f}s < 180s)")
                                return
                            if sec_left < 180:
                                return
                            actual_win_conf = max(conf, 100.0 - conf)
                            if actual_win_conf < 55.0:
                                logger.debug(f"[SaaS Broadcast] User {user.get('username')} PREDICTION skipped: conf {actual_win_conf:.1f}% < 55.0%")
                                return"""

assert old_sb in sb_content, "old_sb not found in saas_broadcaster.py"
sb_content = sb_content.replace(old_sb, new_sb, 1)

with open("backend/btc/auto_executor/saas_broadcaster.py", "w", encoding="utf-8") as f:
    f.write(sb_content)
print("Successfully patched backend/btc/auto_executor/saas_broadcaster.py")

# 3. Patch contract_eval.py
with open("backend/btc/analyzer/contract_eval.py", "r", encoding="utf-8") as f:
    ce_content = f.read()

old_ce = """            catalysts.insert(0, f"🔮 Prediction Style Override: Forcing {direction} trade based on {prob:.1f}% chart-adjusted probability.")"""
new_ce = """            catalysts.insert(0, f"🔮 Prediction Style: Targeting {direction} based on {prob:.1f}% ML confidence (waits up to 3m for post-open confirmation).")"""

assert old_ce in ce_content, "old_ce not found in contract_eval.py"
ce_content = ce_content.replace(old_ce, new_ce, 1)

with open("backend/btc/analyzer/contract_eval.py", "w", encoding="utf-8") as f:
    f.write(ce_content)
print("Successfully patched backend/btc/analyzer/contract_eval.py")
