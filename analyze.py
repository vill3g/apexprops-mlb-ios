import re

with open(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\routes\engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.splitlines()
sports_start = 0
for i, line in enumerate(lines):
    if '@_engine_root_router.get("/api/engine/sports/events"' in line:
        sports_start = i
        break

print(f"Sports endpoints start at line {sports_start}")

core_functions_start = 0
for i, line in enumerate(lines):
    if 'def _execute_sports_trade(' in line:
        core_functions_start = i
        break

print(f"Sports core functions start at line {core_functions_start}")
