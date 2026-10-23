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
    fractional_multiplier: float = 0.25,
    is_unanimous: bool = False,
    agreement_ratio: float = None,
    **kwargs
) -> dict:
    """
    Closed-form binary options Kelly Criterion position sizing:
        f* = (p - C) / (1.0 - C)
    where C = effective_entry + taker_fee.

    Consensus Amplification:
    - Unanimous 3/3 consensus (agreement_ratio == 1.0 or is_unanimous == True):
      Half-Kelly (lambda = 0.50), doubling position size vs majority.
    - Majority 2/3 consensus (agreement_ratio >= 0.65):
      Quarter-Kelly (lambda = 0.25).
    - Low consensus (< 2/3):
      0 allocation (PASS).
    - Single-trade bankroll cap: 15% of available capital.
    """
    import math
    try:
        p = float(win_prob)
        ask = float(ask_price)
        cap = max(0.0, float(available_capital))
        pos_cap = max(0.0, float(max_position_cap))
    except (TypeError, ValueError):
        return {"contracts": 0, "ev": 0.0, "reason": "INVALID_PRICE_OR_PROB"}

    if ask <= 0.01 or ask >= 0.99 or p <= 0.0 or p >= 1.0:
        return {"contracts": 0, "ev": 0.0, "reason": "INVALID_PRICE_OR_PROB"}

    if cap <= 0.0 or pos_cap <= 0.0:
        return {"contracts": 0, "ev": 0.0, "allocated_dollars": 0.0, "reason": "ZERO_AVAILABLE_CAPITAL"}

    effective_entry = min(0.98, ask + float(slippage_buffer))
    taker_fee = math.ceil(0.07 * effective_entry * (1.0 - effective_entry) * 100.0) / 100.0
    total_cost_c = effective_entry + taker_fee  # C: capital invested per contract

    if total_cost_c >= 1.0:
        return {"contracts": 0, "ev": 0.0, "reason": "NON_POSITIVE_KELLY"}

    net_win = 1.0 - total_cost_c
    net_loss = total_cost_c
    ev = (p * net_win) - ((1.0 - p) * net_loss)

    if ev < 0.01:
        logger.info(f"[Kelly] Trade Blocked: Sub-threshold EV (${ev:.4f}/contract < +$0.0100 min).")
        return {"contracts": 0, "ev": round(ev, 4), "reason": "NEGATIVE_OR_NEGLIGIBLE_EV"}

    # Exact closed-form binary options Kelly formula: f* = (p - C) / (1.0 - C)
    f_star = (p - total_cost_c) / (1.0 - total_cost_c)
    if f_star <= 0.0:
        return {"contracts": 0, "ev": round(ev, 4), "reason": "NON_POSITIVE_KELLY"}

    # Consensus Amplification Lambda
    if agreement_ratio is not None:
        if agreement_ratio >= 0.99 or is_unanimous:
            lambda_val = 0.50
        elif agreement_ratio >= 0.65:
            lambda_val = 0.25
        else:
            lambda_val = 0.0
    elif is_unanimous:
        lambda_val = 0.50
    else:
        lambda_val = float(fractional_multiplier)

    if lambda_val <= 0.0:
        return {
            "contracts": 0,
            "ev": round(ev, 4),
            "f_star": round(f_star, 4),
            "allocated_dollars": 0.0,
            "reason": "LOW_CONSENSUS"
        }

    # Bound by 15% single-trade bankroll cap
    f_allocated = min(0.15, f_star * lambda_val)
    alloc_budget = min(cap * f_allocated, pos_cap)
    unit_cost = total_cost_c
    contracts = int(alloc_budget / unit_cost)

    is_unanimous_flag = bool(is_unanimous or (agreement_ratio is not None and agreement_ratio >= 0.99))
    agree_ratio_val = agreement_ratio if agreement_ratio is not None else (1.0 if is_unanimous_flag else 0.67)

    return {
        "contracts": max(1, contracts) if alloc_budget >= unit_cost else 0,
        "recommended_contracts": max(1, contracts) if alloc_budget >= unit_cost else 0,
        "ev": round(ev, 4),
        "f_star": round(f_star, 4),
        "kelly_fraction": round(lambda_val, 2),
        "f_allocated": round(f_allocated, 4),
        "allocated_dollars": round(alloc_budget, 2),
        "effective_entry": round(effective_entry, 2),
        "taker_fee": round(taker_fee, 2),
        "unit_cost": round(unit_cost, 2),
        "is_unanimous": is_unanimous_flag,
        "agreement_ratio": round(agree_ratio_val, 2),
        "reason": "OK" if (alloc_budget >= unit_cost and contracts >= 1) else ("INSUFFICIENT_BUDGET" if alloc_budget < unit_cost else "ZERO_CONTRACTS")
    }


def calculate_kelly_wager(
    p_win: float,
    ask_price: float,
    bankroll: float,
    is_unanimous: bool = False,
    agreement_ratio: float = None,
    max_position_cap: float = None,
    slippage_buffer: float = 0.04,
    **kwargs
) -> dict:
    """
    Convenience wrapper for calculate_binary_kelly_position adhering to PROJECT.md interface contract.
    """
    cap = max_position_cap if max_position_cap is not None else bankroll
    return calculate_binary_kelly_position(
        win_prob=p_win,
        ask_price=ask_price,
        available_capital=bankroll,
        max_position_cap=cap,
        slippage_buffer=slippage_buffer,
        is_unanimous=is_unanimous,
        agreement_ratio=agreement_ratio,
        **kwargs
    )

