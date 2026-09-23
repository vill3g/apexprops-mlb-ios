import os
import json
import random
import logging
import threading
from collections import deque
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F

logger = logging.getLogger(__name__)

class DQN(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(DQN, self).__init__()
        self.fc1 = nn.Linear(input_dim, 128)
        self.ln1 = nn.LayerNorm(128)
        self.fc2 = nn.Linear(128, 64)
        self.ln2 = nn.LayerNorm(64)
        self.fc3 = nn.Linear(64, output_dim)

    def forward(self, x):
        x = F.relu(self.ln1(self.fc1(x)))
        x = F.relu(self.ln2(self.fc2(x)))
        return self.fc3(x)

class ReplayBuffer:
    def __init__(self, capacity):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size):
        state, action, reward, next_state, done = zip(*random.sample(self.buffer, batch_size))
        return np.array(state), action, reward, np.array(next_state), done

    def __len__(self):
        return len(self.buffer)

from backend.btc.ml_engine import FEATURE_KEYS

class RLAgent:
    def __init__(self, state_dim=len(FEATURE_KEYS), action_dim=3, lr=1e-4, gamma=0.99, epsilon_start=1.0, epsilon_end=0.01, epsilon_decay=0.995):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.policy_net = DQN(state_dim, action_dim).to(self.device)
        self.target_net = DQN(state_dim, action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=lr)
        self.memory = ReplayBuffer(10000)
        self.batch_size = 64
        self.lock = threading.Lock()

        # Cache file
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "model_cache", "rl_agent.pth")
        self.load()

    def select_action(self, state):
        with self.lock:
            if random.random() < self.epsilon:
                return random.randrange(self.action_dim)
            
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            with torch.no_grad():
                q_values = self.policy_net(state_tensor)
                return q_values.max(1)[1].item()

    def train_step(self):
        with self.lock:
            if len(self.memory) < self.batch_size:
                return 0.0

            state, action, reward, next_state, done = self.memory.sample(self.batch_size)
            
            state = torch.FloatTensor(state).to(self.device)
            next_state = torch.FloatTensor(next_state).to(self.device)
            action = torch.LongTensor(action).to(self.device)
            reward = torch.FloatTensor(reward).to(self.device)
            done = torch.FloatTensor(done).to(self.device)

            q_values = self.policy_net(state)
            state_action_values = q_values.gather(1, action.unsqueeze(1)).squeeze(1)

            with torch.no_grad():
                next_q_values = self.target_net(next_state).max(1)[0]
                expected_state_action_values = reward + (self.gamma * next_q_values * (1 - done))

            loss = F.smooth_l1_loss(state_action_values, expected_state_action_values)

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=1.0)
            self.optimizer.step()

            # Periodically sync target network during continuous live trading
            self.train_steps = getattr(self, "train_steps", 0) + 1
            if self.train_steps % 50 == 0:
                self.target_net.load_state_dict(self.policy_net.state_dict())

            # Decay epsilon
            self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
            return loss.item()

    def update_target_network(self):
        with self.lock:
            self.target_net.load_state_dict(self.policy_net.state_dict())

    def save(self):
        with self.lock:
            torch.save({
                'policy_net': self.policy_net.state_dict(),
                'target_net': self.target_net.state_dict(),
                'optimizer': self.optimizer.state_dict(),
                'epsilon': self.epsilon
            }, self.model_path)
            logger.info(f"[RLAgent] Saved model to {self.model_path}")

    def load(self):
        with self.lock:
            if os.path.exists(self.model_path):
                checkpoint = torch.load(self.model_path, map_location=self.device)
                self.policy_net.load_state_dict(checkpoint['policy_net'])
                self.target_net.load_state_dict(checkpoint['target_net'])
                self.optimizer.load_state_dict(checkpoint['optimizer'])
                self.epsilon = checkpoint['epsilon']
                logger.info(f"[RLAgent] Loaded pre-trained model from {self.model_path}. Epsilon: {self.epsilon:.3f}")
            self.rehydrate_memory_from_disk()

    def rehydrate_memory_from_disk(self):
        shadow_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rl_shadow_trades.json")
        if os.path.exists(shadow_file):
            try:
                import json
                with open(shadow_file, "r") as f:
                    trades = json.load(f)
                count = 0
                for t in trades:
                    if t.get("status") == "SETTLED":
                        s = t.get("state_vector")
                        a = t.get("action")
                        pnl = float(t.get("pnl", 0.0))
                        if s is not None and a is not None:
                            reward = pnl * 10.0
                            if len(s) > 33 and s[33] < 25.0:
                                reward -= 0.5
                            self.memory.push(s, a, reward, s, done=True)
                            count += 1
                logger.info(f"[RLAgent] Rehydrated {count} experiences into replay buffer from disk.")
            except Exception as e:
                logger.warning(f"[RLAgent] Failed to rehydrate replay buffer: {e}")

# Singleton instance
_RL_AGENT = RLAgent()

def get_rl_agent():
    return _RL_AGENT
