import json
import logging
import os
import random
import threading

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

logger = logging.getLogger(__name__)

# =====================================================================
# CONTINUOUS SCALPING AGENT (Dueling Double DQN with PER)
# =====================================================================
# Actions:
# 0: HOLD (or PASS if flat)
# 1: BUY YES (if flat)
# 2: BUY NO (if flat)
# 3: CLOSE (sell current position)

class ScalpingDQN(nn.Module):
    def __init__(self, input_dim: int, action_dim: int = 4, hidden_dim: int = 512):
        super().__init__()
        self.feature_trunk = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.SiLU()
        )
        self.value_stream = nn.Sequential(
            nn.Linear(hidden_dim // 2, 32),
            nn.SiLU(),
            nn.Linear(32, 1)
        )
        self.advantage_stream = nn.Sequential(
            nn.Linear(hidden_dim // 2, 32),
            nn.SiLU(),
            nn.Linear(32, action_dim)
        )

    def forward(self, x):
        features = self.feature_trunk(x)
        values = self.value_stream(features)
        advantages = self.advantage_stream(features)
        return values + (advantages - advantages.mean(dim=-1, keepdim=True))

class PrioritizedReplayBuffer:
    def __init__(self, capacity: int = 25000, alpha: float = 0.6, beta_start: float = 0.4):
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta_start
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
        prios = self.priorities[:N] ** self.alpha
        prob_sum = prios.sum()
        probs = prios / prob_sum if prob_sum > 0 else np.ones(N) / N

        indices = np.random.choice(N, batch_size, p=probs)
        samples = [self.buffer[idx] for idx in indices]

        weights = (N * probs[indices]) ** (-self.beta)
        weights /= weights.max()

        states, actions, rewards, next_states, dones = zip(*samples)
        return (
            np.array(states, dtype=np.float32),
            np.array(actions, dtype=np.int64),
            np.array(rewards, dtype=np.float32),
            np.array(next_states, dtype=np.float32),
            np.array(dones, dtype=np.float32),
            indices,
            np.array(weights, dtype=np.float32)
        )

    def update_priorities(self, indices, errors):
        for idx, e in zip(indices, errors):
            self.priorities[idx] = min(float(abs(e)) + 1e-5, 100.0)

    def __len__(self):
        return len(self.buffer)

def _checkpoint_state_dim(path):
    try:
        if os.path.exists(path):
            ck = torch.load(path, map_location="cpu")
            return int(ck["policy_net"]["feature_trunk.0.weight"].shape[1])
    except Exception as e:
        logger.warning(f"[RLScalper] Could not read checkpoint shape: {e}")
    return None


SCALPER_META_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "model_cache", "rl_scalper.json")


def scalper_live_enabled() -> bool:
    """The scalper may only place trades after a training run has validated it on
    held-out markets (train_rl_scalper.py writes enabled=true only in that case)."""
    try:
        with open(SCALPER_META_PATH, "r", encoding="utf-8") as f:
            return bool(json.load(f).get("enabled", False))
    except (OSError, ValueError):
        return False


class RLScalperAgent:
    def __init__(self, state_dim: int = None, lr: float = 3e-4, gamma: float = 0.99):
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "model_cache", "rl_scalper.pth")
        if state_dim is None:
            # Size the network from the saved checkpoint. A hard-coded 34 did not match the
            # trained model (37 inputs), so loading always failed and the live agent ran
            # with random weights.
            state_dim = _checkpoint_state_dim(self.model_path) or 37
        self.state_dim = state_dim
        self.action_dim = 4
        self.gamma = gamma
        self.tau = 0.005
        self.epsilon = 1.0
        self.epsilon_min = 0.02
        self.epsilon_decay = 0.995

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.policy_net = ScalpingDQN(state_dim, self.action_dim).to(self.device)
        self.target_net = ScalpingDQN(state_dim, self.action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.AdamW(self.policy_net.parameters(), lr=lr)
        self.memory = PrioritizedReplayBuffer()
        self.batch_size = 128
        self.lock = threading.Lock()
        
        self.load()

    def select_action(self, state, exploit: bool = False, valid_actions: list = None) -> int:
        with self.lock:
            if not exploit and random.random() < self.epsilon:
                if valid_actions:
                    return random.choice(valid_actions)
                return random.randrange(self.action_dim)

            state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            with torch.no_grad():
                q_vals = self.policy_net(state_t).squeeze(0).cpu().numpy()

            if valid_actions:
                # Mask out invalid actions
                for i in range(self.action_dim):
                    if i not in valid_actions:
                        q_vals[i] = -np.inf
                return int(np.argmax(q_vals))
            return int(np.argmax(q_vals))

    def train_step(self):
        with self.lock:
            if len(self.memory) < self.batch_size:
                return 0.0

            states, actions, rewards, next_states, dones, indices, weights = self.memory.sample(self.batch_size)

            s_t = torch.FloatTensor(states).to(self.device)
            a_t = torch.LongTensor(actions).unsqueeze(1).to(self.device)
            r_t = torch.FloatTensor(rewards).to(self.device)
            s_next_t = torch.FloatTensor(next_states).to(self.device)
            d_t = torch.FloatTensor(dones).to(self.device)
            w_t = torch.FloatTensor(weights).to(self.device)

            q_values = self.policy_net(s_t).gather(1, a_t).squeeze(1)

            with torch.no_grad():
                next_actions = self.policy_net(s_next_t).argmax(dim=1, keepdim=True)
                next_q = self.target_net(s_next_t).gather(1, next_actions).squeeze(1)
                expected_q = r_t + (self.gamma * next_q * (1.0 - d_t))

            td_errors = (q_values - expected_q).abs().detach().cpu().numpy()
            self.memory.update_priorities(indices, td_errors)

            loss = (F.smooth_l1_loss(q_values, expected_q, reduction='none') * w_t).mean()

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
            self.optimizer.step()

            for target_param, policy_param in zip(self.target_net.parameters(), self.policy_net.parameters()):
                target_param.data.copy_(self.tau * policy_param.data + (1.0 - self.tau) * target_param.data)

            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
            return float(loss.item())

    def save(self):
        with self.lock:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            torch.save({
                'policy_net': self.policy_net.state_dict(),
                'target_net': self.target_net.state_dict(),
                'optimizer': self.optimizer.state_dict(),
                'epsilon': self.epsilon
            }, self.model_path)
            logger.info(f"[RLScalper] Saved model to {self.model_path}")

    def load(self):
        with self.lock:
            if os.path.exists(self.model_path):
                try:
                    checkpoint = torch.load(self.model_path, map_location=self.device)
                    self.policy_net.load_state_dict(checkpoint['policy_net'])
                    self.target_net.load_state_dict(checkpoint['target_net'])
                    self.optimizer.load_state_dict(checkpoint['optimizer'])
                    self.epsilon = checkpoint.get('epsilon', self.epsilon)
                    logger.info(f"[RLScalper] Loaded model from {self.model_path}")
                except Exception as e:
                    logger.warning(f"[RLScalper] Load failed: {e}. Starting fresh.")

# Singleton
_SCALPER_AGENT = RLScalperAgent()

def get_rl_scalper():
    return _SCALPER_AGENT
