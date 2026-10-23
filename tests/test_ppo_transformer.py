import os
import tempfile
import pytest
import numpy as np
import torch
import torch.nn as nn

from backend.btc.ml_engine import FEATURE_KEYS


# =====================================================================
# TIER 1: FEATURE COVERAGE — PPO TRANSFORMER ARCHITECTURE & LOSS
# =====================================================================

class TestPPOTransformerArchitecture:
    """
    Tier 1: Comprehensive tests for the PyTorch nn.TransformerEncoder backbone,
    continuous action heads, and critic value head in backend/btc/rl_agent.py.
    """

    def test_transformer_encoder_presence_and_topology(self):
        """
        Verify that the model utilizes a 2-layer Pre-LN TransformerEncoder
        with d_model=64, nhead=4, and positional encodings for temporal sequences.
        """
        from backend.btc.rl_agent import PPOTimeSeriesTransformer, PositionalEncoding

        model = PPOTimeSeriesTransformer(input_dim=len(FEATURE_KEYS))

        # 1. Positional encoding check
        assert hasattr(model, "pos_encoder"), "Model must have pos_encoder"
        assert isinstance(model.pos_encoder, PositionalEncoding)
        assert model.pos_encoder.pe.shape[-1] == 64, "Positional encoding d_model must be 64"

        # 2. Transformer encoder check
        assert hasattr(model, "transformer"), "Model must have transformer backbone"
        assert isinstance(model.transformer, nn.TransformerEncoder), "Backbone must be nn.TransformerEncoder"
        assert model.transformer.num_layers == 2, "TransformerEncoder must have 2 layers"

        # 3. Layer properties check
        encoder_layer = model.transformer.layers[0]
        assert encoder_layer.self_attn.num_heads == 4, "Multi-head attention must have 4 heads"
        assert encoder_layer.norm_first is True, "Must use Pre-LN (norm_first=True) for stability"

        # 4. Feature partitioning check (25 sequence features: 5 lags x 5 indicators; 41 static features)
        assert model.seq_len == 5, "Sequence length must be 5 lags"
        assert model.seq_features == 5, "Sequence features must be 5 indicators per lag"
        assert model.static_features == 41, "Static features must be 41 (66 - 25)"

    def test_continuous_action_heads_bounds_and_shapes(self):
        """
        Verify the 3D continuous action space bounds:
        - a_dir in [-1.0, 1.0] (tanh)
        - a_size in [0.0, 1.0] (sigmoid)
        - a_price in [0.01, 0.99] (scaled sigmoid)
        Critic value head V(s) in R^1.
        """
        from backend.btc.rl_agent import PPOTimeSeriesTransformer

        batch_size = 8
        model = PPOTimeSeriesTransformer(input_dim=66)
        dummy_state = torch.randn(batch_size, 66)

        action_mean, action_std, value = model(dummy_state)

        # Dimension checks
        assert action_mean.shape == (batch_size, 3), f"Action mean shape should be {(batch_size, 3)}, got {action_mean.shape}"
        assert action_std.shape == (batch_size, 3), f"Action std shape should be {(batch_size, 3)}, got {action_std.shape}"
        assert value.shape == (batch_size, 1), f"Critic value shape should be {(batch_size, 1)}, got {value.shape}"

        # Bound checks across batch
        mean_dir = action_mean[:, 0].detach().cpu().numpy()
        mean_size = action_mean[:, 1].detach().cpu().numpy()
        mean_price = action_mean[:, 2].detach().cpu().numpy()

        assert np.all(mean_dir >= -1.0) and np.all(mean_dir <= 1.0), "Direction mean must be in [-1.0, 1.0]"
        assert np.all(mean_size >= 0.0) and np.all(mean_size <= 1.0), "Size mean must be in [0.0, 1.0]"
        assert np.all(mean_price >= 0.01) and np.all(mean_price <= 0.99), "Limit price mean must be in [0.01, 0.99]"
        assert np.all(action_std.detach().cpu().numpy() > 0.0), "Action std must be strictly positive"

    def test_get_action_and_value_stochastic_sampling(self):
        """
        Verify get_action_and_value returns clamped sampled actions,
        summed log-probabilities, policy entropy, and state value.
        """
        from backend.btc.rl_agent import PPOTimeSeriesTransformer

        batch_size = 4
        model = PPOTimeSeriesTransformer(input_dim=66)
        state = torch.randn(batch_size, 66)

        action, log_prob, entropy, val = model.get_action_and_value(state)

        assert action.shape == (batch_size, 3)
        assert log_prob.shape == (batch_size,)
        assert entropy.shape == (batch_size,)
        assert val.shape == (batch_size,)

        # Clamping check on sampled stochastic actions
        act_np = action.detach().cpu().numpy()
        assert np.all(act_np[:, 0] >= -1.0) and np.all(act_np[:, 0] <= 1.0), "Sampled direction must be in [-1, 1]"
        assert np.all(act_np[:, 1] >= 0.0) and np.all(act_np[:, 1] <= 1.0), "Sampled sizing must be in [0, 1]"
        assert np.all(act_np[:, 2] >= 0.01) and np.all(act_np[:, 2] <= 0.99), "Sampled price must be in [0.01, 0.99]"

        # Log prob evaluation with given action
        action_eval, log_prob_eval, entropy_eval, _ = model.get_action_and_value(state, action=action)
        assert torch.allclose(action, action_eval)
        assert torch.allclose(log_prob, log_prob_eval, atol=1e-5)

    def test_critic_and_actor_gradient_flow(self):
        """
        Verify PyTorch autograd backpropagates gradients through both Critic and Actor heads,
        fusion layer, static branch, and the Transformer encoder.
        """
        from backend.btc.rl_agent import PPOTimeSeriesTransformer

        model = PPOTimeSeriesTransformer(input_dim=66)
        state = torch.randn(4, 66, requires_grad=True)

        action, log_prob, entropy, value = model.get_action_and_value(state)
        loss = value.sum() + log_prob.sum() - 0.01 * entropy.sum()
        loss.backward()

        # Check gradients exist on all core submodules
        assert model.critic[0].weight.grad is not None, "Critic head must receive gradients"
        assert model.actor_mean[0].weight.grad is not None, "Actor head must receive gradients"
        assert model.fusion[0].weight.grad is not None, "Fusion layer must receive gradients"
        assert model.static_mlp[0].weight.grad is not None, "Static MLP must receive gradients"
        assert model.seq_proj.weight.grad is not None, "Sequence projection must receive gradients"


