import json; c = json.load(open('backend/data/trading_config.json')); c['ai_settings']['tradingStyle'] = 'CHOP'; json.dump(c, open('backend/data/trading_config.json', 'w'), indent=2)
