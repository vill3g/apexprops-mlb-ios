import json
import pytest
from unittest.mock import MagicMock, patch

from backend.btc.loss_analyzer import LossAnalyzer, loss_analyzer


def test_extract_features_string_json():
    analyzer = LossAnalyzer()
    trade = {
        "ticker": "KXBTC15M-TEST",
        "side": "NO",
        "market_snapshot": json.dumps({
            "price": 81000,
            "target": 81200,
            "raw_features": {
                "rsi": 32.5,
                "atr": 210.0,
                "cvd_value": -450.0,
                "delta_to_target": -0.05
            }
        })
    }
    feats = analyzer._extract_features(trade)
    assert feats["raw_features"]["rsi"] == 32.5
    assert feats["raw_features"]["atr"] == 210.0
    assert feats["raw_features"]["cvd_value"] == -450.0


def test_diagnose_loss_oversold_bounce():
    analyzer = LossAnalyzer()
    # Test current RSI < 38.0
    trade = {
        "id": "trade_oversold_1",
        "ticker": "KXBTC15M-TEST",
        "side": "NO",
        "market_snapshot": {
            "raw_features": {
                "rsi": 33.0,
                "atr": 150.0,
                "cvd_value": -50.0,
                "delta_to_target": -0.15
            }
        }
    }
    diag = analyzer.diagnose_loss(trade)
    assert diag["category"] == "FALSE_BREAKOUT_OVERSOLD"
    assert "mean-reversion bounce reversal" in diag["summary"]

    # Test lagged RSI where current RSI is 42 but recent candle dipped to 29
    trade_lagged = {
        "id": "trade_oversold_lagged",
        "ticker": "KXBTC15M-TEST",
        "side": "NO",
        "market_snapshot": {
            "raw_features": {
                "rsi": 42.0,
                "rsi_lag_2": 0.29,  # 29.0 on 0-1 scale
                "atr": 150.0,
                "cvd_value": -50.0,
                "delta_to_target": -0.15
            }
        }
    }
    diag_lagged = analyzer.diagnose_loss(trade_lagged)
    assert diag_lagged["category"] == "FALSE_BREAKOUT_OVERSOLD"
    assert diag_lagged["min_rsi_lag"] == 29.0


def test_diagnose_loss_overbought_exhaustion():
    analyzer = LossAnalyzer()
    trade = {
        "id": "trade_overbought_1",
        "ticker": "KXBTC15M-TEST",
        "side": "YES",
        "market_snapshot": {
            "raw_features": {
                "rsi": 68.0,
                "atr": 180.0,
                "cvd_value": 200.0,
                "delta_to_target": 0.20
            }
        }
    }
    diag = analyzer.diagnose_loss(trade)
    assert diag["category"] == "FALSE_BREAKOUT_OVERBOUGHT"
    assert "exhaustion reversal" in diag["summary"]


def test_diagnose_loss_cvd_divergence():
    analyzer = LossAnalyzer()
    # YES trade placed into heavy spot selling (-5.0 CVD)
    trade = {
        "id": "trade_cvd_div",
        "ticker": "KXBTC15M-TEST",
        "side": "YES",
        "market_snapshot": {
            "raw_features": {
                "rsi": 52.0,
                "atr": 150.0,
                "cvd_value": -5.5,
                "delta_to_target": 0.10
            }
        }
    }
    diag = analyzer.diagnose_loss(trade)
    assert diag["category"] == "ORDERBOOK_CVD_DIVERGENCE"


def test_diagnose_loss_choppy_range_bound():
    analyzer = LossAnalyzer()
    # BTC trade with very low ATR ($25)
    trade = {
        "id": "trade_chop",
        "ticker": "KXBTC15M-TEST",
        "side": "YES",
        "market_snapshot": {
            "raw_features": {
                "rsi": 50.0,
                "atr": 25.0,
                "cvd_value": 0.0,
                "delta_to_target": 0.10
            }
        }
    }
    diag = analyzer.diagnose_loss(trade)
    assert diag["category"] == "CHOPPY_RANGE_BOUND"


def test_get_loss_regime_vetoes_generation():
    analyzer = LossAnalyzer()
    # Feed 2 oversold losses into history
    history = [
        {
            "ticker": "KXBTC15M-TEST1",
            "side": "NO",
            "status": "SETTLED",
            "pnl": -50.0,
            "market_snapshot": {"raw_features": {"rsi": 32.0, "atr": 200.0, "cvd_value": 0.0, "delta_to_target": -0.2}}
        },
        {
            "ticker": "KXBTC15M-TEST2",
            "side": "NO",
            "status": "SETTLED",
            "pnl": -50.0,
            "market_snapshot": {"raw_features": {"rsi": 34.0, "atr": 200.0, "cvd_value": 0.0, "delta_to_target": -0.2}}
        }
    ]
    vetoes = analyzer.get_loss_regime_vetoes("BTC", history)
    assert len(vetoes) >= 1
    veto_types = [v["veto_type"] for v in vetoes]
    assert "BLOCK_OVERSOLD_NO" in veto_types


def test_calculate_regime_penalties():
    analyzer = LossAnalyzer()
    history = [
        {"status": "SETTLED", "pnl": -50.0, "loss_analysis": {"category": "FALSE_BREAKOUT_OVERSOLD"}},
        {"status": "SETTLED", "pnl": -50.0, "loss_analysis": {"category": "FALSE_BREAKOUT_OVERSOLD"}},
        {"status": "SETTLED", "pnl": -50.0, "loss_analysis": {"category": "CHOPPY_RANGE_BOUND"}},
        {"status": "SETTLED", "pnl": -50.0, "loss_analysis": {"category": "CHOPPY_RANGE_BOUND"}},
        {"status": "SETTLED", "pnl": 50.0}
    ]
    penalties = analyzer.calculate_regime_penalties(history)
    assert penalties["conviction_multiplier"] < 1.0
    assert penalties["extra_min_rsi_cushion"] == 6
    assert penalties["chop_warning"] is True