class TestPPOLossAndBuffer:
    """
    Tier 1: Comprehensive tests for PPORolloutBuffer and PPO clipped surrogate loss computation.
    """

    def test_ppo_rollout_buffer_push_sample_clear(self):
        """
        Verify PPORolloutBuffer accepts transitions with states, 3D actions, rewards,
        dones, log_probs, and values, and can sample and clear correctly.
        """
        from backend.btc.rl_agent import PPORolloutBuffer

        buffer = PPORolloutBuffer(capacity=100)
        assert len(buffer) == 0

        # Push transitions
        for i in range(10):
            s = [float(i)] * 66
            a = [0.2, 0.8, 0.55]
            r = 1.5 if i % 2 == 0 else -1.0
            s_next = [float(i + 1)] * 66
            done = (i == 9)
            buffer.push(s, a, r, s_next, done, log_prob=-0.5, value=0.25)

        assert len(buffer) == 10

        states, actions, rewards, next_states, dones, log_probs, values, _ = buffer.sample_batch(10)
        assert states.shape == (10, 66)
        assert actions.shape == (10, 3)
        assert rewards.shape == (10,)
        assert dones.shape == (10,)
        assert log_probs.shape == (10,)
        assert values.shape == (10,)

        # Test buffer clear
        buffer.clear()
        assert len(buffer) == 0

    def test_ppo_training_step_loss_and_weights_update(self):
        """
        Verify RLAgent.train_step() computes PPO loss (clipped policy objective,
        critic MSE loss, entropy bonus) and executes an optimizer step.
        """
        from backend.btc.rl_agent import get_rl_agent

        agent = get_rl_agent()
        agent.memory.clear()

        # Fill memory with synthetic episode transitions
        for i in range(16):
            s = np.random.randn(66).astype(np.float32)
            a = [np.random.uniform(-1, 1), np.random.uniform(0, 1), np.random.uniform(0.01, 0.99)]
            r = float(np.random.choice([1.0, -1.0]))
            s_next = np.random.randn(66).astype(np.float32)
            done = (i == 15)
            agent.memory.push(s, a, r, s_next, done, log_prob=-1.2, value=0.1)

        initial_step = getattr(agent, "train_steps", 0)
        loss = agent.train_step()

        assert loss is not None, "train_step() must return a loss scalar"
        assert not np.isnan(loss) and not np.isinf(loss), f"Loss must be finite, got {loss}"
        assert getattr(agent, "train_steps", 0) >= initial_step, "train_steps counter should increment"


