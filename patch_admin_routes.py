import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\auth\\admin_routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add to AdminUserUpdateSettings
content = content.replace('stop_loss_pct: Optional[float] = Field(None, gt=0, le=100)', 'stop_loss_pct: Optional[float] = Field(None, gt=0, le=100)\n    stop_loss_enabled: Optional[bool] = None')

# 2. Add to return dict in get_users
content = content.replace('"stop_loss_pct": float(u.get("stop_loss_pct", 50.0)),', '"stop_loss_pct": float(u.get("stop_loss_pct", 50.0)),\n            "stop_loss_enabled": bool(u.get("stop_loss_enabled", 1)),')

# 3. Add to admin_update_user payload dict mapping
content = content.replace('"trade_size_dollars", "stop_loss_pct", "take_profit_pct", "trading_style",', '"trade_size_dollars", "stop_loss_pct", "stop_loss_enabled", "take_profit_pct", "trading_style",')
content = content.replace('if payload.stop_loss_pct is not None:\n                new_settings["stopLossPercent"] = payload.stop_loss_pct', 'if payload.stop_loss_pct is not None:\n                new_settings["stopLossPercent"] = payload.stop_loss_pct\n            if payload.stop_loss_enabled is not None:\n                new_settings["stopLossEnabled"] = payload.stop_loss_enabled')

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\auth\\admin_routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated admin_routes.py!")
