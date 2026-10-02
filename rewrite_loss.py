import re

with open("backend/btc/rl_agent.py", "r") as f:
    code = f.read()

pattern = r'            # Weighted Huber Loss \(Smooth L1 with PER importance sampling weights\).*?loss = \(loss_per_sample \* weights_t\)\.mean\(\)'
code = re.sub(pattern, "", code, flags=re.DOTALL)

with open("backend/btc/rl_agent.py", "w") as f:
    f.write(code)
print("Removed old loss computation!")
