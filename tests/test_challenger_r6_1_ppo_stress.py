"""
Adversarial Empirical Stress Test Suite for PPO Time-Series Transformer RL Architecture.
Authored by Challenger 1 (teamwork_preview_challenger_r6_1).

Scope & Coverage:
1. Continuous Action Bounds across 1,000 diverse states:
   - a_dir in [-1.0, 1.0]
   - a_size in [0.0, 1.0]
   - a_price in [0.01, 0.99]
   - dynamic_contracts >= 1 integer
   - dynamic_sizing_factor in [0.0, 1.0]
   - target_limit_price in [0.01, 0.99]
   - p_model in [0.0, 1.0]
2. High-Throughput Inference Batches:
   - Batched inference across various batch sizes (1 to 1024)
   - Vectorized throughput benchmarking
3. Numerical Stability on Extreme Inputs:
   - All zeros, extreme large (+1e8, -1e8), tiny subnormals (1e-30)
   - Alternating spikes and high-variance regimes
   - Pipeline sanitization verification for invalid non-finite values
4. Autograd Backpropagation Through ALL Layers & Heads:
   - Comprehensive gradient verification across all 44 named parameters
   - Transformer layers (self-attention, FFN, layer norms), sequence projection,
     static MLP branch, fusion layer, actor head, critic head, and actor_log_std
5. Memory Safety & Leak Verification:
   - Memory delta post-warmup across 1,000 inferences and 100 PPO training steps
   - Buffer capacity and ring buffer memory bounds enforcement
6. Adversarial PPO RL Scenarios:
   - Zero-variance reward advantage normalization
   - Extreme reward bounds
   - Uninitialized log-probs and values recovery
"""

import gc
import os
import time
import pytest
import numpy as np
import torch
import torch.nn as nn
import psutil

from backend.btc.ml_engine import FEATURE_KEYS
from backend.btc.rl_agent import (
    RLAgent,
    PPOTimeSeriesTransformer,
    PPORolloutBuffer,
    get_rl_agent,
)
from backend.btc.shadow_executor import _build_state_vector


# =====================================================================
# 1. CONTINUOUS ACTION BOUNDS ACROSS 1,000 STATES
# =====================================================================

