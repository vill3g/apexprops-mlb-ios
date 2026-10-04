"""
Empirical Verification & Adversarial Stress Testing Suite
Challenger: challenger_1
Target: Deliverable in EVALUATION_REPORT.md

Tests:
1. Trailing stop mathematical degeneracy proof & fuzzing (M * (1 - D) >= M - D for all M <= 1.0)
2. Kelly criterion fee-omission & exact EV with Kalshi taker fees
3. Section 4 Proposed Code Remediations (4.1 to 4.9) syntax, typing, and logic soundness
4. Empirical database validation of claims against users.db, trades.db, and market_results.json
"""

import math
import os
import sqlite3
import json
import logging
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(REPO_ROOT, "backend", "data")


# ==============================================================================
# 1. TRAILING STOP MATHEMATICAL DEGENERACY VERIFICATION
# ==============================================================================

def test_trailing_stop_degeneracy_algebraic_and_fuzzing():
    """
    Verify the mathematical degeneracy claim:
    Formula: trail_threshold = max(M - D, M * (1.0 - D))
    Claim: M * (1.0 - D) >= M - D for all M <= 1.0, D >= 0.
    Algebraic Proof:
        M * (1.0 - D) - (M - D) = M - M*D - M + D = D * (1 - M).
        Since M <= 1.0, 1 - M >= 0.
        Since D >= 0, D * (1 - M) >= 0.
        Therefore M * (1 - D) >= M - D always holds on [0, 1].
    """
    # 1. Algebraic assertion: D * (1 - M) >= 0
    # Test on full grid of M in [0.01, 1.00] and D in [0.01, 0.50]
    m_steps = [round(i * 0.01, 4) for i in range(1, 101)]  # 0.01 to 1.00
    d_steps = [round(j * 0.01, 4) for j in range(1, 51)]   # 0.01 to 0.50

    violations = []
    dead_code_count = 0
    equal_count = 0

    for M in m_steps:
        for D in d_steps:
            val_percent = M * (1.0 - D)
            val_cents = M - D
            diff = val_percent - val_cents

            # Check if M*(1-D) < M-D ever occurs for M <= 1.0
            if diff < -1e-12:
                violations.append((M, D, val_percent, val_cents, diff))
            
            # Check dead code: max() choice
            chosen = max(val_cents, val_percent)
            assert chosen == pytest.approx(val_percent, abs=1e-9)

            if abs(diff) < 1e-12:
                equal_count += 1
            else:
                dead_code_count += 1

    assert len(violations) == 0, f"Found {len(violations)} violations where M*(1-D) < M-D!"
    # When M = 1.0, both are equal; for all M < 1.0, M*(1-D) is strictly greater
    assert equal_count == len(d_steps)  # exactly when M == 1.00
    assert dead_code_count == len(d_steps) * (len(m_steps) - 1)


def test_trailing_stop_effective_buffer_collapse():
    """
    Demonstrate that for realistic Kalshi prices (M in [0.20, 0.70]) and D = 0.06 (6%),
    the effective buffer is M * D, which collapses below the 2-5 cent bid-ask spread.
    """
    D = 0.06
    test_cases = [
        # (Peak Bid M, Expected Trail Distance M*D, Nominal D)
        (0.70, 0.042, 0.06),  # 4.2 cents vs 6.0 cents
        (0.50, 0.030, 0.06),  # 3.0 cents vs 6.0 cents
        (0.35, 0.021, 0.06),  # 2.1 cents vs 6.0 cents
        (0.20, 0.012, 0.06),  # 1.2 cents vs 6.0 cents
    ]

    for M, expected_distance, nominal_d in test_cases:
        threshold = max(M - D, M * (1.0 - D))
        effective_buffer = M - threshold
        assert effective_buffer == pytest.approx(expected_distance, abs=1e-5)
        # Verify that M - D (nominal 6 cents) was discarded in favor of smaller buffer
        assert threshold > (M - nominal_d)
        assert effective_buffer < nominal_d


# ==============================================================================
# 2. KELLY CRITERION FEE-OMISSION & EXACT MATHEMATICAL EV VERIFICATION
# ==============================================================================

