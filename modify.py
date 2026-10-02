import re

with open('backend/btc/train_rl_scalper.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace build_state
old_build_state = '''def build_state(base, pos_type, unrealized, snap):
    yes_ask, yes_bid = snap["ask"], snap["bid"]
    keys = sorted(base.keys())
    vec = [base[k] for k in keys]
    vec += [pos_type, unrealized, yes_ask, yes_bid, 1.0 - yes_bid, 1.0 - yes_ask, 900.0 - snap["off"]]
    return np.array(vec, dtype=np.float32)'''

new_build_state = '''def build_state(base, pos_type, unrealized, snap, prev_snap=None):
    yes_ask, yes_bid = snap["ask"], snap["bid"]
    prev_ask = prev_snap["ask"] if prev_snap else yes_ask
    prev_bid = prev_snap["bid"] if prev_snap else yes_bid
    
    velocity_ask = yes_ask - prev_ask
    velocity_bid = yes_bid - prev_bid
    spread = yes_ask - yes_bid
    
    keys = sorted(base.keys())
    vec = [base[k] for k in keys]
    vec += [
        pos_type, unrealized, 
        yes_ask, yes_bid, 1.0 - yes_bid, 1.0 - yes_ask, 
        900.0 - snap["off"],
        velocity_ask, velocity_bid, spread
    ]
    return np.array(vec, dtype=np.float32)'''

content = content.replace(old_build_state, new_build_state)

# Replace run_episode loop
old_loop = '''    snaps = ep["snaps"]
    for k, snap in enumerate(snaps):
        last = k == len(snaps) - 1
        nxt = snap if last else snaps[k + 1]
        state = build_state(ep["base"], pos_type, unrealized_pnl(pos_type, entry, snap), snap)
        action = agent.select_action(state, exploit=not explore, valid_actions=valid_actions(pos_type))
        cash, new_pos, new_entry = step(pos_type, entry, action, snap)
        if action in (1, 2) and pos_type == 0.0:
            trades += 1
        if last and new_pos != 0.0:
            # Held past the trained window: value it at settlement (no exit fee at expiry)
            payout = (1.0 if ep["result_yes"] else 0.0) if new_pos == 1.0 else (0.0 if ep["result_yes"] else 1.0)
            cash += payout - new_entry
        pnl += cash
        if learn:
            phi_next = 0.0 if last else potential(new_pos, new_entry, nxt)
            shaped = cash + gamma * phi_next - potential(pos_type, entry, snap)
            next_state = build_state(ep["base"], new_pos, unrealized_pnl(new_pos, new_entry, nxt), nxt)'''

new_loop = '''    snaps = ep["snaps"]
    for k, snap in enumerate(snaps):
        last = k == len(snaps) - 1
        nxt = snap if last else snaps[k + 1]
        prev_snap = snaps[k - 1] if k > 0 else snap
        state = build_state(ep["base"], pos_type, unrealized_pnl(pos_type, entry, snap), snap, prev_snap)
        action = agent.select_action(state, exploit=not explore, valid_actions=valid_actions(pos_type))
        cash, new_pos, new_entry = step(pos_type, entry, action, snap)
        if action in (1, 2) and pos_type == 0.0:
            trades += 1
        if last and new_pos != 0.0:
            # Held past the trained window: value it at settlement (no exit fee at expiry)
            payout = (1.0 if ep["result_yes"] else 0.0) if new_pos == 1.0 else (0.0 if ep["result_yes"] else 1.0)
            cash += payout - new_entry
        pnl += cash
        if learn:
            # Add time-decay penalty to force faster scalps
            time_penalty = -0.0005 if pos_type != 0.0 else 0.0
            phi_next = 0.0 if last else potential(new_pos, new_entry, nxt)
            shaped = cash + time_penalty + gamma * phi_next - potential(pos_type, entry, snap)
            next_state = build_state(ep["base"], new_pos, unrealized_pnl(new_pos, new_entry, nxt), nxt, snap)'''

content = content.replace(old_loop, new_loop)

with open('backend/btc/train_rl_scalper.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("train_rl_scalper.py modified")
