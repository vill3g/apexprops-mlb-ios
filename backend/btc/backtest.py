"""
backend/btc/backtest.py
Walk-Forward Backtest & Probability Calibration Harness for Kalshi BTC 15M Trader.

Evaluates XGBoostModel across rolling historical windows of 15m candles with strict
out-of-sample forward evaluation.
Metrics produced:
- Brier score: mean((p - y) ** 2)
- Log loss: mean(-(y*log(p) + (1-y)*log(1-p)))
- Accuracy at 0.5 threshold
- 10-bucket probability calibration table
"""

import os
import sys
import json
import math
import argparse
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger("backtest")

# Ensure repository root is on path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.btc.ml_engine import XGBoostModel, build_feature_row, FEATURE_KEYS
from backend.btc.indicators import add_all_indicators
from backend.btc.data_fetcher import fetch_15m_candles_history


def run_walkforward_backtest(
    df_ind: pd.DataFrame,
    window_sizes: list[int] | None = None,
    step: int = 1,
    retrain_every: int = 48,
) -> dict:
    """
    For each candidate training window size, walks forward through df_ind:
    trains an XGBoostModel on the trailing `window` bars (using the SAME feature
    extraction as MLEngine.self_train_on_historical_market via build_feature_row),
    predicts P(close >= open) for out-of-sample bars, records (prediction, actual_label),
    and evaluates metrics. No lookahead: at prediction time for bar i, the model
    only sees bars < i.

    To keep runtime reasonable, retrains every `retrain_every` bars (e.g. 48 bars = 12 hours)
    using the most recent `window` bars, and predicts the subsequent bars up to the next retrain.
    """
    if window_sizes is None:
        window_sizes = [250, 500, 1000, 2000, 4000]
    n_rows = len(df_ind)
    results = {}

    # Pre-build feature vectors and labels for all valid rows (index >= 50 for indicator warmup)
    warmup = 50
    if n_rows <= warmup + 10:
        raise ValueError(f"DataFrame has {n_rows} rows, need at least {warmup + 10} for backtest.")

    logger.info(f"Extracting features for {n_rows - warmup} bars...")
    all_features = []
    all_labels = []
    indices = []

    for i in range(warmup, n_rows):
        feat_dict = build_feature_row(df_ind, i)
        vec = []
        for k in FEATURE_KEYS:
            val = feat_dict.get(k, 0.0)
            try:
                val = float(val) if val is not None else 0.0
                if not math.isfinite(val):
                    val = 0.0
            except (TypeError, ValueError):
                val = 0.0
            vec.append(val)

        c = df_ind.iloc[i]
        p = df_ind.iloc[i - 1]
        target_price = float(c.get("open", p["close"]))
        actual_close = float(c["close"])
        label = 1 if actual_close >= target_price else 0

        all_features.append(vec)
        all_labels.append(label)
        indices.append(i)

    X_all = np.array(all_features, dtype=float)
    y_all = np.array(all_labels, dtype=int)
    total_valid = len(y_all)

    for w in window_sizes:
        if total_valid <= w + 10:
            logger.warning(f"Window size {w} exceeds available data ({total_valid} samples after warmup). Skipping.")
            continue

        preds = []
        actuals = []

        # Walk-forward loop
        # Start out-of-sample evaluation immediately after the initial window `w`
        curr_train_idx = w

        while curr_train_idx < total_valid:
            # Train model on trailing `w` bars
            train_start = curr_train_idx - w
            X_train = X_all[train_start:curr_train_idx]
            y_train = y_all[train_start:curr_train_idx]

            model = XGBoostModel()
            # Split trailing 20% of X_train for calibration holdout (Task 1)
            n_tr = len(X_train)
            split = max(0, n_tr - max(20, int(n_tr * 0.2)))
            X_tr_fit, y_tr_fit = X_train[:split], y_train[:split]
            X_cal, y_cal = X_train[split:], y_train[split:]
            model.fit(X_tr_fit, y_tr_fit)
            if len(X_cal) >= 20:
                model.fit_calibration(X_cal, y_cal)

            # Predict next chunk up to retrain_every
            chunk_end = min(total_valid, curr_train_idx + retrain_every)
            X_test_chunk = X_all[curr_train_idx:chunk_end]
            y_test_chunk = y_all[curr_train_idx:chunk_end]

            chunk_probs = model.predict_proba_calibrated(X_test_chunk)
            preds.extend(chunk_probs.tolist())
            actuals.extend(y_test_chunk.tolist())

            curr_train_idx = chunk_end

        if not preds:
            continue

        p_arr = np.array(preds)
        y_arr = np.array(actuals)

        # 1. Brier Score: mean((p - y) ** 2)
        brier_score = float(np.mean((p_arr - y_arr) ** 2))

        # 2. Log Loss: clip to [1e-6, 1 - 1e-6]
        p_clipped = np.clip(p_arr, 1e-6, 1.0 - 1e-6)
        log_loss_val = float(np.mean(-(y_arr * np.log(p_clipped) + (1.0 - y_arr) * np.log(1.0 - p_clipped))))

        # 3. Accuracy at 0.5 threshold
        pred_labels = (p_arr >= 0.5).astype(int)
        accuracy = float(np.mean(pred_labels == y_arr))

        # 4. Calibration table: 10 buckets [0-10%, 10-20%, ..., 90-100%]
        calibration_table = []
        for b in range(10):
            low = b * 0.10
            high = (b + 1) * 0.10
            if b == 9:
                mask = (p_arr >= low) & (p_arr <= high)
            else:
                mask = (p_arr >= low) & (p_arr < high)

            count = int(np.sum(mask))
            if count > 0:
                mean_p = float(np.mean(p_arr[mask]))
                realized_wr = float(np.mean(y_arr[mask]))
            else:
                mean_p = float((low + high) / 2.0)
                realized_wr = 0.0

            calibration_table.append({
                "bucket": f"{int(low * 100)}-{int(high * 100)}%",
                "count": count,
                "mean_predicted_prob": round(mean_p, 4),
                "realized_win_rate": round(realized_wr, 4),
                "diff": round(mean_p - realized_wr, 4),
            })

        results[str(w)] = {
            "window_size": w,
            "test_samples": len(actuals),
            "brier_score": round(brier_score, 5),
            "log_loss": round(log_loss_val, 5),
            "accuracy": round(accuracy, 4),
            "calibration_table": calibration_table,
        }

    return results