def kalshi_taker_fee_exact(b: float) -> float:
    """Official Kalshi taker fee per contract (cents rounded up to whole cent)."""
    raw = 0.07 * b * (1.0 - b)
    return math.ceil(round(raw * 100.0, 6)) / 100.0


def exact_mathematical_ev(p_win: float, b_price: float, slippage: float = 0.0) -> float:
    """Exact expected value per contract held to settlement."""
    b_eff = min(0.99, b_price + slippage)
    fee = kalshi_taker_fee_exact(b_eff)
    total_cost = b_eff + fee
    # EV = p * (1.0 - total_cost) - (1.0 - p) * total_cost = p - total_cost
    return p_win - total_cost


def test_kelly_fee_omission_proof():
    """
    Verify the claim:
    In executor.py:1046:
        if p_win <= b_price: return None
    This omits Kalshi taker fee.
    For p_win = 0.51 and b_price = 0.50:
    - Code evaluates edge = 0.51 - 0.50 = +0.01 (+1 cent) -> Trade ACCEPTED!
    - True EV with fee = 0.51 - 0.50 - 0.02 = -0.01 (-1 cent) -> Structurally NEGATIVE EV!
    """
    p_win = 0.51
    b_price = 0.50

    # Code evaluation
    code_accepts = (p_win > b_price)
    code_reported_edge = p_win - b_price
    assert code_accepts is True
    assert code_reported_edge == pytest.approx(0.01, abs=1e-6)

    # True EV with Kalshi taker fee
    fee = kalshi_taker_fee_exact(b_price)
    assert fee == 0.02  # ceil(0.07 * 0.25 * 100) / 100 = 0.02
    true_ev = exact_mathematical_ev(p_win, b_price)
    assert true_ev == pytest.approx(-0.01, abs=1e-6)
    assert true_ev < 0.0, "Trade has negative EV despite code accepting it!"


def test_kelly_lower_clamp_25_pct_distortion():
    """
    Verify the claim:
    Line 1050: kelly_frac = min(1.0, max(0.25, edge / 0.15))
    Forces an allocation of AT LEAST 25% of bankroll even when edge is near-zero!
    """
    # Micro edge test
    edge = 0.005  # 0.5 cents edge
    kelly_code = min(1.0, max(0.25, edge / 0.15))
    # Code forces 0.25 (25% allocation!)
    assert kelly_code == 0.25

    # Theoretical Kelly without fee for b=0.50: f* = edge / (1 - b) = 0.005 / 0.50 = 0.01 (1%)
    # Over-allocation factor: 0.25 / 0.01 = 25x!
    theoretical_f = edge / (1.0 - 0.50)
    assert theoretical_f == pytest.approx(0.01, abs=1e-6)
    assert kelly_code / theoretical_f == 25.0


def test_fees_py_calculate_realized_edge_cents_omits_ceil():
    """
    Verify the claim:
    backend/btc/fees.py calculate_realized_edge_cents computes:
        round((p - a - TAKER_FEE_RATE * a * (1.0 - a)) * 100.0, 1)
    Omits math.ceil, calculating 1.75 cents instead of 2.0 cents fee at a = 0.50.
    """
    from backend.btc.fees import calculate_realized_edge_cents, kalshi_order_fee

    ask = 0.50
    prob_percent = 51.0  # 51%

    reported_edge = calculate_realized_edge_cents(prob_percent, ask, slippage_buffer_dollars=0.0)

    # But exact fee charged by Kalshi is 2.0 cents (math.ceil):
    actual_fee_cents = kalshi_order_fee(ask, 1) * 100.0
    assert actual_fee_cents == 2.0

    # True edge with exact fee in cents is 51.0 - 50.0 - 2.0 = -1.0 cent
    exact_edge = round((0.51 - 0.50 - 0.02) * 100.0, 1)
    assert exact_edge == -1.0
    
    # Since we fixed the bug, reported_edge should equal exact_edge
    assert reported_edge == exact_edge


# ==============================================================================
# 3. VERIFICATION OF SECTION 4 CODE REMEDIATIONS (4.1 to 4.9)
# ==============================================================================

