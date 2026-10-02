file_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\saas_settler.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('from backend.database.trade_store import TradeStore\n                                        db_trades = TradeStore.get_recent_trades(user_id, limit=50)', 'from backend.database.trade_store import TradeStore\n                                    db_trades = TradeStore.get_recent_trades(user_id, limit=50)')

# Let's just do a string replace of the block
old_block = """                                    if ap_yes > 0:
                                        from backend.database.trade_store import TradeStore
                                        db_trades = TradeStore.get_recent_trades(user_id, limit=50)"""

new_block = """                                    from backend.database.trade_store import TradeStore
                                    db_trades = TradeStore.get_recent_trades(user_id, limit=50)
                                    if ap_yes > 0:"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed saas_settler.py db_trades bug")
else:
    print("Could not find exact block to replace")
