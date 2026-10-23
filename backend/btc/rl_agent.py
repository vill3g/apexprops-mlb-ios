import json
import logging
import math
import os
import random
import threading
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal

from backend.btc.ml_engine import FEATURE_KEYS

logger = logging.getLogger(__name__)

# =====================================================================
# PROBABILITY CALIBRATION + PRICE-AWARE DECISION
# =====================================================================
CALIBRATION_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "model_cache", "rl_calibration.json")
DEFAULT_MIN_EDGE = 0.02  # required (probability - price - fee), in dollars per $1 contract
_calibration_cache = {"mtime": None, "data": None}


def kalshi_fee_per_contract(price: float) -> float:
    """Kalshi taker fee approximation per contract: 0.07 * P * (1 - P)."""
    price = min(max(float(price), 0.0), 1.0)
    return 0.07 * price * (1.0 - price)


def load_calibration() -> Optional[dict]:
    """Return the Platt calibration dict {a, b, ...} or None if missing/invalid."""
    try:
        mtime = os.path.getmtime(CALIBRATION_PATH)
    except OSError:
        _calibration_cache.update(mtime=None, data=None)
        return None
    if _calibration_cache["mtime"] != mtime:
        try:
            with open(CALIBRATION_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            float(data["a"])
            float(data["b"])
            _calibration_cache.update(mtime=mtime, data=data)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            logger.warning(f"[RLAgent] Ignoring invalid calibration file: {e}")
            _calibration_cache.update(mtime=mtime, data=None)
    return _calibration_cache["data"]


def calibrated_p_yes(score: float, calibration=None) -> Optional[float]:
    """P(YES) for a directional score (Q_yes - Q_no); None when uncalibrated."""
    cal = calibration if calibration is not None else load_calibration()
    if not cal:
        return None
    z = float(cal["a"]) * float(score) + float(cal["b"])
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + float(np.exp(-z)))


def fit_platt(scores, labels, l2: float = 1e-3, iters: int = 50) -> Tuple[float, float]:
    """1-D logistic regression P(y=1) = sigmoid(a*score + b) via Newton's method."""
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    X = np.c_[s, np.ones_like(s)]
    w = np.zeros(2)
    reg = l2 * np.diag([1.0, 0.0])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (p - y) + reg @ w
        H = (X * (p * (1 - p))[:, None]).T @ X + reg
        w = w - np.linalg.solve(H, g)
    return float(w[0]), float(w[1])


def market_prices(kalshi_m) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """(yes_ask, no_ask, yes_mid) in dollars from a Kalshi market dict; Nones if unusable."""
    if not kalshi_m or kalshi_m.get("is_synthetic") or str(kalshi_m.get("ticker", "")).endswith("_SYNTH"):
        return None, None, None

    def _px(k):
        try:
            v = float(kalshi_m.get(k))
            return v if 0.0 < v < 1.0 else None
        except (TypeError, ValueError):
            return None

    yes_ask, no_ask, yes_bid = _px("yes_ask"), _px("no_ask"), _px("yes_bid")
    if yes_ask is None or no_ask is None:
        return yes_ask, no_ask, None
    yes_mid = (yes_bid + yes_ask) / 2.0 if (yes_bid is not None and yes_bid <= yes_ask) else (yes_ask + (1.0 - no_ask)) / 2.0
    return yes_ask, no_ask, yes_mid


# =====================================================================
# TIME-SERIES TRANSFORMER ENCODER & ACTOR-CRITIC (PPO)
# =====================================================================

