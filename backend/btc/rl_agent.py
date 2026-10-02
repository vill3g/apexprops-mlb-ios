import json
import logging
import os
import random
import threading

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from backend.btc.ml_engine import FEATURE_KEYS

logger = logging.getLogger(__name__)

# =====================================================================
# PROBABILITY CALIBRATION + PRICE-AWARE DECISION
# =====================================================================
# The network outputs Q-values (expected shaped reward), not probabilities.
# The live "confidence %" used to be a temperature softmax over Q-values, which
# routinely reported 95-100% on coin-flip setups. We now map the directional
# score (Q_yes - Q_no) to P(YES) with Platt scaling fitted on out-of-sample
# 15m candles (see backend/scripts/calibrate_rl.py), and only allow a trade
# when that probability beats the contract's ask price plus Kalshi fees.
CALIBRATION_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "model_cache", "rl_calibration.json")
DEFAULT_MIN_EDGE = 0.02  # required (probability - price - fee), in dollars per $1 contract
_calibration_cache = {"mtime": None, "data": None}


def kalshi_fee_per_contract(price: float) -> float:
    """Kalshi taker fee approximation per contract: 0.07 * P * (1 - P)."""
    price = min(max(float(price), 0.0), 1.0)
    return 0.07 * price * (1.0 - price)


def load_calibration():
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
            float(data["a"]); float(data["b"])
            _calibration_cache.update(mtime=mtime, data=data)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            logger.warning(f"[RLAgent] Ignoring invalid calibration file: {e}")
            _calibration_cache.update(mtime=mtime, data=None)
    return _calibration_cache["data"]


def calibrated_p_yes(score: float, calibration=None):
    """P(YES) for a directional score (Q_yes - Q_no); None when uncalibrated."""
    cal = calibration if calibration is not None else load_calibration()
    if not cal:
        return None
    z = float(cal["a"]) * float(score) + float(cal["b"])
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + float(np.exp(-z)))


def fit_platt(scores, labels, l2: float = 1e-3, iters: int = 50):
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


def market_prices(kalshi_m):
    """(yes_ask, no_ask, yes_mid) in dollars from a Kalshi market dict; Nones if unusable.
    yes_mid is the market-implied P(YES): the YES bid/ask midpoint, or the midpoint of
    the YES ask and (1 - NO ask) when bids are missing."""
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
# DUELING DEEP Q-NETWORK (Dueling DQN)
# =====================================================================
class DuelingDQN(nn.Module):
    """
    Hybrid LSTM Quantile Regression Dueling Deep Q-Network (QR-DQN).
    Outputs a distribution of Q-values (quantiles) rather than a single mean expected reward,
    enabling the agent to understand fat-tail risk, uncertainty, and conviction grading.
    """
    def __init__(self, input_dim: int, output_dim: int = 3, hidden_dim: int = 128, num_quantiles: int = 51):
        super(DuelingDQN, self).__init__()
        
        self.num_actions = output_dim
        self.num_quantiles = num_quantiles
        
        # We know from FEATURE_KEYS that the last 25 features are 5 lags of 5 indicators:
        # [lag_4, lag_3, lag_2, lag_1, lag_0] where each lag is 5 features.
        self.seq_len = 5
        self.seq_features = 5
        self.static_features = input_dim - (self.seq_len * self.seq_features)
        
        # LSTM for the sequence (tape reading)
        self.lstm = nn.LSTM(input_size=self.seq_features, hidden_size=64, num_layers=1, batch_first=True)
        self.lstm_ln = nn.LayerNorm(64)
        
        # MLP for the static/base features
        self.static_mlp = nn.Sequential(
            nn.Linear(self.static_features, 64),
            nn.LayerNorm(64),
            nn.SiLU()
        )
        
        # Fusion layer combining LSTM output and Static MLP output
        self.fusion_layer = nn.Sequential(
            nn.Linear(64 + 64, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU()
        )
        
        # State Value stream V(s) -> num_quantiles
        self.value_stream = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.SiLU(),
            nn.Linear(64, num_quantiles)
        )
        
        # Action Advantage stream A(s, a) -> num_actions * num_quantiles
        self.advantage_stream = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.SiLU(),
            nn.Linear(64, output_dim * num_quantiles)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Split the input vector: static features vs sequence features
        x_static = x[:, :self.static_features]
        x_seq_flat = x[:, self.static_features:]
        
        # Reshape the flat sequence features back into (batch, seq_len, seq_features)
        batch_size = x.size(0)
        x_seq = x_seq_flat.view(batch_size, self.seq_len, self.seq_features)
        
        # Process sequence with LSTM
        lstm_out, _ = self.lstm(x_seq)
        seq_out = torch.nn.functional.silu(self.lstm_ln(lstm_out[:, -1, :])) # Take the last timestep's output
        
        # Process static features with MLP
        static_out = self.static_mlp(x_static)
        
        # Fuse representations
        merged = self.fusion_layer(torch.cat([static_out, seq_out], dim=1))
        
        # Calculate Value and Advantage
        val = self.value_stream(merged).view(batch_size, 1, self.num_quantiles)
        adv = self.advantage_stream(merged).view(batch_size, self.num_actions, self.num_quantiles)
        
        # Combine using Dueling DQN formula: Q(s, a) = V(s) + A(s, a) - mean(A(s, a))
        q_dist = val + adv - adv.mean(dim=1, keepdim=True)
        return q_dist