# --- Remediation 4.1 ---
def test_remediation_4_1_binary_kelly():
    """Verify Section 4.1 calculate_binary_kelly_position logic."""
    def calculate_binary_kelly_position(
        win_prob: float,
        ask_price: float,
        available_capital: float,
        max_position_cap: float,
        slippage_buffer: float = 0.04,
        fractional_multiplier: float = 0.25
    ) -> dict:
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

    # Test 1: Sub-threshold EV (51% win prob @ 50c ask) should be blocked!
    res1 = calculate_binary_kelly_position(0.51, 0.50, 100.0, 50.0)
    assert res1["contracts"] == 0
    assert res1["reason"] == "NEGATIVE_OR_NEGLIGIBLE_EV"

    # Test 2: Strong edge (70% win prob @ 50c ask)
    res2 = calculate_binary_kelly_position(0.70, 0.50, 1000.0, 100.0)
    assert res2["contracts"] > 0
    assert res2["ev"] > 0.01
    assert res2["f_star"] > 0.0
    # No artificial 25% floor: f_allocated is capped at 15%
    assert res2["allocated_dollars"] <= 100.0

    # Test 3: Micro bankroll where budget < unit_cost returns 0
    res3 = calculate_binary_kelly_position(0.70, 0.50, 1.0, 100.0)
    assert res3["contracts"] == 0


# --- Remediation 4.2 ---
def test_remediation_4_2_exit_discipline():
    """Verify Section 4.2 evaluate_exit_discipline logic."""
    def evaluate_exit_discipline(trade: dict, current_bid: float, spot_price: float, strike_price: float, seconds_left: int) -> dict:
        entry_price = float(trade.get("entry_price", 0.50))
        direction = str(trade.get("direction", "ABOVE")).upper()
        if current_bid >= 0.88:
            return {"should_close": True, "reason": "NEAR_CERTAINTY_TAKE_PROFIT", "exit_price": current_bid}
        spot_deficit = (strike_price - spot_price) if direction in ["ABOVE", "YES"] else (spot_price - strike_price)
        if spot_deficit > 75.0 and seconds_left > 300:
            return {"should_close": True, "reason": "STRUCTURAL_SPOT_INVALIDATION", "exit_price": current_bid}
        return {"should_close": False, "reason": "HOLD_TO_SETTLEMENT"}

    trade = {"entry_price": 0.50, "direction": "ABOVE"}
    # 1. Normal hold to settlement
    assert evaluate_exit_discipline(trade, 0.65, 65100, 65000, 400)["should_close"] is False

    # 2. Near certainty TP at 0.88
    res_tp = evaluate_exit_discipline(trade, 0.89, 65300, 65000, 200)
    assert res_tp["should_close"] is True
    assert res_tp["reason"] == "NEAR_CERTAINTY_TAKE_PROFIT"

    # 3. Structural spot invalidation (> $75 deficit with > 300s left)
    res_inv = evaluate_exit_discipline(trade, 0.30, 64900, 65000, 400)
    assert res_inv["should_close"] is True
    assert res_inv["reason"] == "STRUCTURAL_SPOT_INVALIDATION"

    # 4. Same spot deficit with < 300s left holds for settlement jump
    res_late = evaluate_exit_discipline(trade, 0.30, 64900, 65000, 150)
    assert res_late["should_close"] is False
    assert res_late["reason"] == "HOLD_TO_SETTLEMENT"


# --- Remediation 4.3 ---
def test_remediation_4_3_reentry_guard():
    """Verify Section 4.3 is_reentry_permitted logic."""
    logger = logging.getLogger("test")
    def is_reentry_permitted(user_history: list, current_ticker: str, last_exit_reason: str, seconds_left: int) -> bool:
        if "STOP_LOSS" in str(last_exit_reason).upper() or "INVALIDATION" in str(last_exit_reason).upper():
            return False
        interval_trades = [t for t in user_history if t.get("ticker") == current_ticker]
        if len(interval_trades) >= 1:
            return False
        if seconds_left < 210:
            return False
        return True

    # 1. Blocked after stop loss
    assert is_reentry_permitted([], "KXBT-15M", "CONTRACT_STOP_LOSS", 600) is False

    # 2. Blocked if interval already traded
    history = [{"ticker": "KXBT-15M"}]
    assert is_reentry_permitted(history, "KXBT-15M", "TAKE_PROFIT", 600) is False

    # 3. Blocked if seconds_left < 210
    assert is_reentry_permitted([], "KXBT-15M", "TAKE_PROFIT", 150) is False

    # 4. Permitted for fresh interval with > 210s left
    assert is_reentry_permitted([], "KXBT-15M", "TAKE_PROFIT", 600) is True


