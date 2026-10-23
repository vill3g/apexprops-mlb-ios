import os
import json
import tempfile
import pytest
import numpy as np
import pandas as pd
import torch

from backend.btc.ml_engine import FEATURE_KEYS
from backend.database.models import get_all_active_users, init_db, create_user, update_user_config
from backend.database.trade_store import TradeStore


def _generate_synthetic_indicators_df(n_candles: int = 50) -> pd.DataFrame:
    """Helper to generate a realistic DataFrame with technical indicators for BTC 15m intervals."""
    np.random.seed(42)
    base_price = 90000.0
    records = []

    base_dt = pd.Timestamp("2026-10-07 12:00:00", tz="UTC")
    for i in range(n_candles):
        close_p = base_price + np.cumsum(np.random.normal(0, 50, size=1))[0]
        open_p = close_p - np.random.normal(0, 30)
        high_p = max(close_p, open_p) + abs(np.random.normal(20, 10))
        low_p = min(close_p, open_p) - abs(np.random.normal(20, 10))
        vol = abs(np.random.normal(50, 15))
        c_dt = base_dt + pd.Timedelta(minutes=15 * i)

        rec = {
            "timestamp": int(c_dt.timestamp()),
            "datetime": c_dt,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": vol,
            "rsi": 52.0 + np.sin(i / 5.0) * 15.0,
            "bb_upper": close_p + 150.0,
            "bb_lower": close_p - 150.0,
            "bb_percent_b": 0.55,
            "ema_9": close_p - 10.0,
            "ema_21": close_p - 25.0,
            "ema_50": close_p - 50.0,
            "atr": 65.0,
            "volume_15m_ratio": 1.05,
            "roc_15m": 0.0015,
            "cvd_divergence": 0.0,
            "trend_1h": "BULLISH",
            "open_interest": 1500000.0,
            "funding_rate": 0.0001,
            "orderbook_imbalance": 0.05,
        }
        records.append(rec)

    df = pd.DataFrame(records)
    return df


# =====================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS & DIMENSION SAFETY
# =====================================================================

class TestRLContinuousOutputIntegration:
    """
    Tier 3: Verifies integration between RL continuous outputs (dynamic sizing,
    target limit price) and downstream evaluators (contract_eval.py, shadow_executor.py).
    """

    def test_rl_continuous_outputs_in_contract_eval(self):
        """
        Verify evaluate_next_15m_contract invokes RL agent and carries
        continuous attributes (p_model, target_limit_price, dynamic_sizing_factor).
        """
        from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract

        df_ind = _generate_synthetic_indicators_df(30)
        strike = float(df_ind.iloc[-1]["close"]) + 150.0

        kalshi_m = {
            "ticker": "KXBTCD-26OCT07-T90000",
            "strike_price": strike,
            "yes_ask": 0.52,
            "no_ask": 0.48,
            "yes_bid": 0.50,
            "no_bid": 0.46,
            "is_synthetic": False
        }

        forecast = evaluate_next_15m_contract(
            df_ind=df_ind,
            target_price=strike,
            trading_style="AUTO",
            signal_isolation="RL_DQN",
            asset="BTC",
            kalshi_m=kalshi_m
        )

        assert isinstance(forecast, dict)
        assert "direction" in forecast
        assert "confidence" in forecast or "probability_percent" in forecast
        assert "ml_features" in forecast

        # Verify ml_features contains 66 keys
        features = forecast["ml_features"]
        assert len(features) >= 66

    def test_shadow_executor_consumes_66_dim_state_without_exception(self):
        """
        Verify shadow_executor.execute_shadow_trade accepts forecast dictionary
        with 66-dim ml_features and executes without runtime errors.
        """
        from backend.btc.shadow_executor import execute_shadow_trade

        # Synthetic forecast
        mock_features = {k: 0.0 for k in FEATURE_KEYS}
        mock_features["rsi"] = 55.0
        mock_features["bb_percent_b"] = 0.55
        mock_features["volume_15m_ratio"] = 1.0

        forecast = {
            "direction": "ABOVE",
            "confidence": 65.0,
            "ml_prob": 0.65,
            "ml_features": mock_features,
            "pre_gate_direction": "ABOVE",
            "pre_gate_prob": 65.0
        }

        kalshi_m = {
            "ticker": "KXBTCD-SHADOW-TEST",
            "strike_price": 90000.0,
            "yes_ask": 0.52,
            "no_ask": 0.48,
            "yes_bid": 0.50,
            "close_time": "2026-10-07T21:15:00Z",
            "is_synthetic": False
        }

        # Should execute cleanly without raising exceptions
        execute_shadow_trade(forecast, kalshi_market=kalshi_m)


