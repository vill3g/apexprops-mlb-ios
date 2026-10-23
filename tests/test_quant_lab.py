"""
Unit Tests for Autonomous Reflexive Quant Lab & Strategy Graveyard.
"""
import pytest
from backend.engine.quant_lab.graveyard import StrategyGraveyard, StrategyRegistry, init_db
from backend.engine.quant_lab.alpha_ideator import AlphaIdeator
from backend.engine.quant_lab.strategy_coder import StrategyCoder, StrategySecurityError
from backend.engine.quant_lab.validator import StrategyValidator
from backend.engine.quant_lab.incubator import PaperIncubator
from backend.engine.quant_lab.orchestrator import QuantLabOrchestrator


def test_graveyard_record_and_retrieve():
    init_db()
    entry_id = StrategyGraveyard.record_failure(
        strategy_id="unit_test_strat_1",
        name="Unit Test Momentum Break",
        hypothesis="Test hypothesis that failed",
        asset="BTC",
        failure_stage="BACKTEST_FAILED",
        post_mortem_summary="High slippage pin",
        negative_rule="Do not trade momentum when ATR < 30 on BTC",
        metrics_snapshot={"win_rate": 0.40, "sharpe": -0.5}
    )
    assert entry_id > 0

    entries = StrategyGraveyard.get_entries(limit=10)
    assert len(entries) >= 1
    assert any(e["strategy_id"] == "unit_test_strat_1" for e in entries)

    lessons = StrategyGraveyard.get_relevant_lessons(asset="BTC")
    assert any("ATR < 30" in l.get("negative_rule", "") for l in lessons)


def test_strategy_coder_sandbox_safety():
    # Valid code should compile
    safe_hypo = {
        "name": "Safe Mean Reversion",
        "target_side": "YES",
        "entry_conditions": [{"indicator": "rsi", "operator": "<", "threshold": 30.0}],
        "stop_loss_pct": 20.0,
        "take_profit_pct": 30.0,
        "max_entry_price": 0.70,
        "min_entry_price": 0.30
    }
    code, code_hash = StrategyCoder.generate_code(safe_hypo)
    assert code_hash is not None
    fn = StrategyCoder.compile_strategy(code)
    
    # Matching snapshot
    res_buy = fn({"raw_features": {"rsi": 25.0}, "cur_price": 0.50})
    assert res_buy["action"] == "BUY"
    assert res_buy["side"] == "YES"

    # Non-matching snapshot
    res_pass = fn({"raw_features": {"rsi": 55.0}, "cur_price": 0.50})
    assert res_pass["action"] == "PASS"

    # Malicious injection must raise StrategySecurityError
    malicious_code = "import os\nos.system('echo hacked')"
    with pytest.raises(StrategySecurityError):
        StrategyCoder.compile_strategy(malicious_code)

    eval_injection = "def evaluate_signal(snap): eval('1+1')"
    with pytest.raises(StrategySecurityError):
        StrategyCoder.compile_strategy(eval_injection)


def test_alpha_ideator_respects_graveyard():
    ideator = AlphaIdeator()
    hypo = ideator.generate_hypothesis(asset="BTC", target_interval="15m")
    assert hypo["asset"] == "BTC"
    assert hypo["target_interval"] == "15m"
    assert "entry_conditions" in hypo
    assert len(hypo["entry_conditions"]) >= 1


def test_validator_and_monte_carlo():
    def always_lose(snapshot):
        return {"action": "BUY", "side": "YES"}

    val_res = StrategyValidator.validate(always_lose, asset="BTC")
    assert "in_sample" in val_res
    assert "out_of_sample" in val_res


def test_paper_incubator_lifecycle():
    incubator = PaperIncubator()
    strat_id = "inc_test_001"
    safe_code = """
def evaluate_signal(snapshot):
    return {"action": "BUY", "side": "YES"}
"""
    incubator.incubate_strategy(strat_id, "Incubation Test Strat", "BTC", safe_code)
    active = incubator.get_active_incubating(asset="BTC")
    assert any(s["strategy_id"] == strat_id for s in active)

    # Evaluate snapshot with ticker -> records forward entry
    test_ticker = "KXBTC15M-TEST-FORWARD"
    signals = incubator.evaluate_snapshot("BTC", {"cur_price": 0.50, "ticker": test_ticker, "strike_price": 65000.0})
    assert len(signals) >= 1

    # Check forward trade was recorded
    fwd_trades = incubator.get_incubation_trades(limit=10, strategy_id=strat_id)
    assert any(t["ticker"] == test_ticker for t in fwd_trades)

    # Settle the contract
    settled = incubator.settle_live_contract(test_ticker, winning_side="YES", exit_price=1.0)
    assert len(settled) >= 1
    assert settled[0]["trades"] >= 1
    assert settled[0]["total_pnl"] > 0