# --- Remediation 4.4 ---
def test_remediation_4_4_anti_whipsaw_trailing_stop():
    """Verify Section 4.4 calculate_anti_whipsaw_trailing_stop logic."""
    def calculate_anti_whipsaw_trailing_stop(
        entry_price: float,
        max_seen_bid: float,
        current_bid: float,
        ts_activation_pct: float = 40.0,
        ts_distance_pct: float = 15.0,
        min_buffer_cents: float = 0.12
    ) -> dict:
        profit_pct = ((max_seen_bid - entry_price) / entry_price) * 100.0
        if profit_pct < ts_activation_pct:
            return {"should_exit": False}
        percentage_distance = max_seen_bid * (ts_distance_pct / 100.0)
        effective_trail_distance = max(min_buffer_cents, percentage_distance)
        stop_threshold = max_seen_bid - effective_trail_distance
        breakeven_floor = entry_price + 0.04
        stop_threshold = max(stop_threshold, breakeven_floor)
        if current_bid <= stop_threshold:
            return {
                "should_exit": True,
                "exit_threshold": round(stop_threshold, 2),
                "current_bid": round(current_bid, 2),
                "reason": "ANTI_WHIPSAW_TRAILING_STOP"
            }
        return {"should_exit": False, "stop_threshold": round(stop_threshold, 2)}

    # Entry 0.50, Peak 0.72 (+44% profit, exceeds 40% activation)
    # percentage_distance = 0.72 * 0.15 = 0.108
    # effective_trail_distance = max(0.12, 0.108) = 0.12
    # stop_threshold = 0.72 - 0.12 = 0.60
    # breakeven_floor = 0.50 + 0.04 = 0.54 -> threshold is 0.60
    res = calculate_anti_whipsaw_trailing_stop(0.50, 0.72, 0.65)
    assert res["should_exit"] is False
    assert res["stop_threshold"] == 0.60

    # Bid drops to 0.59 (below 0.60 threshold)
    res_trigger = calculate_anti_whipsaw_trailing_stop(0.50, 0.72, 0.59)
    assert res_trigger["should_exit"] is True
    assert res_trigger["exit_threshold"] == 0.60

    # Profit < 40% (peak 0.60, profit 20%) should not activate
    res_unact = calculate_anti_whipsaw_trailing_stop(0.50, 0.60, 0.55)
    assert res_unact["should_exit"] is False


# --- Remediation 4.5 ---
def test_remediation_4_5_execution_signal():
    """Verify Section 4.5 determine_execution_signal logic."""
    def determine_execution_signal(model_prob: float, heuristic_grade: str, is_force_flag: bool) -> dict:
        MINIMUM_CONVICTION = 60.0
        if model_prob < MINIMUM_CONVICTION:
            return {
                "execute": False,
                "direction": "PASS",
                "reason": f"INSUFFICIENT_CONVICTION: Model {model_prob:.1f}% < {MINIMUM_CONVICTION}% required"
            }
        direction = "YES" if model_prob >= 50.0 else "NO"
        return {"execute": True, "direction": direction, "conviction": model_prob}

    # 1. 51% coinflip is strictly blocked
    res_coinflip = determine_execution_signal(51.0, "GRADE B", True)
    assert res_coinflip["execute"] is False
    assert res_coinflip["direction"] == "PASS"

    # 2. 65% conviction executes
    res_high = determine_execution_signal(65.0, "GRADE A", False)
    assert res_high["execute"] is True
    assert res_high["direction"] == "YES"