class TestContinuousActionBounds1000States:
    """
    Adversarial verification of 3D continuous action bounds across 1,000 diverse
    and adversarial state vectors.
    """

    @classmethod
    @pytest.fixture(scope="class")
    def state_cohort_1000(cls):
        """Generates exactly 1,000 diverse state vectors with varied statistical properties."""
        np.random.seed(42)
        states = []

        # 1. Standard normal states (300)
        for _ in range(300):
            states.append(np.random.randn(66).astype(np.float32))

        # 2. Uniform wide dynamic range [-50, 50] (300)
        for _ in range(300):
            states.append(np.random.uniform(-50.0, 50.0, 66).astype(np.float32))

        # 3. Heavy-tailed Cauchy distributions (200)
        for _ in range(200):
            states.append(np.random.standard_cauchy(66).astype(np.float32))

        # 4. Sparse one-hot / isolated spike states (100)
        for i in range(100):
            s = np.zeros(66, dtype=np.float32)
            idx = i % 66
            s[idx] = 100.0 if (i % 2 == 0) else -100.0
            states.append(s)

        # 5. Extreme boundary states (100)
        for i in range(100):
            if i < 25:
                states.append(np.full(66, 1e4, dtype=np.float32))
            elif i < 50:
                states.append(np.full(66, -1e4, dtype=np.float32))
            elif i < 75:
                states.append(np.zeros(66, dtype=np.float32))
            else:
                s = np.array([10.0 if j % 2 == 0 else -10.0 for j in range(66)], dtype=np.float32)
                states.append(s)

        assert len(states) == 1000, f"Expected 1000 states, got {len(states)}"
        return states

    def test_continuous_action_bounds_compliance_1000_states(self, state_cohort_1000):
        """
        Empirically verify across 1,000 states that:
        - a_dir in [-1.0, 1.0]
        - a_size in [0.0, 1.0]
        - a_price in [0.01, 0.99]
        """
        agent = get_rl_agent()

        for idx, s in enumerate(state_cohort_1000):
            # Exploit mode (mean action)
            a_dir, a_size, a_price = agent.select_continuous_action(s, exploit=True)

            assert -1.0 - 1e-6 <= a_dir <= 1.0 + 1e-6, f"State {idx}: a_dir={a_dir} out of [-1.0, 1.0]"
            assert 0.0 - 1e-6 <= a_size <= 1.0 + 1e-6, f"State {idx}: a_size={a_size} out of [0.0, 1.0]"
            assert 0.01 - 1e-6 <= a_price <= 0.99 + 1e-6, f"State {idx}: a_price={a_price} out of [0.01, 0.99]"
            assert np.isfinite(a_dir) and np.isfinite(a_size) and np.isfinite(a_price)

            # Stochastic sampling mode
            s_dir, s_size, s_price = agent.select_continuous_action(s, exploit=False)
            assert -1.0 - 1e-6 <= s_dir <= 1.0 + 1e-6, f"State {idx} (stoch): s_dir={s_dir} out of [-1.0, 1.0]"
            assert 0.0 - 1e-6 <= s_size <= 1.0 + 1e-6, f"State {idx} (stoch): s_size={s_size} out of [0.0, 1.0]"
            assert 0.01 - 1e-6 <= s_price <= 0.99 + 1e-6, f"State {idx} (stoch): s_price={s_price} out of [0.01, 0.99]"
            assert np.isfinite(s_dir) and np.isfinite(s_size) and np.isfinite(s_price)

    def test_evaluate_contract_bounds_and_schema_1000_states(self, state_cohort_1000):
        """
        Empirically verify evaluate_contract returns compliant keys and valid bounds:
        - target_limit_price in [0.01, 0.99]
        - dynamic_sizing_factor in [0.0, 1.0]
        - dynamic_contracts >= 1 (integer)
        - p_model in [0.0, 1.0]
        - action in {0, 1, 2}
        """
        agent = get_rl_agent()
        sample_markets = [
            {"ticker": "KXTEST-MID", "yes_ask": 0.50, "no_ask": 0.50, "yes_bid": 0.48},
            {"ticker": "KXTEST-LOW", "yes_ask": 0.05, "no_ask": 0.95, "yes_bid": 0.04},
            {"ticker": "KXTEST-HIGH", "yes_ask": 0.95, "no_ask": 0.05, "yes_bid": 0.94},
            None
        ]

        for idx, s in enumerate(state_cohort_1000):
            m = sample_markets[idx % len(sample_markets)]
            res = agent.evaluate_contract(s, kalshi_m=m)

            assert isinstance(res, dict)
            assert res["action"] in (0, 1, 2)
            assert res["action_name"] in ("PASS", "BUY YES", "BUY NO")

            # Check bounds
            limit_px = res["target_limit_price"]
            assert 0.01 <= limit_px <= 0.99, f"State {idx}: limit_px={limit_px} out of bounds"

            sz_factor = res["dynamic_sizing_factor"]
            assert 0.0 <= sz_factor <= 1.0, f"State {idx}: sz_factor={sz_factor} out of bounds"

            contracts = res["dynamic_contracts"]
            assert isinstance(contracts, int) and contracts >= 1, f"State {idx}: contracts={contracts} < 1"

            p_model = res["p_model"]
            assert 0.0 <= p_model <= 1.0, f"State {idx}: p_model={p_model} out of [0, 1]"
            assert np.isfinite(res["v_state"])

    def test_stochastic_sampling_clamps_extreme_noise(self):
        """
        Verify that even if normal distribution samples extreme values,
        get_action_and_value clamps them strictly within valid bounds.
        """
        model = PPOTimeSeriesTransformer(input_dim=66)
        # Artificially set actor_log_std very high to trigger extreme samples
        model.actor_log_std.data.fill_(5.0)

        batch_state = torch.randn(200, 66)
        actions, log_prob, entropy, val = model.get_action_and_value(batch_state)

        act_np = actions.detach().cpu().numpy()
        assert np.all(act_np[:, 0] >= -1.0) and np.all(act_np[:, 0] <= 1.0)
        assert np.all(act_np[:, 1] >= 0.0) and np.all(act_np[:, 1] <= 1.0)
        assert np.all(act_np[:, 2] >= 0.01) and np.all(act_np[:, 2] <= 0.99)
        assert torch.all(torch.isfinite(log_prob))
        assert torch.all(torch.isfinite(entropy))
        assert torch.all(torch.isfinite(val))


# =====================================================================
# 2. HIGH-THROUGHPUT INFERENCE BATCHES
# =====================================================================

