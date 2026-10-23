import pytest
from backend.btc.strategies.spike_dip_scalper import SpikeDipScalper
from backend.btc.auto_executor.remediations import evaluate_exit_discipline

def test_spike_dip_fair_value_calculation():
    # Spot far above strike -> fair value high
    p_high = SpikeDipScalper.calculate_fair_value_prob(spot_price=68150, strike_price=68000, atr=100, side="YES")
    assert p_high >= 0.75

    # Spot far below strike -> fair value low
    p_low = SpikeDipScalper.calculate_fair_value_prob(spot_price=67850, strike_price=68000, atr=100, side="YES")
    assert p_low <= 0.25

    # At the money -> near 0.50
    p_atm = SpikeDipScalper.calculate_fair_value_prob(spot_price=68000, strike_price=68000, atr=100, side="YES")
    assert 0.45 <= p_atm <= 0.55

def test_spike_dip_opportunity_detection():
    # Test DIP BUY: Spot at 68020 (fair value ~0.55), but market panicked and dumped YES ask to 0.28
    opp = SpikeDipScalper.evaluate_opportunity(
        ticker="KXBTC15M-TEST",
        spot_price=68020,
        strike_price=68000,
        yes_bid=0.25,
        yes_ask=0.28,
        no_bid=0.68,
        no_ask=0.72,
        seconds_left=400,
        atr=100.0,
        min_edge_cents=3.5
    )
    assert opp is not None
    assert opp["action"] == "BUY"
    assert opp["side"] == "YES"
    assert opp["setup_type"] == "15M_DIP_SCALP"
    assert opp["edge_cents"] > 10.0

def test_spike_dip_opportunity_spike_fade():
    # Test SPIKE FADE: Spot at 67900 (far below strike, fair value ~0.25), but someone spiked YES to 0.75
    # NO is available at 0.22
    opp = SpikeDipScalper.evaluate_opportunity(
        ticker="KXBTC15M-TEST",
        spot_price=67900,
        strike_price=68000,
        yes_bid=0.72,
        yes_ask=0.78,
        no_bid=0.18,
        no_ask=0.22,
        seconds_left=350,
        atr=100.0,
        min_edge_cents=3.5
    )
    assert opp is not None
    assert opp["action"] == "BUY"
    assert opp["side"] == "NO"
    assert opp["setup_type"] == "15M_SPIKE_FADE"

def test_pre_settlement_salvage_guard():
    trade = {"entry_price": 0.50, "direction": "ABOVE", "side": "YES"}

    # Case 1: T-60s, weak bid (0.35) and narrow cushion ($10) -> Must trigger salvage exit
    res_salvage = evaluate_exit_discipline(trade, current_bid=0.35, spot_price=68010, strike_price=68000, seconds_left=60)
    assert res_salvage["should_close"] is True
    assert "PRE_SETTLEMENT_SALVAGE_GUARD" in res_salvage["reason"]

    # Case 2: Deeply in the money with high bid (0.92) -> Hold to 100c settlement
    res_hold = evaluate_exit_discipline(trade, current_bid=0.92, spot_price=68200, strike_price=68000, seconds_left=45)
    assert res_hold["should_close"] is False
    assert "HIGH_CONVICTION_HOLD_TO_SETTLEMENT" in res_hold["reason"]