class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for temporal multi-lag sequence features."""
    def __init__(self, d_model: int = 64, max_len: int = 20):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, :x.size(1)]


class PPOTimeSeriesTransformer(nn.Module):
    """
    Time-Series Transformer Actor-Critic Network for Kalshi 15-Minute Markets.
    - PyTorch nn.TransformerEncoder on sequence indicators (5 lags x 5 indicators = 25 features).
    - MLP branch on static market features (41 indicators).
    - Fusion layer combining temporal and static representations (128-dim latent space).
    - Continuous Actor Heads (R^3):
        * a_dir in [-1.0, 1.0] (Directional Conviction via tanh)
        * a_size in [0.0, 1.0] (Dynamic Order Sizing via sigmoid -> contract count)
        * a_price in [0.01, 0.99] (Target Limit Price via 0.01 + 0.98 * sigmoid)
    - Value Function Critic Head: V(s) in R scalar return.
    """
    def __init__(
        self,
        input_dim: int = len(FEATURE_KEYS),
        seq_len: int = 5,
        seq_features: int = 5,
        hidden_dim: int = 128,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2
    ):
        super().__init__()
        self.input_dim = input_dim
        self.seq_len = seq_len
        self.seq_features = seq_features
        self.static_features = input_dim - (seq_len * seq_features)
        self.d_model = d_model
        self.hidden_dim = hidden_dim

        # Sequence Branch: Projection -> Positional Encoding -> 2-layer Pre-LN TransformerEncoder (SiLU)
        self.seq_proj = nn.Linear(seq_features, d_model)
        self.pos_encoder = PositionalEncoding(d_model=d_model, max_len=seq_len + 5)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=128,
            activation=torch.nn.functional.silu,
            dropout=0.0,
            batch_first=True,
            norm_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers, enable_nested_tensor=False)
        self.seq_norm = nn.LayerNorm(d_model)

        # Static Features Branch: Linear(41, 64) -> LayerNorm -> SiLU
        self.static_mlp = nn.Sequential(
            nn.Linear(self.static_features, 64),
            nn.LayerNorm(64),
            nn.SiLU()
        )

        # Feature Fusion Layer: Linear(64 + 64, 128) -> LayerNorm -> SiLU
        self.fusion = nn.Sequential(
            nn.Linear(64 + d_model, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU()
        )

        # Critic Head: Linear(128, 64) -> SiLU -> Linear(64, 1) -> V(s)
        self.critic = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.SiLU(),
            nn.Linear(64, 1)
        )

        # Actor Head: Linear(128, 64) -> SiLU -> Linear(64, 3)
        self.actor_mean = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.SiLU(),
            nn.Linear(64, 3)
        )
        # Learnable log standard deviation parameter for 3 continuous action dimensions
        self.actor_log_std = nn.Parameter(torch.zeros(3))

    def _extract_latent(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 1:
            x = x.unsqueeze(0)
        batch_size = x.size(0)
        x_static = x[:, :self.static_features]
        x_seq_flat = x[:, self.static_features:]
        x_seq = x_seq_flat.view(batch_size, self.seq_len, self.seq_features)

        # Process sequence through Time-Series Transformer
        h_seq = self.pos_encoder(self.seq_proj(x_seq))
        trans_out = self.transformer(h_seq)
        seq_rep = self.seq_norm(trans_out[:, -1, :])  # Extract latest timestep lag_0

        # Process static market indicators
        static_rep = self.static_mlp(x_static)

        # Fused 128-dim latent space
        return self.fusion(torch.cat([static_rep, seq_rep], dim=1))

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Returns (action_mean, action_std, value)."""
        if x.dim() == 1:
            x = x.unsqueeze(0)
        latent = self._extract_latent(x)
        value = self.critic(latent)
        raw_mean = self.actor_mean(latent)

        # Bounded continuous action heads
        mean_dir = torch.tanh(raw_mean[:, 0:1])                         # [-1.0, 1.0]
        mean_size = torch.sigmoid(raw_mean[:, 1:2])                      # [0.0, 1.0]
        mean_price = 0.01 + 0.98 * torch.sigmoid(raw_mean[:, 2:3])       # [0.01, 0.99]
        action_mean = torch.cat([mean_dir, mean_size, mean_price], dim=1)

        std = torch.exp(self.actor_log_std).unsqueeze(0).expand_as(action_mean)
        return action_mean, std, value

    def compute_pseudo_q(self, x: torch.Tensor) -> torch.Tensor:
        """
        Computes calibrated pseudo-Q values [Q_pass, Q_yes, Q_no] with shape (batch, 3).
        Preserves strictly monotonic directional conviction slope:
            Q_yes - Q_no = 2 * a_dir * a_size
        """
        if x.dim() == 1:
            x = x.unsqueeze(0)
        action_mean, _, value = self.forward(x)
        v = value.squeeze(-1)
        a_dir = action_mean[:, 0]
        a_size = action_mean[:, 1]
        q_pass = v
        q_yes = v + a_dir * a_size
        q_no = v - a_dir * a_size
        return torch.stack([q_pass, q_yes, q_no], dim=1)

    def get_action_and_value(self, x: torch.Tensor, action: torch.Tensor = None):
        """Used during PPO training and evaluation to compute log_prob and entropy."""
        action_mean, action_std, value = self.forward(x)
        dist = Normal(action_mean, action_std)

        if action is None:
            raw_sample = dist.sample()
            action = torch.stack([
                torch.clamp(raw_sample[:, 0], -1.0, 1.0),
                torch.clamp(raw_sample[:, 1], 0.0, 1.0),
                torch.clamp(raw_sample[:, 2], 0.01, 0.99)
            ], dim=1)

        log_prob = dist.log_prob(action).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1)
        return action, log_prob, entropy, value.squeeze(-1)


