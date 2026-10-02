import re

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'class UserConfigRequest\(BaseModel\):\n    trade_size_pct: float\n    stop_loss_pct: float\n    one_click_trade: bool', 'class UserConfigRequest(BaseModel):\n    trade_size_pct: float\n    stop_loss_pct: float\n    one_click_trade: bool\n    auto_force_trade: bool = False', c)

c = re.sub(r'update_user_config\(current_user\["id"\], req.trade_size_pct, req.stop_loss_pct, req.one_click_trade\)', 'update_user_config(current_user["id"], req.trade_size_pct, req.stop_loss_pct, req.one_click_trade, req.auto_force_trade)', c)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)


with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    m = f.read()

m = re.sub(r'def update_user_config\(user_id: int, trade_size_pct: float, stop_loss_pct: float, one_click_trade: bool\):', 'def update_user_config(user_id: int, trade_size_pct: float, stop_loss_pct: float, one_click_trade: bool, auto_force_trade: bool = False):', m)

m = re.sub(r'one_click_trade = \? WHERE id = \?', 'one_click_trade = ?, auto_force_trade = ? WHERE id = ?', m)

m = re.sub(r'\(trade_size_pct, stop_loss_pct, one_click_trade, user_id\)', '(trade_size_pct, stop_loss_pct, one_click_trade, auto_force_trade, user_id)', m)

with open('backend/database/models.py', 'w', encoding='utf-8') as f:
    f.write(m)
