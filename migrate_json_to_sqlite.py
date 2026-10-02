import os
import json
from backend.database.models import DATA_DIR, init_db, get_db_connection
from backend.database.trade_store import TradeStore

def migrate():
    init_db() # Ensures table exists
    conn = get_db_connection()
    cursor = conn.cursor()
    
    users_dir = os.path.join(DATA_DIR, "users")
    if not os.path.exists(users_dir):
        return
        
    for user_id_str in os.listdir(users_dir):
        if not user_id_str.isdigit():
            continue
            
        user_id = int(user_id_str)
        hist_path = os.path.join(users_dir, user_id_str, "trades_history.json")
        arch_path = os.path.join(users_dir, user_id_str, "trades_history_archive.json")
        
        all_trades = []
        if os.path.exists(arch_path):
            try:
                with open(arch_path, "r") as f:
                    all_trades.extend(json.load(f))
            except Exception:
                pass
                
        if os.path.exists(hist_path):
            try:
                with open(hist_path, "r") as f:
                    all_trades.extend(json.load(f))
            except Exception:
                pass
                
        for t in all_trades:
            # Check if exists
            cursor.execute("SELECT id FROM trades WHERE id = ?", (t.get("id"),))
            if not cursor.fetchone():
                TradeStore.insert_trade(user_id, t)
                
        # Optional: rename files to .bak
        if os.path.exists(hist_path):
            os.rename(hist_path, hist_path + ".bak")
        if os.path.exists(arch_path):
            os.rename(arch_path, arch_path + ".bak")

if __name__ == "__main__":
    migrate()
    print("Migration complete!")