# Alias for backwards compatibility
DQN = DuelingDQN


# =====================================================================
# PRIORITIZED EXPERIENCE REPLAY (PER)
# =====================================================================
class PrioritizedReplayBuffer:
    """
    Prioritized Experience Replay (PER) (Schaul et al., 2015).
    Samples transitions with probability proportional to their TD-error magnitude:
        P(i) = p_i^alpha / sum_k(p_k^alpha)
    Corrects non-uniform sampling bias via importance-sampling weights:
        w_i = (N * P(i))^(-beta) / max_k(w_k)
    This ensures high-information market events (trend reversals, breakouts, large losses)
    are prioritized over low-information chop transitions.
    """
    def __init__(self, capacity: int = 20000, alpha: float = 0.6, beta_start: float = 0.4, beta_frames: int = 10000):
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta_start
        self.beta_start = beta_start
        self.beta_frames = beta_frames
        self.frame = 1
        
        self.buffer = []
        self.priorities = np.zeros((capacity,), dtype=np.float32)
        self.pos = 0

    def push(self, state, action, reward, next_state, done):
        max_prio = self.priorities[:len(self.buffer)].max() if self.buffer else 1.0
        if max_prio <= 0.0 or not np.isfinite(max_prio):
            max_prio = 1.0

        item = (
            np.array(state, dtype=np.float32),
            int(action),
            float(reward),
            np.array(next_state, dtype=np.float32),
            bool(done)
        )

        if len(self.buffer) < self.capacity:
            self.buffer.append(item)
        else:
            self.buffer[self.pos] = item
            
        self.priorities[self.pos] = max_prio
        self.pos = (self.pos + 1) % self.capacity

    def sample(self, batch_size: int):
        N = len(self.buffer)
        if N == 0:
            raise ValueError("Cannot sample from an empty ReplayBuffer")

        prios = self.priorities[:N]
        # Anneal beta toward 1.0
        self.beta = min(1.0, self.beta_start + self.frame * (1.0 - self.beta_start) / max(1, self.beta_frames))
        self.frame += 1

        probs = prios ** self.alpha
        prob_sum = probs.sum()
        if prob_sum <= 0 or not np.isfinite(prob_sum):
            probs = np.ones(N, dtype=np.float32) / N
        else:
            probs = probs / prob_sum

        indices = np.random.choice(N, min(batch_size, N), replace=(N < batch_size), p=probs)
        samples = [self.buffer[idx] for idx in indices]

        # Importance-sampling weights
        weights = (N * probs[indices]) ** (-self.beta)
        max_w = weights.max()
        weights = weights / (max_w if max_w > 0 else 1.0)
        weights = np.array(weights, dtype=np.float32)

        states, actions, rewards, next_states, dones = zip(*samples)
        return (
            np.array(states, dtype=np.float32),
            np.array(actions, dtype=np.int64),
            np.array(rewards, dtype=np.float32),
            np.array(next_states, dtype=np.float32),
            np.array(dones, dtype=np.float32),
            indices,
            weights
        )

    def update_priorities(self, batch_indices, batch_priorities):
        for idx, prio in zip(batch_indices, batch_priorities):
            prio_val = float(abs(prio)) + 1e-5
            self.priorities[idx] = min(prio_val, 100.0)

    def __len__(self):
        return len(self.buffer)

# Alias for backwards compatibility
ReplayBuffer = PrioritizedReplayBuffer