class TestHighThroughputInferenceBatches:
    """
    Stress-tests batched inference across varying batch sizes and measures throughput.
    """

    @pytest.mark.parametrize("batch_size", [1, 16, 64, 256, 1024])
    def test_batched_forward_pass_dimensions(self, batch_size):
        """Verify model handles small to large batches cleanly."""
        model = PPOTimeSeriesTransformer(input_dim=66)
        x = torch.randn(batch_size, 66)

        action_mean, action_std, value = model(x)
        assert action_mean.shape == (batch_size, 3)
        assert action_std.shape == (batch_size, 3)
        assert value.shape == (batch_size, 1)

    def test_inference_throughput_benchmark(self):
        """
        Verify inference throughput meets high-performance requirements (> 10,000 samples/sec batched).
        """
        agent = get_rl_agent()
        batch_size = 512
        x = torch.randn(batch_size, 66, device=agent.device)

        # Warmup
        for _ in range(5):
            _ = agent.actor_critic(x)

        start = time.perf_counter()
        iters = 20
        for _ in range(iters):
            _ = agent.actor_critic(x)
        elapsed = time.perf_counter() - start

        total_samples = batch_size * iters
        throughput = total_samples / elapsed
        print(f"\nPPO Transformer Throughput: {throughput:,.1f} samples/sec ({elapsed:.4f}s for {total_samples} samples)")
        assert throughput > 10000, f"Throughput too low: {throughput:.1f} samples/sec"

    def test_q_values_batch_vectorization(self):
        """Verify q_values_batch produces consistent results with scalar q_values."""
        agent = get_rl_agent()
        states = [list(np.random.randn(66)) for _ in range(16)]

        batch_q = agent.q_values_batch(states)
        assert batch_q.shape == (16, 3)

        for i, s in enumerate(states):
            single_q = agent.q_values(s)
            np.testing.assert_allclose(batch_q[i], single_q, atol=1e-5)


# =====================================================================
# 3. NUMERICAL STABILITY ON EXTREME INPUTS
# =====================================================================

class TestNumericalStabilityExtremeInputs:
    """
    Stress-tests numerical stability under extreme outliers, near-zero subnormals,
    and large dynamic range inputs.
    """

    def test_all_zeros_input(self):
        """Verify model on zero vector produces valid finite outputs."""
        agent = get_rl_agent()
        zero_state = [0.0] * 66
        res = agent.evaluate_contract(zero_state)
        assert res["action"] in (0, 1, 2)
        assert np.isfinite(res["target_limit_price"])
        assert 0.01 <= res["target_limit_price"] <= 0.99
        assert 0.0 <= res["dynamic_sizing_factor"] <= 1.0

    def test_massive_positive_and_negative_saturation(self):
        """Verify +1e8 and -1e8 do not produce NaN or overflow."""
        agent = get_rl_agent()

        # Extreme positive
        res_pos = agent.evaluate_contract([1e8] * 66)
        assert np.isfinite(res_pos["target_limit_price"])
        assert 0.01 <= res_pos["target_limit_price"] <= 0.99
        assert 0.0 <= res_pos["p_model"] <= 1.0
        assert res_pos["dynamic_contracts"] >= 1

        # Extreme negative
        res_neg = agent.evaluate_contract([-1e8] * 66)
        assert np.isfinite(res_neg["target_limit_price"])
        assert 0.01 <= res_neg["target_limit_price"] <= 0.99
        assert 0.0 <= res_neg["p_model"] <= 1.0
        assert res_neg["dynamic_contracts"] >= 1

    def test_tiny_subnormals_near_zero(self):
        """Verify 1e-30 subnormal values execute stably without underflow errors."""
        agent = get_rl_agent()
        res = agent.evaluate_contract([1e-30] * 66)
        assert np.isfinite(res["target_limit_price"])
        assert 0.01 <= res["target_limit_price"] <= 0.99
        assert res["dynamic_contracts"] >= 1

    def test_alternating_polar_spikes(self):
        """Verify input with alternating large positive and negative spikes."""
        agent = get_rl_agent()
        state = [1e6 if i % 2 == 0 else -1e6 for i in range(66)]
        res = agent.evaluate_contract(state)
        assert np.isfinite(res["target_limit_price"])
        assert 0.01 <= res["target_limit_price"] <= 0.99

    def test_pipeline_sanitizes_nan_and_inf_features(self):
        """
        Verify that _build_state_vector properly filters out NaN and Inf values
        from raw feature dictionaries, protecting the downstream PyTorch model.
        """
        raw_feat_with_nans = {k: float("nan") for k in FEATURE_KEYS[:10]}
        raw_feat_with_nans.update({k: float("inf") for k in FEATURE_KEYS[10:20]})
        raw_feat_with_nans.update({k: float("-inf") for k in FEATURE_KEYS[20:30]})

        state = _build_state_vector(raw_feat_with_nans)
        assert len(state) == 66
        assert all(np.isfinite(x) for x in state), "All state elements must be finite after _build_state_vector"

        agent = get_rl_agent()
        res = agent.evaluate_contract(state)
        assert np.isfinite(res["target_limit_price"])
        assert 0.01 <= res["target_limit_price"] <= 0.99


