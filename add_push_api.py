import re

path = "backend/auth/routes.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

push_api_code = """
@router.get("/api/push/public_key")
async def get_vapid_public_key(current_user: str = Depends(get_current_user)):
    try:
        with open("backend/data/vapid.json", "r") as f:
            keys = __import__("json").load(f)
        return {"public_key": keys["public_key"]}
    except:
        return {"public_key": None}

@router.post("/api/push/subscribe")
async def subscribe_push(sub: dict, current_user: str = Depends(get_current_user)):
    user_id = int(current_user)
    os.makedirs(f"backend/data/users/{user_id}", exist_ok=True)
    with open(f"backend/data/users/{user_id}/push_sub.json", "w") as f:
        __import__("json").dump(sub, f)
    return {"success": True}
"""

if "get_vapid_public_key" not in code:
    code += "\n" + push_api_code

with open(path, "w", encoding="utf-8") as f:
    f.write(code)
