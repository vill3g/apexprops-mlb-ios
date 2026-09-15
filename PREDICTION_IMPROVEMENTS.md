# BTC 15-Minute Prediction Improvements

**Repository:** kalshi-ai-trader  
**Date:** September 13, 2026  
**Status:** Completed & Verified  

## 1. Summary of Changes

Four key enhancements were made to improve 15-minute prediction quality without touching safety guards:

1. **Task 3: Walk-Forward Backtesting Framework & Calibration Reporting (ackend/btc/backtest.py)**
   - Historical candle fetching (etch_15m_candles_history) with Binance.US pagination, rate limiting, and 12-hour disk caching.
   - Refactored uild_feature_row(df_ind, i) in ml_engine.py to share identical feature extraction across self-training and backtesting.
   - Walk-forward evaluation across training windows [250, 500, 1000, 2000, 4000] computing Brier scores, log loss, and 10-bucket calibration tables.
   - Saved report at ackend/data/backtest_report.json.

2. **Task 1: Calibrated Probability Blending (ackend/btc/analyzer.py)**
   - Added HEURISTIC_WEIGHT = 0.60 and ML_WEIGHT = 0.40.
   - In evaluate_next_15m_contract(), blended heuristic probability with ML engine inference.
   - Implemented conflict capping: when ML probability < 50% and divergence >= 15%, blended confidence is capped at 58.0% and Grade A+ is downgraded to Grade A.

3. **Task 5: Time-to-Expiry Decay Feature (minutes_remaining)**
   - Added minutes_remaining to FEATURE_KEYS in ml_engine.py.
   - Wired live wall-clock minutes remaining into inference inputs and trade snapshot metadata.
   - Synthetic bars default to 14.5 minutes.

4. **Task 6: Kalshi Market-Implied Features (kalshi_yes_prob, kalshi_book_imbalance)**
   - Added kalshi_yes_prob and kalshi_book_imbalance to FEATURE_KEYS (26 total features).
   - Wired live Kalshi mid-price probability and orderbook imbalance into model inference and ledger records with neutral defaults (50.0% / 0.0) for offline execution.

## 2. 60-Day Walk-Forward Results

- **Recommended Window Size:** 4,000 bars (Log Loss: 0.61899, Accuracy: 64.1%).
- Full report saved to ackend/data/backtest_report.json.