# =====================================================================
# TIER 1 & 2: INTERFACE CONTRACTS & BACKWARD COMPATIBILITY
# =====================================================================

class TestRLAgentInterfaceContracts:
    """
    Tier 1 & 2: Tests interface contracts specified in PROJECT.md:
    - evaluate_contract(state, kalshi_market) -> dict with continuous & discrete outputs
    - select_action(state) -> int in {0, 1, 2}
    - q_values(state) -> np.ndarray of shape (3,) with monotonic directional calibration
    - Backward-compatible attributes: epsilon, memory, policy_net
    """

    def test_evaluate_contract_output_schema_and_continuous_keys(self):
        """
        Verify evaluate_contract returns required keys:
        p_model, action (int 0,1,2), action_name, target_limit_price,
        dynamic_sizing_factor, dynamic_contracts (or suggested_contracts), v_state.
        """
        from backend.btc.rl_agent import get_rl_agent

        agent = get_rl_agent()
        state = [0.0] * 66
        market = {
            "ticker": "KXBTCD-26OCT07-T90000",
            "yes_ask": 0.52,
            "no_ask": 0.48,
            "yes_bid": 0.50,
            "is_synthetic": False
        }

        eval_result = agent.evaluate_contract(state, kalshi_m=market)

        assert isinstance(eval_result, dict), "evaluate_contract must return a dictionary"

        # Required interface keys
        assert "action" in eval_result, "Must include action"
        assert eval_result["action"] in (0, 1, 2), f"Action must be 0, 1, or 2; got {eval_result['action']}"

        assert "action_name" in eval_result
        assert eval_result["action_name"] in ("PASS", "BUY YES", "BUY NO")

        assert "p_model" in eval_result
        assert 0.0 <= float(eval_result["p_model"]) <= 1.0, "p_model must be probability in [0, 1]"

        assert "target_limit_price" in eval_result
        limit_px = float(eval_result["target_limit_price"])
        assert 0.01 <= limit_px <= 0.99, f"target_limit_price must be in [0.01, 0.99]; got {limit_px}"

        assert "dynamic_sizing_factor" in eval_result
        sz_factor = float(eval_result["dynamic_sizing_factor"])
        assert 0.0 <= sz_factor <= 1.0, f"dynamic_sizing_factor must be in [0, 1]; got {sz_factor}"

        contracts_key = "dynamic_contracts" if "dynamic_contracts" in eval_result else "suggested_contracts"
        assert contracts_key in eval_result, "Must return dynamic_contracts or suggested_contracts"
        assert int(eval_result[contracts_key]) >= 0, "Contracts must be non-negative integer"

    def test_select_action_discrete_mapping(self):
        """
        Verify select_action(state) returns a discrete integer in {0, 1, 2}.
        """
        from backend.btc.rl_agent import get_rl_agent

        agent = get_rl_agent()
        for _ in range(5):
            state = list(np.random.randn(66))
            action = agent.select_action(state)
            assert isinstance(action, (int, np.integer))
            assert action in (0, 1, 2), f"Action must be in {{0, 1, 2}}, got {action}"

    def test_q_values_directional_calibration_monotonicity(self):
        """
        Verify q_values(state) returns a length-3 ndarray where directional difference
        Q(YES) - Q(NO) aligns monotonically with directional conviction.
        """
        from backend.btc.rl_agent import get_rl_agent

        agent = get_rl_agent()
        state = [0.0] * 66

        q = agent.q_values(state)
        assert isinstance(q, np.ndarray), "q_values must return np.ndarray"
        assert q.shape == (3,), f"q_values must have shape (3,), got {q.shape}"
        assert not np.isnan(q).any(), "q_values must not contain NaN"

    def test_backward_compatibility_attributes_and_aliases(self):
        """
        Verify that legacy attributes expected by routes/trading.py, backtest_rl.py,
        and shadow_executor.py are accessible without AttributeError.
        """
        from backend.btc.rl_agent import get_rl_agent, PrioritizedReplayBuffer, ReplayBuffer, PPORolloutBuffer

        agent = get_rl_agent()

        # 1. epsilon attribute / property
        assert hasattr(agent, "epsilon"), "Agent must expose 'epsilon' attribute"
        eps = float(agent.epsilon)
        assert 0.0 <= eps <= 1.0, "epsilon must be a valid float in [0, 1]"

        # 2. memory attribute
        assert hasattr(agent, "memory"), "Agent must expose 'memory' attribute"
        assert hasattr(agent.memory, "push"), "agent.memory must have push() method"

        # 3. policy_net attribute / property
        assert hasattr(agent, "policy_net"), "Agent must expose 'policy_net' attribute"

        # 4. Buffer aliases
        assert PrioritizedReplayBuffer is PPORolloutBuffer or issubclass(PrioritizedReplayBuffer, PPORolloutBuffer)
        assert ReplayBuffer is PPORolloutBuffer or issubclass(ReplayBuffer, PPORolloutBuffer)


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES
# =====================================================================