def analyze_calibration_overconfidence(cal_table: list[dict], min_bucket_count: int = 10) -> tuple[bool, str]:
    """
    Checks if calibration table shows systematic overconfidence:
    any bucket where mean_predicted_prob - realized_win_rate exceeds 8 percentage points
    in the same direction across 3 or more buckets.
    """
    overconfident_buckets = 0
    underconfident_buckets = 0

    for row in cal_table:
        if row.get("count", 0) < min_bucket_count:
            continue
        diff = row.get("diff", 0.0)
        if diff > 0.08:
            overconfident_buckets += 1
        elif diff < -0.08:
            underconfident_buckets += 1

    if overconfident_buckets >= 3:
        return True, f"[WARN] Systematic OVERCONFIDENCE detected across {overconfident_buckets} buckets (predicted probabilities exceed realized win rates by >8%)."
    elif underconfident_buckets >= 3:
        return True, f"[WARN] Systematic UNDERCONFIDENCE detected across {underconfident_buckets} buckets (realized win rates exceed predictions by >8%)."
    return False, "Calibration profile appears well-balanced across populated buckets."


def run_model_hyperparam_search(
    df_ind: pd.DataFrame,
    window_size: int = 4000,
    candidate_params: list[dict] | None = None,
    step: int = 1,
    retrain_every: int = 48,
) -> dict:
    """
    Evaluates different XGBoost hyperparameter candidates on df_ind using the walk-forward
    harness with calibration, tracking Brier score, log loss, accuracy, and calibration tables.
    """
    if candidate_params is None:
        candidate_params = [
            {"n_estimators": 100, "max_depth": 3, "learning_rate": 0.05},
            {"n_estimators": 150, "max_depth": 3, "learning_rate": 0.03},
            {"n_estimators": 100, "max_depth": 4, "learning_rate": 0.05},
            {"n_estimators": 200, "max_depth": 2, "learning_rate": 0.05},
        ]

    n_rows = len(df_ind)
    warmup = 50
    if n_rows <= warmup + 10:
        raise ValueError(f"DataFrame has {n_rows} rows, need at least {warmup + 10} for hyperparameter search.")

    logger.info(f"Extracting features for {n_rows - warmup} bars...")
    all_features = []
    all_labels = []

    for i in range(warmup, n_rows):
        feat_dict = build_feature_row(df_ind, i)
        vec = []
        for k in FEATURE_KEYS:
            val = feat_dict.get(k, 0.0)
            try:
                val = float(val) if val is not None else 0.0
                if not math.isfinite(val):
                    val = 0.0
            except (TypeError, ValueError):
                val = 0.0
            vec.append(val)

        c = df_ind.iloc[i]
        p = df_ind.iloc[i - 1]
        target_price = float(c.get("open", p["close"]))
        actual_close = float(c["close"])
        label = 1 if actual_close >= target_price else 0

        all_features.append(vec)
        all_labels.append(label)

    X_all = np.array(all_features, dtype=float)
    y_all = np.array(all_labels, dtype=int)
    total_valid = len(y_all)
    w = window_size

    if total_valid <= w + 10:
        logger.warning(f"Window size {w} exceeds available data ({total_valid} samples). Using {max(100, total_valid // 2)}.")
        w = max(100, total_valid // 2)

    results = {}

    for cand in candidate_params:
        cand_key = f"n{cand.get('n_estimators', 100)}_d{cand.get('max_depth', 3)}_lr{cand.get('learning_rate', 0.05)}"
        logger.info(f"[HyperparamSearch] Evaluating candidate: {cand} (key={cand_key})...")
        curr_train_idx = w
        preds = []
        actuals = []

        while curr_train_idx < total_valid:
            train_start = curr_train_idx - w
            X_train = X_all[train_start:curr_train_idx]
            y_train = y_all[train_start:curr_train_idx]

            model = XGBoostModel()
            # Override hyperparams on pipeline's xgbclassifier
            model.model.named_steps["xgbclassifier"].set_params(**cand)

            n_tr = len(X_train)
            split = max(0, n_tr - max(20, int(n_tr * 0.2)))
            X_tr_fit, y_tr_fit = X_train[:split], y_train[:split]
            X_cal, y_cal = X_train[split:], y_train[split:]
            model.fit(X_tr_fit, y_tr_fit)
            if len(X_cal) >= 20:
                model.fit_calibration(X_cal, y_cal)

            chunk_end = min(total_valid, curr_train_idx + retrain_every)
            X_test_chunk = X_all[curr_train_idx:chunk_end]
            y_test_chunk = y_all[curr_train_idx:chunk_end]

            chunk_probs = model.predict_proba_calibrated(X_test_chunk)
            preds.extend(chunk_probs.tolist())
            actuals.extend(y_test_chunk.tolist())

            curr_train_idx = chunk_end

        if not preds:
            continue

        p_arr = np.array(preds)
        y_arr = np.array(actuals)
        brier_score = float(np.mean((p_arr - y_arr) ** 2))
        p_clipped = np.clip(p_arr, 1e-6, 1.0 - 1e-6)
        log_loss_val = float(np.mean(-(y_arr * np.log(p_clipped) + (1.0 - y_arr) * np.log(1.0 - p_clipped))))
        pred_labels = (p_arr >= 0.5).astype(int)
        accuracy = float(np.mean(pred_labels == y_arr))

        calibration_table = []
        for b in range(10):
            low = b * 0.10
            high = (b + 1) * 0.10
            mask = (p_arr >= low) & (p_arr <= high) if b == 9 else (p_arr >= low) & (p_arr < high)
            count = int(np.sum(mask))
            if count > 0:
                mean_p = float(np.mean(p_arr[mask]))
                realized_wr = float(np.mean(y_arr[mask]))
            else:
                mean_p = float((low + high) / 2.0)
                realized_wr = 0.0
            calibration_table.append({
                "bucket": f"{int(low * 100)}-{int(high * 100)}%",
                "count": count,
                "mean_predicted_prob": round(mean_p, 4),
                "realized_win_rate": round(realized_wr, 4),
                "diff": round(mean_p - realized_wr, 4),
            })

        results[cand_key] = {
            "params": cand,
            "window_size": w,
            "test_samples": len(actuals),
            "brier_score": round(brier_score, 5),
            "log_loss": round(log_loss_val, 5),
            "accuracy": round(accuracy, 4),
            "calibration_table": calibration_table,
        }

    return results


def main():
    parser = argparse.ArgumentParser(description="BTC 15M Walk-Forward Backtest & Calibration")
    parser.add_argument("--days", type=int, default=90, help="Days of 15m candle history to evaluate")
    parser.add_argument("--windows", type=str, default="250,500,1000,2000,4000", help="Comma-separated window sizes")
    args = parser.parse_args()

    window_sizes = [int(w.strip()) for w in args.windows.split(",") if w.strip()]

    print(f"\n=======================================================")
    print(f" BTC 15M WALK-FORWARD BACKTEST & CALIBRATION HARNESS")
    print(f" Historical Horizon: {args.days} Days | Windows: {window_sizes}")
    print(f"=======================================================\n")

    print(f"[*] Fetching deep historical 15m candles from Binance.US (or cache)...")
    df_raw = fetch_15m_candles_history(days=args.days)
    print(f"[OK] Retrieved {len(df_raw)} candles covering {args.days} days.")

    print(f"[*] Computing multi-timeframe indicators (EMAs, RSI, VWAP, ATR, CVD)...")
    df_ind = add_all_indicators(df_raw)
    print(f"[OK] Indicators computed successfully.")

    print(f"[*] Executing walk-forward evaluation loop...")
    results = run_walkforward_backtest(df_ind, window_sizes=window_sizes, step=1, retrain_every=48)

    if not results:
        print("[!] No window sizes could be evaluated with the available data.")
        return

    # Print summary table
    print("\n" + "=" * 68)
    print(f"{'Window Size':<14} | {'Test Samples':<14} | {'Brier Score':<12} | {'Log Loss':<10} | {'Accuracy':<8}")
    print("=" * 68)

    best_window = None
    min_log_loss = float("inf")

    for w_str, metrics in results.items():
        w = metrics["window_size"]
        samples = metrics["test_samples"]
        brier = metrics["brier_score"]
        loss = metrics["log_loss"]
        acc = metrics["accuracy"]
        print(f"{w:<14} | {samples:<14} | {brier:<12.5f} | {loss:<10.5f} | {acc * 100:<7.1f}%")

        if loss < min_log_loss:
            min_log_loss = loss
            best_window = w_str

    print("=" * 68)

    best_res = results[best_window]
    print(f"\n[BEST] Recommended Window Size: {best_res['window_size']} bars (Lowest Log Loss: {best_res['log_loss']:.5f})")

    # Calibration table inspection for best window
    cal_table = best_res["calibration_table"]
    has_warning, warn_msg = analyze_calibration_overconfidence(cal_table)
    if has_warning:
        print(f"\n{warn_msg}")
    else:
        print(f"\n[OK] {warn_msg}")

    print("\nCalibration Table (Best Window):")
    print(f"{'Bucket':<12} | {'Count':<8} | {'Mean Pred P':<12} | {'Realized WR':<12} | {'Diff':<8}")
    print("-" * 60)
    for b in cal_table:
        print(f"{b['bucket']:<12} | {b['count']:<8} | {b['mean_predicted_prob'] * 100:<11.1f}% | {b['realized_win_rate'] * 100:<11.1f}% | {b['diff'] * 100:+5.1f}%")
    print("-" * 60)

    # Save report
    data_dir = os.path.join(REPO_ROOT, "backend", "data")
    os.makedirs(data_dir, exist_ok=True)
    report_path = os.path.join(data_dir, "backtest_report.json")

    report_payload = {
        "timestamp": pd.Timestamp.utcnow().isoformat(),
        "days_evaluated": args.days,
        "total_candles": len(df_raw),
        "recommended_window": int(best_window),
        "results": results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    print(f"\n[OK] Full backtest and calibration report written to: {report_path}\n")


if __name__ == "__main__":
    main()
