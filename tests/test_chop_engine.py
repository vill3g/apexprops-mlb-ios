import pytest
from backend.btc.chop_engine import evaluate_chop_trade

def test_chop_engine_rejects_coinflip_50c():
    # In tight chop deadzone with 50c contracts, trade must be rejected
    res = evaluate_chop_trade(
        asset="BTC",
        spot_price=67500.0,
        strike_price=67500.0,
        kalshi_yes_ask=0.50,
        kalshi_no_ask=0.50,
        kalshi_yes_bid=0.48,
        kalshi_no_bid=0.48,
        rsi_1m=50.0,
        rsi_5m=50.0,
        bb_upper_1m=67550.0,
        bb_lower_1m=67450.0,
        bb_middle_1m=67500.0,
        seconds_to_expiry=450,
    )
    assert res is None, "Chop engine should not take 50/50 coin flips in center of range"

def test_chop_engine_triggers_overbought_discount_fade():
    # Spot hits upper Bollinger band, RSI is 72, NO contract is discounted at 24c
    res = evaluate_chop_trade(
        asset="BTC",
        spot_price=67580.0,
        strike_price=67500.0,
        kalshi_yes_ask=0.78,
        kalshi_no_ask=0.24,
        kalshi_yes_bid=0.75,
        kalshi_no_bid=0.22,
        rsi_1m=72.0,
        rsi_5m=65.0,
        bb_upper_1m=67575.0,
        bb_lower_1m=67450.0,
        bb_middle_1m=67510.0,
        seconds_to_expiry=400,
    )
    assert res is not None, "Chop engine should trigger on overbought resistance fade"
    assert res["side"] == "NO"
    assert res["target_price"] == 0.24
    assert res["target_scalp_exit"] == 0.36  # +12c profit scalp
    assert res["strategy"] == "CHOP_FADE_OVERBOUGHT"

def test_chop_engine_triggers_oversold_discount_bounce():
    # Spot hits lower Bollinger band, RSI is 26, YES contract is discounted at 22c
    res = evaluate_chop_trade(
        asset="BTC",
        spot_price=67420.0,
        strike_price=67500.0,
        kalshi_yes_ask=0.22,
        kalshi_no_ask=0.80,
        kalshi_yes_bid=0.20,
        kalshi_no_bid=0.77,
        rsi_1m=26.0,
        rsi_5m=32.0,
        bb_upper_1m=67550.0,
        bb_lower_1m=67425.0,
        bb_middle_1m=67485.0,
        seconds_to_expiry=500,
    )
    assert res is not None, "Chop engine should trigger on oversold support bounce"
    assert res["side"] == "YES"
    assert res["target_price"] == 0.22
    assert res["target_scalp_exit"] == 0.34  # +12c profit scalp
    assert res["strategy"] == "CHOP_FADE_OVERSOLD"

def test_chop_engine_expiration_safety():
    # Late in candle (< 180s left), skip trade to prevent settlement roulette
    res = evaluate_chop_trade(
        asset="BTC",
        spot_price=67420.0,
        strike_price=67500.0,
        kalshi_yes_ask=0.22,
        kalshi_no_ask=0.80,
        kalshi_yes_bid=0.20,
        kalshi_no_bid=0.77,
        rsi_1m=26.0,
        rsi_5m=32.0,
        bb_upper_1m=67550.0,
        bb_lower_1m=67425.0,
        bb_middle_1m=67485.0,
        seconds_to_expiry=120,
    )
    assert res is None, "Should refuse chop entries with < 180s left"
