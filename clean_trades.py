import json

file_path = 'backend/data/trades_history.json'

with open(file_path, 'r') as f:
    trades = json.load(f)

# Filter out trades with id 'sim_test123'
initial_count = len(trades)
trades = [t for t in trades if t.get('id') != 'sim_test123']

with open(file_path, 'w') as f:
    json.dump(trades, f, indent=2)

print(f"Removed {initial_count - len(trades)} fake test trades.")
