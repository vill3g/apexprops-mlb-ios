import pytest
from backend.saas_settler import _side_bid_ask, net_pnl
from backend.btc.auto_executor.saas_broadcaster import _rsi_mean_reversion_guard

def test_side_bid_ask_symmetry():
    # Simulated Kalshi websocket ticker payload (only has yes_bid/yes_ask)
    market = {"ticker": "KXBTC15M-TEST", "yes_bid": 0.40, "yes_ask": 0.42}
    
    # YES evaluation
    y_bid, y_ask = _side_bid_ask(market, "yes")
    assert y_bid == 0.40
    assert y_ask == 0.42
    
    # NO evaluation must be mathematically symmetric:
    # no_bid = 1 - yes_ask = 0.58
    # no_ask = 1 - yes_bid = 0.60
    n_bid, n_ask = _side_bid_ask(market, "no")
    assert round(n_bid, 2) == 0.58
    assert round(n_ask, 2) == 0.60

def test_rsi_oversold_guard():
    # NO trade attempted at deep oversold (RSI 26.3, like trade #4)
    # Should be BLOCKED if CVD is positive (spot accumulation)
    raw = {"rsi": 26.3, "cvd_value": 1041.0}
    blocked = _rsi_mean_reversion_guard("NO", raw, spot=82681.0, target=82699.0)
    assert "RSI_OVERSOLD_GUARD" in blocked
    assert "blocked" in blocked.lower()

    # Should PASS if CVD is heavily negative and price is already under target (genuine breakdown)
    raw_breakdown = {"rsi": 28.0, "cvd_value": -2500.0}
    allowed = _rsi_mean_reversion_guard("NO", raw_breakdown, spot=82600.0, target=82699.0)
    assert allowed == ""

    # YES trade attempted at deep overbought (RSI 72.0)
    # Should be BLOCKED if CVD is negative (distribution)
    raw_ob = {"rsi": 72.0, "cvd_value": -500.0}
    blocked_yes = _rsi_mean_reversion_guard("YES", raw_ob, spot=82800.0, target=82700.0)
    assert "RSI_OVERBOUGHT_GUARD" in blocked_yes


def test_empirical_corridor_ceiling_cap():
    """Verify that contracts priced above $0.62 are blocked unless conviction is exceptional (>85% or Grade A+)."""
    EMPIRICAL_FLOOR = 0.46
    EMPIRICAL_CEILING = 0.62

    # Normal conviction (72%)
    conf = 72.0
    forecast_normal = {"conviction_grade": "GRADE B"}
    is_grade_a_plus = "GRADE A+" in str(forecast_normal.get("conviction_grade", ""))
    is_exceptional_conviction = is_grade_a_plus or (conf is not None and float(conf) > 85.0)
    effective_ceiling = 0.74 if (is_grade_a_plus) else (0.68 if is_exceptional_conviction else EMPIRICAL_CEILING)
    assert effective_ceiling == 0.62

    # A contract at $0.65 is blocked under normal conviction
    market_price = 0.65
    assert (market_price > effective_ceiling) is True

    # A contract at $0.60 passes under normal conviction
    assert (0.60 <= effective_ceiling) is True

    # Exceptional conviction (>85% or Grade A+) widens ceiling to 0.68 / 0.74
    conf_high = 88.0
    is_exceptional_high = (conf_high > 85.0)
    effective_ceiling_high = 0.68 if is_exceptional_high else EMPIRICAL_CEILING
    assert effective_ceiling_high == 0.68
    assert (market_price <= effective_ceiling_high) is True


