import os
import sys
import json
import logging
import torch
import numpy as np
import pandas as pd

REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_DIR)

from backend.btc.rl_agent import get_rl_agent
from backend.btc.ml_engine import FEATURE_KEYS, NEUTRAL_FEATURE_DEFAULTS, build_feature_row
from backend.btc.indicators import add_all_indicators
from backend.btc.data_fetcher import fetch_15m_candles_history

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def build_vector_from_dict(d: dict) -> list:
    vec = []
    for k in FEATURE_KEYS:
        default_val = NEUTRAL_FEATURE_DEFAULTS.get(k, 0.0)
        val = d.get(k, default_val)
        try:
            val = float(val)
            if not np.isfinite(val):
                val = default_val
        except (ValueError, TypeError):
            val = default_val
        vec.append(val)
    return vec

def run_curriculum_training(
    stage1_epochs: int = 3,
    stage2_epochs: int = 5,
    final_epsilon: float = 0.20
):
    agent = get_rl_agent()
    logger.info("=== INITIALIZING RL CURRICULUM TRAINING ===")
    logger.info(f"Agent Device: {agent.device} | State Dim: {agent.state_dim} | Action Dim: {agent.action_dim}")

    # -------------------------------------------------------------
    # STAGE 1: FOUNDATION TRAINING ON 60 DAYS OF MARKET PRICE ACTION
    # -------------------------------------------------------------
    logger.info("\n--- STAGE 1: 60-Day Market Simulation (Foundation) ---")
    df = fetch_15m_candles_history(days=60)
    logger.info(f"Loaded {len(df)} 15m historical candles. Computing indicators...")
    df_ind = add_all_indicators(df)
    
    stage1_episodes = []
    # Start after warm-up bars
    for i in range(50, len(df_ind) - 1):
        c = df_ind.iloc[i]
        c_open = float(c.get("open", 0.0))
        c_close = float(c.get("close", 0.0))
        delta = c_close - c_open
        
        # Build feature row safely
        raw_feat = build_feature_row(df_ind, i)
        raw_feat["minutes_remaining"] = 1.0
        state = build_vector_from_dict(raw_feat)
        
        # Determine optimal action & reward
        # Action 0: PASS, Action 1: BUY YES (ABOVE), Action 2: BUY NO (BELOW)
        if delta > 15.0: # Clean win for ABOVE
            action = 1
            reward = 10.0
        elif delta < -15.0: # Clean win for BELOW
            action = 2
            reward = 10.0
        else: # Chop / Pin near strike
            action = 0
            reward = 5.0

        stage1_episodes.append((state, action, reward))

    logger.info(f"Generated {len(stage1_episodes)} foundation episodes from historical market data.")
    
    # Push all into memory buffer
    for state, action, reward in stage1_episodes:
        agent.memory.push(state, action, reward, state, done=True)

    logger.info(f"ReplayBuffer primed with {len(agent.memory)} experiences. Running {stage1_epochs} training epochs...")
    
    total_loss_s1 = 0.0
    steps_s1 = 0
    for ep in range(stage1_epochs):
        epoch_loss = 0.0
        epoch_steps = 0
        for _ in range(min(len(stage1_episodes), 1500)):
            loss = agent.train_step()
            if loss > 0:
                epoch_loss += loss
                epoch_steps += 1
        agent.update_target_network()
        avg_loss = epoch_loss / max(1, epoch_steps)
        logger.info(f"Stage 1 Epoch {ep+1}/{stage1_epochs} complete | Avg Loss: {avg_loss:.4f}")
        total_loss_s1 += epoch_loss
        steps_s1 += epoch_steps

    # -------------------------------------------------------------
    # STAGE 2: FINE-TUNING ON REAL KALSHI EXCHANGE TRADES
    # -------------------------------------------------------------
    logger.info("\n--- STAGE 2: Real Kalshi Exchange Fine-Tuning ---")
    trades_file = os.path.join(REPO_DIR, "backend", "data", "trades_history.json")
    valid_trades = []
    if os.path.exists(trades_file):
        with open(trades_file, "r", encoding="utf-8") as f:
            trades = json.load(f)
        for t in trades:
            raw = t.get("raw_features", t.get("market_snapshot", {}).get("raw_features"))
            pnl = t.get("pnl")
            if raw and pnl is not None:
                state = build_vector_from_dict(raw)
                direction = t.get("direction", "ABOVE")
                action = 1 if direction == "ABOVE" else 2
                reward = float(pnl) * 10.0
                valid_trades.append((state, action, reward))
                # Add extra weight to real exchange experiences in the buffer
                agent.memory.push(state, action, reward, state, done=True)

    logger.info(f"Loaded {len(valid_trades)} real Kalshi trades for fine-tuning.")
    
    total_loss_s2 = 0.0
    steps_s2 = 0
    for ep in range(stage2_epochs):
        epoch_loss = 0.0
        epoch_steps = 0
        for _ in range(max(len(valid_trades) * 2, 200)):
            loss = agent.train_step()
            if loss > 0:
                epoch_loss += loss
                epoch_steps += 1
        agent.update_target_network()
        avg_loss = epoch_loss / max(1, epoch_steps)
        logger.info(f"Stage 2 Epoch {ep+1}/{stage2_epochs} complete | Avg Loss: {avg_loss:.4f}")
        total_loss_s2 += epoch_loss
        steps_s2 += epoch_steps

    # -------------------------------------------------------------
    # STAGE 3: CALIBRATE EPSILON & PERSIST MODEL
    # -------------------------------------------------------------
    logger.info("\n--- STAGE 3: Final Calibration & Persistence ---")
    agent.epsilon = final_epsilon
    agent.update_target_network()
    agent.save()
    logger.info(f"Curriculum Training Succeeded!")
    logger.info(f"Total Experiences in Buffer: {len(agent.memory)}")
    logger.info(f"Calibrated Epsilon: {agent.epsilon:.3f} (80% exploitation / 20% exploration)")
    logger.info(f"Model successfully saved to {agent.model_path}")

if __name__ == "__main__":
    run_curriculum_training()
