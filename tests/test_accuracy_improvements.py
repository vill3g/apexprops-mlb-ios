"""
tests/test_accuracy_improvements.py
Unit tests for the 6 Prediction Accuracy & Calibration improvements:
1. Isotonic Regression Calibration on holdout split
2. Training sample size confidence-weighted blending
3. XGBoost walk-forward hyperparameter search
4. Optimal training window enforcement (4,000 bars bootstrap, 500 live trades)
5. Volatility regime feature (rolling 96-bar ATR percentile rank)
6. Scheduled live calibration drift monitoring in AutoExecutor
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
import tempfile
import shutil
import os

from backend.btc.ml_engine import (
    XGBoostModel,
    MLEngine,
    FEATURE_KEYS,
    OPTIMAL_TRAINING_WINDOW_BARS,
    MAX_LIVE_TRAINING_TRADES,
    build_feature_row,
)
from backend.btc.dual_ml_engine import DualMLEngine
from backend.btc.backtest import (
    analyze_calibration_overconfidence,
    run_model_hyperparam_search,
)
from backend.btc.auto_executor import AutoExecutor


class TestAccuracyImprovements(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Task 1: Calibration (Isotonic Regression)
    # -------------------------------------------------------------------------
    def test_calibration_fit_and_predict_clipped(self):
        """Verify Isotonic Regression calibrates raw probabilities and clips to [0, 1]."""
        model = XGBoostModel()
        X_holdout = np.array([
            [0.1, 0.2], [0.2, 0.3], [0.3, 0.4], [0.4, 0.5], [0.5, 0.6],
            [0.6, 0.7], [0.7, 0.8], [0.8, 0.9], [0.85, 0.9], [0.9, 0.95],
            [0.15, 0.25], [0.25, 0.35], [0.35, 0.45], [0.45, 0.55], [0.55, 0.65],
            [0.65, 0.75], [0.75, 0.85], [0.82, 0.88], [0.88, 0.92], [0.95, 0.98],
        ])
        y_holdout = np.array([0, 0, 0, 0, 1, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1])

        model.pipeline = MagicMock()
        mock_raw_probs = np.linspace(0.1, 0.9, len(y_holdout))
        model.pipeline.predict_proba.return_value = np.column_stack([1.0 - mock_raw_probs, mock_raw_probs])

        model.fit_calibration(X_holdout, y_holdout)
        self.assertIsNotNone(model.calibrator)

        test_X = np.array([[0.2, 0.3], [0.8, 0.9]])
        model.pipeline.predict_proba.return_value = np.array([[0.8, 0.2], [0.15, 0.85]])
        cal_probs = model.predict_proba_calibrated(test_X)

        self.assertEqual(len(cal_probs), 2)
        # predict_proba_calibrated returns 1D array of positive class probabilities
        self.assertTrue(all(0.0 <= p <= 1.0 for p in cal_probs))
        self.assertGreaterEqual(cal_probs[1], cal_probs[0])

    def test_calibration_unfitted_fallback(self):
        """When calibrator is None, predict_proba_calibrated falls back to raw pipeline output."""
        model = XGBoostModel()
        model.predict_proba = MagicMock(return_value=np.array([0.7]))
        res = model.predict_proba_calibrated(np.array([[1.0, 2.0]]))
        self.assertAlmostEqual(res[0], 0.7)

    # -------------------------------------------------------------------------
    # Task 2: Confidence-Weighted Blending
    # -------------------------------------------------------------------------
    def test_sample_size_confidence_weighting(self):
        """Verify linear scaling from 0 at <= 10 samples to full weight at 300 samples."""
        engine = MLEngine(data_dir=self.temp_dir, trading_style="SNIPER")
        base_w = 0.40

        engine.last_train_sample_count = 5
        self.assertEqual(engine.get_ml_confidence_weight(base_w, full_sample_threshold=300), 0.0)

        engine.last_train_sample_count = 10
        self.assertEqual(engine.get_ml_confidence_weight(base_w, full_sample_threshold=300), 0.0)

        engine.last_train_sample_count = 155
        mid_weight = engine.get_ml_confidence_weight(base_w, full_sample_threshold=300)
        self.assertAlmostEqual(mid_weight, 0.20, places=3)

        engine.last_train_sample_count = 300
        self.assertEqual(engine.get_ml_confidence_weight(base_w, full_sample_threshold=300), 0.40)

        engine.last_train_sample_count = 1500
        self.assertEqual(engine.get_ml_confidence_weight(base_w, full_sample_threshold=300), 0.40)

    def test_dual_ml_engine_weight_forwarding(self):
        """Verify DualMLEngine forwards sample count and confidence weight to active sub-engine."""
        dual = DualMLEngine(data_dir=self.temp_dir, trading_style="SNIPER")
        dual.day_engine.is_trained = True
        dual.night_engine.is_trained = True
        dual.day_engine.last_train_sample_count = 300
        dual.night_engine.last_train_sample_count = 10

        with patch.object(dual, "_is_night_time", return_value=False):
            self.assertEqual(dual.last_train_sample_count, 300)
            self.assertEqual(dual.get_ml_confidence_weight(0.40), 0.40)

        with patch.object(dual, "_is_night_time", return_value=True):
            self.assertEqual(dual.last_train_sample_count, 10)
            self.assertEqual(dual.get_ml_confidence_weight(0.40), 0.0)

    # -------------------------------------------------------------------------
    # Task 4: Optimal Training Window Constraints
    # -------------------------------------------------------------------------
    def test_optimal_window_constants_and_bootstrap_slice(self):
        """Verify 4,000 bars for bootstrap and 4,000 trades for live training."""
        self.assertEqual(OPTIMAL_TRAINING_WINDOW_BARS, 4000)
        self.assertEqual(MAX_LIVE_TRAINING_TRADES, 4000)

        engine = MLEngine(data_dir=self.temp_dir, trading_style="SNIPER")
        engine.model = MagicMock()

        dates = pd.date_range("2026-01-01", periods=5000, freq="15min")
        df_large = pd.DataFrame({
            "datetime": dates,
            "open": 60000.0 + np.arange(5000),
            "high": 60050.0 + np.arange(5000),
            "low": 59950.0 + np.arange(5000),
            "close": 60020.0 + np.arange(5000),
            "volume": 100.0,
            "rsi": 50.0,
            "bb_upper": 60500.0,
            "bb_lower": 59500.0,
            "ema_9": 60000.0,
            "ema_21": 60000.0,
            "ema_50": 60000.0,
            "atr": 50.0,
            "cvd": 0.0,
        })

        engine.self_train_on_historical_market(df_large)
        self.assertLessEqual(engine.last_train_sample_count, 4000)

    # -------------------------------------------------------------------------
    # Task 5: Volatility Regime Feature
    # -------------------------------------------------------------------------
    def test_volatility_regime_feature_calculation(self):
        """Verify vol_regime_percentile is in FEATURE_KEYS and computes rolling ATR rank."""
        self.assertIn("vol_regime_percentile", FEATURE_KEYS)

        n = 120
        atrs = np.linspace(10.0, 100.0, n)
        df = pd.DataFrame({
            "datetime": pd.date_range("2026-01-01", periods=n, freq="15min"),
            "open": np.full(n, 60000.0),
            "high": np.full(n, 60100.0),
            "low": np.full(n, 59900.0),
            "close": np.full(n, 60000.0),
            "volume": np.full(n, 10.0),
            "rsi": np.full(n, 50.0),
            "bb_upper": np.full(n, 60500.0),
            "bb_lower": np.full(n, 59500.0),
            "ema_9": np.full(n, 60000.0),
            "ema_21": np.full(n, 60000.0),
            "ema_50": np.full(n, 60000.0),
            "atr": atrs,
            "cvd": np.zeros(n),
        })

        row = build_feature_row(df, n - 1)
        self.assertIn("vol_regime_percentile", row)
        self.assertAlmostEqual(row["vol_regime_percentile"], 1.0, places=2)

    # -------------------------------------------------------------------------
    # Task 3: Hyperparameter Search
    # -------------------------------------------------------------------------
    def test_run_model_hyperparam_search(self):
        """Verify run_model_hyperparam_search evaluates candidate params and returns metrics."""
        n = 120
        df = pd.DataFrame({
            "datetime": pd.date_range("2026-01-01", periods=n, freq="15min"),
            "open": 60000.0 + np.sin(np.linspace(0, 10, n)) * 200,
            "high": 60100.0 + np.sin(np.linspace(0, 10, n)) * 200,
            "low": 59900.0 + np.sin(np.linspace(0, 10, n)) * 200,
            "close": 60050.0 + np.sin(np.linspace(0, 10, n)) * 200,
            "volume": np.full(n, 10.0),
            "rsi": 50.0 + np.sin(np.linspace(0, 10, n)) * 20,
            "bb_upper": np.full(n, 60500.0),
            "bb_lower": np.full(n, 59500.0),
            "ema_9": np.full(n, 60000.0),
            "ema_21": np.full(n, 60000.0),
            "ema_50": np.full(n, 60000.0),
            "atr": np.full(n, 50.0),
            "cvd": np.zeros(n),
        })

        candidates = [
            {"n_estimators": 5, "max_depth": 2, "learning_rate": 0.1},
        ]

        results = run_model_hyperparam_search(
            df_ind=df,
            window_size=30,
            candidate_params=candidates,
            step=10,
            retrain_every=20
        )

        expected_key = "n5_d2_lr0.1"
        self.assertIn(expected_key, results)
        res = results[expected_key]
        self.assertIn("brier_score", res)
        self.assertIn("log_loss", res)
        self.assertIn("accuracy", res)
        self.assertIn("calibration_table", res)

    # -------------------------------------------------------------------------
    # Task 6: Scheduled Calibration & Drift Monitoring
    # -------------------------------------------------------------------------
    def test_drift_detection_on_overconfident_predictions(self):
        """Verify analyze_calibration_overconfidence triggers on systematic overconfidence."""
        cal_table = [
            {"bucket": "50-60%", "count": 15, "mean_predicted_prob": 0.55, "realized_win_rate": 0.40, "diff": 0.15},
            {"bucket": "60-70%", "count": 20, "mean_predicted_prob": 0.65, "realized_win_rate": 0.50, "diff": 0.15},
            {"bucket": "70-80%", "count": 18, "mean_predicted_prob": 0.75, "realized_win_rate": 0.55, "diff": 0.20},
            {"bucket": "80-90%", "count": 5, "mean_predicted_prob": 0.85, "realized_win_rate": 0.80, "diff": 0.05},
        ]

        is_drift, msg = analyze_calibration_overconfidence(cal_table, min_bucket_count=10)
        self.assertTrue(is_drift)
        self.assertIn("OVERCONFIDENCE", msg)

    def test_auto_executor_check_live_calibration_drift(self):
        """Verify AutoExecutor.check_live_calibration_drift handles insufficient data and triggers retrain on drift."""
        executor = AutoExecutor()

        with patch.object(executor, "get_trades_history", return_value=[]):
            res = executor.check_live_calibration_drift(min_samples=40)
            self.assertEqual(res["status"], "insufficient_data")
            self.assertFalse(res["drift_detected"])

        # Create 60 synthetic overconfident settled trades spread across 3 buckets (55%, 65%, 75%)
        mock_trades = []
        for i in range(60):
            if i < 20:
                prob = 0.55
            elif i < 40:
                prob = 0.65
            else:
                prob = 0.75

            # Only 20% win rate across all buckets -> huge overconfidence (>15% diff)
            result = "WIN" if (i % 5 == 0) else "LOSS"
            mock_trades.append({
                "id": f"trade_{i}",
                "status": "SETTLED",
                "result": result,
                "predicted_probability": prob,
                "probability_percent": int(prob * 100),
            })

        with patch.object(executor, "get_trades_history", return_value=mock_trades):
            with patch("threading.Thread") as mock_thread:
                res = executor.check_live_calibration_drift(min_samples=40, window=60)
                self.assertEqual(res["status"], "ok")
                self.assertEqual(res["sample_count"], 60)
                self.assertTrue(res["drift_detected"])
                mock_thread.assert_called()

    def test_auto_executor_toggle_and_status_link(self):
        """Verify AutoExecutor set_enabled toggles and reflects boolean state in get_status."""
        executor = AutoExecutor()
        with patch.object(executor, "_save_config"):
            res_on = executor.set_enabled(True)
            self.assertTrue(executor.enabled)
            self.assertTrue(res_on.get("enabled"))

            res_off = executor.set_enabled(False)
            self.assertFalse(executor.enabled)
            self.assertFalse(res_off.get("enabled"))

    def test_static_html_beacon_and_trader_text(self):
        """Verify static/index.html has Kalshi AI Trader text and beacon elements starting unlit."""
        html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('id="kalshiAiTraderText"', html)
        self.assertIn("Kalshi AI Trader", html)
        self.assertIn('id="kalshiBeaconPing"', html)
        self.assertIn('id="kalshiBeaconDot"', html)
        self.assertIn("updateKalshiBeacon", html)
        # Verify initial state is unlit / hidden ping
        self.assertIn('id="kalshiBeaconPing" class="hidden', html)
        self.assertIn('id="kalshiBeaconDot" class="relative inline-flex rounded-full h-2 sm:h-2.5 w-2 sm:w-2.5 bg-slate-600 opacity-40"', html)

    def test_down_bias_fix_settlement_and_defaults(self):
        """
        Verify that Kalshi $1.00 settlement values for YES are labeled 1 (UP)
        instead of falsely comparing 1.00 < 77000.00 -> 0 (DOWN), and that missing
        features safely default to neutral baselines instead of 0.0.
        """
        import json
        from backend.btc.ml_engine import NEUTRAL_FEATURE_DEFAULTS, build_live_ml_features

        engine = MLEngine(data_dir=self.temp_dir, trading_style="SNIPER")
        mock_trades = [
            {
                "id": "t1",
                "status": "SETTLED",
                "result": "WIN",
                "side": "YES",
                "direction": "ABOVE",
                "strike": 77241.45,
                "settle_price": 1.0,  # $1.00 binary payout from Kalshi
                "market_snapshot": {"raw_features": {"rsi": 62.0, "delta_to_target": 0.05}},
            },
            {
                "id": "t2",
                "status": "SETTLED",
                "result": "WIN",
                "side": "NO",
                "direction": "BELOW",
                "strike": 77241.45,
                "settle_price": 0.0,  # $0.00 binary payout from Kalshi
                "market_snapshot": {"raw_features": {"rsi": 38.0, "delta_to_target": -0.05}},
            },
            {
                "id": "t3",
                "status": "SETTLED",
                "result": "WIN",
                "side": "YES",
                "direction": "ABOVE",
                "official_result": "YES",
                "strike": 77500.0,
                "market_snapshot": {"raw_features": {"rsi": 65.0}},
            },
        ]
        # Pad to 12 trades to meet >= 10 minimum
        for idx in range(4, 15):
            mock_trades.append({
                "id": f"t{idx}",
                "status": "SETTLED",
                "result": "WIN" if idx % 2 == 0 else "LOSS",
                "side": "YES",
                "direction": "ABOVE",
                "strike": 77000.0 + idx,
                "settle_price": 1.0 if idx % 2 == 0 else 0.0,
                "market_snapshot": {"raw_features": {"rsi": 55.0}},
            })

        history_file = os.path.join(self.temp_dir, "trades_history.json")
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(mock_trades, f)

        X, y, w = engine._extract_features_and_labels(time_filter="all")
        self.assertIsNotNone(X)
        self.assertIsNotNone(y)

        # First trade was YES winning ($1.00 payout) -> MUST be labeled 1 (UP), NOT 0
        self.assertEqual(y[0], 1, "Winning YES trade with settle_price 1.0 must be labeled 1 (UP)")
        # Second trade was NO winning ($0.00 payout) -> MUST be labeled 0 (DOWN)
        self.assertEqual(y[1], 0, "Winning NO trade with settle_price 0.0 must be labeled 0 (DOWN)")
        # Third trade was official_result YES -> MUST be labeled 1 (UP)
        self.assertEqual(y[2], 1, "Official result YES must be labeled 1 (UP)")

        # Verify missing feature defaulting:
        # Trade 1 only had rsi and delta_to_target in raw_features.
        # Check that minutes_remaining and kalshi_yes_prob defaulted to neutral baselines
        m_rem_idx = engine.feature_keys.index("minutes_remaining")
        k_prob_idx = engine.feature_keys.index("kalshi_yes_prob")
        self.assertEqual(X[0, m_rem_idx], NEUTRAL_FEATURE_DEFAULTS["minutes_remaining"])
        self.assertEqual(X[0, k_prob_idx], NEUTRAL_FEATURE_DEFAULTS["kalshi_yes_prob"])

    def test_build_live_ml_features_time_and_24h_window(self):
        """Verify build_live_ml_features includes all expected FEATURE_KEYS with 24h rolling window."""
        from backend.btc.ml_engine import build_live_ml_features

        # Create mock DataFrame of 120 candles
        candles = []
        for i in range(120):
            candles.append({
                "time": 1789300000 + i * 900,
                "open": 77000.0 + i,
                "high": 77050.0 + i,
                "low": 76950.0 + i,
                "close": 77020.0 + i,
                "volume": 10.0,
                "rsi": 52.0,
                "ema_9": 77010.0,
                "ema_21": 77000.0,
                "ema_50": 76980.0,
                "bb_upper": 77100.0,
                "bb_lower": 76900.0,
                "atr": 100.0,
                "cvd": 50.0,
            })
        df_ind = pd.DataFrame(candles)
        feats = build_live_ml_features(df_ind)

        for k in FEATURE_KEYS:
            self.assertIn(k, feats, f"Feature key {k} must be in build_live_ml_features output")

        self.assertIn("is_weekend", feats)
        self.assertIn("hour_of_day", feats)
        self.assertIn("volume_15m_ratio", feats)
        self.assertGreaterEqual(feats["range_24h_pos"], 0.0)
        self.assertLessEqual(feats["range_24h_pos"], 1.0)


if __name__ == "__main__":
    unittest.main()
