import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\auto_executor\saas_broadcaster.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the heuristic Kelly block with the True Binary Options Half-Kelly block
# We will do this universally by stripping out the `if use_kelly_criterion:` check 
# and running it universally.

# The pattern appears 4 times (live/paper in _broadcast_trade_to_users, and live/paper in _broadcast_reentry_to_users)

pattern = re.compile(
    r"[ \t]*# Kelly Criterion Sizing: ONLY active when user explicitly enabled switch in settings\n"
    r"[ \t]*if bool\(user\.get\(\"use_kelly_criterion\", 0\)\):\n"
    r"([ \t]*)p_win = (.*?)\n"
    r"([ \t]*)b_price = (.*?)\n"
    r"([ \t]*)if p_win <= b_price:\n"
    r"([ \t]*)logger\.info\(f\"\[.*?\] Kelly Criterion.*?\"\)\n"
    r"([ \t]*)return\n"
    r"([ \t]*)edge = p_win - b_price\n"
    r"([ \t]*)kelly_frac = min\(1\.0, max\(0\.25, edge / 0\.15\)\)\n"
    r"([ \t]*)risk_amount = max\((.*?), risk_amount \* kelly_frac\)"
)

def replacement(match):
    indent = match.group(1)
    p_win_expr = match.group(2)
    b_price_expr = match.group(4)
    min_risk = match.group(11)
    
    return f"""{indent}# Pillar 6: True Binary Options Half-Kelly Sizing
{indent}p_win = {p_win_expr}
{indent}b_price = {b_price_expr}
{indent}if p_win <= b_price:
{indent}    logger.info(f"[SaaS Broadcast] EV/Kelly Block: {{user.get('username')}} skipped trade @ ${{b_price:.2f}} (win prob {{p_win*100:.1f}}% <= ask)")
{indent}    return
{indent}f_star = (p_win - b_price) / (1.0 - b_price) if b_price < 1.0 else 0.0
{indent}kelly_frac = min(1.25, max(0.25, 0.50 * f_star))
{indent}risk_amount = max({min_risk}, risk_amount * kelly_frac)"""

new_content = pattern.sub(replacement, content)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Patched saas_broadcaster.py Kelly sizing successfully.")
