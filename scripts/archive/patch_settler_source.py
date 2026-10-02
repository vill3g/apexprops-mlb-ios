import re

with open('backend/saas_settler.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace signal extraction
old_sig = """        try:
            _, analysis = get_cached_btc_analysis(asset="BTC", timeframe="15m")
        except Exception:
            return
            
        signal = analysis.get("signal", "HOLD")"""

new_sig = """        try:
            _, analysis = get_cached_btc_analysis(asset="BTC", timeframe="15m")
        except Exception:
            return"""

if old_sig in c:
    c = c.replace(old_sig, new_sig)
    
# In the loop, dynamically check signal_source
old_loop_check = """        for user in force_users:
            if direction not in ["YES", "NO"]:
                continue"""
                
new_loop_check = """        for user in force_users:
            # Check user signal source
            u_source = str(user.get("signal_source", "ML_ENSEMBLE")).upper()
            if u_source == "TECHNICAL_ONLY":
                signal = analysis.get("primary_bias", "HOLD")
            else:
                signal = analysis.get("signal", "HOLD")
                
            direction = "YES" if "BUY YES" in signal else ("NO" if "BUY NO" in signal else "HOLD")
            
            if direction not in ["YES", "NO"]:
                continue"""
                
if old_loop_check in c:
    c = c.replace(old_loop_check, new_loop_check)
    
# But wait, `direction = "YES" if "BUY YES" in signal else ("NO" if "BUY NO" in signal else "HOLD")` was defined before the loop!
# I need to remove it from outside the loop.
old_dir_out = """        direction = "YES" if "BUY YES" in signal else ("NO" if "BUY NO" in signal else "HOLD")"""
if old_dir_out in c:
    c = c.replace(old_dir_out, "")

with open('backend/saas_settler.py', 'w', encoding='utf-8') as f:
    f.write(c)
