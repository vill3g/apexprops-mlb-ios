with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

import re

# Fix 1: manual_trade
old_place_order = """        # Place live order
        res = kt.place_order(
            ticker=market.get("ticker"),
            action="buy",
            side="yes" if side=="YES" else "no",
            count=count,
            price_cents=int(price * 100),
            client_order_id=trade_id
        )"""

new_place_order = """        # Place live order
        res = kt.place_order(
            ticker=market.get("ticker"),
            side="yes" if side=="YES" else "no",
            count=count,
            limit_price_dollars=price,
            dry_run=False
        )"""

c = c.replace(old_place_order, new_place_order)

# Fix 2: close_all_trades
old_close_all = """        # Get live portfolio
        pf = kt.get_portfolio()
        if pf and pf.get('success'):
            positions = pf.get('positions', [])
            for p in positions:
                ticker = p.get('ticker')
                pos = p.get('position', 0)
                if pos > 0:
                    kt.place_order(ticker=ticker, action="sell", side="yes", count=pos)
                    closed_count += 1
                elif pos < 0:
                    kt.place_order(ticker=ticker, action="sell", side="no", count=abs(pos))
                    closed_count += 1"""

new_close_all = """        # Get live positions
        pos_resp = kt.get_positions()
        if pos_resp and pos_resp.get('success'):
            positions = pos_resp.get('positions', [])
            for p in positions:
                ticker = p.get('ticker')
                yes_pos = p.get('position_yes', 0)
                no_pos = p.get('position_no', 0)
                if yes_pos > 0:
                    kt.close_position(ticker=ticker, purchased_side="yes", count=yes_pos, dry_run=False)
                    closed_count += 1
                if no_pos > 0:
                    kt.close_position(ticker=ticker, purchased_side="no", count=no_pos, dry_run=False)
                    closed_count += 1"""

c = c.replace(old_close_all, new_close_all)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)