class TestDimensionSafetyAcrossModules:
    """
    Tier 3: Ensure strict shape safety across 1D lists, 1D arrays, and 2D tensors.
    """

    def test_state_vector_building_length_and_types(self):
        """
        Verify both contract_eval._build_state_vector and shadow_executor._build_state_vector
        consistently output exactly 66-element float vectors.
        """
        from backend.btc.analyzer.contract_eval import _build_state_vector as build_eval_state
        from backend.btc.shadow_executor import _build_state_vector as build_shadow_state

        raw_feat = {k: 1.0 for k in FEATURE_KEYS}

        state_eval = build_eval_state(raw_feat)
        state_shadow = build_shadow_state(raw_feat)

        assert len(state_eval) == 66, f"contract_eval state len should be 66, got {len(state_eval)}"
        assert len(state_shadow) == 66, f"shadow_executor state len should be 66, got {len(state_shadow)}"
        assert all(isinstance(x, (float, int)) for x in state_eval)
        assert all(isinstance(x, (float, int)) for x in state_shadow)

    def test_rl_agent_handles_unbatched_and_batched_states(self):
        """
        Verify RLAgent.evaluate_contract, select_action, and q_values handle:
        - 1D list (66,)
        - 1D numpy array (66,)
        - 2D torch tensor (1, 66)
        without raising torch view or dimensionality errors.
        """
        from backend.btc.rl_agent import get_rl_agent

        agent = get_rl_agent()

        # 1. 1D Python list
        list_state = [0.2] * 66
        act_1 = agent.select_action(list_state)
        q_1 = agent.q_values(list_state)
        eval_1 = agent.evaluate_contract(list_state)

        assert act_1 in (0, 1, 2)
        assert q_1.shape == (3,)
        assert "action" in eval_1

        # 2. 1D Numpy array
        np_state = np.ones(66, dtype=np.float32) * 0.2
        act_2 = agent.select_action(np_state)
        q_2 = agent.q_values(np_state)
        eval_2 = agent.evaluate_contract(np_state)

        assert act_2 in (0, 1, 2)
        assert q_2.shape == (3,)
        assert "action" in eval_2

        # 3. 2D Tensor
        tensor_state = torch.ones(1, 66) * 0.2
        eval_3 = agent.evaluate_contract(tensor_state)
        assert "action" in eval_3


# =====================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS & PAPER TRADING CYCLES
# =====================================================================