# =====================================================================
# REINFORCEMENT LEARNING AGENT (Dueling Double DQN with PER)
# =====================================================================
class RLAgent:
    """
    Production-grade Reinforcement Learning Agent for Kalshi 15-Minute Binary Markets.
    Features:
      - Dueling Architecture (Decoupled Value V(s) & Advantage A(s, a))
      - Double DQN (DDQN) Target Evaluation (Zero Maximization Bias)
      - Prioritized Experience Replay (PER) with Importance-Sampling Bias Correction
      - Soft Polyak Target Updates (Continuous Monotonic Target Stability)
      - Calibrated Action Softmax with Temperature Scaling
    """
    def __init__(
        self,
        state_dim: int = len(FEATURE_KEYS),
        action_dim: int = 3,
        lr: float = 3e-4,
        gamma: float = 0.95,
        tau: float = 0.005,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.02,
        epsilon_decay: float = 0.998
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.tau = tau
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.policy_net = DuelingDQN(state_dim, action_dim).to(self.device)
        self.target_net = DuelingDQN(state_dim, action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.AdamW(self.policy_net.parameters(), lr=lr, weight_decay=1e-4)
        self.memory = PrioritizedReplayBuffer(capacity=25000, alpha=0.6, beta_start=0.4)
        self.batch_size = 128
        self.lock = threading.Lock()
        self.train_steps = 0

        # Model checkpoint path
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "model_cache", "rl_agent.pth")
        self.load()

    def select_action(self, state, exploit: bool = False) -> int:
        with self.lock:
            # Exploration mode vs pure exploitation
            if not exploit and random.random() < self.epsilon:
                return random.randrange(self.action_dim)
            
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            with torch.no_grad():
                q_dist = self.policy_net(state_tensor)  # (1, 3, 51)
                expected_q = q_dist.mean(dim=2).squeeze(0)  # (3,)
                return int(expected_q.argmax().item())

    def q_values(self, state) -> np.ndarray:
        with self.lock:
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            with torch.no_grad():
                q_dist = self.policy_net(state_tensor) # (1, 3, 51)
                return q_dist.mean(dim=2).squeeze(0).cpu().numpy()

    def predict_with_confidence(self, state, temperature: float = 0.6) -> tuple:
        """
        Greedy policy evaluation (no price check — see evaluate_contract).
        Returns:
            prob (float): calibrated P(YES) (0.50 when PASS or when no calibration exists)
            action (int): 0: PASS, 1: ABOVE (YES), 2: BELOW (NO)
            reasoning (str): Explanation including Q-values
        `temperature` is accepted for backwards compatibility and ignored.
        """
        q = self.q_values(state)
        best_action = int(np.argmax(q))
        score = float(q[1] - q[2])
        p_cal = calibrated_p_yes(score)
        p_yes = 0.50 if (best_action == 0 or p_cal is None) else p_cal
        action_str = {0: "PASS (CAPITAL PRESERVATION)", 1: "BUY YES (ABOVE)", 2: "BUY NO (BELOW)"}[best_action]
        cal_note = f"calibrated P(YES)={p_cal:.3f}" if p_cal is not None else "UNCALIBRATED (no confidence reported)"
        reasoning = (
            f"Dueling DDQN Policy: Best Action={action_str} "
            f"[Q-Pass: {q[0]:+.2f}, Q-Yes: {q[1]:+.2f}, Q-No: {q[2]:+.2f}] {cal_note}"
        )
        return p_yes, best_action, reasoning

    def evaluate_contract(self, state, kalshi_m=None, min_edge: float = None) -> dict:
        """
        Price-aware decision. P(YES) = market-implied probability (Kalshi mid) plus the
        calibrated model's deviation from its base rate. Trades only when the model's
        chosen side has P > 50% and beats that side's ask plus the Kalshi fee by
        `min_edge` (env RL_MIN_EDGE, default 0.02).
        Returns a dict with p_yes, action (0 PASS / 1 YES / 2 NO after the gate),
        model_action (raw argmax), asks, edges and a reasoning string.
        """
        if min_edge is None:
            try:
                min_edge = float(os.environ.get("RL_MIN_EDGE", DEFAULT_MIN_EDGE))
            except ValueError:
                min_edge = DEFAULT_MIN_EDGE
        q = self.q_values(state)
        model_action = int(np.argmax(q))
        cal = load_calibration()
        p_cal = calibrated_p_yes(float(q[1] - q[2]), cal)
        yes_ask, no_ask, yes_mid = market_prices(kalshi_m)

        # Market-anchored probability. The Kalshi price already reflects where BTC is
        # versus the strike; the model was calibrated on candles where the fair price was
        # ~50/50. So we only credit the model for how far it deviates from its base rate,
        # applied on top of the market's own implied probability. (Using the raw
        # calibrated probability against the ask led to buying cheap sides the market had
        # correctly priced as unlikely — 24% win rate when replayed on past shadow trades.)
        p_yes = None
        model_shift = None
        if p_cal is not None and yes_mid is not None:
            base = float(cal.get("base_rate", 0.5)) if cal else 0.5
            model_shift = p_cal - base
            p_yes = min(0.99, max(0.01, yes_mid + model_shift))

        edge_yes = edge_no = None
        if p_yes is not None:
            edge_yes = p_yes - yes_ask - kalshi_fee_per_contract(yes_ask)
            edge_no = (1.0 - p_yes) - no_ask - kalshi_fee_per_contract(no_ask)

        action = 0
        why = ""
        if model_action == 0:
            why = "model prefers PASS"
        elif p_cal is None:
            why = "no calibration file — RL cannot state a probability, passing"
        elif p_yes is None:
            why = "no real Kalshi price available, passing"
        else:
            edge = edge_yes if model_action == 1 else edge_no
            leans_yes = model_shift > 0
            p_side = p_yes if model_action == 1 else 1.0 - p_yes
            if (model_action == 1) != leans_yes:
                why = "calibrated model does not lean toward the chosen side"
            elif p_side <= 0.5:
                # The rest of the analyzer treats RL output as "direction + confidence",
                # so long-shot value bets on the cheaper side are not taken.
                why = f"P(side)={p_side:.3f} is not above 50%"
            elif edge < min_edge:
                why = f"edge {edge:+.3f} after price+fee is below required {min_edge:.3f}"
            else:
                action = model_action
                why = f"edge {edge:+.3f} clears {min_edge:.3f}"

        side_txt = {0: "PASS", 1: "BUY YES", 2: "BUY NO"}
        p_txt = f"{p_yes:.3f}" if p_yes is not None else "n/a"
        shift_txt = f"{model_shift:+.3f}" if model_shift is not None else "n/a"
        mid_txt = f"{yes_mid:.3f}" if yes_mid is not None else "n/a"
        reasoning = (
            f"RL DQN: model={side_txt[model_action]} -> decision={side_txt[action]} ({why}). "
            f"P(YES)={p_txt} = market {mid_txt} {shift_txt} model shift; YES ask={yes_ask}, NO ask={no_ask} "
            f"[Q-Pass {q[0]:+.2f}, Q-Yes {q[1]:+.2f}, Q-No {q[2]:+.2f}]"
        )
        return {
            "p_yes": p_yes,
            "p_model": p_cal,
            "market_p_yes": yes_mid,
            "action": action,
            "model_action": model_action,
            "yes_ask": yes_ask,
            "no_ask": no_ask,
            "edge_yes": None if edge_yes is None else round(edge_yes, 4),
            "edge_no": None if edge_no is None else round(edge_no, 4),
            "min_edge": min_edge,
            "reasoning": reasoning,
        }

    def train_step(self) -> float:
        with self.lock:
            if len(self.memory) < self.batch_size:
                return 0.0

            states, actions, rewards, next_states, dones, indices, weights = self.memory.sample(self.batch_size)
            
            state_t = torch.FloatTensor(states).to(self.device)
            next_state_t = torch.FloatTensor(next_states).to(self.device)
            action_t = torch.LongTensor(actions).to(self.device)
            reward_t = torch.FloatTensor(rewards).to(self.device)
            done_t = torch.FloatTensor(dones).to(self.device)
            weights_t = torch.FloatTensor(weights).to(self.device)

            # Current Q-distribution
            q_dist = self.policy_net(state_t) # (batch, 3, num_quantiles)
            action_t_expanded = action_t.unsqueeze(1).unsqueeze(2).expand(-1, -1, self.policy_net.num_quantiles)
            state_action_quantiles = q_dist.gather(1, action_t_expanded).squeeze(1) # (batch, num_quantiles)

            # Double DQN action selection
            with torch.no_grad():
                next_q_dist = self.policy_net(next_state_t)
                next_q_values = next_q_dist.mean(dim=2)
                next_policy_actions = next_q_values.argmax(dim=1, keepdim=True)
                
                next_target_dist = self.target_net(next_state_t)
                next_policy_actions_expanded = next_policy_actions.unsqueeze(2).expand(-1, -1, self.policy_net.num_quantiles)
                next_target_quantiles = next_target_dist.gather(1, next_policy_actions_expanded).squeeze(1)
                
                expected_quantiles = reward_t.unsqueeze(1) + (self.gamma * next_target_quantiles * (1.0 - done_t.unsqueeze(1)))

            # Quantile Huber Loss
            td_errors = expected_quantiles.unsqueeze(1) - state_action_quantiles.unsqueeze(2)
            k = 1.0
            huber_loss = torch.where(td_errors.abs() <= k, 0.5 * td_errors.pow(2), k * (td_errors.abs() - 0.5 * k))
            
            tau = torch.linspace(0.5 / self.policy_net.num_quantiles, 1.0 - 0.5 / self.policy_net.num_quantiles, self.policy_net.num_quantiles).to(self.device)
            tau = tau.unsqueeze(0).unsqueeze(1)
            quantile_loss = torch.abs(tau - (td_errors < 0).float()) * huber_loss
            loss = (quantile_loss.sum(dim=2).mean(dim=1) * weights_t).mean()
            
            mean_td_errors = td_errors.mean(dim=(1, 2)).detach().abs().cpu().numpy()
            self.memory.update_priorities(indices, mean_td_errors)



            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=1.0)
            self.optimizer.step()

            # Soft Polyak target update: theta_target = tau * theta_policy + (1 - tau) * theta_target
            for target_param, policy_param in zip(self.target_net.parameters(), self.policy_net.parameters()):
                target_param.data.copy_(self.tau * policy_param.data + (1.0 - self.tau) * target_param.data)

            self.train_steps += 1
            # Epsilon decay
            self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
            return float(loss.item())

    def update_target_network(self):
        """Hard synchronization of target network weights with policy network."""
        with self.lock:
            self.target_net.load_state_dict(self.policy_net.state_dict())

    def save(self):
        with self.lock:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            torch.save({
                'policy_net': self.policy_net.state_dict(),
                'target_net': self.target_net.state_dict(),
                'optimizer': self.optimizer.state_dict(),
                'epsilon': self.epsilon,
                'train_steps': self.train_steps,
                'architecture': 'DuelingDoubleDQN'
            }, self.model_path)
            logger.info(f"[RLAgent] Saved Dueling Double DQN model to {self.model_path}")

    def load(self):
        with self.lock:
            if os.path.exists(self.model_path):
                try:
                    checkpoint = torch.load(self.model_path, map_location=self.device)
                    self.policy_net.load_state_dict(checkpoint['policy_net'])
                    self.target_net.load_state_dict(checkpoint['target_net'])
                    if 'optimizer' in checkpoint:
                        self.optimizer.load_state_dict(checkpoint['optimizer'])
                    self.epsilon = checkpoint.get('epsilon', self.epsilon)
                    self.train_steps = checkpoint.get('train_steps', 0)
                    logger.info(f"[RLAgent] Loaded pre-trained model from {self.model_path}. Epsilon: {self.epsilon:.3f}")
                except Exception as e:
                    logger.warning(f"[RLAgent] Architecture mismatch or load failed ({e}), starting with fresh Dueling DDQN weights.")
            self.rehydrate_memory_from_disk()

    def rehydrate_memory_from_disk(self):
        """Rehydrates replay buffer from historical settled shadow trades."""
        shadow_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rl_shadow_trades.json")
        if os.path.exists(shadow_file):
            try:
                with open(shadow_file, "r") as f:
                    trades = json.load(f)
                count = 0
                for t in trades:
                    # Only states built by the live feature builder (feature_version 2+);
                    # older shadow trades used a different, mismatched feature dict.
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
                            # Risk-adjusted reward: Asymmetric penalty on losses
                            if unit_pnl < 0:
                                reward = (unit_pnl * 2.0) * 1.5 # Asymmetric penalty
                            else:
                                reward = unit_pnl * 2.0
                                
                            try:
                                vol_idx = FEATURE_KEYS.index("vol_regime_percentile")
                                # Fixed: vol_regime_percentile is [0.0, 1.0], so 25th percentile is 0.25
                                if len(s) > vol_idx and s[vol_idx] < 0.25:
                                    reward -= 0.5
                            except (ValueError, IndexError):
                                pass
                                
                            reward = max(-3.0, min(3.0, reward))
                            self.memory.push(s, a, reward, s, done=True)
                            count += 1
                logger.info(f"[RLAgent] Rehydrated {count} experiences into PER replay buffer from disk.")
            except Exception as e:
                logger.warning(f"[RLAgent] Failed to rehydrate replay buffer: {e}")

# Singleton instance
_RL_AGENT = RLAgent()

def get_rl_agent():
    return _RL_AGENT