# =====================================================================
# 4. AUTOGRAD BACKPROPAGATION THROUGH ALL LAYERS AND HEADS
# =====================================================================

class TestAutogradBackpropagationThroughAllLayersAndHeads:
    """
    Exhaustive empirical test verifying that autograd backpropagation flows through
    EVERY named parameter in the PPO Transformer Actor-Critic network during PPO training.
    """

    def test_all_trainable_parameters_receive_valid_gradients(self):
        """
        Inspect all 44 named parameters of PPOTimeSeriesTransformer after train_step():
        1. Verify requires_grad is True for all parameters.
        2. Verify param.grad is not None.
        3. Verify param.grad is finite (no NaNs, no Infs).
        4. Verify param.grad is non-zero.
        """
        agent = get_rl_agent()
        agent.memory.clear()

        # Prime memory buffer with synthetic transitions
        for i in range(32):
            s = np.random.randn(66).astype(np.float32)
            a = [float(np.random.uniform(-0.8, 0.8)), float(np.random.uniform(0.2, 0.8)), float(np.random.uniform(0.2, 0.8))]
            r = float(np.random.choice([1.5, -1.5]))
            s_next = np.random.randn(66).astype(np.float32)
            done = (i % 8 == 7)
            agent.memory.push(s, a, r, s_next, done, log_prob=-0.5, value=0.1)

        # Clear prior grads and execute training step
        agent.optimizer.zero_grad()
        loss = agent.train_step()
        assert loss > 0.0, f"PPO loss must be positive, got {loss}"

        named_params = list(agent.actor_critic.named_parameters())
        assert len(named_params) > 30, f"Expected >30 parameters, found {len(named_params)}"

        missing_grad = []
        zero_grad = []
        nan_grad = []

        for name, param in named_params:
            assert param.requires_grad is True, f"Parameter {name} requires_grad is False"
            if param.grad is None:
                missing_grad.append(name)
            else:
                if torch.isnan(param.grad).any() or torch.isinf(param.grad).any():
                    nan_grad.append(name)
                if torch.all(param.grad == 0):
                    zero_grad.append(name)

        assert not missing_grad, f"Parameters missing gradients: {missing_grad}"
        assert not nan_grad, f"Parameters with NaN/Inf gradients: {nan_grad}"
        assert not zero_grad, f"Parameters with all-zero gradients: {zero_grad}"

    def test_gradient_norm_clipping_bounds(self):
        """Verify gradient norm clipping successfully caps exploding gradients."""
        model = PPOTimeSeriesTransformer(input_dim=66)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

        # Create massive synthetic loss
        state = torch.randn(8, 66)
        _, log_prob, _, val = model.get_action_and_value(state)
        huge_loss = (val * 1e6).sum() - (log_prob * 1e6).sum()

        optimizer.zero_grad()
        huge_loss.backward()

        # Before clip, gradient norm should be large
        pre_clip_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        assert pre_clip_norm > 1.0, f"Pre-clip norm should be large, got {pre_clip_norm}"

        # After clipping, re-check total norm
        total_norm = 0.0
        for p in model.parameters():
            if p.grad is not None:
                param_norm = p.grad.data.norm(2)
                total_norm += param_norm.item() ** 2
        total_norm = total_norm ** 0.5
        assert total_norm <= 1.05, f"Clipped norm must be <= 1.0 (with slight fp margin), got {total_norm}"


# =====================================================================
# 5. MEMORY SAFETY & LEAK VERIFICATION
# =====================================================================