# --- Remediation 4.6 ---
def test_remediation_4_6_realized_edge_cents():
    """Verify Section 4.6 calculate_realized_edge_cents logic."""
    def calculate_realized_edge_cents(
        prob_percent: float, 
        ask_price: float, 
        slippage_buffer_dollars: float = 0.04
    ) -> float:
        p = float(prob_percent) / 100.0
        ask = float(ask_price)
        fill_price = min(0.99, ask + slippage_buffer_dollars)
        exact_taker_fee = math.ceil(0.07 * fill_price * (1.0 - fill_price) * 100.0) / 100.0
        expected_value_dollars = (p * (1.0 - fill_price - exact_taker_fee)) - ((1.0 - p) * (fill_price + exact_taker_fee))
        return round(expected_value_dollars * 100.0, 2)

    # 51% win prob, 50c ask + 4c slippage = 54c fill, 2c fee -> 56c total cost
    # EV = 0.51 - 0.56 = -0.05 dollars = -5.0 cents
    edge1 = calculate_realized_edge_cents(51.0, 0.50, 0.04)
    assert edge1 == -5.0

    # 70% win prob, 50c ask + 4c slippage = 54c fill, 2c fee -> 56c total cost
    # EV = 0.70 - 0.56 = +0.14 dollars = +14.0 cents
    edge2 = calculate_realized_edge_cents(70.0, 0.50, 0.04)
    assert edge2 == 14.0


# --- Remediation 4.7 ---
def test_remediation_4_7_market_structure_confluence():
    """Verify Section 4.7 check_kalshi_market_structure_confluence logic."""
    def check_kalshi_market_structure_confluence(kalshi_market: dict, thresholds: dict) -> dict:
        if not kalshi_market:
            return {"override": False}
        raw_yes = float(kalshi_market.get("yes_ask", 0.50) or 0.50)
        raw_no = float(kalshi_market.get("no_ask", 0.50) or 0.50)
        yes_cents = raw_yes * 100.0 if raw_yes <= 1.0 else raw_yes
        no_cents = raw_no * 100.0 if raw_no <= 1.0 else raw_no
        imbalance = float(kalshi_market.get("book_imbalance", 0.0) or 0.0)
        target_yes = float(thresholds.get("kalshi_override_yes", 62.0))
        target_imbalance = float(thresholds.get("kalshi_imbalance_threshold", 0.35))
        if yes_cents >= target_yes or imbalance >= target_imbalance:
            return {"override": True, "direction": "YES", "implied_prob": yes_cents, "imbalance": imbalance}
        return {"override": False}

    thresholds = {"kalshi_override_yes": 62.0, "kalshi_imbalance_threshold": 0.35}
    # Market price in dollars (0.65 -> 65 cents) triggers override
    res1 = check_kalshi_market_structure_confluence({"yes_ask": 0.65, "book_imbalance": 0.10}, thresholds)
    assert res1["override"] is True
    assert res1["implied_prob"] == 65.0

    # Market price 0.52 (52 cents < 62) does not trigger
    res2 = check_kalshi_market_structure_confluence({"yes_ask": 0.52, "book_imbalance": 0.10}, thresholds)
    assert res2["override"] is False


# --- Remediation 4.8 ---
def test_remediation_4_8_entry_timing_valid():
    """Verify Section 4.8 is_entry_timing_valid logic."""
    def is_entry_timing_valid(seconds_left: int, timeframe_seconds: int = 900) -> dict:
        seconds_elapsed = timeframe_seconds - seconds_left
        minute_elapsed = seconds_elapsed // 60
        if seconds_left < 210:
            return {"valid": False, "reason": f"TERMINAL_GAMMA_LOCK: {seconds_left}s remaining < 210s minimum corridor"}
        if 3 <= minute_elapsed <= 6:
            return {"valid": False, "reason": f"TOXIC_TIMING_WINDOW: Minute {minute_elapsed} (opening drive mean-reversion trap)"}
        return {"valid": True, "minute": minute_elapsed, "seconds_left": seconds_left}

    # 1. Minute 0 (900s left) is valid
    assert is_entry_timing_valid(900)["valid"] is True
    # 2. Minute 4 (660s left: elapsed 240s -> min 4) is blocked
    assert is_entry_timing_valid(660)["valid"] is False
    # 3. Minute 8 (420s left: elapsed 480s -> min 8) is valid
    assert is_entry_timing_valid(420)["valid"] is True
    # 4. Terminal zone (150s left < 210s) is blocked
    assert is_entry_timing_valid(150)["valid"] is False


