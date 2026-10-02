import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\auth\\routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add to UserConfigRequest
content = content.replace('stop_loss_pct: float = 50.0\n    one_click_trade', 'stop_loss_pct: float = 50.0\n    stop_loss_enabled: bool = True\n    one_click_trade')

# 2. Add to get_dashboard_stats return dict
content = content.replace('"stop_loss_pct": float(current_user.get("stop_loss_pct", 50.0)),', '"stop_loss_pct": float(current_user.get("stop_loss_pct", 50.0)),\n        "stop_loss_enabled": bool(current_user.get("stop_loss_enabled", 1)),')

# 3. Add to UserStore.update_user_settings arguments
content = re.sub(r'(req\.stop_loss_pct,\s*)', r'\1req.stop_loss_enabled, \n        ', content)

# 4. Add to new_settings
content = content.replace('new_settings["stop_loss_pct"] = req.stop_loss_pct\n    new_settings["stopLossPercent"] = req.stop_loss_pct   # camelCase alias read by stop_manager.py', 'new_settings["stop_loss_pct"] = req.stop_loss_pct\n    new_settings["stopLossPercent"] = req.stop_loss_pct\n    new_settings["stop_loss_enabled"] = req.stop_loss_enabled\n    new_settings["stopLossEnabled"] = req.stop_loss_enabled')

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\auth\\routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated routes.py!")
