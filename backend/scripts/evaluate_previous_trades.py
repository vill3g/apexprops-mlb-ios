"""
backend/scripts/evaluate_previous_trades.py
Backtest all historical trades against the currently retrained, Platt-calibrated ML model.
"""
import os
import sys
import json
import math
import numpy as np
from collections import defaultdict

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.btc.trade_db import get_trade_db
from backend.btc.ml_engine import get_ml_engine, FEATURE_KEYS, NEUTRAL_FEATURE_DEFAULTS


def evaluate():
    db = get_trade_db()
    trades = db.get_trades("BTC")
    print(f"Loaded {len(trades)} total trades from SQLite trades.db")

    engine = get_ml_engine(trading_style="MOMENTUM_SURFER", asset="BTC")
    print(f"Current Model Engine loaded: {engine.trading_style}")

    evaluated = []
    skipped_no_outcome = 0
    skipped_no_features = 0

    for t in trades:
        # Determine ground truth outcome (1 = YES expired ITM, 0 = NO expired ITM)
        official_result = str(t.get("official_result", "")).upper().strip()
        strike = t.get("strike")
        settle_price = t.get("settle_price")
        side = str(t.get("side", "")).upper().strip()
        res = str(t.get("result", "")).upper().strip()
        direction = str(t.get("direction", "")).upper().strip()

        outcome = None
        if official_result in ["YES", "NO"]:
            outcome = 1 if official_result == "YES" else 0
        elif strike is not None and settle_price is not None:
            try:
                s_val = float(strike)
                sp_val = float(settle_price)
                if sp_val in (1.0, 100.0) or sp_val == 1:
                    outcome = 1
                elif sp_val in (0.0, 0) and s_val > 0:
                    outcome = 0
                elif s_val > 1000 and sp_val > 1000:
                    outcome = 1 if sp_val >= s_val else 0
            except (ValueError, TypeError):
                outcome = None

        if outcome is None:
            is_win = ("WIN" in res) or ("WON" in res)
            is_loss = ("LOSS" in res) or ("LOST" in res)
            if is_win or is_loss:
                if direction == "ABOVE" or side == "YES":
                    outcome = 1 if is_win else 0
                elif direction == "BELOW" or side == "NO":
                    outcome = 0 if is_win else 1

        if outcome is None:
            skipped_no_outcome += 1
            continue

        raw = (t.get("market_snapshot") or {}).get("raw_features")
        if not raw:
            skipped_no_features += 1
            continue

        # Prepare feature vector for the current model
        feature_dict = dict(raw)
        # Ensure new vol_time_z_score is present
        if "vol_time_z_score" not in feature_dict:
            p_close = float(raw.get("delta_to_target", 0.0))
            atr = float(raw.get("atr", 100.0))
            rem = float(raw.get("minutes_remaining", 14.5))
            time_factor = math.sqrt(max(0.05, rem / 15.0))
            feature_dict["vol_time_z_score"] = float(p_close / max(1.0, atr * time_factor))

        prob, reasoning = engine.predict_with_reasoning(feature_dict)
        prob = float(prob)

        # Historical trade stats
        hist_side = side if side in ["YES", "NO"] else ("YES" if direction == "ABOVE" else "NO")
        hist_won = ("WIN" in res) or ("WON" in res)
        hist_pnl = float(t.get("pnl", 0.0) or 0.0)
        entry_price = float(t.get("entry_price", 0.50) or 0.50)
        count = float(t.get("count", 1.0) or 1.0)

        # Current model trade decision
        if prob > 0.50:
            model_side = "YES"
            model_conf = prob
        elif prob < 0.50:
            model_side = "NO"
            model_conf = 1.0 - prob
        else:
            model_side = "PASS"
            model_conf = 0.50

        model_won = (model_side == "YES" and outcome == 1) or (model_side == "NO" and outcome == 0)

        # Simulated PnL under current model decision
        if model_side == "YES":
            pnl_sim = round(((1.0 - entry_price) * count) if outcome == 1 else (-entry_price * count), 2)
        elif model_side == "NO":
            no_entry = 1.0 - entry_price if entry_price < 1.0 else 0.50
            pnl_sim = round(((1.0 - no_entry) * count) if outcome == 0 else (-no_entry * count), 2)
        else:
            pnl_sim = 0.0

        evaluated.append({
            "id": t.get("id"),
            "timestamp": t.get("timestamp"),
            "outcome": outcome,
            "prob": prob,
            "model_side": model_side,
            "model_conf": model_conf,
            "model_won": model_won,
            "model_pnl": pnl_sim,
            "hist_side": hist_side,
            "hist_won": hist_won,
            "hist_pnl": hist_pnl,
            "count": count
        })

    print(f"Evaluated {len(evaluated)} trades with full features and verified outcomes.")
    print(f"Skipped without outcome: {skipped_no_outcome}, skipped without raw features: {skipped_no_features}")

    if not evaluated:
        return

    # 1. Overall Model Performance Metrics
    total_trades = len(evaluated)
    model_wins = sum(1 for e in evaluated if e["model_won"])
    model_win_rate = (model_wins / total_trades) * 100.0

    hist_wins = sum(1 for e in evaluated if e["hist_won"])
    hist_win_rate = (hist_wins / total_trades) * 100.0

    model_total_pnl = sum(e["model_pnl"] for e in evaluated)
    hist_total_pnl = sum(e["hist_pnl"] for e in evaluated)

    # 2. Calibration & Brier Score
    probs = np.array([e["prob"] for e in evaluated])
    actuals = np.array([e["outcome"] for e in evaluated])
    brier_score = float(np.mean((probs - actuals) ** 2))
    
    eps = 1e-6
    clipped_probs = np.clip(probs, eps, 1.0 - eps)
    log_loss = float(-np.mean(actuals * np.log(clipped_probs) + (1.0 - actuals) * np.log(1.0 - clipped_probs)))

    # 3. Bucket Calibration Analysis (10% bins)
    bins = [0.0, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 1.0]
    bucket_data = []
    for i in range(len(bins) - 1):
        low, high = bins[i], bins[i + 1]
        mask = (probs >= low) & (probs < high) if i < len(bins) - 2 else (probs >= low) & (probs <= high)
        n_in_bin = int(np.sum(mask))
        if n_in_bin > 0:
            avg_pred = float(np.mean(probs[mask]))
            act_rate = float(np.mean(actuals[mask]))
            cal_err = abs(avg_pred - act_rate)
            bucket_data.append({
                "range": f"{int(low*100)}-{int(high*100)}%",
                "count": n_in_bin,
                "predicted_prob": f"{avg_pred*100:.1f}%",
                "actual_rate": f"{act_rate*100:.1f}%",
                "calibration_gap": f"{cal_err*100:.1f}%"
            })

    # 4. High Conviction Filter Analysis (Confidence >= 60% vs < 60%)
    high_conf = [e for e in evaluated if e["model_conf"] >= 0.60]
    hc_wins = sum(1 for e in high_conf if e["model_won"])
    hc_wr = (hc_wins / len(high_conf) * 100.0) if high_conf else 0.0
    hc_pnl = sum(e["model_pnl"] for e in high_conf)

    low_conf = [e for e in evaluated if e["model_conf"] < 0.60]
    lc_wins = sum(1 for e in low_conf if e["model_won"])
    lc_wr = (lc_wins / len(low_conf) * 100.0) if low_conf else 0.0
    lc_pnl = sum(e["model_pnl"] for e in low_conf)

    # 5. Profit Factor
    gross_win = sum(e["model_pnl"] for e in evaluated if e["model_pnl"] > 0)
    gross_loss = abs(sum(e["model_pnl"] for e in evaluated if e["model_pnl"] < 0))
    profit_factor = round(gross_win / max(0.01, gross_loss), 2)

    results = {
        "total_evaluated_trades": total_trades,
        "model_wins": model_wins,
        "model_losses": total_trades - model_wins,
        "model_win_rate_pct": round(model_win_rate, 2),
        "hist_win_rate_pct": round(hist_win_rate, 2),
        "win_rate_delta": round(model_win_rate - hist_win_rate, 2),
        "model_total_pnl": round(model_total_pnl, 2),
        "hist_total_pnl": round(hist_total_pnl, 2),
        "pnl_delta": round(model_total_pnl - hist_total_pnl, 2),
        "profit_factor": profit_factor,
        "brier_score": round(brier_score, 4),
        "log_loss": round(log_loss, 4),
        "high_conviction": {
            "threshold": ">= 60%",
            "count": len(high_conf),
            "wins": hc_wins,
            "win_rate_pct": round(hc_wr, 2),
            "pnl": round(hc_pnl, 2)
        },
        "lower_conviction": {
            "threshold": "< 60%",
            "count": len(low_conf),
            "wins": lc_wins,
            "win_rate_pct": round(lc_wr, 2),
            "pnl": round(lc_pnl, 2)
        },
        "calibration_buckets": bucket_data
    }

    out_file = os.path.join(REPO_ROOT, "backend", "data", "previous_trades_backtest_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    print("BACKTEST OF PREVIOUS TRADES WITH CURRENT CALIBRATED MODEL")
    print("=" * 60)
    print(f"Total Evaluated: {total_trades} trades")
    print(f"Current Model Win Rate: {model_win_rate:.2f}%  (Historical: {hist_win_rate:.2f}%)")
    print(f"Win Rate Edge Delta: {model_win_rate - hist_win_rate:+.2f}%")
    print(f"Current Model PnL: ${model_total_pnl:+.2f}  (Historical: ${hist_total_pnl:+.2f})")
    print(f"PnL Delta: ${model_total_pnl - hist_total_pnl:+.2f}")
    print(f"Profit Factor: {profit_factor}")
    print(f"Brier Score: {brier_score:.4f} (Benchmark Coin-Flip: 0.2500)")
    print(f"Log Loss: {log_loss:.4f}")
    print("\n--- CONVICTION FILTER COMPARISON ---")
    print(f"High Conviction (>=60%): {len(high_conf)} trades | Win Rate: {hc_wr:.1f}% | PnL: ${hc_pnl:+.2f}")
    print(f"Chop/Low Conviction (<60%): {len(low_conf)} trades | Win Rate: {lc_wr:.1f}% | PnL: ${lc_pnl:+.2f}")
    print("\n--- 10-BUCKET PROBABILITY CALIBRATION ---")
    print(f"{'Bin':10} | {'Count':5} | {'Avg Predicted':14} | {'Actual Outcome':14} | {'Calibration Gap'}")
    for b in bucket_data:
        print(f"{b['range']:10} | {b['count']:5} | {b['predicted_prob']:14} | {b['actual_rate']:14} | {b['calibration_gap']}")
    print("=" * 60)


if __name__ == "__main__":
    evaluate()