# --- Remediation 4.9 ---
def test_remediation_4_9_interval_circuit_breaker():
    """Verify Section 4.9 evaluate_consecutive_interval_circuit_breaker logic."""
    def evaluate_consecutive_interval_circuit_breaker(today_trades: list, max_consecutive_losing_intervals: int = 3) -> str:
        interval_pnl_map = {}
        for trade in sorted(today_trades, key=lambda x: str(x.get("timestamp", ""))):
            ticker = trade.get("ticker")
            if trade.get("status") in ["SETTLED", "CLOSED"]:
                pnl = float(trade.get("pnl", 0.0))
                interval_pnl_map.setdefault(ticker, []).append(pnl)
        consecutive_losses = 0
        for ticker in reversed(list(interval_pnl_map.keys())):
            net_interval_pnl = sum(interval_pnl_map[ticker])
            if net_interval_pnl < 0.0:
                consecutive_losses += 1
                if consecutive_losses >= max_consecutive_losing_intervals:
                    return f"CIRCUIT_BREAKER_ACTIVE: {consecutive_losses} consecutive losing INTERVALS. Halting trading."
            else:
                break
        return "OK"

    # 3 consecutive losing intervals trips breaker
    trades = [
        {"ticker": "KXBT-15M-01", "status": "SETTLED", "pnl": -5.0, "timestamp": "2026-10-03T10:00:00Z"},
        {"ticker": "KXBT-15M-02", "status": "SETTLED", "pnl": -3.0, "timestamp": "2026-10-03T10:15:00Z"},
        {"ticker": "KXBT-15M-03", "status": "SETTLED", "pnl": -4.0, "timestamp": "2026-10-03T10:30:00Z"},
    ]
    res = evaluate_consecutive_interval_circuit_breaker(trades, 3)
    assert "CIRCUIT_BREAKER_ACTIVE" in res

    # Winning interval breaks streak
    trades_with_win = trades + [
        {"ticker": "KXBT-15M-04", "status": "SETTLED", "pnl": +10.0, "timestamp": "2026-10-03T10:45:00Z"}
    ]
    res_ok = evaluate_consecutive_interval_circuit_breaker(trades_with_win, 3)
    assert res_ok == "OK"


# ==============================================================================
# 4. EMPIRICAL DATABASE INTEGRITY & CLAIM RECONCILIATION
# ==============================================================================

def test_database_users_db_claims_empirical_reconciliation():
    """
    Directly query backend/data/users.db to verify:
    - 2,150 trades
    - Net PnL is -$814.90
    - Win rate is ~51.7%
    - SETTLEMENT exits vs STOP_LOSS exits
    """
    db_path = os.path.join(DATA_DIR, "users.db")
    assert os.path.isfile(db_path), f"users.db not found at {db_path}"

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Query trades table
    c.execute("SELECT count(*), sum(pnl), sum(case when pnl > 0 then 1 else 0 end) FROM trades")
    total_trades, total_pnl, total_wins = c.fetchone()
    
    # In users.db there are 2151 total rows (2145 closed, 6 open, or 2150 evaluated in report)
    assert total_trades in (2150, 2151)
    assert total_pnl == pytest.approx(-814.90, abs=0.50), f"Expected -$814.90 net PnL, found {total_pnl}"
    win_rate = (total_wins / total_trades) * 100.0
    assert win_rate == pytest.approx(51.72, abs=0.5), f"Expected ~51.72% win rate, found {win_rate}%"

    # Exit reason breakdown using standardized categories
    c.execute("""
        SELECT 
            CASE 
                WHEN exit_reason LIKE 'SETTLE%' THEN 'SETTLEMENT'
                WHEN exit_reason LIKE 'TAKE_PROFIT%' THEN 'TAKE_PROFIT'
                WHEN exit_reason LIKE 'STOP_LOSS%' OR exit_reason LIKE 'CONTRACT_STOP%' OR exit_reason LIKE 'TRAILING_STOP%' THEN 'STOP_LOSS'
                WHEN exit_reason LIKE 'MANUAL%' THEN 'MANUAL_CLOSE'
                ELSE 'OTHER'
            END as cat,
            count(*), 
            sum(pnl), 
            sum(case when pnl > 0 then 1 else 0 end)
        FROM trades
        GROUP BY cat
    """)
    exit_breakdown = {r[0]: (r[1], r[2], r[3]) for r in c.fetchall()}

    # Check SETTLEMENT: net positive > +$1800
    if "SETTLEMENT" in exit_breakdown:
        settle_count, settle_pnl, settle_wins = exit_breakdown["SETTLEMENT"]
        assert settle_count >= 270
        assert settle_pnl > 1800.0
        assert (settle_wins / settle_count) * 100.0 >= 70.0

    # Check STOP_LOSS: net negative < -$4500
    if "STOP_LOSS" in exit_breakdown:
        sl_count, sl_pnl, sl_wins = exit_breakdown["STOP_LOSS"]
        assert sl_count >= 800
        assert sl_pnl < -4500.0

    conn.close()