class TestMemorySafetyAndLeakVerification:
    """
    Stress-tests memory safety, tracking process RSS across 1,000 inferences
    and 100 PPO training steps, and tests buffer capacity bounds.
    """

    def test_inference_and_training_memory_stability(self):
        """
        Verify that repeated inference (1,000 steps) and PPO training (100 steps)
        do not leak memory (RSS delta post-warmup < 25 MB).
        """
        agent = get_rl_agent()
        proc = psutil.Process(os.getpid())

        # Warmup: populate buffer and run a few steps
        for _ in range(50):
            agent.memory.push(np.random.randn(66), [0.1, 0.5, 0.5], 1.0, np.random.randn(66), False, -0.5, 0.2)
        for _ in range(10):
            agent.train_step()
        gc.collect()

        mem_warmup = proc.memory_info().rss / (1024 * 1024)

        # 1,000 sequential inferences
        dummy_state = np.zeros(66, dtype=np.float32)
        for _ in range(1000):
            agent.evaluate_contract(dummy_state)

        # 100 additional experiences and 100 training steps
        for _ in range(100):
            agent.memory.push(np.random.randn(66), [0.2, 0.6, 0.5], -1.0, np.random.randn(66), False, -0.6, 0.1)
        for _ in range(100):
            agent.train_step()

        gc.collect()
        mem_final = proc.memory_info().rss / (1024 * 1024)
        mem_delta = mem_final - mem_warmup

        print(f"\nMemory Profile — Warmup: {mem_warmup:.2f} MB | Final: {mem_final:.2f} MB | Delta: {mem_delta:+.2f} MB")
        assert mem_delta < 25.0, f"Memory leak detected: RSS increased by {mem_delta:.2f} MB (threshold 25 MB)"

    def test_rollout_buffer_capacity_enforcement(self):
        """
        Verify PPORolloutBuffer strictly respects capacity limit when overloaded.
        """
        cap = 500
        buf = PPORolloutBuffer(capacity=cap)
        dummy_s = np.zeros(66)

        # Push 1,500 items into buffer with capacity 500
        for i in range(1500):
            buf.push(dummy_s, [0.0, 0.5, 0.5], float(i), dummy_s, False)

        assert len(buf) == cap, f"Buffer size {len(buf)} exceeded capacity {cap}"
        # Verify circular ring buffer overwritten items
        assert buf.rewards[0] == 1000.0, "Expected ring buffer to overwrite earlier items"


# =====================================================================
# 6. ADVERSARIAL PPO RL SCENARIOS
# =====================================================================

class TestPPOAdversarialRLScenarios:
    """
    Stress-tests edge-case RL scenarios: zero reward variance, uninitialized log-probs,
    extreme rewards, and pseudo-Q monotonicity.
    """

    def test_zero_reward_variance_advantage_normalization(self):
        """
        Verify that when all rewards are identical (variance = 0), advantage normalization
        does not divide by zero or produce NaNs.
        """
        agent = get_rl_agent()
        agent.memory.clear()

        # Push 20 identical transitions with reward = 0.0
        for _ in range(20):
            s = np.zeros(66, dtype=np.float32)
            agent.memory.push(s, [0.0, 0.5, 0.5], 0.0, s, False, log_prob=0.0, value=0.0)

        loss = agent.train_step()
        assert np.isfinite(loss), f"Loss on zero-variance batch should be finite, got {loss}"

    def test_extreme_rewards_stability(self):
        """
        Verify that extreme rewards (+1000, -1000) do not cause loss blowup or NaNs.
        """
        agent = get_rl_agent()
        agent.memory.clear()

        for i in range(20):
            s = np.random.randn(66).astype(np.float32)
            r = 1000.0 if i % 2 == 0 else -1000.0
            agent.memory.push(s, [0.5, 0.5, 0.5], r, s, False, log_prob=-1.0, value=0.0)

        loss = agent.train_step()
        assert np.isfinite(loss), f"Loss on extreme rewards must be finite, got {loss}"

    def test_pseudo_q_directional_monotonicity(self):
        """
        Verify that compute_pseudo_q guarantees:
        Q(yes) - Q(no) = 2 * a_dir * a_size
        """
        agent = get_rl_agent()
        states = torch.randn(10, 66)

        q_vals = agent.actor_critic.compute_pseudo_q(states)
        action_mean, _, _ = agent.actor_critic(states)

        a_dir = action_mean[:, 0]
        a_size = action_mean[:, 1]
        expected_diff = 2.0 * a_dir * a_size
        actual_diff = q_vals[:, 1] - q_vals[:, 2]

        torch.testing.assert_close(actual_diff, expected_diff, atol=1e-5, rtol=1e-5)
