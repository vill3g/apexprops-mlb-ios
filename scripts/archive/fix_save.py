import sqlite3
import os

with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    c = f.read()

old_func = """def update_user_config(user_id: int, size: float, sl: float, one_click: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE users 
        SET trade_size_pct = ?, stop_loss_pct = ?, one_click_trade = ?
        WHERE id = ?
    ''', (size, sl, 1 if one_click else 0, user_id))
    conn.commit()
    conn.close()"""

new_func = """def update_user_config(user_id: int, trade_size_pct: float, stop_loss_pct: float, one_click_trade: bool, auto_force_trade: bool = False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE users 
        SET trade_size_pct = ?, stop_loss_pct = ?, one_click_trade = ?, auto_force_trade = ?
        WHERE id = ?
    ''', (trade_size_pct, stop_loss_pct, 1 if one_click_trade else 0, 1 if auto_force_trade else 0, user_id))
    conn.commit()
    conn.close()"""

if old_func in c:
    c = c.replace(old_func, new_func)
else:
    # Just to be safe, replace it manually
    import re
    c = re.sub(r'def update_user_config\(.*?conn\.close\(\)', new_func, c, flags=re.DOTALL)

with open('backend/database/models.py', 'w', encoding='utf-8') as f:
    f.write(c)

# Also check routes.py to ensure it passes the correct kwargs
with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    r = f.read()

r = r.replace('update_user_config(current_user["id"], req.trade_size_pct, req.stop_loss_pct, req.one_click_trade)', 
              'update_user_config(current_user["id"], req.trade_size_pct, req.stop_loss_pct, req.one_click_trade, getattr(req, "auto_force_trade", False))')

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(r)
