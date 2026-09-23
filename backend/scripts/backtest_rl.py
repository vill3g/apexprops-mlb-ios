import os
import sys
import json
import logging
import torch
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from datetime import datetime

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

def evaluate_rl_agent():
    agent = get_rl_agent()
    # Put policy net in eval mode
    agent.policy_net.eval()
    
    print("=" * 68)
    print("        RL SHADOW AGENT BACKTEST & ACCURACY AUDIT")
    print("=" * 68)
    print(f"Model Path:     {agent.model_path}")
    print(f"Device:         {agent.device}")
    print(f"Active Epsilon: {agent.epsilon:.3f}")
    print(f"Replay Buffer:  {len(agent.memory)} experiences")

    # =========================================================================
    # PART 1: EVALUATION ON 234 REAL KALSHI RECORDED TRADES
    # =========================================================================
    print("\n" + "-" * 68)
    print(" PART 1: REPLAY ON REAL HISTORICAL KALSHI TRADES (trades_history.json)")
    print("-" * 68)
    
    trades_file = os.path.join(REPO_DIR, "backend", "data", "trades_history.json")
    if not os.path.exists(trades_file):
        print("trades_history.json not found.")
        return

    with open(trades_file, "r", encoding="utf-8") as f:
        trades = json.load(f)

    # Replay on completed trades
    total_replayed = 0
    rl_agreed_trades = 0
    rl_pass_count = 0
    rl_active_trades = 0
    rl_wins = 0
    rl_losses = 0
    original_wins = 0
    original_losses = 0
    
    q_confidence_margins = []

    for t in trades:
        raw = t.get("raw_features", t.get("market_snapshot", {}).get("raw_features"))
        pnl = t.get("pnl")
        actual_dir = t.get("direction")
        
        if not raw or pnl is None or not actual_dir:
            continue

        state = build_vector_from_dict(raw)
        state_t = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
        with torch.no_grad():
            q_vals = agent.policy_net(state_t).cpu().numpy()[0]
        
        best_action = int(np.argmax(q_vals)) # 0: PASS, 1: ABOVE (YES), 2: BELOW (NO)
        q_margin = float(np.max(q_vals) - np.min(q_vals))
        q_confidence_margins.append(q_margin)

        # Track what original strategy did
        orig_win = float(pnl) > 0
        if orig_win:
            original_wins += 1
        else:
            original_losses += 1

        total_replayed += 1

        if best_action == 0:
            rl_pass_count += 1
        else:
            rl_active_trades += 1
            rl_dir = "ABOVE" if best_action == 1 else "BELOW"
            
            # Did RL pick the winning side?
            # If original trade won and RL agreed with original direction -> RL won
            # If original trade lost and RL picked opposite direction -> RL won
            if orig_win:
                if rl_dir == actual_dir:
                    rl_wins += 1
                else:
                    rl_losses += 1
            else:
                if rl_dir != actual_dir:
                    rl_wins += 1
                else:
                    rl_losses += 1

    orig_total = original_wins + original_losses
    orig_wr = (original_wins / orig_total * 100) if orig_total > 0 else 0
    rl_wr = (rl_wins / rl_active_trades * 100) if rl_active_trades > 0 else 0

    print(f"Total Completed Trades Analyzed: {total_replayed}")
    print(f"Original System Win Rate:        {orig_wr:.1f}% ({original_wins}W / {original_losses}L)")
    print(f"RL Agent PASS Decisions:         {rl_pass_count} ({rl_pass_count/max(1, total_replayed)*100:.1f}% filtered)")
    print(f"RL Agent Active Trades:          {rl_active_trades}")
    print(f"RL Agent Directional Wins:       {rl_wins}")
    print(f"RL Agent Directional Losses:     {rl_losses}")
    print(f"RL Agent Win Rate:               {rl_wr:.1f}%")
    print(f"Win Rate Improvement:            {rl_wr - orig_wr:+.1f}%")
    print(f"Avg Q-Value Decision Margin:     {np.mean(q_confidence_margins):.3f}")

    # =========================================================================
    # PART 2: COMPREHENSIVE 60-DAY MARKET INTERVAL BACKTEST
    # =========================================================================
    print("\n" + "-" * 68)
    print(" PART 2: 60-DAY MARKET INTERVAL WALK-FORWARD BACKTEST (5,700+ Candles)")
    print("-" * 68)
    
    df = fetch_15m_candles_history(days=60)
    df_ind = add_all_indicators(df)

    total_candles = 0
    market_pass = 0
    market_trades = 0
    market_wins = 0
    market_losses = 0
    market_pnl_cents = 0.0

    day_trades = 0
    day_wins = 0
    night_trades = 0
    night_wins = 0

    high_vol_trades = 0
    high_vol_wins = 0
    low_vol_trades = 0
    low_vol_wins = 0

    for i in range(50, len(df_ind) - 1):
        c = df_ind.iloc[i]
        c_open = float(c.get("open", 0.0))
        c_close = float(c.get("close", 0.0))
        
        if c_open <= 0 or c_close <= 0:
            continue

        raw_feat = build_feature_row(df_ind, i)
        raw_feat["minutes_remaining"] = 1.0
        state = build_vector_from_dict(raw_feat)

        state_t = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
        with torch.no_grad():
            q_vals = agent.policy_net(state_t).cpu().numpy()[0]

        action = int(np.argmax(q_vals))
        total_candles += 1

        # Check time filter (Day vs Night ET)
        dt_val = c.get("datetime")
        is_night = False
        if dt_val:
            try:
                if isinstance(dt_val, str):
                    dt_obj = datetime.fromisoformat(dt_val.replace('Z', '+00:00'))
                else:
                    dt_obj = dt_val
                ny_dt = dt_obj.astimezone(ZoneInfo("America/New_York"))
                is_night = 0 <= ny_dt.hour < 7
            except Exception:
                pass

        # Volatility regime
        vol_pct = raw_feat.get("vol_regime_percentile", 50.0)
        is_high_vol = vol_pct >= 50.0

        if action == 0:
            market_pass += 1
        else:
            market_trades += 1
            predicted_up = (action == 1)
            actual_up = (c_close > c_open)
            actual_down = (c_close < c_open)

            is_win = (predicted_up and actual_up) or (not predicted_up and actual_down)

            if is_win:
                market_wins += 1
                market_pnl_cents += 48.0 # typical 48c profit on Kalshi 52c entry
            else:
                market_losses += 1
                market_pnl_cents -= 52.0

            if is_night:
                night_trades += 1
                if is_win: night_wins += 1
            else:
                day_trades += 1
                if is_win: day_wins += 1

            if is_high_vol:
                high_vol_trades += 1
                if is_win: high_vol_wins += 1
            else:
                low_vol_trades += 1
                if is_win: low_vol_wins += 1

    m_wr = (market_wins / market_trades * 100) if market_trades > 0 else 0
    day_wr = (day_wins / day_trades * 100) if day_trades > 0 else 0
    night_wr = (night_wins / night_trades * 100) if night_trades > 0 else 0
    h_vol_wr = (high_vol_wins / high_vol_trades * 100) if high_vol_trades > 0 else 0
    l_vol_wr = (low_vol_wins / low_vol_trades * 100) if low_vol_trades > 0 else 0

    print(f"Total 15m Intervals Evaluated:   {total_candles}")
    print(f"RL PASS Rate (Filtered Out):     {market_pass} ({market_pass/total_candles*100:.1f}%)")
    print(f"Total Trades Taken:              {market_trades}")
    print(f"Wins:                            {market_wins}")
    print(f"Losses:                          {market_losses}")
    print(f"Overall Walk-Forward Win Rate:   {m_wr:.2f}%")
    print(f"Simulated Profit/Loss:           ${market_pnl_cents/100:.2f}")
    print(f"\nBreakdown by Market Regime:")
    print(f"  Day Session (07:00-23:59 ET):  {day_wr:.1f}% ({day_wins}/{day_trades})")
    print(f"  Night Session (00:00-06:59 ET):{night_wr:.1f}% ({night_wins}/{night_trades})")
    print(f"  High Volatility Regimes:       {h_vol_wr:.1f}% ({high_vol_wins}/{high_vol_trades})")
    print(f"  Low Volatility / Chop Regimes: {l_vol_wr:.1f}% ({low_vol_wins}/{low_vol_trades})")
    print("=" * 68)

if __name__ == "__main__":
    evaluate_rl_agent()