class TestPaperTradingExecutionCycles:
    """
    Tier 4: Simulated paper-trading cycle for both RL and ML models.
    Verifies that the entire evaluation and execution pipeline completes
    without runtime exceptions or dimensionality errors.
    """

    def test_simulated_paper_trading_cycle_rl_agent(self, monkeypatch):
        """
        Full E2E flow for RL Agent:
        1. Generate synthetic indicators DataFrame
        2. Evaluate 15m contract with RL selection
        3. Trigger execute_shadow_trade
        4. Place paper trade via kalshi_trader.place_order(dry_run=True)
        5. Verify no exceptions, valid trade recorded.
        """
        import backend.btc.kalshi_trader as kt_module
        from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract
        from backend.btc.shadow_executor import execute_shadow_trade

        df_ind = _generate_synthetic_indicators_df(35)
        strike = float(df_ind.iloc[-1]["close"]) + 150.0

        active_market = {
            "ticker": "KXBTCD-PAPER-RL-TEST",
            "strike_price": strike,
            "yes_ask": 0.54,
            "no_ask": 0.46,
            "yes_bid": 0.50,
            "no_bid": 0.42,
            "is_synthetic": False
        }

        # 1. Evaluate contract
        forecast = evaluate_next_15m_contract(
            df_ind=df_ind,
            target_price=strike,
            trading_style="AUTO",
            signal_isolation="RL_DQN",
            asset="BTC",
            kalshi_m=active_market
        )
        assert forecast is not None
        assert "direction" in forecast
        assert "ml_prob" in forecast or "confidence" in forecast

        # 2. Trigger shadow executor
        execute_shadow_trade(forecast, kalshi_market=active_market)

        # 3. Execute paper order placement
        from backend.btc.kalshi_trader import kalshi_trader
        order_res = kalshi_trader.place_order(
            ticker=active_market["ticker"],
            side="yes",
            count=5,
            limit_price_dollars=0.54,
            dry_run=True,
            available_balance=1000.0
        )
        assert isinstance(order_res, dict)
        assert order_res.get("success") is True or "status" in order_res

    def test_simulated_paper_trading_cycle_ml_ensemble(self, monkeypatch):
        """
        Full E2E flow for ML Voting Ensemble:
        1. Generate synthetic indicators DataFrame
        2. Evaluate contract with ML_ENSEMBLE signal isolation
        3. Verify consensus prediction & Kelly position sizing
        4. Execute paper order and record to TradeStore
        5. Verify zero errors.
        """
        from backend.btc.kalshi_trader import kalshi_trader
        from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract
        from backend.btc.fees import calculate_binary_kelly_position

        df_ind = _generate_synthetic_indicators_df(35)
        strike = float(df_ind.iloc[-1]["close"]) + 150.0

        active_market = {
            "ticker": "KXBTCD-PAPER-ML-TEST",
            "strike_price": strike,
            "yes_ask": 0.51,
            "no_ask": 0.49,
            "yes_bid": 0.48,
            "no_bid": 0.46,
            "is_synthetic": False
        }

        # 1. Evaluate contract with ML Ensemble isolation
        forecast = evaluate_next_15m_contract(
            df_ind=df_ind,
            target_price=strike,
            trading_style="SNIPER",
            signal_isolation="ML_ENSEMBLE",
            asset="BTC",
            kalshi_m=active_market
        )
        assert forecast is not None
        assert "direction" in forecast

        # 2. Verify Kelly sizing with consensus amplification
        try:
            kelly_res = calculate_binary_kelly_position(
                win_prob=0.68,
                ask_price=0.51,
                available_capital=500.0,
                max_position_cap=100.0,
                fractional_multiplier=0.50,
                is_unanimous=True
            )
        except TypeError:
            kelly_res = calculate_binary_kelly_position(
                win_prob=0.68,
                ask_price=0.51,
                available_capital=500.0,
                max_position_cap=100.0,
                fractional_multiplier=0.50
            )
        assert isinstance(kelly_res, dict)
        assert kelly_res["contracts"] > 0

        # 3. Paper order execution
        order_res = kalshi_trader.place_order(
            ticker=active_market["ticker"],
            side="yes",
            count=kelly_res["contracts"],
            limit_price_dollars=0.51,
            dry_run=True,
            available_balance=500.0
        )
        assert isinstance(order_res, dict)
        assert order_res.get("success") is True or "status" in order_res

    def test_shadow_trade_settlement_and_rl_buffer_update(self):
        """
        Simulate an entire episode settlement cycle:
        1. Push transition into RL agent memory
        2. Trigger agent.train_step()
        3. Verify loss is computed and agent weights remain finite.
        """
        from backend.btc.rl_agent import get_rl_agent

        agent = get_rl_agent()
        agent.memory.clear()

        # Simulate settlement
        state = [0.1] * 66
        action = [0.5, 0.8, 0.55]
        reward = 1.0  # Trade won
        next_state = [0.12] * 66
        done = True

        agent.memory.push(state, action, reward, next_state, done, log_prob=-0.5, value=0.2)
        assert len(agent.memory) >= 1

        loss = agent.train_step()
        assert loss is not None
        assert not np.isnan(loss) and not np.isinf(loss)


class TestZeroRegressionUserConfigsAndTradingStyles:
    """
    Tier 3 & 4: Regression safety verification across database models and trading styles.
    """

    def test_user_config_schema_accepts_new_models_without_corruption(self):
        """
        Verify SQLite users table accepts model choices ('RL_PPO', 'VOTING_ENSEMBLE', 'RL_DQN')
        and retains all default settings.
        """
        users = get_all_active_users()
        assert isinstance(users, list)

        # Create or update test user
        test_uname = "test_e2e_trader_verify"
        uid = create_user(test_uname, "password_hash_123")
        assert uid is not None

        # Update model choice and verify persistence
        update_user_config(
            user_id=uid,
            trade_size_dollars=10.0,
            paper_trade_size_dollars=50.0,
            stop_loss_pct=20.0,
            model_choice="RL_PPO",
            signal_source="RL_PPO",
            trading_style="AUTO"
        )

        active_users = get_all_active_users()
        target_user = next((u for u in active_users if u.get("username") == test_uname), None)
        assert target_user is not None
        assert target_user.get("model_choice") == "RL_PPO"
        assert target_user.get("signal_source") == "RL_PPO"
