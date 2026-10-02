import re

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Update UserConfigRequest
old_req = """class UserConfigRequest(BaseModel):
    trade_size_pct: float
    stop_loss_pct: float
    one_click_trade: bool
    auto_force_trade: bool = False"""

new_req = """class UserConfigRequest(BaseModel):
    trade_size_dollars: float
    stop_loss_pct: float
    one_click_trade: bool
    auto_force_trade: bool = False
    trading_style: str = "AUTO"
    signal_source: str = "ML_ENSEMBLE\""""

if old_req in c:
    c = c.replace(old_req, new_req)

# Update set_user_config endpoint
old_route = """def set_user_config(req: UserConfigRequest, current_user: dict = Depends(get_current_user)):
    from backend.database.models import update_user_config
    update_user_config(current_user["id"], req.trade_size_pct, req.stop_loss_pct, req.one_click_trade, getattr(req, "auto_force_trade", False))"""

new_route = """def set_user_config(req: UserConfigRequest, current_user: dict = Depends(get_current_user)):
    from backend.database.models import update_user_config
    update_user_config(current_user["id"], req.trade_size_dollars, req.stop_loss_pct, req.one_click_trade, getattr(req, "auto_force_trade", False), req.trading_style, req.signal_source)"""

if old_route in c:
    c = c.replace(old_route, new_route)

# Update dashboard_stats return
old_stats = """"trade_size_pct": float(current_user.get("trade_size_pct", 20.0)),"""
new_stats = """"trade_size_dollars": float(current_user.get("trade_size_dollars", 50.0)),
        "trading_style": current_user.get("trading_style", "AUTO"),
        "signal_source": current_user.get("signal_source", "ML_ENSEMBLE"),"""

if old_stats in c:
    c = c.replace(old_stats, new_stats)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)

with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    m = f.read()

old_mod = """def update_user_config(user_id: int, trade_size_pct: float, stop_loss_pct: float, one_click_trade: bool, auto_force_trade: bool = False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE users 
        SET trade_size_pct = ?, stop_loss_pct = ?, one_click_trade = ?, auto_force_trade = ?
        WHERE id = ?
    ''', (trade_size_pct, stop_loss_pct, 1 if one_click_trade else 0, 1 if auto_force_trade else 0, user_id))"""

new_mod = """def update_user_config(user_id: int, trade_size_dollars: float, stop_loss_pct: float, one_click_trade: bool, auto_force_trade: bool = False, trading_style: str = "AUTO", signal_source: str = "ML_ENSEMBLE"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE users 
        SET trade_size_dollars = ?, stop_loss_pct = ?, one_click_trade = ?, auto_force_trade = ?, trading_style = ?, signal_source = ?
        WHERE id = ?
    ''', (trade_size_dollars, stop_loss_pct, 1 if one_click_trade else 0, 1 if auto_force_trade else 0, trading_style, signal_source, user_id))"""

if old_mod in m:
    m = m.replace(old_mod, new_mod)

with open('backend/database/models.py', 'w', encoding='utf-8') as f:
    f.write(m)
