import re

with open("backend/btc/kalshi_trader.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = """            # In paper trading, fill the full requested contract count to strictly respect the user's trade size.
            filled_count = count_int
            fill_source = "estimated_top_of_book"

            # Fix D: walk Kalshi's real order book up to the same limit a live order would send
            # (ask + slippage buffer). Thin books now partially fill or miss, like a live IOC.
            book_fill = paper_buy_from_book(ticker, side_clean, count_int, min(0.99, raw_price + buf))
            if book_fill is not None:
                book_filled, book_vwap = book_fill
                if book_filled <= 0:
                    return {
                        "success": False,
                        "error": f"No {side_clean.upper()} liquidity on {ticker} at or below ${min(0.99, raw_price + buf):.2f} (simulated IOC missed, same as live).",
                    }
                filled_count = book_filled
                simulated_price = round(max(0.01, min(book_vwap + PAPER_LATENCY_TAX_DOLLARS, raw_price + buf, 0.99)), 4)
                fill_source = "kalshi_order_book"

            cost = round(simulated_price * filled_count, 4)"""

new_block = """            sim_depth = _simulated_book_depth(ticker, f"entry_{side_clean}")
            filled_count = min(count_int, sim_depth) if sim_depth > 0 else count_int
            
            if sim_depth == 0:
                return {
                    "success": False,
                    "error": f"No {side_clean.upper()} liquidity on {ticker} at or below ${min(0.99, raw_price + buf):.2f} (simulated IOC missed, same as live)."
                }
                
            fill_source = "estimated_top_of_book"

            # Fix D: walk Kalshi's real order book up to the same limit a live order would send
            # (ask + slippage buffer). Thin books now partially fill or miss, like a live IOC.
            book_fill = paper_buy_from_book(ticker, side_clean, count_int, min(0.99, raw_price + buf))
            if book_fill is not None:
                book_filled, book_vwap = book_fill
                if book_filled <= 0:
                    return {
                        "success": False,
                        "error": f"No {side_clean.upper()} liquidity on {ticker} at or below ${min(0.99, raw_price + buf):.2f} (simulated IOC missed, same as live).",
                    }
                filled_count = book_filled
                simulated_price = round(max(0.01, min(book_vwap + PAPER_LATENCY_TAX_DOLLARS, raw_price + buf, 0.99)), 4)
                fill_source = "kalshi_order_book"

            cost = round(simulated_price * filled_count, 4)"""

if old_block in content:
    content = content.replace(old_block, new_block)
    print("Replaced _simulated_book_depth logic in place_order_internal")
else:
    print("Could not find the block to replace!")

with open("backend/btc/kalshi_trader.py", "w", encoding="utf-8") as f:
    f.write(content)
