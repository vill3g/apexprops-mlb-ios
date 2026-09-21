import os
import json
import logging
from backend.btc.rl_agent import get_rl_agent
from backend.btc.ml_engine import FEATURE_KEYS, NEUTRAL_FEATURE_DEFAULTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")

def _build_state_vector(raw_features: dict) -> list:
    vec = []
    for k in FEATURE_KEYS:
        default_val = NEUTRAL_FEATURE_DEFAULTS.get(k, 0.0)
        val = raw_features.get(k, default_val)
        try:
            val = float(val)
        except (ValueError, TypeError):
            val = default_val
        vec.append(val)
    return vec

def pre_train_rl_agent(epochs=3):
    if not os.path.exists(HISTORY_FILE):
        logger.error(f"Cannot pre-train, history file not found: {HISTORY_FILE}")
        return

    with open(HISTORY_FILE, 'r') as f:
        try:
            trades = json.load(f)
        except json.JSONDecodeError:
            logger.error("Failed to parse trades_history.json")
            return

    # Filter trades that have raw_features and pnl
    valid_episodes = []
    for t in trades:
        raw = t.get("raw_features", t.get("market_snapshot", {}).get("raw_features"))
        if not raw:
            continue
            
        pnl = t.get("pnl")
        if pnl is None:
            continue
            
        state = _build_state_vector(raw)
        
        # Determine the action the AI actually took
        # 1: BUY YES (ABOVE), 2: BUY NO (BELOW)
        direction = t.get("direction", "ABOVE")
        action = 1 if direction == "ABOVE" else 2

        valid_episodes.append({
            "state": state,
            "action": action,
            "reward": float(pnl) * 10.0 # Scale reward
        })

    if not valid_episodes:
        logger.info("No valid episodes found for RL pre-training.")
        return

    agent = get_rl_agent()
    logger.info(f"Starting Pre-Training on {len(valid_episodes)} historical trades over {epochs} epochs...")

    total_loss = 0
    steps = 0

    for epoch in range(epochs):
        logger.info(f"--- Epoch {epoch+1}/{epochs} ---")
        for i, ep in enumerate(valid_episodes):
            state = ep["state"]
            action = ep["action"]
            reward = ep["reward"]
            
            # Since Kalshi contracts resolve independently, we treat each trade as a single-step episode.
            # Next state is terminal (same state, done=True)
            agent.memory.push(state, action, reward, state, done=True)
            
            loss = agent.train_step()
            if loss > 0:
                total_loss += loss
                steps += 1
                
        agent.update_target_network()

    if steps > 0:
        logger.info(f"Pre-Training Complete. Avg Loss: {total_loss/steps:.4f}")
    agent.save()

if __name__ == "__main__":
    pre_train_rl_agent(epochs=10)
