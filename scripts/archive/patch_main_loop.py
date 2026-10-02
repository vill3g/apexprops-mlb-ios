import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    c = f.read()

old_loop = """                for asset in ["BTC", "ETH", "GOLD"]:
                try:
                    get_auto_executor(asset).check_and_execute_rollover()
                except Exception:
                    pass"""

new_loop = """                for asset in ["BTC", "ETH", "GOLD"]:
                try:
                    ae = get_auto_executor(asset)
                    ae.check_and_execute_rollover()
                    ae.evaluate_and_execute_saas_users()
                except Exception:
                    pass"""

if old_loop in c:
    c = c.replace(old_loop, new_loop)
else:
    # Less strict replacement
    c = re.sub(
        r'get_auto_executor\(asset\)\.check_and_execute_rollover\(\)',
        r'ae = get_auto_executor(asset)\n                    ae.check_and_execute_rollover()\n                    ae.evaluate_and_execute_saas_users()',
        c
    )

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(c)
