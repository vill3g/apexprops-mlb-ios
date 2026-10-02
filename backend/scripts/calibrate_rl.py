"""
Fit the RL DQN probability calibration (Platt scaling) on out-of-sample 15m candles.

The DQN outputs Q-values, not probabilities. This script maps the directional score
(Q_yes - Q_no) to P(YES) = sigmoid(a * score + b), using candles the model was NOT
trained on, and writes backend/data/model_cache/rl_calibration.json. The live RL
signal refuses to trade (PASS) when that file is missing.

Usage (from the project root, with the app's venv):
    python backend/scripts/calibrate_rl.py
    python backend/scripts/calibrate_rl.py --exclude-days 60 --minutes 14.5

Re-run it after every full retrain (train_rl_full.py runs it automatically).
"""
import argparse
import datetime
import json
import os
import sys
import time

import numpy as np
import pandas as pd

REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_DIR)

from backend.btc.indicators import add_all_indicators  # noqa: E402
from backend.btc.io_utils import atomic_json_write  # noqa: E402
from backend.btc.ml_engine import build_feature_row  # noqa: E402
from backend.btc.rl_agent import (CALIBRATION_PATH, fit_platt,  # noqa: E402
                                  get_rl_agent)
from backend.btc.shadow_executor import _build_state_vector  # noqa: E402

DEFAULT_CSV = os.path.join(REPO_DIR, "backend", "data", "historical_candles_btc_15m.csv")


def _log_loss(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _auc(score, y):
    order = np.argsort(score)
    ranks = np.empty(len(order))
    ranks[order] = np.arange(1, len(order) + 1)
    n1 = y.sum()
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return 0.5
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def calibrate(csv_path: str = DEFAULT_CSV, exclude_days: float = 60.0, minutes: float = 14.5,
              exclude_after: float = None, write: bool = True) -> dict:
    agent = get_rl_agent()
    model_mtime = os.path.getmtime(agent.model_path) if os.path.exists(agent.model_path) else time.time()
    # Candles inside the model's training window are excluded (train_rl_full uses the last 60 days)
    cutoff = exclude_after if exclude_after is not None else model_mtime - exclude_days * 86400

    df = pd.read_csv(csv_path)
    df_ind = add_all_indicators(df.copy())

    states, labels, times = [], [], []
    for i in range(300, len(df_ind)):
        c = df_ind.iloc[i]
        if float(c["time"]) >= cutoff:
            break
        raw = build_feature_row(df_ind, i)
        raw["minutes_remaining"] = minutes
        states.append(_build_state_vector(raw))
        labels.append(1 if float(c["close"]) > float(c["open"]) else 0)
        times.append(int(c["time"]))
    if len(states) < 2000:
        raise RuntimeError(f"Only {len(states)} out-of-sample candles before cutoff — need at least 2000.")

    q = np.array([agent.q_values(s) for s in states])
    score = q[:, 1] - q[:, 2]
    y = np.array(labels, dtype=np.float64)

    # Honest check: fit on the first 70%, evaluate on the last 30%
    split = int(len(y) * 0.7)
    a_tr, b_tr = fit_platt(score[:split], y[:split])
    p_te = 1 / (1 + np.exp(-(a_tr * score[split:] + b_tr)))
    base = float(y[:split].mean())
    test = {
        "n": int(len(y) - split),
        "log_loss_model": round(_log_loss(p_te, y[split:]), 5),
        "log_loss_base_rate": round(_log_loss(np.full(len(p_te), base), y[split:]), 5),
        "auc": round(_auc(score[split:], y[split:]), 4),
    }
    test["skill_vs_base_rate"] = round(test["log_loss_base_rate"] - test["log_loss_model"], 5)

    a, b = fit_platt(score, y)
    p_all = 1 / (1 + np.exp(-(a * score + b)))
    fmt = lambda e: datetime.datetime.utcfromtimestamp(e).strftime("%Y-%m-%d")
    result = {
        "a": a,
        "b": b,
        "method": "platt(Q_yes - Q_no)",
        # Unconditional P(YES) over the same window. Live decisions use the model's
        # deviation from this base rate on top of the market's own price.
        "base_rate": float(y.mean()),
        "minutes_remaining": minutes,
        "n": int(len(y)),
        "window": f"{fmt(times[0])} to {fmt(times[-1])} (UTC)",
        "p_yes_range_1_99pct": [round(float(x), 4) for x in np.percentile(p_all, [1, 99])],
        "holdout": test,
        "model_train_steps": int(agent.train_steps),
        "model_mtime": model_mtime,
        "fitted_at": time.time(),
    }
    if write:
        atomic_json_write(CALIBRATION_PATH, result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--exclude-days", type=float, default=60.0,
                    help="skip candles within this many days before the model file's timestamp (its training window)")
    ap.add_argument("--minutes", type=float, default=14.5, help="minutes_remaining used for the features")
    args = ap.parse_args()
    res = calibrate(args.csv, args.exclude_days, args.minutes)
    print(json.dumps(res, indent=2))
    h = res["holdout"]
    if h["skill_vs_base_rate"] <= 0 or h["auc"] < 0.52:
        print("\nWARNING: the model shows no out-of-sample skill (AUC %.3f). Calibrated probabilities will sit "
              "near 50%%, so the price-aware gate will almost never allow RL trades." % h["auc"])


if __name__ == "__main__":
    main()
