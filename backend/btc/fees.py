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


def entry_edge_cents(prob_percent: float, ask: float) -> float:
    """Expected profit per contract, in cents, of buying one contract at `ask` when that side
    wins with probability prob_percent, after the taker entry fee. Held to settlement there is
    no exit fee. Positive = the price is cheaper than the forecast says it is worth."""
    p = float(prob_percent) / 100.0
    a = min(max(float(ask), 0.0), 1.0)
    return round((p - a - TAKER_FEE_RATE * a * (1.0 - a)) * 100.0, 1)


def net_pnl(entry: float, exit_price: float, count: float) -> float:
    """Realized P&L after the entry fee and (if sold before expiry) the exit fee."""
    gross = (float(exit_price) - float(entry)) * float(count)
    return round(gross - kalshi_order_fee(entry, count) - kalshi_order_fee(exit_price, count), 4)
