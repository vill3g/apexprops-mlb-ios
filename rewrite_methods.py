import re

with open("backend/btc/rl_agent.py", "r") as f:
    code = f.read()

# 1. Update q_values
pattern = r'def q_values\(self, state\) -> np\.ndarray:.*?return self\.policy_net\(state_tensor\)\.squeeze\(0\)\.cpu\(\)\.numpy\(\)'
replacement = """def q_values(self, state) -> np.ndarray:
        with self.lock:
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            with torch.no_grad():
                q_dist = self.policy_net(state_tensor) # (1, 3, 51)
                return q_dist.mean(dim=2).squeeze(0).cpu().numpy()"""
code = re.sub(pattern, replacement, code, flags=re.DOTALL)

# 2. Update select_action
pattern = r'def select_action\(self, state\):.*?q_values = self\.policy_net\(state_tensor\).*?return int\(q_values\.argmax\(dim=1\)\.item\(\)\)'
replacement = """def select_action(self, state):
        if random.random() < self.epsilon:
            return random.randint(0, 2)
        with self.lock:
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            with torch.no_grad():
                q_dist = self.policy_net(state_tensor)
                q_values = q_dist.mean(dim=2)
                return int(q_values.argmax(dim=1).item())"""
code = re.sub(pattern, replacement, code, flags=re.DOTALL)

# 3. Update train_step
pattern = r'# Current Q-values.*?self\.memory\.update_priorities\(indices, td_errors\)'
replacement = """# Current Q-distribution
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
            self.memory.update_priorities(indices, mean_td_errors)"""
code = re.sub(pattern, replacement, code, flags=re.DOTALL)

with open("backend/btc/rl_agent.py", "w") as f:
    f.write(code)
print("Updated RLAgent methods!")
