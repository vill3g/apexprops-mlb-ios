import re

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. UserConfigRequest
old_req = '''class UserConfigRequest(BaseModel):
    trade_size_dollars: float
    stop_loss_pct: float
    one_click_trade: bool
    auto_force_trade: bool = False
    trading_style: str = "AUTO"
    signal_source: str = "ML_ENSEMBLE"
    take_profit_pct: float = 50.0
    max_daily_trades: int = 10
    max_daily_risk: float = 50.0'''

new_req = '''class UserConfigRequest(BaseModel):
    trade_size_dollars: float
    stop_loss_pct: float
    one_click_trade: bool
    auto_force_trade: bool = False
    trading_style: str = "AUTO"
    signal_source: str = "ML_ENSEMBLE"
    take_profit_pct: float = 50.0
    max_daily_trades: int = 10
    max_daily_risk: float = 50.0
    trailing_stop_enabled: bool = False
    trailing_stop_activation_pct: float = 35.0
    trailing_stop_distance_pct: float = 6.0'''
content = content.replace(old_req, new_req)

# 2. get_dashboard_stats
old_stats = '''        "stop_loss_pct": float(current_user.get("stop_loss_pct", 10.0)),
        "take_profit_pct": float(current_user.get("take_profit_pct", 50.0)),
        "max_daily_trades": int(current_user.get("max_daily_trades", 10)),
        "max_daily_risk": float(current_user.get("max_daily_risk", 50.0)),
        "one_click_trade": bool(current_user.get("one_click_trade", 0)),'''

new_stats = '''        "stop_loss_pct": float(current_user.get("stop_loss_pct", 10.0)),
        "take_profit_pct": float(current_user.get("take_profit_pct", 50.0)),
        "max_daily_trades": int(current_user.get("max_daily_trades", 10)),
        "max_daily_risk": float(current_user.get("max_daily_risk", 50.0)),
        "trailing_stop_enabled": bool(current_user.get("trailing_stop_enabled", 0)),
        "trailing_stop_activation_pct": float(current_user.get("trailing_stop_activation_pct", 35.0)),
        "trailing_stop_distance_pct": float(current_user.get("trailing_stop_distance_pct", 6.0)),
        "one_click_trade": bool(current_user.get("one_click_trade", 0)),'''
content = content.replace(old_stats, new_stats)

# 3. set_user_config
old_set = '''    update_user_config(
        current_user["id"], 
        req.trade_size_dollars, 
        req.stop_loss_pct, 
        req.one_click_trade, 
        req.auto_force_trade, 
        req.trading_style, 
        req.signal_source,
        req.take_profit_pct,
        req.max_daily_trades,
        req.max_daily_risk
    )'''

new_set = '''    update_user_config(
        current_user["id"], 
        req.trade_size_dollars, 
        req.stop_loss_pct, 
        req.one_click_trade, 
        req.auto_force_trade, 
        req.trading_style, 
        req.signal_source,
        req.take_profit_pct,
        req.max_daily_trades,
        req.max_daily_risk,
        req.trailing_stop_enabled,
        req.trailing_stop_activation_pct,
        req.trailing_stop_distance_pct
    )'''
content = content.replace(old_set, new_set)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
