import re

with open("backend/btc/kalshi_trader.py", "r", encoding="utf-8") as f:
    content = f.read()

old_func = """        ob = (r.json() or {}).get("orderbook_fp") or {}
        book = {}
        for side in ("yes", "no"):
            levels = []
            for p, q in (ob.get(f"{side}_dollars") or []):
                try:
                    p, q = float(p), float(q)
                except (TypeError, ValueError):
                    continue
                if 0.0 < p < 1.0 and q > 0:
                    levels.append((p, q))
            levels.sort(key=lambda x: x[0], reverse=True)  # best bid first
            book[side] = levels
        with _paper_book_lock:
            _paper_book_cache[t] = (now, book)
        return book"""

new_func = """        ob = (r.json() or {}).get("orderbook_fp") or {}
        book = {}
        is_empty = True
        for side in ("yes", "no"):
            levels = []
            for p, q in (ob.get(f"{side}_dollars") or []):
                try:
                    p, q = float(p), float(q)
                except (TypeError, ValueError):
                    continue
                if 0.0 < p < 1.0 and q > 0:
                    levels.append((p, q))
                    is_empty = False
            levels.sort(key=lambda x: x[0], reverse=True)  # best bid first
            book[side] = levels
        if is_empty:
            return None
        with _paper_book_lock:
            _paper_book_cache[t] = (now, book)
        return book"""

if old_func in content:
    content = content.replace(old_func, new_func)
    print("Replaced _fetch_order_book logic.")
else:
    print("Could not find the old _fetch_order_book logic.")

with open("backend/btc/kalshi_trader.py", "w", encoding="utf-8") as f:
    f.write(content)
