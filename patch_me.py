file_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\auth\routes.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add profile_pic to /me
if '"profile_pic": current_user.get("profile_pic")' not in content:
    content = content.replace(
        '"has_kalshi_keys": bool(current_user[\'kalshi_key_id\'] and current_user[\'kalshi_priv_key_encrypted\'])',
        '"has_kalshi_keys": bool(current_user[\'kalshi_key_id\'] and current_user[\'kalshi_priv_key_encrypted\']),\n        "profile_pic": current_user.get("profile_pic")'
    )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Added profile_pic to /me")
else:
    print("Already added")
