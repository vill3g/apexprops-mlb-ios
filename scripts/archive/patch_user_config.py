with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

import re

# 1. Add UserConfigRequest
old_imports = """class ManualTradeRequest(BaseModel):
    direction: str
    amount_dollars: float"""

new_imports = """class ManualTradeRequest(BaseModel):
    direction: str
    amount_dollars: float

class UserConfigRequest(BaseModel):
    trade_size_pct: float
    stop_loss_pct: float
    one_click_trade: bool"""

c = c.replace(old_imports, new_imports)

# 2. Add /user/config route
route_code = """
@router.post("/user/config")
def set_user_config(req: UserConfigRequest, current_user: dict = Depends(get_current_user)):
    from backend.database.models import update_user_config
    update_user_config(current_user["id"], req.trade_size_pct, req.stop_loss_pct, req.one_click_trade)
    return {"success": True}
"""
c += route_code

# 3. Add to dashboard_stats return
old_ret = """        "ai_enabled": current_user.get('ai_enabled', 1),"""

new_ret = """        "ai_enabled": current_user.get('ai_enabled', 1),
        "trade_size_pct": current_user.get('trade_size_pct', 20.0),
        "stop_loss_pct": current_user.get('stop_loss_pct', 10.0),
        "one_click_trade": bool(current_user.get('one_click_trade', 0)),"""

c = c.replace(old_ret, new_ret)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)
