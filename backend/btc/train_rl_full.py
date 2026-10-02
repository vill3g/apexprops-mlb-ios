import json
import logging
import os
import sys

import numpy as np
import torch

REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_DIR)

from backend.btc.data_fetcher import fetch_15m_candles_history
from backend.btc.indicators import add_all_indicators
from backend.btc.ml_engine import (FEATURE_KEYS, NEUTRAL_FEATURE_DEFAULTS,
                                   build_feature_row, normalize_features)
from backend.btc.rl_agent import get_rl_agent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def build_vector_from_dict(d: dict) -> list:
    """Build normalized feature vector guaranteed to match FEATURE_KEYS order and sanity checks."""
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
    stage1_epochs: int = 5,
    stage2_epochs: int = 6,
    final_epsilon: float = 0.05
):
    """
    State-of-the-Art Curriculum Training for Dueling Double DQN with Prioritized Experience Replay.
    Stages:
      1. Foundational Walkforward Learning on 60 Days of 15m Market Candles (Chronological Split)
         - ATR-scaled reward function with clear capital-preservation signals for PASS (Action 0).
         - Multi-horizon time decay simulation (14m, 7m, 2m).
      2. Real Kalshi Prediction Market Fine-Tuning
         - Direct experience replay from trades_history.json with asymmetric loss penalization.
      3. Calibration & Safe Checkpoint Persistence
    """
    agent = get_rl_agent()
    logger.info("=" * 68)
    logger.info("   INITIALIZING DUELING DOUBLE DQN CURRICULUM TRAINING")
    logger.info("=" * 68)
    logger.info(f"Agent Device: {agent.device} | State Dim: {agent.state_dim} | Action Dim: {agent.action_dim}")
    logger.info(f"Policy Net Architecture: {agent.policy_net.__class__.__name__}")

    # -------------------------------------------------------------
    # STAGE 1: FOUNDATION TRAINING ON 60 DAYS OF MARKET PRICE ACTION
    # -------------------------------------------------------------
    logger.info("\n--- STAGE 1: 60-Day Market Simulation (Foundation) ---")
    df = fetch_15m_candles_history(days=60)
    logger.info(f"Loaded {len(df)} 15m historical candles. Computing indicators...")
    df_ind = add_all_indicators(df)
    
    n_candles = len(df_ind)
    split_idx = int(n_candles * 0.80) # Strict Chronological Split (80% Train / 20% Val)
    logger.info(f"Dataset Chronological Split: {split_idx} Train Candles, {n_candles - split_idx} Validation Candles")

    # Precompute feature rows once for all candles to avoid redundant pandas slicing
    logger.info("Precomputing feature representations for historical candles...")
    feature_cache = {}
    for i in range(50, n_candles):
        feature_cache[i] = build_feature_row(df_ind, i)

    stage1_episodes = []
    # Loop over training slice
    for i in range(50, split_idx - 1):
        c = df_ind.iloc[i]
        c_open = float(c.get("open", 0.0))
        c_close = float(c.get("close", 0.0))
        delta = c_close - c_open
        atr = float(c.get("atr", 120.0))
        if atr <= 0 or not np.isfinite(atr):
            atr = 120.0

        # Volatility regime
        vol_pct = float(c.get("vol_regime_percentile", 0.5))
        if vol_pct > 1.0:
            vol_pct = vol_pct / 100.0

        raw_feat_base = feature_cache[i]
        raw_feat_next_base = feature_cache.get(i + 1, raw_feat_base)

        # Chop vs Trend Decision Rules
        # Threshold: moves under 0.25 * ATR are market noise/chop
        chop_threshold = max(20.0, 0.25 * atr)
        is_deadzone = (abs(delta) < chop_threshold) or (vol_pct < 0.20)

        # Multi-horizon time decay augmentation
        for time_rem in [14.5, 7.5, 2.0]:
            raw_feat = dict(raw_feat_base)
            raw_feat["minutes_remaining"] = time_rem
            norm_feat = normalize_features(raw_feat)
            state = build_vector_from_dict(norm_feat)

            raw_feat_next = dict(raw_feat_next_base)
            raw_feat_next["minutes_remaining"] = max(0.5, time_rem - 2.0)
            norm_feat_next = normalize_features(raw_feat_next)
            next_state = build_vector_from_dict(norm_feat_next)

            if is_deadzone:
                # In chop, PASS is optimal (+0.8). Trading incurs bid-ask and noise penalty (-0.8).
                stage1_episodes.append((state, 0, 0.8, next_state, True))
                stage1_episodes.append((state, 1, -0.8, next_state, True))
                stage1_episodes.append((state, 2, -0.8, next_state, True))
            elif delta > chop_threshold:
                # Upward trend: BUY YES wins (+1.8), BUY NO loses (-2.0), PASS incurs opportunity cost (-0.5).
                mag = min(2.0, delta / atr)
                stage1_episodes.append((state, 1, 1.8 * mag, next_state, True))
                stage1_episodes.append((state, 2, -2.0 * mag, next_state, True))
                stage1_episodes.append((state, 0, -0.5, next_state, True))
            else: # delta < -chop_threshold
                # Downward trend: BUY NO wins (+1.8), BUY YES loses (-2.0), PASS incurs opportunity cost (-0.5).
                mag = min(2.0, abs(delta) / atr)
                stage1_episodes.append((state, 2, 1.8 * mag, next_state, True))
                stage1_episodes.append((state, 1, -2.0 * mag, next_state, True))
                stage1_episodes.append((state, 0, -0.5, next_state, True))

    logger.info(f"Generated {len(stage1_episodes)} foundation transitions with multi-horizon augmentation.")
    
    # Prime PER memory buffer
    for state, action, reward, next_state, done in stage1_episodes:
        agent.memory.push(state, action, reward, next_state, done)

    logger.info(f"PER ReplayBuffer primed with {len(agent.memory)} transitions. Running {stage1_epochs} training epochs...")
    
    # Validation transitions
    val_states = []
    val_actions = []
    for i in range(split_idx, n_candles - 1):
        c = df_ind.iloc[i]
        c_open = float(c.get("open", 0.0))
        c_close = float(c.get("close", 0.0))
        delta = c_close - c_open
        atr = float(c.get("atr", 120.0))
        if atr <= 0 or not np.isfinite(atr):
            atr = 120.0
        raw_feat = dict(feature_cache.get(i, {}))
        raw_feat["minutes_remaining"] = 7.5
        norm_feat = normalize_features(raw_feat)
        state = build_vector_from_dict(norm_feat)
        chop_threshold = max(20.0, 0.25 * atr)
        true_action = 0 if abs(delta) < chop_threshold else (1 if delta > 0 else 2)
        val_states.append(state)
        val_actions.append(true_action)

    val_states_tensor = torch.FloatTensor(val_states).to(agent.device)
    val_actions_arr = np.array(val_actions)

    for ep in range(stage1_epochs):
        epoch_loss = 0.0
        epoch_steps = 0
        steps_target = min(len(stage1_episodes), 1500)
        for _ in range(steps_target):
            loss = agent.train_step()
            if loss > 0:
                epoch_loss += loss
                epoch_steps += 1
        
        # Fast vectorized validation
        agent.policy_net.eval()
        with torch.no_grad():
            preds = agent.policy_net(val_states_tensor).mean(dim=2).argmax(dim=1).cpu().numpy()
            val_acc = (preds == val_actions_arr).mean() * 100.0
        agent.policy_net.train()

        avg_loss = epoch_loss / max(1, epoch_steps)
        logger.info(f"Stage 1 Epoch {ep+1}/{stage1_epochs} complete | Train Loss: {avg_loss:.4f} | Val Accuracy: {val_acc:.1f}%")

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
            direction = t.get("direction")
            if raw and pnl is not None and direction in ["ABOVE", "BELOW"]:
                norm_raw = normalize_features(raw)
                state = build_vector_from_dict(norm_raw)
                action = 1 if direction == "ABOVE" else 2
                contracts = float(t.get("contracts", t.get("count", 1.0)) or 1.0)
                unit_pnl = float(pnl) / contracts if contracts > 0 else float(pnl)
                
                # Balanced Economic Reality:
                # If trade won: Chosen action wins (+1.8), opposite loses (-2.0), PASS incurs opportunity cost (-0.6)
                # If trade lost: Chosen action loses (-2.0), opposite wins (+1.8), PASS preserves capital (+0.6)
                if unit_pnl > 0:
                    agent.memory.push(state, action, 1.8, state, done=True)
                    opp_action = 2 if action == 1 else 1
                    agent.memory.push(state, opp_action, -2.0, state, done=True)
                    agent.memory.push(state, 0, -0.6, state, done=True)
                else:
                    agent.memory.push(state, action, -2.0, state, done=True)
                    opp_action = 2 if action == 1 else 1
                    agent.memory.push(state, opp_action, 1.8, state, done=True)
                    agent.memory.push(state, 0, 0.6, state, done=True)

                valid_trades.append((state, action, unit_pnl))

    logger.info(f"Loaded and augmented {len(valid_trades)} real Kalshi exchange trades for fine-tuning.")
    
    for ep in range(stage2_epochs):
        epoch_loss = 0.0
        epoch_steps = 0
        steps_target = max(len(valid_trades) * 3, 400)
        for _ in range(steps_target):
            loss = agent.train_step()
            if loss > 0:
                epoch_loss += loss
                epoch_steps += 1
        avg_loss = epoch_loss / max(1, epoch_steps)
        logger.info(f"Stage 2 Epoch {ep+1}/{stage2_epochs} complete | Fine-Tune Loss: {avg_loss:.4f} | Epsilon: {agent.epsilon:.3f}")

    # -------------------------------------------------------------
    # STAGE 3: CALIBRATE EPSILON & PERSIST MODEL
    # -------------------------------------------------------------
    logger.info("\n--- STAGE 3: Final Calibration & Model Checkpoint ---")
    agent.epsilon = final_epsilon
    agent.update_target_network()
    agent.save()

    # The old probability calibration belongs to the previous weights — refit it on
    # candles outside this training window, or remove it so RL passes until calibrated.
    try:
        from backend.scripts.calibrate_rl import calibrate
        cal = calibrate()
        logger.info(f"Recalibrated RL probabilities: a={cal['a']:.4f} b={cal['b']:.4f} holdout={cal['holdout']}")
    except Exception as e:
        from backend.btc.rl_agent import CALIBRATION_PATH
        if os.path.exists(CALIBRATION_PATH):
            os.remove(CALIBRATION_PATH)
        logger.warning(f"RL calibration failed ({e}); removed stale calibration. RL will PASS until "
                       f"backend/scripts/calibrate_rl.py succeeds.")
    logger.info("Curriculum Training Succeeded!")
    logger.info(f"Total Experiences in Buffer: {len(agent.memory)}")
    logger.info(f"Live Policy Epsilon: {agent.epsilon:.3f} (95% exploitation / 5% exploration)")
    logger.info(f"Saved Checkpoint: {agent.model_path}")

if __name__ == "__main__":
    run_curriculum_training()