class PolicyNetAdapter(nn.Module):
    """
    100% Backward compatibility adapter wrapping PPOTimeSeriesTransformer to behave
    identically to legacy policy_net callers expecting (batch, 3) Q-values.
    """
    def __init__(self, actor_critic: PPOTimeSeriesTransformer):
        super().__init__()
        self.actor_critic = actor_critic
        self.num_actions = 3
        self.num_quantiles = 1

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.actor_critic.compute_pseudo_q(x)

    def eval(self):
        self.actor_critic.eval()
        return self

    def train(self, mode: bool = True):
        self.actor_critic.train(mode)
        return self

    def state_dict(self, *args, **kwargs):
        return self.actor_critic.state_dict(*args, **kwargs)

    def load_state_dict(self, *args, **kwargs):
        return self.actor_critic.load_state_dict(*args, **kwargs)

    def parameters(self, *args, **kwargs):
        return self.actor_critic.parameters(*args, **kwargs)

    def named_parameters(self, *args, **kwargs):
        return self.actor_critic.named_parameters(*args, **kwargs)

    def to(self, *args, **kwargs):
        self.actor_critic.to(*args, **kwargs)
        return self

    def __getattr__(self, name: str):
        try:
            return super().__getattr__(name)
        except AttributeError:
            return getattr(self.actor_critic, name)


# Aliases for backwards compatibility with legacy imports
DuelingDQN = PPOTimeSeriesTransformer
DQN = PPOTimeSeriesTransformer


# =====================================================================
# PPO ROLLOUT BUFFER & GENERALIZED ADVANTAGE ESTIMATION (GAE)
# =====================================================================