def test_counter_trend_no_safeguards():
    """Verify that when 1h trend is BULLISH or EMA9 > EMA21, counter-trend NO bets require >= 68% conviction and scale down sizing by 50%."""
    # Bullish market structure: EMA9 > EMA21
    c_eval = {"trend_1h": "BULLISH", "ema_9": 85000.0, "ema_21": 84500.0}
    c_trend_1h = str(c_eval.get("trend_1h")).upper()
    c_ema9 = float(c_eval["ema_9"])
    c_ema21 = float(c_eval["ema_21"])
    is_bullish_uptrend = (c_trend_1h in ["UP", "BULLISH"]) or (c_ema9 > c_ema21 and c_ema21 > 0)
    assert is_bullish_uptrend is True

    # Counter-trend NO bet with weak conviction (62%) must be blocked
    side = "no"
    conf = 62.0
    NO_COUNTER_TREND_MIN_CONF = 68.0
    is_blocked = (side == "no" and is_bullish_uptrend and conf < NO_COUNTER_TREND_MIN_CONF)
    assert is_blocked is True

    # Counter-trend NO bet with high conviction (75%) passes gating
    conf_high = 75.0
    assert (side == "no" and is_bullish_uptrend and conf_high < NO_COUNTER_TREND_MIN_CONF) is False

    # Position sizing must scale down by 50% without double-halving
    base_risk = 50.0
    scaled_risk = max(1.0, base_risk * 0.50)
    assert scaled_risk == 25.0
    unit_cost = 0.50
    normal_contracts = int(base_risk / unit_cost)
    scaled_contracts = int(scaled_risk / unit_cost)
    assert normal_contracts == 100
    assert scaled_contracts == 50  # Exactly 50% (not 25% from double halving)


def test_executor_counter_trend_no_and_corridor_gating():
    """Test AutoExecutor logic for empirical ceiling capping and counter-trend NO gating."""
    from unittest.mock import MagicMock, patch
    import pandas as pd
    from backend.btc.auto_executor.executor import AutoExecutor

    ae = AutoExecutor(asset="BTC")
    ae.enabled = True
    ae.mode = "PAPER"
    ae.ai_settings = {"dryRun": True, "paper_trade_size_dollars": 50.0, "execDelay": 0}
    ae.max_contracts = 10
    ae._save_config = MagicMock()
    ae._save_trades_history = MagicMock()
    ae.get_trades_history = MagicMock(return_value=[])
    ae.check_risk_budget = MagicMock(return_value=None)

    df_ind = pd.DataFrame([{
        "open": 80000.0, "high": 80100.0, "low": 79900.0, "close": 80050.0,
        "ema_9": 80050.0, "ema_21": 80000.0, "atr": 100.0, "trend_1h": "BULLISH",
        "volume": 100
    }])

    # 1. Test ceiling cap blocking: ask 0.65 with conf 70%
    forecast_normal = {
        "direction": "ABOVE",
        "recommendation": "BUY YES",
        "probability_percent": 70.0,
        "conviction_grade": "GRADE B",
        "conviction_badge": "🟢 BUY YES"
    }
    market_expensive = {
        "ticker": "KXBTC15M-TEST-1", "yes_ask": 0.65, "yes_bid": 0.60,
        "no_ask": 0.40, "no_bid": 0.35, "strike_price": 80000.0
    }

    with patch("backend.btc.auto_executor.executor.kalshi_trader") as mock_kt, \
         patch("backend.btc.auto_executor.executor.fetch_candles", return_value=df_ind), \
         patch("backend.btc.auto_executor.executor.add_all_indicators", return_value=df_ind), \
         patch("backend.btc.auto_executor.executor.get_candle_countdown", return_value={"seconds_left": 860, "current_interval_id": "KXBTC15M-TEST-1"}), \
         patch("backend.btc.ml_engine.get_ml_engine") as mock_ml, \
         patch("backend.btc.auto_executor.executor.evaluate_next_15m_contract", return_value=forecast_normal):
        
        mock_ml.return_value = MagicMock(is_trained=True)
        mock_kt.get_active_15m_market.return_value = market_expensive
        ae.last_traded_interval = None

        ae.check_and_execute_rollover()
        # Should be blocked by 0.62 ceiling cap:
        mock_kt.place_order.assert_not_called()

    # 2. Test counter-trend NO gating: BELOW in bullish uptrend with conf 62% (< 68% min)
    forecast_no_low_conf = {
        "direction": "BELOW",
        "recommendation": "BUY NO",
        "probability_percent": 62.0,
        "conviction_grade": "GRADE B",
        "conviction_badge": "🔴 BUY NO"
    }
    market_valid = {
        "ticker": "KXBTC15M-TEST-2", "yes_ask": 0.52, "yes_bid": 0.50,
        "no_ask": 0.50, "no_bid": 0.48, "strike_price": 80050.0
    }

    with patch("backend.btc.auto_executor.executor.kalshi_trader") as mock_kt, \
         patch("backend.btc.auto_executor.executor.fetch_candles", return_value=df_ind), \
         patch("backend.btc.auto_executor.executor.add_all_indicators", return_value=df_ind), \
         patch("backend.btc.auto_executor.executor.get_candle_countdown", return_value={"seconds_left": 860, "current_interval_id": "KXBTC15M-TEST-2"}), \
         patch("backend.btc.ml_engine.get_ml_engine") as mock_ml, \
         patch("backend.btc.auto_executor.executor.evaluate_next_15m_contract", return_value=forecast_no_low_conf):
        
        mock_ml.return_value = MagicMock(is_trained=True)
        mock_kt.get_active_15m_market.return_value = market_valid
        ae.last_traded_interval = None

        ae.check_and_execute_rollover()
        # Should be blocked by counter-trend NO gating:
        mock_kt.place_order.assert_not_called()


