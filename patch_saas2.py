file_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\saas_settler.py"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for idx, line in enumerate(lines):
    if "db_trades = TradeStore.get_recent_trades(user_id, limit=50)" in line and "from backend.database.trade_store" in lines[idx-1]:
        # Move these two lines up before the if ap_yes > 0
        pass
    else:
        if "if ap_yes > 0:" in line and "db_trades =" not in "".join(lines[max(0, idx-10):idx]):
            # Insert the import and call here
            indent = line.split("if")[0]
            new_lines.append(indent + "from backend.database.trade_store import TradeStore\n")
            new_lines.append(indent + "db_trades = TradeStore.get_recent_trades(user_id, limit=50)\n")
        
        # Don't add the lines again if they are exactly the ones we moved
        if "from backend.database.trade_store import TradeStore" in line and "db_trades = TradeStore.get_recent_trades" in lines[idx+1]:
            continue
        if "db_trades = TradeStore.get_recent_trades" in line and "from backend.database.trade_store import TradeStore" in lines[idx-1]:
            continue
            
        new_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Applied saas_settler fix")