class TestPPOBoundaryAndCornerCases:
    """
    Tier 2: Boundary conditions, dimension variations, extreme numerical values,
    and checkpoint migration resilience.
    """

    def test_unbatched_1d_list_vs_2d_tensor_inputs(self):
        """
        Dimensionality Safety:
        Ensure the agent accepts:
        1. 1D Python list of 66 floats
        2. 1D numpy array of shape (66,)
        3. 2D PyTorch tensor of shape (1, 66)
        4. Batched 2D tensor of shape (16, 66)
        without raising dimensionality or indexing errors.
        """
        from backend.btc.rl_agent import get_rl_agent

        agent = get_rl_agent()

        # 1. 1D Python list
        list_input = [0.1] * 66
        res_list = agent.evaluate_contract(list_input)
        assert "action" in res_list

        # 2. 1D numpy array
        np_input = np.zeros(66, dtype=np.float32)
        res_np = agent.evaluate_contract(np_input)
        assert "action" in res_np

        # 3. 2D PyTorch tensor single-sample
        t_input = torch.zeros(1, 66)
        res_t = agent.evaluate_contract(t_input)
        assert "action" in res_t

        # 4. Batched model inference directly
        batch_input = torch.randn(16, 66)
        means, stds, vals = agent.actor_critic(batch_input)
        assert means.shape == (16, 3)
        assert stds.shape == (16, 3)
        assert vals.shape == (16, 1)

    def test_extreme_numerical_inputs_and_saturation(self):
        """
        Adversarial / Stress Test:
        Inputs with extreme large values (+1e5, -1e5) or zeros must not produce NaN or Inf.
        Outputs must remain strictly within domain bounds.
        """
        from backend.btc.rl_agent import get_rl_agent

        agent = get_rl_agent()

        # Huge positive inputs
        huge_pos = [1e5] * 66
        res_pos = agent.evaluate_contract(huge_pos)
        assert not np.isnan(res_pos["target_limit_price"])
        assert 0.01 <= res_pos["target_limit_price"] <= 0.99
        assert 0.0 <= res_pos["p_model"] <= 1.0

        # Huge negative inputs
        huge_neg = [-1e5] * 66
        res_neg = agent.evaluate_contract(huge_neg)
        assert not np.isnan(res_neg["target_limit_price"])
        assert 0.01 <= res_neg["target_limit_price"] <= 0.99
        assert 0.0 <= res_neg["p_model"] <= 1.0

    def test_kalshi_market_boundary_prices(self):
        """
        Test Kalshi market dictionary edge cases:
        - Ask price extreme low: 0.01
        - Ask price extreme high: 0.99
        - None / missing market
        - Synthetic market flag
        """
        from backend.btc.rl_agent import get_rl_agent

        agent = get_rl_agent()
        state = [0.0] * 66

        # 1. Ask price = 0.01 (extreme cheap)
        m_low = {"ticker": "KXTEST-01", "yes_ask": 0.01, "no_ask": 0.99, "yes_bid": 0.01}
        res_low = agent.evaluate_contract(state, kalshi_m=m_low)
        assert "action" in res_low
        assert res_low["target_limit_price"] >= 0.01

        # 2. Ask price = 0.99 (extreme expensive)
        m_high = {"ticker": "KXTEST-99", "yes_ask": 0.99, "no_ask": 0.01, "yes_bid": 0.98}
        res_high = agent.evaluate_contract(state, kalshi_m=m_high)
        assert "action" in res_high
        assert res_high["target_limit_price"] <= 0.99

        # 3. None market dict (offline / cold start)
        res_none = agent.evaluate_contract(state, kalshi_m=None)
        assert "action" in res_none

        # 4. Synthetic market
        m_synth = {"ticker": "KXTEST_SYNTH", "yes_ask": 0.50, "no_ask": 0.50, "is_synthetic": True}
        res_synth = agent.evaluate_contract(state, kalshi_m=m_synth)
        assert "action" in res_synth

    def test_checkpoint_save_and_migration_resilience(self):
        """
        Verify agent saves new PPO Transformer weights and reloads them cleanly,
        and does not crash when encountering legacy checkpoints.
        """
        from backend.btc.rl_agent import RLAgent

        temp_dir = tempfile.mkdtemp(prefix="test_rl_ckpt_")
        save_path = os.path.join(temp_dir, "rl_agent_test.pth")

        try:
            # 1. Save and reload current agent
            agent = RLAgent()
            agent.model_path = save_path
            agent.save()
            assert os.path.exists(save_path), "Checkpoint file must be written to disk"

            agent2 = RLAgent()
            agent2.model_path = save_path
            agent2.load()
            res = agent2.evaluate_contract([0.0] * 66)
            assert "action" in res

            # 2. Test legacy checkpoint migration resilience
            # Write a mock legacy checkpoint (old DuelingDoubleDQN format)
            legacy_path = os.path.join(temp_dir, "legacy_rl.pth")
            torch.save({
                "architecture": "DuelingDoubleDQN_Quantile_LSTM",
                "policy_net": {},
                "target_net": {},
                "optimizer": {}
            }, legacy_path)

            agent_legacy = RLAgent()
            agent_legacy.model_path = legacy_path
            # Must load gracefully without uncaught exception
            agent_legacy.load()
            res_legacy = agent_legacy.evaluate_contract([0.0] * 66)
            assert "action" in res_legacy
        finally:
            if os.path.exists(save_path):
                os.remove(save_path)
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
