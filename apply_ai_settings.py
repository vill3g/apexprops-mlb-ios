import json

with open('backend/data/trading_config.json', 'r') as f:
    config = json.load(f)

# Apply stricter settings
config['ai_settings']['minConf'] = 75
config['ai_settings']['trainWindow'] = 1000
config['ai_settings']['edgeWeightFactor'] = 1.5

with open('backend/data/trading_config.json', 'w') as f:
    json.dump(config, f, indent=2)

print("Updated config successfully.")