def test_database_trades_db_claims_empirical_reconciliation():
    """
    Directly query backend/data/trades.db to verify:
    - 747 trades
    - Net PnL is -$7,350.19
    - Win rate is ~50.2%
    """
    db_path = os.path.join(DATA_DIR, "trades.db")
    assert os.path.isfile(db_path), f"trades.db not found at {db_path}"

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT count(*), sum(pnl), sum(case when pnl > 0 then 1 else 0 end) FROM trades")
    total_trades, total_pnl, total_wins = c.fetchone()

    assert total_trades == 747, f"Expected 747 trades in trades.db, found {total_trades}"
    assert total_pnl == pytest.approx(-7350.19, abs=1.0), f"Expected -$7350.19 net PnL, found {total_pnl}"
    win_rate = (total_wins / total_trades) * 100.0
    assert win_rate == pytest.approx(50.20, abs=0.5), f"Expected ~50.20% win rate, found {win_rate}%"

    conn.close()


# ==============================================================================
# 5. ADVERSARIAL STRESS TESTING: INEQUALITY INVERSION & BOUNDARY STRESS
# ==============================================================================

def test_trailing_stop_inequality_inversion_equity_vs_binary():
    """
    Adversarial Root Cause Discovery:
    In equity / crypto spot (where M >> 1.0, e.g. BTC at $60,000):
        M - D = 60000 - 0.06 = 59999.94  (cents trail)
        M * (1 - D) = 60000 * 0.94 = 56400.0 (percentage trail)
    Here, M - D > M * (1 - D). The developer intended to take the tighter stop!
    
    BUT in binary options, where M <= 1.0:
        D * (1 - M) >= 0, so M * (1 - D) >= M - D.
    The inequality completely inverts!
    The percentage threshold is strictly tighter than the cents threshold,
    reducing trailing stop distance to M * D (1.2 to 4.2 cents),
    instantly getting stopped out by Kalshi's 2-5 cent bid-ask spread!
    """
    D = 0.06
    # 1. Spot equity regime (M >> 1.0)
    spot_btc = 65000.0
    thresh_cents_spot = spot_btc - D
    thresh_pct_spot = spot_btc * (1.0 - D)
    assert thresh_cents_spot > thresh_pct_spot  # In spot, M - D is higher/tighter

    # 2. Binary option regime (M <= 1.0)
    for binary_bid in [0.95, 0.70, 0.50, 0.35, 0.20]:
        thresh_cents_bin = binary_bid - D
        thresh_pct_bin = binary_bid * (1.0 - D)
        assert thresh_pct_bin >= thresh_cents_bin  # In binary, M*(1-D) is higher/tighter
        # Buffer difference D*(1 - M)
        buffer_diff = thresh_pct_bin - thresh_cents_bin
        assert buffer_diff == pytest.approx(D * (1.0 - binary_bid), abs=1e-6)


