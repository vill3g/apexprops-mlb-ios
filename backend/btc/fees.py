"""Kalshi trading-fee helpers used for P&L and paper-balance accounting.

Kalshi's taker fee per order is round_up(0.07 x contracts x P x (1 - P)) dollars
(see kalshi.com/fee-schedule). At P = 0 or 1 (settlement) it is zero, so the same
formula covers both selling before expiry and holding to settlement.
"""
import math

TAKER_FEE_RATE = 0.07


def kalshi_order_fee(price: float, count: float) -> float:
    try:
        p = min(max(float(price), 0.0), 1.0)
        c = max(float(count), 0.0)
    except (TypeError, ValueError):
        return 0.0
    raw = TAKER_FEE_RATE * c * p * (1.0 - p)
    return math.ceil(round(raw * 100.0, 6)) / 100.0 if raw > 0 else 0.0


MIN_EDGE_CENTS_LIMIT = 25.0   # highest "minimum edge" a user can set


def calculate_realized_edge_cents(
    prob_percent: float, 
    ask_price: float, 
    slippage_buffer_dollars: float = 0.04
) -> float:
    """
    Calculates expected profit per contract in cents after taker entry fee AND allowable slippage.
    Returns negative value if trade does not clear transaction friction.
    """
    p = float(prob_percent) / 100.0
    ask = float(ask_price)
    
    # Effective fill price assuming adverse execution across slippage corridor
    fill_price = min(0.99, ask + slippage_buffer_dollars)
    
    # Exact Kalshi Taker Fee (7% of p*(1-p), rounded up to whole cent)
    exact_taker_fee = math.ceil(0.07 * fill_price * (1.0 - fill_price) * 100.0) / 100.0
    
    # True Expected Net Value in cents per contract
    expected_value_dollars = (p * (1.0 - fill_price - exact_taker_fee)) - ((1.0 - p) * (fill_price + exact_taker_fee))
    return round(expected_value_dollars * 100.0, 2)


def net_pnl(entry: float, exit_price: float, count: float) -> float:
    """Realized P&L after the entry fee and (if sold before expiry) the exit fee."""
    gross = (float(exit_price) - float(entry)) * float(count)
    return round(gross - kalshi_order_fee(entry, count) - kalshi_order_fee(exit_price, count), 4)

import logging
logger = logging.getLogger("AutoExecutor.Kelly")

def calculate_binary_kelly_position(
    win_prob: float,
    ask_price: float,
    available_capital: float,
    max_position_cap: float,
    slippage_buffer: float = 0.04,
    fractional_multiplier: float = 0.25
) -> dict:
    import math
    p = float(win_prob)
    ask = float(ask_price)
    if ask <= 0.01 or ask >= 0.99 or p <= 0.0 or p >= 1.0:
        return {"contracts": 0, "ev": 0.0, "reason": "INVALID_PRICE_OR_PROB"}
    effective_entry = min(0.98, ask + slippage_buffer)
    taker_fee = math.ceil(0.07 * effective_entry * (1.0 - effective_entry) * 100.0) / 100.0
    net_win = 1.0 - effective_entry - taker_fee
    net_loss = effective_entry + taker_fee
    ev = (p * net_win) - ((1.0 - p) * net_loss)
    if ev < 0.01:
        logger.info(f"[Kelly] Trade Blocked: Sub-threshold EV (${ev:.4f}/contract < +$0.0100 min).")
        return {"contracts": 0, "ev": round(ev, 4), "reason": "NEGATIVE_OR_NEGLIGIBLE_EV"}
    b_odds = net_win / net_loss
    q = 1.0 - p
    f_star = (p * b_odds - q) / b_odds
    if f_star <= 0.0:
        return {"contracts": 0, "ev": round(ev, 4), "reason": "NON_POSITIVE_KELLY"}
    f_allocated = min(0.15, f_star * fractional_multiplier)
    alloc_budget = min(available_capital * f_allocated, max_position_cap)
    unit_cost = effective_entry + taker_fee
    contracts = int(alloc_budget / unit_cost)
    return {
        "contracts": max(1, contracts) if alloc_budget >= unit_cost else 0,
        "ev": round(ev, 4),
        "f_star": round(f_star, 4),
        "allocated_dollars": round(alloc_budget, 2),
        "effective_entry": round(effective_entry, 2),
        "taker_fee": round(taker_fee, 2)
    }