def test_end_to_end_quant_lab_cycle():
    orchestrator = QuantLabOrchestrator()
    report = orchestrator.run_research_cycle(asset="BTC", target_interval="15m")
    assert report["success"] is True
    assert report["result"] in ("PROMOTED_TO_INCUBATOR", "COMMITTED_TO_GRAVEYARD")
    assert "validation" in report
    assert "strategy_id" in report


def test_market_regime_classification():
    from backend.engine.quant_lab.regime_classifier import (
        MarketRegimeClassifier,
        REGIME_COMPRESSION,
        REGIME_TREND,
        REGIME_WHIPSAW,
        REGIME_SLUG_COMPRESSION,
        REGIME_SLUG_TREND,
        REGIME_SLUG_WHIPSAW,
    )

    # 1. Financial Regimes
    # A. Compression / Mean-Reversion (low ADX, moderate volatility, normal candle)
    comp_feats = {"adx": 16.0, "atr_percentile": 30.0, "body_to_range": 0.40, "vol_ratio": 0.9}
    s_comp = MarketRegimeClassifier.classify_market_state(comp_feats, asset="BTC")
    assert s_comp["regime"] == REGIME_COMPRESSION
    assert s_comp["regime_slug"] == REGIME_SLUG_COMPRESSION
    assert s_comp["regime_code"] == 0

    # B. Trend-Expansion / Momentum (high ADX, strong body-to-range, trend alignment)
    trend_feats = {
        "adx": 32.0, "atr_percentile": 65.0, "body_to_range": 0.70, "vol_ratio": 1.4,
        "ema_fast": 65500.0, "ema_slow": 65200.0, "ema_trend": 64800.0
    }
    s_trend = MarketRegimeClassifier.classify_market_state(trend_feats, asset="BTC")
    assert s_trend["regime"] == REGIME_TREND
    assert s_trend["regime_slug"] == REGIME_SLUG_TREND
    assert s_trend["regime_code"] == 1

    # C. High-Whipsaw / Event-Risk (very high volatility percentile, large wick total)
    whip_feats = {
        "vol_regime_percentile": 0.95, "total_wick": 0.65, "upper_wick_ratio": 0.35,
        "lower_wick_ratio": 0.35, "body_to_range": 0.20, "vol_ratio": 1.8
    }
    s_whip = MarketRegimeClassifier.classify_market_state(whip_feats, asset="BTC")
    assert s_whip["regime"] == REGIME_WHIPSAW
    assert s_whip["regime_slug"] == REGIME_SLUG_WHIPSAW
    assert s_whip["regime_code"] == 2

    # 2. Sports Regimes
    # A. Compression: tight spread, minimal drift
    s_sport_comp = MarketRegimeClassifier.classify_market_state({"spread": 0.02, "price_drift": 0.01}, asset="TEN")
    assert s_sport_comp["regime"] == REGIME_COMPRESSION

    # B. Trend-Expansion: directional drift
    s_sport_trend = MarketRegimeClassifier.classify_market_state({"spread": 0.03, "price_drift": 0.045}, asset="TEN")
    assert s_sport_trend["regime"] == REGIME_TREND

    # C. High-Whipsaw: wide spread or volatile drift
    s_sport_whip = MarketRegimeClassifier.classify_market_state({"spread": 0.08, "price_drift": 0.07}, asset="TEN")
    assert s_sport_whip["regime"] == REGIME_WHIPSAW

    # 3. Snapshot safe enrichment & edge cases
    # Empty dict
    snap_empty = MarketRegimeClassifier.classify_snapshot({})
    assert snap_empty["market_regime"] == REGIME_COMPRESSION
    assert snap_empty["regime_code"] == 0
    assert "raw_features" in snap_empty and snap_empty["raw_features"]["market_regime"] == REGIME_COMPRESSION

    # None snapshot
    snap_none = MarketRegimeClassifier.classify_snapshot(None)
    assert isinstance(snap_none, dict)
    assert snap_none["market_regime"] == REGIME_COMPRESSION

    # Zero-range Doji candle (high == low, open == close)
    snap_doji = {"raw_features": {"high": 50000.0, "low": 50000.0, "open": 50000.0, "close": 50000.0}}
    res_doji = MarketRegimeClassifier.classify_snapshot(snap_doji)
    assert res_doji["market_regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)

    # Sparse dict
    snap_sparse = {"raw_features": {"rsi": 25.0}}
    res_sparse = MarketRegimeClassifier.classify_snapshot(snap_sparse)
    assert "regime" in res_sparse and "regime_code" in res_sparse


def test_calibrated_probabilistic_signals_and_kelly():
    # 1. Hypotheses with target regime and dynamic Kelly
    hypo = {
        "name": "Mean Reversion Dynamic Alpha",
        "target_side": "YES",
        "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
        "base_edge": 0.07,
        "entry_conditions": [
            {"indicator": "rsi", "operator": "<", "threshold": 32.0}
        ],
        "max_entry_price": 0.85,
        "min_entry_price": 0.15,
        "take_profit_pct": 35.0,
        "stop_loss_pct": 25.0
    }
    code, code_hash = StrategyCoder.generate_code(hypo)
    fn = StrategyCoder.compile_strategy(code)

    # Matching regime and conditions -> BUY with dynamic calibrated output
    snap_match = {
        "raw_features": {"rsi": 28.0},
        "cur_price": 0.50,
        "market_regime": "COMPRESSION_MEAN_REVERSION"
    }
    sig_match = fn(snap_match)
    assert sig_match["action"] == "BUY"
    assert sig_match["side"] == "YES"
    # Dynamic confidence must NOT be the static 75.0
    assert sig_match["confidence"] != 75.0
    assert 5.0 <= sig_match["confidence"] <= 95.0
    # Calibrated probability assertions
    assert "calibrated_win_prob" in sig_match
    assert 0.05 <= sig_match["calibrated_win_prob"] <= 0.95
    assert sig_match["win_probability"] == sig_match["calibrated_win_prob"]
    # Closed-form Kelly assertions
    assert "f_star" in sig_match and sig_match["f_star"] > 0.0
    assert "kelly_fraction" in sig_match and sig_match["kelly_fraction"] > 0.0
    assert "projected_edge" in sig_match and sig_match["projected_edge"] > 0.0

    # Mismatching regime -> PASS with regime_mismatch reason
    snap_mismatch = {
        "raw_features": {"rsi": 28.0},
        "cur_price": 0.50,
        "market_regime": "TREND_EXPANSION_MOMENTUM"
    }
    sig_mismatch = fn(snap_mismatch)
    assert sig_mismatch["action"] == "PASS"
    assert sig_mismatch["reason"] == "regime_mismatch"

    # Dynamic pricing sensitivity: varying cur_price changes calibrated probability & Kelly sizing
    snap_p1 = {"raw_features": {"rsi": 28.0}, "cur_price": 0.35, "market_regime": "COMPRESSION_MEAN_REVERSION"}
    snap_p2 = {"raw_features": {"rsi": 28.0}, "cur_price": 0.65, "market_regime": "COMPRESSION_MEAN_REVERSION"}
    sig_p1 = fn(snap_p1)
    sig_p2 = fn(snap_p2)
    assert sig_p1["confidence"] != sig_p2["confidence"]
    assert sig_p1["kelly_fraction"] != sig_p2["kelly_fraction"]

    # String comparison condition test (e.g. regime feature matching)
    str_hypo = {
        "name": "String Feature Guard",
        "target_side": "YES",
        "entry_conditions": [
            {"indicator": "market_regime", "operator": "==", "threshold": "COMPRESSION_MEAN_REVERSION"}
        ],
        "max_entry_price": 0.85,
        "min_entry_price": 0.15
    }
    str_code, _ = StrategyCoder.generate_code(str_hypo)
    str_fn = StrategyCoder.compile_strategy(str_code)
    sig_str = str_fn({"raw_features": {"market_regime": "COMPRESSION_MEAN_REVERSION"}, "cur_price": 0.50})
    assert sig_str["action"] == "BUY"

