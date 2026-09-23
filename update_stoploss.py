import json
import os

config_path = 'backend/data/trading_config.json'

try:
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Update the setting
    if 'ai_settings' not in config:
        config['ai_settings'] = {}
    
    # Set to 10 (representing 10 cents or $0.10)
    config['ai_settings']['stopLossMoveDollars'] = 10
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
        
    print(f"Successfully updated stopLossMoveDollars to 10 in {config_path}")
except Exception as e:
    print(f"Error updating config: {e}")