def test_kelly_negative_ev_zone_surface():
    """
    Compute the exact 2D surface of (p, b) where existing code evaluates as positive edge
    (p > b) but exact mathematical EV is negative (p < b + F_in).
    """
    false_positive_trades = []
    for b_int in range(10, 91):  # b from 0.10 to 0.90
        b = b_int / 100.0
        fee = kalshi_taker_fee_exact(b)
        for p_int in range(10, 95):  # p from 0.10 to 0.95
            p = p_int / 100.0
            # Existing code condition:
            code_accepts = (p > b)
            # True EV condition:
            true_ev = p - (b + fee)
            
            if code_accepts and true_ev < 0:
                false_positive_trades.append((b, p, p - b, fee, true_ev))

    # In 1-cent discrete steps across b in [0.10, 0.90], exactly 81 price points produce false-positive entries
    assert len(false_positive_trades) == 81
    # Every single one has fee >= 0.01 and true_ev <= 0
    for b, p, nominal_edge, fee, ev in false_positive_trades:
        assert nominal_edge <= fee
        assert ev <= 0.0


def test_remediations_adversarial_boundary_inputs():
    """
    Stress-test remediations with boundary, invalid, and malformed inputs.
    """
    # 4.1 Boundary checks: Zero capital / zero max_cap
    def kelly_calc(p, ask, cap, max_cap):
        if ask <= 0.01 or ask >= 0.99 or p <= 0.0 or p >= 1.0:
            return 0
        effective_entry = min(0.98, ask + 0.04)
        taker_fee = math.ceil(0.07 * effective_entry * (1.0 - effective_entry) * 100.0) / 100.0
        net_win = 1.0 - effective_entry - taker_fee
        net_loss = effective_entry + taker_fee
        ev = (p * net_win) - ((1.0 - p) * net_loss)
        if ev < 0.01:
            return 0
        b_odds = net_win / net_loss
        f_star = (p * b_odds - (1 - p)) / b_odds
        if f_star <= 0.0:
            return 0
        f_allocated = min(0.15, f_star * 0.25)
        alloc_budget = min(cap * f_allocated, max_cap)
        unit_cost = effective_entry + taker_fee
        contracts = int(alloc_budget / unit_cost)
        return max(1, contracts) if alloc_budget >= unit_cost else 0

    assert kelly_calc(0.70, 0.50, 0.0, 100.0) == 0
    assert kelly_calc(0.70, 0.50, 100.0, 0.0) == 0
    assert kelly_calc(0.0, 0.50, 1000.0, 100.0) == 0
    assert kelly_calc(1.0, 0.50, 1000.0, 100.0) == 0
    assert kelly_calc(0.70, 0.0, 1000.0, 100.0) == 0
    assert kelly_calc(0.70, 1.0, 1000.0, 100.0) == 0

    # 4.4 Boundary checks: Peak bid equals or less than entry
    def trail_calc(entry, peak, bid):
        profit_pct = ((peak - entry) / entry) * 100.0 if entry > 0 else 0
        if profit_pct < 40.0:
            return False
        effective_dist = max(0.12, peak * 0.15)
        thresh = max(peak - effective_dist, entry + 0.04)
        return bid <= thresh

    assert trail_calc(0.50, 0.50, 0.45) is False  # 0% profit -> False
    assert trail_calc(0.50, 0.40, 0.35) is False  # negative profit -> False

    # 4.8 Timing boundaries: Minute transitions
    def timing_valid(sec_left):
        elapsed_min = (900 - sec_left) // 60
        if sec_left < 210:
            return False
        if 3 <= elapsed_min <= 6:
            return False
        return True

    assert timing_valid(900) is True   # 0m0s -> True
    assert timing_valid(721) is True   # 2m59s elapsed -> True
    assert timing_valid(720) is False  # 3m00s elapsed -> False
    assert timing_valid(481) is False  # 6m59s elapsed -> False
    assert timing_valid(480) is True   # 7m00s elapsed -> True
    assert timing_valid(210) is True   # exactly 210s left -> True
    assert timing_valid(209) is False  # 209s left -> False

