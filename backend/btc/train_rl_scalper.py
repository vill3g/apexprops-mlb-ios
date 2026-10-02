"""
Train and validate the RL scalping agent (backend/btc/rl_scalper.py).

Fixes over the first version:
  * entry fee counted once (it was subtracted on entry AND folded into the entry price);
  * transitions use the NEXT snapshot's prices (they reused the current prices, so the
    agent never learned how prices move);
  * invalid actions are masked (BUY while holding, CLOSE while flat);
  * candles come from coinbase_btc15m_history.csv, the same source the live bot uses;
  * episodes are split by time: trains on the older 85%, then measures the greedy policy
    once on the newest 15%. The agent is ENABLED for live trading only if that held-out
    profit (after fees) has a 95% confidence interval above zero with >= 100 trades.

Data limitation: kalshi_btc15m_history.jsonl holds quotes for the first 4 minutes of each
market (60-240 s). The live scalper therefore only acts in that window; positions still
open afterwards are held to settlement (or exited by the normal stop-loss/take-profit).

Usage: python backend/btc/train_rl_scalper.py [--epochs 5]
"""
import argparse
import json
import logging
import os
import sys
import time

import numpy as np
import pandas as pd

REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_DIR)

from backend.btc.indicators import add_all_indicators  # noqa: E402
from backend.btc.rl_priced import (kalshi_fee, market_features,  # noqa: E402
                                   valid_quote)
from backend.btc.rl_scalper import (SCALPER_META_PATH,  # noqa: E402
                                    get_rl_scalper)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CSV_PATH = os.path.join(REPO_DIR, "backend", "data", "coinbase_btc15m_history.csv")
JSONL_PATH = os.path.join(REPO_DIR, "backend", "data", "kalshi_btc15m_history.jsonl")
MAX_TRAINED_SECONDS = 240


def load_episodes():
    df = add_all_indicators(pd.read_csv(CSV_PATH)).reset_index(drop=True)
    pos = {int(t): i for i, t in enumerate(df["time"].astype("int64"))}
    by_ticker = {}
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                m = json.loads(line)
                by_ticker[m["ticker"]] = m
    episodes = []
    for m in by_ticker.values():
        i = pos.get(int(m["open_ts"]))
        if i is None or i < 300 or m.get("result") not in ("yes", "no"):
            continue
        snaps = [c for c in sorted(m.get("c", []), key=lambda c: c["off"])
                 if c["off"] <= MAX_TRAINED_SECONDS and valid_quote(c.get("ask"), c.get("bid"))]
        if len(snaps) < 2:
            continue
        episodes.append({"open_ts": int(m["open_ts"]), "base": market_features(df, i),
                         "snaps": snaps, "result_yes": m["result"] == "yes"})
    episodes.sort(key=lambda e: e["open_ts"])
    return episodes


def build_state(base, pos_type, unrealized, snap, prev_snap=None):
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
    return np.array(vec, dtype=np.float32)


def unrealized_pnl(pos_type, entry, snap):
    if pos_type == 1.0:
        bid = snap["bid"]
    elif pos_type == -1.0:
        bid = 1.0 - snap["ask"]
    else:
        return 0.0
    return bid - entry - kalshi_fee(bid)


def step(pos_type, entry, action, snap):
    """Returns (reward, new_pos_type, new_entry). Fees are charged exactly once per fill."""
    yes_ask, yes_bid = snap["ask"], snap["bid"]
    no_ask, no_bid = 1.0 - yes_bid, 1.0 - yes_ask
    if action == 1 and pos_type == 0.0:
        return -kalshi_fee(yes_ask), 1.0, yes_ask
    if action == 2 and pos_type == 0.0:
        return -kalshi_fee(no_ask), -1.0, no_ask
    if action == 3 and pos_type != 0.0:
        bid = yes_bid if pos_type == 1.0 else no_bid
        return bid - entry - kalshi_fee(bid), 0.0, 0.0
    return 0.0, pos_type, entry


def valid_actions(pos_type):
    return [0, 3] if pos_type != 0.0 else [0, 1, 2]


def potential(pos_type, entry, snap):
    """Shaping potential: the open position's value if sold now (0 when flat)."""
    return unrealized_pnl(pos_type, entry, snap) if pos_type != 0.0 else 0.0


def run_episode(agent, ep, explore, learn, gamma=None):
    """Play one market. Returns (pnl, trades): pnl is REAL money per contract after
    fees (used for evaluation); the agent learns from pnl plus a shaping term.

    Shaping (dense feedback while holding) is potential-based, F = gamma*phi(s') - phi(s)
    with phi = unrealized P&L of the open position. It telescopes to zero over an
    episode, so it speeds up learning without changing which policy is best, and it
    never enters the P&L used to decide whether the scalper may trade live."""
    if gamma is None:
        gamma = float(getattr(agent, "gamma", 0.99))
    pos_type, entry, pnl, trades = 0.0, 0.0, 0.0, 0
    snaps = ep["snaps"]
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
            next_state = build_state(ep["base"], new_pos, unrealized_pnl(new_pos, new_entry, nxt), nxt, snap)
            agent.memory.push(state, action, shaped, next_state, last)
            agent.train_step()
        pos_type, entry = new_pos, new_entry
    return pnl, trades


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--min-test-trades", type=int, default=100)
    args = ap.parse_args()

    episodes = load_episodes()
    split = int(len(episodes) * 0.85)
    train, test = episodes[:split], episodes[split:]
    logger.info(f"{len(episodes)} episodes: {len(train)} train / {len(test)} held-out test")

    agent = get_rl_scalper()
    dim = len(build_state(train[0]["base"], 0.0, 0.0, train[0]["snaps"][0]))
    if agent.state_dim != dim:
        agent.__init__(state_dim=dim)

    rng = np.random.default_rng(0)
    for epoch in range(args.epochs):
        order = rng.permutation(len(train))
        pnl = [run_episode(agent, train[j], explore=True, learn=True)[0] for j in order]
        logger.info(f"Epoch {epoch + 1}/{args.epochs}: mean train episode P&L {np.mean(pnl):+.4f} (epsilon {agent.epsilon:.3f})")
    agent.save()

    results = [run_episode(agent, ep, explore=False, learn=False) for ep in test]
    traded = np.array([r[0] for r in results if r[1] > 0])
    n_trades = int(sum(r[1] for r in results))
    meta = {"trained_at": time.time(), "episodes_train": len(train), "episodes_test": len(test),
            "test_trades": n_trades, "max_entry_seconds": MAX_TRAINED_SECONDS, "enabled": False}
    if len(traded) >= 10:
        boots = [rng.choice(traded, len(traded)).mean() for _ in range(2000)]
        meta.update(test_net_per_traded_market=float(traded.mean()),
                    test_ci95=[float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))])
        meta["enabled"] = bool(n_trades >= args.min_test_trades and meta["test_ci95"][0] > 0)
    with open(SCALPER_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    logger.info(f"Held-out result: {meta}")
    if not meta["enabled"]:
        logger.warning("Scalper NOT enabled: no statistically reliable profit on held-out markets.")


if __name__ == "__main__":
    main()
