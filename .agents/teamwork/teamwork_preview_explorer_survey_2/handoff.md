# Handoff Report: Explorer Survey 2 (ML Prediction Engine & Data Sources Explorer)

**Recipient**: `orchestrator_1` (Conversation ID: `69f1fc34-0f88-433d-8fc9-49626797374a`)  
**Working Directory**: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_2`  
**Date**: 2026-09-30  
**Status**: Task Complete (Hard Handoff)

---

## 1. Observation

### Exact File Paths, Line Numbers, and Code Entities
1. **Primary ML Ensemble (`backend/btc/ml_ensemble.py:80-273`)**:
   - `GodTierEnsemble`: Combines `XGBClassifier` (`n_estimators=150`, `max_depth=4`, `learning_rate=0.05`), `RandomForestClassifier` (`n_estimators=150`, `max_depth=5`), and `PyTorchLSTM` (1-layer LSTM for 25 sequence lag features + Dense tabular FC layer for 27 static features). Meta-learner is `LogisticRegression(C=0.5, random_state=42)` trained on 5-fold `StratifiedKFold` out-of-fold cross-validation predictions (`oof_xgb`, `oof_rf`, `oof_dnn`).
2. **Dual Day/Night Dispatch (`backend/btc/dual_ml_engine.py:10-99`)**:
   - `DualMLEngine`: Evaluates local Eastern Time via `0 <= ny_time.hour < 7`. Dispatches to `night_engine` during night hours ($[00:00, 07:00)$ ET) and `day_engine` during daytime ($[07:00, 24:00)$ ET). Caches separate `.pkl` files per asset, style, and time filter in `backend/data/model_cache/`.
3. **52-Dimensional Feature Schema & Normalization (`backend/btc/ml_engine.py:199-226, 286-320`)**:
   - `FEATURE_KEYS`: 27 base features (RSI, Bollinger Bands, EMAs, ATR, VWAP delta, CVD proxy, target delta, orderbook imbalance, funding rate, open interest, Fear & Greed, wick ratios, body-to-range, 24h position, volume ratio, minutes remaining, Kalshi implied probability, Kalshi book imbalance, ROC 15m/1h/4h, CVD divergence, CVD acceleration, volatility percentile, VSA absorption, SFP score, vol-time z-score) plus 25 sequence lag features (5 lags $\times$ 5 indicators: `bb_percent_b`, `rsi`, `volume_15m_ratio`, `roc_15m`, `cvd_divergence`).
   - `normalize_features()`: Normalizes prices relative to `ema_50` ($P / \text{ema\_50} - 1.0$), scales ATR and VWAP as percentage of `ema_50`, and applies log-dampening to volume and open interest to maintain feature stationarity.
4. **Reinforcement Learning Frameworks**:
   - `RLAgent` (`backend/btc/rl_agent.py:103-596`): 51-quantile Quantile Regression Dueling Double DQN (QR-DQN) with Prioritized Experience Replay (`PrioritizedReplayBuffer`, capacity=25,000, $\alpha=0.6, \beta=0.4$). Policy network has separate LSTM and static MLP streams fused into Value $V(s)$ and Advantage $A(s, a)$ heads.
   - `PricedDQN` (`backend/btc/rl_priced.py:160-295`): Pure NumPy Dueling Q-Network ensemble trained on 27,876 historical Kalshi contracts with exact net profit after taker fees as the reward for actions `[PASS, BUY YES, BUY NO]`.
   - `RLScalperAgent` (`backend/btc/rl_scalper.py:24-249`): 4-action intraday continuous scalper DQN (HOLD, BUY YES, BUY NO, CLOSE).
5. **Confluence Blending & Decision Gates (`backend/btc/analyzer/contract_eval.py:755-1175`)**:
   - Blending weights (`backend/btc/analyzer/config.py:15-16`): Heuristic setup probability (0.40) and ML model probability (0.60).
   - Sample ramp (`ml_engine.py:822-835`): ML weight ramps from 0.0 to 0.60 as training samples scale from 10 to 300.
   - Model Conflict Veto (lines 771-780): If chart and ML disagree by $\ge 15.0\%$ and ML opposes the trade ($P_{\text{ml}} < 50.0\%$), ML vetoes to `PASS` ($50.0\%$).
   - Strike Pin Dead-Zone (lines 109-127): Blocks trades if $|\text{Spot} - \text{Strike}| \le \$18.00$ and $\text{ATR} \le \$45.00$ without strong breakout volume.
   - Physical Chart Direction Gate (lines 872-904): Blocks YES if spot is $> \$25$ below strike with bearish candle and EMA9 < EMA21; blocks NO if spot is $> \$25$ above strike with bullish candle and EMA9 > EMA21.
   - CVD & Wall Gates (lines 905-964): Blocks trades against heavy CVD divergence, Coinbase L2 ask/bid walls, or liquidation cascades $> \$2\text{M}$.
   - Negative EV Gate (lines 1055-1073): Blocks SNIPER trades if $P_{\text{win}} \le \text{Kalshi\_Ask} + 0.05$.
6. **Empirical Evaluation Data in Repository**:
   - `backend/data/backtest_report.json`: Walk-forward backtest across 480 15m candles (5 days) showed an out-of-sample accuracy of $47.27\%$, Brier score of $0.32785$, and Log Loss of $0.90819$, with severe calibration inversion on a 100-bar window ($0-10\%$ bucket won $75\%$, $80-90\%$ bucket won $32\%$).
   - `backend/data/previous_trades_backtest_results.json`: Re-evaluation of 578 closed historical trades using the retrained, Platt-calibrated `GodTierEnsemble` produced a win rate of $72.66\%$ (vs historical $49.13\%$), profit factor of $2.65$, and $84.11\%$ win rate on high-conviction ($\ge 60\%$) setups.
   - `backend/data/model_cache/rl_scalper.json`: 3,962 test trades showed an average net return of $-\$0.0333$/contract (95% CI: $[-\$0.0447, -\$0.0227]$), empirically confirming that unconstrained high-frequency scalping is unprofitable due to fee drag.
7. **Market Data & Historical Archives**:
   - `backend/data/historical_candles_btc_15m.csv`: 20,002 lines of 15m OHLCV candles.
   - `backend/data/coinbase_btc15m_history.csv`: 32,265 lines of Coinbase 15m OHLCV candles.
   - `backend/data/kalshi_btc15m_history.jsonl`: 27,876 settled Kalshi markets with minute-by-minute order book bid/ask records.

---

## 2. Logic Chain

1. **Model Representation vs. Reality**:
   - From Observation 1 & 4, the system possesses sophisticated mathematical modeling tools (`GodTierEnsemble` with OOF stacking, `RLAgent` QR-DQN with PER, and `PricedDQN`).
   - However, from Observation 6 (`backtest_report.json`), small training windows (e.g. 100 bars) without strict monotonicity constraints result in negative edge (Accuracy $47.27\%$, Log Loss $0.908$, severe inverse calibration where low-probability predictions win at a 75% rate).
2. **Mitigation via Stationarity, Deep Windows & Platt Monotonicity**:
   - From Observation 3, the codebase introduced `normalize_features()` to scale prices relative to `ema_50` and bounds inputs.
   - In `backend/btc/ml_engine.py:20` and `1162`, the training window was expanded to `OPTIMAL_TRAINING_WINDOW_BARS = 20000` bars (~208 days), and `PlattCalibrator` strictly aborts if logistic regression slope is negative ($A \le 0$).
   - Consequently, when evaluated on 578 settled trades (`previous_trades_backtest_results.json`, Observation 6), the retrained calibrated ensemble demonstrated a $72.66\%$ win rate and $2.65$ profit factor.
3. **The Fee Drag & Expected Value Hurdle**:
   - From Observation 5 & 6, Kalshi's taker fee structure ($7\% \times P \times (1-P)$) imposes a major barrier.
   - As observed in `rl_scalper.json`, an RL agent trading without a minimum edge requirement lost $-\$0.0333$ per contract across 3,962 test markets.
   - Therefore, the system's edge relies almost entirely on the **Negative EV Gate** (`contract_eval.py:1063-1073`: $P_{\text{win}} > \text{Ask} + 5\%$), the **Strike Pin Filter** ($|\Delta| > \$18$), and the **Kelly Criterion dampener** (`executor.py:1029-1048`).
4. **Data Ingestion Fidelity & Basis Risk**:
   - From Observation 7 and `kalshi_client.py:141-200`, Kalshi does NOT publish Level 2 orderbook depth on its public API; only top-of-book bids and asks are accessible.
   - Furthermore, spot BTC-USD (Coinbase/Kraken) does not perfectly match the CF Benchmarks BRTI index at contract settlement.
   - Hence, trades executed within $\$18$ of the strike during low-volatility periods face basis divergence risk, which the dead-zone filter correctly identifies and mitigates by forcing `PASS`.

---

## 3. Caveats

1. **Execution Slippage & IOC Fills**:
   - Live limit orders use `immediate_or_cancel` (IOC) with a $\$0.04$ slippage buffer (`slippage_buffer_dollars`). In volatile breakouts, if the book shifts by $> 4\text{¢}$, orders receive zero fill and the trade is aborted.
2. **Missing `rl_calibration.json` in Live Deployment**:
   - The file `backend/data/model_cache/rl_calibration.json` is currently absent from disk. Under `rl_agent.py:410-412`, if this file is missing, `p_cal` returns `None`, forcing `RLAgent` to output `PASS (CAPITAL PRESERVATION)`. If a user selects `modelChoice = "RL_DQN"`, the bot will pass on all trades until `python backend/scripts/calibrate_rl.py` is executed.
3. **Basis Risk Near Expiration**:
   - All technical indicators and ML features are calculated from spot exchange feeds (Coinbase, Kraken, Binance.US). Kalshi contracts officially settle against the CF Benchmarks BRTI index. While highly correlated, momentary basis discrepancies occur during fast market moves.

---

## 4. Conclusion

The Machine Learning prediction engine and data ingestion architecture in `kalshi-ai-trader` is a robust, production-grade quantitative framework. Its primary trading edge does NOT stem from raw model accuracy alone, but from the **strict interaction between calibrated ML probabilities and institutional risk gates**:
- When unconstrained or trading short windows, models suffer from regime drift and fee drag (evidenced by the negative returns in `rl_scalper.json` and poor metrics in `backtest_report.json`).
- When constrained by deep training horizons (20,000 bars), stationarity transforms, monotonic Platt calibration, the Negative EV Gate ($P_{\text{win}} > \text{Ask} + 0.05$), and strike-pin deadzone suppression, the system achieves a strong theoretical and historical edge ($72.66\%$ win rate, $2.65$ profit factor on 578 evaluated trades).

---

## 5. Verification Method

To independently verify these findings, execute the following commands in the application's Python environment:

1. **Verify Unit & Component Tests**:
   ```powershell
   python -m unittest discover -s tests -p "test_*.py"
   ```
2. **Inspect Walk-Forward Backtest Report**:
   ```powershell
   python -c "import json; d=json.load(open('backend/data/backtest_report.json')); print('Recommended Window:', d['recommended_window'], 'Accuracy:', d['results']['100']['accuracy'], 'LogLoss:', d['results']['100']['log_loss'])"
   ```
3. **Inspect Historical Trade Re-Evaluation Metrics**:
   ```powershell
   python -c "import json; d=json.load(open('backend/data/previous_trades_backtest_results.json')); print('Win Rate:', d['model_win_rate_pct'], 'Profit Factor:', d['profit_factor'], 'Brier Score:', d['brier_score'])"
   ```
4. **Inspect RL Scalper Empirical Loss**:
   ```powershell
   python -c "import json; d=json.load(open('backend/data/model_cache/rl_scalper.json')); print('Test Net Per Market:', d['test_net_per_traded_market'], 'CI95:', d['test_ci95'])"
   ```
5. **Inspect Feature Schema Alignment**:
   ```powershell
   python -c "from backend.btc.ml_engine import FEATURE_KEYS; print('Feature count:', len(FEATURE_KEYS)); assert len(FEATURE_KEYS) == 52"
   ```

**Invalidation Conditions**:
- If `len(FEATURE_KEYS)` is modified without updating `_checkpoint_state_dim` and invalidating `.pkl` cache files.
- If `PlattCalibrator` allows negative coefficients ($A \le 0$), which would invert prediction probabilities.
- If Kalshi changes its taker fee schedule from $7\% \times P \times (1-P)$, altering the mathematical EV floor.
