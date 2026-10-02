import re

with open("backend/btc/rl_agent.py", "r") as f:
    code = f.read()

pattern = r'class DuelingDQN\(nn\.Module\):.*?return q_values'
replacement = """class DuelingDQN(nn.Module):
    \"\"\"
    Hybrid LSTM Quantile Regression Dueling Deep Q-Network (QR-DQN).
    Outputs a distribution of Q-values (quantiles) rather than a single mean expected reward,
    enabling the agent to understand fat-tail risk, uncertainty, and conviction grading.
    \"\"\"
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
        return q_dist"""

new_code = re.sub(pattern, replacement, code, flags=re.DOTALL)
with open("backend/btc/rl_agent.py", "w") as f:
    f.write(new_code)
print("Replaced DuelingDQN!")
