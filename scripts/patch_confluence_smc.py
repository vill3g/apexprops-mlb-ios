import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\analyzer\confluence.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

old_call = "next_contract_forecast = evaluate_next_15m_contract(df_ind, target_price=active_target, patterns=patterns, structure=structure, kalshi_m=kalshi_m)"
new_call = "next_contract_forecast = evaluate_next_15m_contract(df_ind, target_price=active_target, patterns=patterns, structure=structure, kalshi_m=kalshi_m, fvgs=fvgs, obs=obs, sweeps=sweeps, wicks=wicks)"

content = content.replace(old_call, new_call)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Patched confluence.py")
