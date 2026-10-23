"""
Unit tests for PortfolioGovernor: Cross-Universe Capital Coordination,
In-Flight Cash Reservations, Pre-Cached Balances, and Global Circuit Breakers.
"""
import time
from unittest.mock import MagicMock
import pytest

from backend.engine.portfolio_governor import PortfolioGovernor, get_portfolio_governor


def test_portfolio_governor_singleton():
    gov1 = get_portfolio_governor()
    gov2 = PortfolioGovernor()
    assert gov1 is gov2


def test_balance_caching_and_staleness():
    gov = get_portfolio_governor()
    uid = 88888
    gov.update_cached_balance(uid, 500.0)
    assert gov.get_cached_balance(uid, max_age_seconds=5.0) == 500.0

    # Simulate expired cache
    gov._balance_cache[uid]["updated_at"] = time.time() - 10.0
    assert gov.get_cached_balance(uid, max_age_seconds=5.0) is None


def test_cross_universe_capital_reservation_lifecycle():
    gov = get_portfolio_governor()
    uid = 99999
    gov.update_cached_balance(uid, 100.0)

    # 1. User has $100 effective available
    user = {"id": uid, "trading_mode": "LIVE"}
    avail = gov.get_effective_available_balance(user, max_cache_age=10.0)
    assert avail == 100.0

    # 2. Sports universe places an order and reserves $25
    res_id_sports = "sports_res_1"
    gov.reserve_capital(uid, 25.0, "SPORTS", "KXNFLGAME-1", res_id_sports)

    # Effective available capital drops immediately to $75 for Financial universe
    avail_after_sports = gov.get_effective_available_balance(user, max_cache_age=10.0)
    assert avail_after_sports == 75.0

    # 3. Financial universe attempts trade and reserves $50
    res_id_fin = "fin_res_1"
    gov.reserve_capital(uid, 50.0, "FINANCIAL", "KXBTCD-1", res_id_fin)

    # Effective available capital drops to $25
    avail_after_both = gov.get_effective_available_balance(user, max_cache_age=10.0)
    assert avail_after_both == 25.0

    # 4. Financial order fills with $48.50 actual cost
    gov.release_capital(res_id_fin, actual_deducted_cost=48.50, user_id=uid)
    # Reservation released, balance adjusted to 100 - 48.50 = 51.50
    # Remaining reservation: Sports $25 -> Effective available: 51.50 - 25 = 26.50
    avail_after_fin_fill = gov.get_effective_available_balance(user, max_cache_age=10.0)
    assert pytest.approx(avail_after_fin_fill, 0.01) == 26.50

    # 5. Sports order cancels/fails (actual_deducted=0.0)
    gov.release_capital(res_id_sports, actual_deducted_cost=0.0, user_id=uid)
    avail_final = gov.get_effective_available_balance(user, max_cache_age=10.0)
    assert pytest.approx(avail_final, 0.01) == 51.50


def test_paper_mode_capital_reservation():
    gov = get_portfolio_governor()
    uid = 77777
    user = {"id": uid, "trading_mode": "PAPER", "paper_balance": 250.0}

    assert gov.get_effective_available_balance(user) == 250.0
    res_id = "paper_res_1"
    gov.reserve_capital(uid, 50.0, "SPORTS", "KXATPMATCH-1", res_id)
    assert gov.get_effective_available_balance(user) == 200.0
    gov.release_capital(res_id)
    assert gov.get_effective_available_balance(user) == 250.0


def test_global_circuit_breaker_logic():
    gov = get_portfolio_governor()
    uid = 66666
    user = {
        "id": uid,
        "trading_mode": "LIVE",
        "max_daily_risk": 50.0,
        "sports_max_daily_risk": 40.0
    }

    # Under limit
    from unittest.mock import patch
    with patch("backend.database.trade_store.TradeStore.get_today_activity", return_value={"realized": -10.0, "open_cost": 15.0}):
        tripped, reason = gov.check_global_circuit_breaker(user)
        assert not tripped
        assert reason is None

    # Over limit (-60 > 50 risk cap)
    with patch("backend.database.trade_store.TradeStore.get_today_activity", return_value={"realized": -45.0, "open_cost": 20.0}):
        tripped, reason = gov.check_global_circuit_breaker(user)
        assert tripped
        assert "Global portfolio daily risk limit reached" in reason
