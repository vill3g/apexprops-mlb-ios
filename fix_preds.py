import re

with open("backend/btc/train_rl_full.py", "r") as f:
    code = f.read()

pattern = r'preds = agent\.policy_net\(val_states_tensor\)\.argmax\(dim=1\)\.cpu\(\)\.numpy\(\)'
replacement = 'preds = agent.policy_net(val_states_tensor).mean(dim=2).argmax(dim=1).cpu().numpy()'
code = re.sub(pattern, replacement, code)

with open("backend/btc/train_rl_full.py", "w") as f:
    f.write(code)
print("Fixed preds shape in train_rl_full.py!")
