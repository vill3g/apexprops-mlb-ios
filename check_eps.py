import sys
sys.path.append('.')
from backend.btc.rl_agent import get_rl_agent
print(get_rl_agent().epsilon)