class PPORolloutBuffer:
    """
    PPO Rollout Buffer with support for both multi-step trajectories with GAE-lambda
    and backward-compatible single-step pushes from shadow settlements.
    """
    def __init__(self, capacity: int = 25000, gamma: float = 0.99, gae_lambda: float = 0.95):
        self.capacity = capacity
        self.gamma = gamma
        self.gae_lambda = gae_lambda

        self.states: List[np.ndarray] = []
        self.actions: List[np.ndarray] = []
        self.rewards: List[float] = []
        self.next_states: List[np.ndarray] = []
        self.dones: List[bool] = []
        self.log_probs: List[float] = []
        self.values: List[float] = []
        self.pos = 0

    def push(
        self,
        state,
        action,
        reward,
        next_state,
        done,
        log_prob: Optional[float] = None,
        value: Optional[float] = None
    ):
        s = np.array(state, dtype=np.float32)
        ns = np.array(next_state, dtype=np.float32)

        # Convert discrete action integer to continuous target vector if necessary
        if isinstance(action, (int, np.integer)):
            if action == 1:       # BUY YES
                a = np.array([0.8, 0.8, 0.50], dtype=np.float32)
            elif action == 2:     # BUY NO
                a = np.array([-0.8, 0.8, 0.50], dtype=np.float32)
            else:                 # PASS
                a = np.array([0.0, 0.1, 0.50], dtype=np.float32)
        elif isinstance(action, (list, tuple, np.ndarray)):
            a = np.array(action, dtype=np.float32)
            if a.ndim == 0 or len(a) != 3:
                a = np.array([float(action), 0.5, 0.50], dtype=np.float32)
        else:
            a = np.array([float(action), 0.5, 0.50], dtype=np.float32)

        lp = float(log_prob) if log_prob is not None else 0.0
        val = float(value) if value is not None else 0.0
        r = float(reward)
        d = bool(done)

        if len(self.states) < self.capacity:
            self.states.append(s)
            self.actions.append(a)
            self.rewards.append(r)
            self.next_states.append(ns)
            self.dones.append(d)
            self.log_probs.append(lp)
            self.values.append(val)
        else:
            idx = self.pos % self.capacity
            self.states[idx] = s
            self.actions[idx] = a
            self.rewards[idx] = r
            self.next_states[idx] = ns
            self.dones[idx] = d
            self.log_probs[idx] = lp
            self.values[idx] = val
        self.pos += 1

    def sample_batch(self, batch_size: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        N = len(self.states)
        if N == 0:
            raise ValueError("Cannot sample from an empty PPORolloutBuffer")
        size = min(batch_size, N)
        indices = np.random.choice(N, size, replace=False)

        states = np.array([self.states[i] for i in indices], dtype=np.float32)
        actions = np.array([self.actions[i] for i in indices], dtype=np.float32)
        rewards = np.array([self.rewards[i] for i in indices], dtype=np.float32)
        next_states = np.array([self.next_states[i] for i in indices], dtype=np.float32)
        dones = np.array([self.dones[i] for i in indices], dtype=np.float32)
        log_probs = np.array([self.log_probs[i] for i in indices], dtype=np.float32)
        values = np.array([self.values[i] for i in indices], dtype=np.float32)
        return states, actions, rewards, next_states, dones, log_probs, values, indices

    def sample(self, batch_size: int):
        """Legacy adapter returning 7-element tuple compatible with legacy PER samplers."""
        states, actions, rewards, next_states, dones, _, _, indices = self.sample_batch(batch_size)
        weights = np.ones(len(indices), dtype=np.float32)
        # Convert continuous actions to discrete argmax for legacy discrete callers if needed
        discrete_actions = []
        for a in actions:
            if a[0] > 0.15:
                discrete_actions.append(1)
            elif a[0] < -0.15:
                discrete_actions.append(2)
            else:
                discrete_actions.append(0)
        return (
            states,
            np.array(discrete_actions, dtype=np.int64),
            rewards,
            next_states,
            dones,
            indices,
            weights
        )

    def update_priorities(self, batch_indices, batch_priorities):
        """No-op for backward compatibility with legacy PER updates."""
        pass

    def clear(self):
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.next_states.clear()
        self.dones.clear()
        self.log_probs.clear()
        self.values.clear()
        self.pos = 0

    def __len__(self):
        return len(self.states)


# Backward compatibility aliases
PrioritizedReplayBuffer = PPORolloutBuffer
ReplayBuffer = PPORolloutBuffer


# =====================================================================
# REINFORCEMENT LEARNING AGENT (PPO Transformer Actor-Critic)
# =====================================================================

class RLAgent:
    """
    Production-grade Reinforcement Learning Agent for Kalshi 15-Minute Markets.
    Architecture:
      - 2-Layer Pre-LN PyTorch nn.TransformerEncoder backbone on multi-lag features.
      - Continuous Action Space Heads (Conviction, Dynamic Contract Sizing, Target Limit Price).
      - State Value Critic V(s).
      - PPO Clipped Surrogate Loss + Critic MSE Loss + Action Entropy Bonus.
      - Generalized Advantage Estimation (GAE).
      - 100% Backward-Compatible Interfaces (select_action, q_values, policy_net, etc.).
    """
    def __init__(
        self,
        state_dim: int = len(FEATURE_KEYS),
        action_dim: int = 3,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_eps: float = 0.20,
        c_val: float = 0.50,
        c_ent: float = 0.01,
        tau: float = 0.005,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.02,
        epsilon_decay: float = 0.998
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_eps = clip_eps
        self.c_val = c_val
        self.c_ent = c_ent
        self.tau = tau

        self._epsilon = float(epsilon_start)
        self.epsilon_end = float(epsilon_end)
        self.epsilon_decay = float(epsilon_decay)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.actor_critic = PPOTimeSeriesTransformer(input_dim=state_dim).to(self.device)
        self.policy_net = PolicyNetAdapter(self.actor_critic)
        self.target_net = self.policy_net

        self.optimizer = optim.AdamW(self.actor_critic.parameters(), lr=lr, weight_decay=1e-4)
        self.memory = PPORolloutBuffer(capacity=25000, gamma=gamma, gae_lambda=gae_lambda)
        self.batch_size = 128
        self.lock = threading.RLock()
        self.train_steps = 0

        self.model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "model_cache", "rl_agent.pth")
        self.load()

    @property
    def epsilon(self) -> float:
        return self._epsilon

    @epsilon.setter
    def epsilon(self, value: float):
        self._epsilon = float(value)

    def select_continuous_action(self, state, exploit: bool = False) -> Tuple[float, float, float]:
        """
        Returns continuous action tuple (a_dir, a_size, a_price) in R^3.
        a_dir in [-1, 1], a_size in [0, 1], a_price in [0.01, 0.99].
        """
        with self.lock:
            state_tensor = torch.FloatTensor(state).to(self.device)
            if state_tensor.dim() == 1:
                state_tensor = state_tensor.unsqueeze(0)

            with torch.no_grad():
                if exploit or (random.random() >= self._epsilon):
                    action_mean, _, _ = self.actor_critic(state_tensor)
                    a = action_mean[0].cpu().numpy()
                else:
                    action, _, _, _ = self.actor_critic.get_action_and_value(state_tensor)
                    a = action[0].cpu().numpy()

            return float(a[0]), float(a[1]), float(a[2])

    def select_action(self, state, exploit: bool = False) -> int:
        """
        Backward-compatible discrete action selector:
            0: PASS (CAPITAL PRESERVATION)
            1: BUY YES (ABOVE)
            2: BUY NO (BELOW)
        """
        with self.lock:
            if not exploit and random.random() < self._epsilon:
                return random.randrange(3)

            a_dir, a_size, _ = self.select_continuous_action(state, exploit=True)
            if abs(a_dir) <= 0.15 or a_size < 0.10:
                return 0
            return 1 if a_dir > 0.15 else 2

    def q_values(self, state) -> np.ndarray:
        """
        Backward-compatible pseudo-Q values [Q_pass, Q_yes, Q_no].
        Shape: (3,). Preserves directional monotonicity for calibrate_rl.py.
        """
        with self.lock:
            state_tensor = torch.FloatTensor(state).to(self.device)
            if state_tensor.dim() == 1:
                state_tensor = state_tensor.unsqueeze(0)
            with torch.no_grad():
                pseudo_q = self.actor_critic.compute_pseudo_q(state_tensor)
                return pseudo_q.squeeze(0).cpu().numpy()

    def q_values_batch(self, states) -> np.ndarray:
        """Vectorized batch pseudo-Q values. Shape: (batch, 3)."""
        with self.lock:
            state_tensor = torch.FloatTensor(np.array(states)).to(self.device)
            if state_tensor.dim() == 1:
                state_tensor = state_tensor.unsqueeze(0)
            with torch.no_grad():
                pseudo_q = self.actor_critic.compute_pseudo_q(state_tensor)
                return pseudo_q.cpu().numpy()

    def predict_with_confidence(self, state, temperature: float = 0.6) -> tuple:
        """
        Greedy policy evaluation for dashboard/monitoring.
        Returns: (p_yes, best_action, reasoning)
        """
        q = self.q_values(state)
        best_action = int(np.argmax(q))
        score = float(q[1] - q[2])
        p_cal = calibrated_p_yes(score)
        p_yes = 0.50 if (best_action == 0 or p_cal is None) else p_cal
        action_str = {0: "PASS (CAPITAL PRESERVATION)", 1: "BUY YES (ABOVE)", 2: "BUY NO (BELOW)"}[best_action]
        cal_note = f"calibrated P(YES)={p_cal:.3f}" if p_cal is not None else "UNCALIBRATED (no confidence reported)"
        reasoning = (
            f"PPO Transformer Policy: Best Action={action_str} "
            f"[Q-Pass: {q[0]:+.2f}, Q-Yes: {q[1]:+.2f}, Q-No: {q[2]:+.2f}] {cal_note}"
        )
        return p_yes, best_action, reasoning

    def evaluate_contract(self, state, kalshi_m=None, min_edge: float = None) -> dict:
        """
        Comprehensive Price-Aware Contract Evaluator.
        Computes continuous actions, state value V(s), dynamic order sizing, and target limit prices.
        Returns dict containing:
          - p_model: float
          - p_yes: float
          - market_p_yes: float
          - action: int (0: PASS, 1: BUY YES, 2: BUY NO)
          - action_name: str
          - model_action: int (raw un-gated action)
          - target_limit_price: float in [0.01, 0.99]
          - dynamic_sizing_factor: float in [0.0, 1.0]
          - dynamic_contracts: int >= 1
          - contracts: int (alias)
          - v_state: float
          - yes_ask, no_ask, edge_yes, edge_no, min_edge, reasoning
        """
        if min_edge is None:
            try:
                min_edge = float(os.environ.get("RL_MIN_EDGE", DEFAULT_MIN_EDGE))
            except ValueError:
                min_edge = DEFAULT_MIN_EDGE

        state_tensor = torch.FloatTensor(state).to(self.device)
        if state_tensor.dim() == 1:
            state_tensor = state_tensor.unsqueeze(0)

        with torch.no_grad():
            action_mean, _, val_tensor = self.actor_critic(state_tensor)
            a_dir = float(action_mean[0, 0].item())
            a_size = float(action_mean[0, 1].item())
            a_price = float(action_mean[0, 2].item())
            v_state = float(val_tensor[0, 0].item())

        q = self.q_values(state)
        # Determine raw policy recommendation
        if abs(a_dir) <= 0.15 or a_size < 0.10:
            model_action = 0
        else:
            model_action = 1 if a_dir > 0.15 else 2

        score = float(q[1] - q[2])
        cal = load_calibration()
        p_cal = calibrated_p_yes(score, cal)
        uncal_p_yes = min(0.99, max(0.01, (1.0 + a_dir) / 2.0))
        p_model = p_cal if p_cal is not None else uncal_p_yes

        yes_ask, no_ask, yes_mid = market_prices(kalshi_m)

        # Market-anchored probability
        p_yes = None
        model_shift = None
        if p_cal is not None and yes_mid is not None:
            base = float(cal.get("base_rate", 0.5)) if cal else 0.5
            model_shift = p_cal - base
            p_yes = min(0.99, max(0.01, yes_mid + model_shift))
        elif yes_mid is not None:
            model_shift = p_model - 0.50
            p_yes = min(0.99, max(0.01, yes_mid + model_shift))

        edge_yes = edge_no = None
        if p_yes is not None and yes_ask is not None:
            edge_yes = p_yes - yes_ask - kalshi_fee_per_contract(yes_ask)
        if p_yes is not None and no_ask is not None:
            edge_no = (1.0 - p_yes) - no_ask - kalshi_fee_per_contract(no_ask)

        action = 0
        why = ""
        if model_action == 0:
            why = "model prefers PASS / capital preservation"
        elif p_cal is None:
            why = "no calibration file — RL cannot state a probability, passing"
        elif p_yes is None:
            why = "no real Kalshi price available, passing"
        else:
            edge = edge_yes if model_action == 1 else edge_no
            leans_yes = model_shift > 0 if model_shift is not None else (a_dir > 0)
            p_side = p_yes if model_action == 1 else 1.0 - p_yes
            if (model_action == 1) != leans_yes:
                why = "model shift direction does not match action"
            elif p_side <= 0.50:
                why = f"P(side)={p_side:.3f} is not above 50%"
            elif edge is not None and edge < min_edge:
                why = f"edge {edge:+.3f} after price+fee is below required {min_edge:.3f}"
            else:
                action = model_action
                why = f"edge {edge:+.3f} clears required {min_edge:.3f}"

        # Dynamic contract sizing calculation
        trade_size = 100.0
        entry_px = yes_ask if action == 1 and yes_ask else (no_ask if action == 2 and no_ask else a_price)
        entry_px = max(0.01, min(0.99, float(entry_px or 0.50)))
        contracts_base = max(1, int(trade_size / entry_px))
        dynamic_contracts = max(1, int(round(a_size * contracts_base)))

        side_names = {0: "PASS", 1: "BUY YES", 2: "BUY NO"}
        action_name = side_names.get(action, "PASS")
        p_txt = f"{p_yes:.3f}" if p_yes is not None else "n/a"
        shift_txt = f"{model_shift:+.3f}" if model_shift is not None else "n/a"
        mid_txt = f"{yes_mid:.3f}" if yes_mid is not None else "n/a"

        reasoning = (
            f"PPO Transformer: model={side_names[model_action]} -> decision={action_name} ({why}). "
            f"P(YES)={p_txt} = market {mid_txt} {shift_txt} model shift; YES ask={yes_ask}, NO ask={no_ask} "
            f"[a_dir={a_dir:+.2f}, a_size={a_size:.2f}, target_limit=${a_price:.2f}, V(s)={v_state:+.2f}]"
        )

        return {
            "p_yes": p_yes,
            "p_model": p_model,
            "market_p_yes": yes_mid,
            "action": action,
            "action_name": action_name,
            "model_action": model_action,
            "target_limit_price": round(float(a_price), 2),
            "dynamic_sizing_factor": round(float(a_size), 4),
            "dynamic_contracts": int(dynamic_contracts),
            "contracts": int(dynamic_contracts),
            "v_state": round(float(v_state), 4),
            "yes_ask": yes_ask,
            "no_ask": no_ask,
            "edge_yes": None if edge_yes is None else round(edge_yes, 4),
            "edge_no": None if edge_no is None else round(edge_no, 4),
            "min_edge": min_edge,
            "reasoning": reasoning,
        }

    def train_step(self) -> float:
        """
        Executes a PPO training step:
          1. Samples batch of rollouts from PPORolloutBuffer.
          2. Computes Generalized Advantage Estimation (GAE) and target returns.
          3. Evaluates current policy log-probs, entropy, and state values.
          4. Computes PPO clipped surrogate policy loss L_CLIP.
          5. Computes Critic MSE value function loss L_VF.
          6. Computes policy action entropy bonus S[pi].
          7. Backpropagates total loss with gradient norm clipping (1.0).
        """
        with self.lock:
            if len(self.memory) < min(16, self.batch_size):
                return 0.0

            states, actions, rewards, next_states, dones, old_log_probs, old_values, _ = self.memory.sample_batch(self.batch_size)

            states_t = torch.FloatTensor(states).to(self.device)
            actions_t = torch.FloatTensor(actions).to(self.device)
            rewards_t = torch.FloatTensor(rewards).to(self.device)
            next_states_t = torch.FloatTensor(next_states).to(self.device)
            dones_t = torch.FloatTensor(dones).to(self.device)
            old_log_probs_t = torch.FloatTensor(old_log_probs).to(self.device)
            old_values_t = torch.FloatTensor(old_values).to(self.device)

            with torch.no_grad():
                _, _, next_values_t = self.actor_critic(next_states_t)
                next_values = next_values_t.squeeze(-1)

                # If stored old values are zero (uninitialized), estimate with current critic
                if torch.all(old_values_t == 0.0):
                    _, _, cur_vals = self.actor_critic(states_t)
                    old_values_t = cur_vals.squeeze(-1)

                # GAE-lambda advantage computation
                deltas = rewards_t + self.gamma * next_values * (1.0 - dones_t) - old_values_t
                advantages = deltas.clone()
                returns = advantages + old_values_t

                # Normalize advantages for training stability
                adv_mean = advantages.mean()
                adv_std = advantages.std()
                if torch.isnan(adv_std) or adv_std < 1e-6:
                    adv_norm = advantages - adv_mean
                else:
                    adv_norm = (advantages - adv_mean) / (adv_std + 1e-8)

                # If stored old log probs are uninitialized, compute baseline log probs
                if torch.all(old_log_probs_t == 0.0):
                    _, cur_lp, _, _ = self.actor_critic.get_action_and_value(states_t, actions_t)
                    old_log_probs_t = cur_lp.detach()

            # Forward pass with current policy
            _, new_log_probs, entropy, new_values = self.actor_critic.get_action_and_value(states_t, actions_t)

            # 1. Clipped Surrogate Policy Objective
            log_ratios = new_log_probs - old_log_probs_t
            ratios = torch.exp(torch.clamp(log_ratios, -20.0, 20.0))
            surr1 = ratios * adv_norm
            surr2 = torch.clamp(ratios, 1.0 - self.clip_eps, 1.0 + self.clip_eps) * adv_norm
            policy_loss = -torch.min(surr1, surr2).mean()

            # 2. Critic Value Function Loss (MSE with target returns)
            val_loss = 0.5 * ((new_values - returns) ** 2).mean()

            # 3. Action Entropy Bonus (encouraging exploration)
            entropy_loss = -entropy.mean()

            # Combined PPO Objective: L = L_CLIP + c1 * L_VF - c2 * Entropy
            total_loss = policy_loss + self.c_val * val_loss + self.c_ent * entropy_loss

            self.optimizer.zero_grad()
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.actor_critic.parameters(), max_norm=1.0)
            self.optimizer.step()

            self.train_steps += 1
            self._epsilon = max(self.epsilon_end, self._epsilon * self.epsilon_decay)
            return float(total_loss.item())

    def update_target_network(self):
        """Soft synchronization / compatibility hook."""
        pass

    def save(self):
        with self.lock:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            torch.save({
                "architecture": "PPO_TimeSeriesTransformer",
                "actor_critic": self.actor_critic.state_dict(),
                "policy_net": self.actor_critic.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "epsilon": self._epsilon,
                "train_steps": self.train_steps,
                "state_dim": self.state_dim,
                "action_dim": self.action_dim,
                "feature_version": 2
            }, self.model_path)
            logger.info(f"[RLAgent] Saved PPO Time-Series Transformer model to {self.model_path}")

    def load(self):
        with self.lock:
            if os.path.exists(self.model_path):
                try:
                    checkpoint = torch.load(self.model_path, map_location=self.device)
                    arch = checkpoint.get("architecture", "")
                    if "PPO" in arch and "actor_critic" in checkpoint:
                        self.actor_critic.load_state_dict(checkpoint["actor_critic"])
                        if "optimizer" in checkpoint:
                            self.optimizer.load_state_dict(checkpoint["optimizer"])
                        self._epsilon = checkpoint.get("epsilon", self._epsilon)
                        self.train_steps = checkpoint.get("train_steps", 0)
                        logger.info(f"[RLAgent] Loaded PPO Time-Series Transformer from {self.model_path}. Steps: {self.train_steps}")
                    else:
                        logger.warning(f"[RLAgent] Legacy checkpoint detected ({arch}). Initializing fresh PPO Transformer weights.")
                except Exception as e:
                    logger.warning(f"[RLAgent] Checkpoint load failed or architecture mismatch ({e}), starting with fresh PPO Transformer weights.")
            self.rehydrate_memory_from_disk()

    def rehydrate_memory_from_disk(self):
        """Rehydrates rollout buffer from historical settled shadow trades."""
        shadow_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rl_shadow_trades.json")
        if os.path.exists(shadow_file):
            try:
                with open(shadow_file, "r") as f:
                    trades = json.load(f)
                count = 0
                for t in trades:
                    if t.get("status") == "SETTLED" and int(t.get("feature_version", 1) or 1) >= 2:
                        s = t.get("state_vector")
                        if s is None or len(s) != len(FEATURE_KEYS):
                            continue
                        a = t.get("action")
                        if "unit_pnl" in t:
                            unit_pnl = float(t["unit_pnl"])
                        else:
                            raw_pnl = float(t.get("pnl", 0.0))
                            contracts = float(t.get("contracts", 1.0))
                            unit_pnl = raw_pnl / contracts if contracts > 1 else raw_pnl
                        if s is not None and a is not None:
                            # Asymmetric penalty on losses
                            reward = (unit_pnl * 2.0) * 1.5 if unit_pnl < 0 else unit_pnl * 2.0
                            try:
                                vol_idx = FEATURE_KEYS.index("vol_regime_percentile")
                                if len(s) > vol_idx and s[vol_idx] < 0.25:
                                    reward -= 0.5
                            except (ValueError, IndexError):
                                pass
                            reward = max(-3.0, min(3.0, reward))
                            self.memory.push(s, a, reward, s, done=True)
                            count += 1
                logger.info(f"[RLAgent] Rehydrated {count} experiences into PPO buffer from disk.")
            except Exception as e:
                logger.warning(f"[RLAgent] Failed to rehydrate replay buffer: {e}")


# Singleton instance
_RL_AGENT = RLAgent()


def get_rl_agent() -> RLAgent:
    return _RL_AGENT
