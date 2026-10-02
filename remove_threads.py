import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(
    r'def _auto_trader_background_loop\(\):.*?time\.sleep\(2\)',
    '', code, flags=re.DOTALL
)

code = re.sub(
    r'_autotrader_thread = None.*?def _watchdog_monitor_loop\(\):.*?logger\.error\(f"\[AutoTrader Watchdog\] Error: \{e\}"\)',
    '', code, flags=re.DOTALL
)

code = re.sub(
    r'def start_background_tasks\(\):.*?start_forex_executor\(\)',
    'def start_background_tasks():\n    pass', code, flags=re.DOTALL
)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(code)
