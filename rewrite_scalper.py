import re

with open("backend/btc/train_rl_scalper.py", "r") as f:
    code = f.read()

pattern = r'        reward, new_pos, new_entry = step\(pos_type, entry, action, snap\).*?pos_type, entry = new_pos, new_entry'
replacement = """        reward, new_pos, new_entry = step(pos_type, entry, action, snap)
        
        # CONTINUOUS REWARD SHAPING: Dense feedback for holding positions
        if action == 0 and pos_type != 0.0:
            nxt_snap = snaps[k + 1] if not last else snap
            current_upnl = unrealized_pnl(pos_type, entry, snap)
            next_upnl = unrealized_pnl(pos_type, entry, nxt_snap)
            
            # 1. Potential-based shaping (delta PnL)
            reward += (next_upnl - current_upnl)
            
            # 2. Drawdown Penalty (MAE)
            if next_upnl < -0.05:
                reward -= 0.01
                
            # 3. Winning Hold Reward
            if next_upnl > 0.02:
                reward += 0.005
                
        if action in (1, 2) and pos_type == 0.0:
            trades += 1
        last = k == len(snaps) - 1
        if last and new_pos != 0.0:
            # Held past the trained window: value it at settlement (no exit fee at expiry)
            payout = (1.0 if ep["result_yes"] else 0.0) if new_pos == 1.0 else (0.0 if ep["result_yes"] else 1.0)
            reward += payout - new_entry
        total += reward
        if learn:
            nxt = snaps[k + 1] if not last else snap
            next_state = build_state(ep["base"], new_pos, unrealized_pnl(new_pos, new_entry, nxt), nxt)
            agent.memory.push(state, action, reward, next_state, last)
            agent.train_step()
        pos_type, entry = new_pos, new_entry"""

code = re.sub(pattern, replacement, code, flags=re.DOTALL)

with open("backend/btc/train_rl_scalper.py", "w") as f:
    f.write(code)
print("Updated run_episode with Continuous Reward Shaping!")
