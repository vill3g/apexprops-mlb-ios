import os

with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Inject ai_enabled into dashboard_stats return
c = c.replace(
    '"trading_mode": trading_mode,',
    '"trading_mode": trading_mode,\n        "ai_enabled": bool(current_user.get("ai_enabled", 1)),'
)

# Add new endpoints
add_route = """
class AIToggleRequest(BaseModel):
    enabled: bool

@router.post("/ai_toggle")
def toggle_ai_signals(req: AIToggleRequest, current_user: dict = Depends(get_current_user)):
    from backend.database.models import update_user_ai_enabled
    update_user_ai_enabled(current_user["id"], req.enabled)
    return {"success": True, "ai_enabled": req.enabled}
"""

if 'toggle_ai_signals' not in c:
    c += '\n' + add_route

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)
