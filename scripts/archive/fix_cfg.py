import json

with open('backend/data/trading_config.json', 'r') as f:
    cfg = json.load(f)

cfg["ai_settings"]["ignorePass"] = False
cfg["ai_settings"]["tradingStyle"] = "AUTO"

with open('backend/data/trading_config.json', 'w') as f:
    json.dump(cfg, f, indent=2)

print("Updated config successfully.")
