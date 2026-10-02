import pytest
import threading
import json
import os
from unittest.mock import patch, MagicMock
from backend.core.registry import get_auto_executor
from backend.database.models import get_all_active_users, deduct_user_paper_balance, credit_user_paper_balance

def test_saas_eval_lock_exists():
    ae = get_auto_executor("BTC")
    assert hasattr(ae, "_saas_eval_lock")
    assert isinstance(ae._saas_eval_lock, type(threading.Lock()))
    assert hasattr(ae, "_last_saas_eval_time")

def test_evaluate_next_15m_contract_accepts_signal_isolation():
    from backend.btc.analyzer import evaluate_next_15m_contract
    import pandas as pd
    import numpy as np

    # Create dummy dataframe with necessary columns
    n = 20
    df = pd.DataFrame({
        "open": np.linspace(80000, 81000, n),
        "high": np.linspace(80500, 81500, n),
        "low": np.linspace(79500, 80500, n),
        "close": np.linspace(80200, 81200, n),
        "volume": np.full(n, 100.0),
        "rsi": np.full(n, 55.0),
        "ema_9": np.linspace(80100, 81100, n),
        "ema_21": np.linspace(80000, 81000, n),
        "ema_50": np.linspace(79900, 80900, n),
        "bb_upper": np.linspace(80600, 81600, n),
        "bb_lower": np.linspace(79800, 80800, n),
        "atr": np.full(n, 100.0),
        "cvd": np.full(n, 50.0),
        "vol_ratio": np.full(n, 1.2),
        "adx": np.full(n, 30.0),
        "time": np.arange(1000, 1000 + n * 900, 900)
    })

    kalshi_m = {
        "ticker": "KXBTC15M-TEST",
        "strike_price": 80500.0,
        "yes_ask": 0.55,
        "no_ask": 0.45,
        "status": "active"
    }

    # Test with signal_isolation="AI_ONLY"
    res_ai = evaluate_next_15m_contract(df, target_price=80500.0, kalshi_m=kalshi_m, signal_isolation="AI_ONLY")
    assert "direction" in res_ai
    assert "probability_percent" in res_ai

    # Test with signal_isolation="CHART_ONLY"
    res_chart = evaluate_next_15m_contract(df, target_price=80500.0, kalshi_m=kalshi_m, signal_isolation="CHART_ONLY")
    assert "direction" in res_chart

@pytest.mark.skip(reason="process_auto_force_trades is a deprecated no-op; auto-force now lives in saas_broadcaster")
def test_auto_force_trade_fallback_in_settler():
    from backend.saas_settler import process_auto_force_trades
    
    mock_users = [{
        "id": 9999,
        "username": "mock_force_user",
        "auto_force_trade": 1,
        "signal_source": "ML_ENSEMBLE",
        "trading_mode": "PAPER",
        "trade_size_dollars": 50.0,
        "paper_balance": 1000.0
    }]
    
    mock_market = {
        "ticker": "KXBTC15M-MOCK-TEST",
        "status": "active",
        "yes_ask": 0.52,
        "no_ask": 0.48
    }
    
    mock_analysis = {
        "signal": "HOLD",
        "ml_prob": 0.68,
        "primary_bias": "BULLISH"
    }
    
    with patch("backend.saas_settler.get_all_active_users", return_value=mock_users), \
         patch("backend.saas_settler.get_kalshi_15m_market", return_value=mock_market), \
         patch("backend.saas_settler.get_cached_btc_analysis", return_value=(None, mock_analysis)), \
         patch("backend.saas_settler.deduct_user_paper_balance", return_value=True) as mock_deduct, \
         patch("backend.saas_settler.get_user_lock") as mock_lock, \
         patch("os.path.exists", return_value=False), \
         patch("builtins.open", MagicMock()):
        
        process_auto_force_trades()
        # Ensure deduct was called because ml_prob > 0.50 fell back from HOLD to YES
        assert mock_deduct.called