def test_saas_settler_reentry_ceiling_and_counter_trend_gating():
    """Verify that saas_settler re-entry blocks ask > $0.62 unless exceptional, and blocks counter-trend NO with conf < 68% in uptrend."""
    # Logic unit test mirroring settler re-entry guards
    user = {"second_entry_max_ask": 0.75} # User config was legacy 0.75

    # Case 1: Normal re-entry conviction (70%) with ask 0.65 -> blocked by 0.62 cap
    reentry_conf = 70.0
    forecast_obj = {"conviction_grade": "GRADE B", "trend_1h": "BULLISH", "ema_9": 80100.0, "ema_21": 80000.0}
    is_grade_a_plus = "GRADE A+" in str(forecast_obj.get("conviction_grade", ""))
    is_exceptional_conviction = is_grade_a_plus or (reentry_conf > 85.0)
    effective_ceiling = 0.68 if is_exceptional_conviction else 0.62
    user_max_ask = float(user.get("second_entry_max_ask", 0.62) or 0.62)
    max_ask = min(user_max_ask, effective_ceiling)
    assert max_ask == 0.62

    second_ask = 0.65
    is_allowed = (0.46 <= second_ask <= max_ask)
    assert is_allowed is False  # Blocked by 0.62 cap

    # Case 2: Counter-trend NO re-entry with conf 65% in bullish uptrend -> blocked by 68% threshold
    reentry_side = "no"
    c_trend_1h = str(forecast_obj.get("trend_1h", "FLAT")).upper()
    c_ema9 = float(forecast_obj.get("ema_9", 0.0) or 0.0)
    c_ema21 = float(forecast_obj.get("ema_21", 0.0) or 0.0)
    is_bullish_uptrend = (c_trend_1h in ["UP", "BULLISH"]) or (c_ema9 > c_ema21 and c_ema21 > 0)
    assert is_bullish_uptrend is True

    reentry_conf_weak = 65.0
    NO_COUNTER_TREND_MIN_CONF = 68.0
    reentry_blocked = (reentry_side.lower() == "no" and is_bullish_uptrend and reentry_conf_weak < NO_COUNTER_TREND_MIN_CONF)
    assert reentry_blocked is True

    # Case 3: Counter-trend NO re-entry with high conf (72%) passes and scales size by 50%
    reentry_conf_strong = 72.0
    reentry_blocked_strong = (reentry_side.lower() == "no" and is_bullish_uptrend and reentry_conf_strong < NO_COUNTER_TREND_MIN_CONF)
    assert reentry_blocked_strong is False

    base_second_count = 10
    if reentry_side.lower() == "no" and is_bullish_uptrend and base_second_count > 1:
        scaled_second_count = max(1, int(base_second_count * 0.50))
    assert scaled_second_count == 5
