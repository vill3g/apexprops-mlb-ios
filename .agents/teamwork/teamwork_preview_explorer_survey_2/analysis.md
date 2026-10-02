# Comprehensive Investigation & Architecture Analysis: Machine Learning Prediction Engine & Data Sources

**Repository**: `C:\Users\Vill3\Desktop\kalshi-ai-trader`  
**Explorer Survey**: Explorer Survey 2 (ML Prediction Engine & Data Sources Explorer)  
**Date**: 2026-09-30  
**Target Market**: Kalshi 15-Minute Bitcoin Binary Prediction Markets (`KXBTC15M`), with auxiliary support for ETH (`KXETH15M`), Gold (`KXGOLD15M`), and Forex.

---

## Executive Summary

The Kalshi AI Trader incorporates an advanced, multi-layered machine learning and algorithmic decision framework designed to forecast directional outcomes ($P(\text{Close} \ge \text{Target})$) for 15-minute prediction market contracts. The architecture is composed of:
1. **Primary Ensemble Machine Learning Engine (`GodTierEnsemble` in `backend/btc/ml_ensemble.py`)**: A stacking ensemble combining an XGBoost classifier, Random Forest classifier, and a PyTorch Deep Neural Network with an LSTM sequence memory branch for 5-lag tape reading, integrated via a regularized Logistic Regression meta-learner trained with 5-fold out-of-fold stratified cross-validation.
2. **Dual-Regime Execution Framework (`DualMLEngine` in `backend/btc/dual_ml_engine.py`)**: Separate Day (07:00–23:59 ET) and Night (00:00–06:59 ET) models serialized to disk, reflecting diurnal liquidity and volatility regime shifts.
3. **Deep Reinforcement Learning Agents**:
   - `RLAgent` (`backend/btc/rl_agent.py`): A 51-quantile Quantile Regression Dueling Double Deep Q-Network (QR-DQN) with Prioritized Experience Replay (PER), incorporating Platt calibration and market-implied fee-aware edge gating.
   - `PricedDQN` (`backend/btc/rl_priced.py`): A pure NumPy Dueling Q-Network trained directly on 27,876 historical Kalshi 15-minute contracts with exact net profit after taker fees as reward.
   - `RLScalperAgent` (`backend/btc/rl_scalper.py`): An intraday 4-action continuous scalping DQN.
4. **Comprehensive 52-Dimensional Feature Pipeline (`FEATURE_KEYS` in `backend/btc/ml_engine.py`)**: Microstructure, wick dynamics, stationary relative metrics, orderbook imbalances, CVD proxies, funding rates, open interest, FinBERT NLP sentiment, macro correlation, and 25 lag features (5 lags $\times$ 5 indicators).
5. **Rigorous Confluence & Safety Gates (`backend/btc/analyzer/contract_eval.py` & `backend/btc/auto_executor/executor.py`)**: Multi-signal blending, ML conflict vetoes, physical chart alignment gates, CVD divergence blocks, order book bid/ask wall blocks, liquidation cascade filters, strike pin dead-zone filters, and positive Expected Value ($EV \ge \text{Ask} + 5\%$) requirements.
6. **Data Ingestion & Kalshi Execution**: High-speed, cached REST API integration for Kalshi contracts, Coinbase L2 order books, Binance Futures funding/liquidations, crypto news NLP feeds, and historical datasets (`kalshi_btc15m_history.jsonl` with 27,876 settled contracts, `coinbase_btc15m_history.csv` with 32,265 candles, and `historical_candles_btc_15m.csv` with 20,002 candles).

---

## 1. Machine Learning Models, Architectures & Pipelines

### 1.1 Model Inventory & Architecture

| Model / Agent | Implementation File | Architecture / Algorithm | Input Dimensions & Structure | Loss / Objective & Optimization |
| :--- | :--- | :--- | :--- | :--- |
| **`GodTierEnsemble`** | `backend/btc/ml_ensemble.py:80-273` | **Stacking Ensemble**: <br>1. `XGBClassifier` (n=150, depth=4, lr=0.05)<br>2. `RandomForestClassifier` (n=150, max_depth=5)<br>3. `PyTorchLSTM` (1-layer LSTM for lags + Dense FC for tabular)<br>4. Meta-Learner: `LogisticRegression(C=0.5)` | 52 normalized features (`FEATURE_KEYS`):<br>- 27 static features<br>- 25 sequence lag features (5 lags $\times$ 5 indicators) | - Base models: Log loss, Gini, BCE loss (`Adam`, lr=0.003, 15 epochs)<br>- Meta-learner: L2 regularized log loss on OOF fold predictions |
| **`DualMLEngine`** | `backend/btc/dual_ml_engine.py:10-99` | **Day/Night Coordinator**: Wraps two independent instances of `MLEngine` (`day_engine` and `night_engine`). Switches active engine based on America/New_York hour ($[0, 7)$ = Night, $[7, 24)$ = Day). | 52 features passed to respective engine | Delegates training and inference to wrapped `MLEngine` instances |
| **`XGBoostModel`** | `backend/btc/ml_engine.py:69-194` | **Pipeline**: `StandardScaler` + `XGBClassifier` with dynamic L1 alpha heuristic ($\alpha = \frac{1}{\text{reg\_c} + 0.1}$) and class balance weighting (`scale_pos_weight = num_neg / num_pos`). | 52 features | Binary logistic (`eval_metric='logloss'`), calibrated via `PlattCalibrator` |
| **`RLAgent` (QR-DQN)** | `backend/btc/rl_agent.py:103-596` | **Hybrid LSTM Quantile Regression Dueling DQN**: 51 quantiles. Action space (3): HOLD/PASS (0), BUY YES (1), BUY NO (2). Decoupled Value $V(s)$ and Advantage $A(s, a)$. | 52 features (split into 27 static MLP inputs + $5 \times 5$ LSTM sequence) | Quantile Huber Loss over 51 fixed target quantiles; AdamW (lr=3e-4, weight_decay=1e-4); Double DQN action selection; Prioritized Experience Replay (PER, capacity=25,000, $\alpha=0.6, \beta=0.4 \to 1.0$) |
| **`PricedDQN`** | `backend/btc/rl_priced.py:160-295` | **Ensemble of Dueling Q-Networks (Pure NumPy)**: Dueling streams with SiLU activation ($\text{SiLU}(x) = x \cdot \sigma(x)$). Actions (3): PASS (0), BUY YES (1), BUY NO (2). Learns expected net profit per $1 contract. | 29 market features + 6 quote features (`yes_ask`, `yes_bid`, `mid`, `spread`, `mid_logit`, `mid_dist`) + `elapsed_min` = 36 inputs | Huber loss on exact net profit after fees ($Q - R$); Adam optimizer (lr=1e-3, l2=1e-4) with validation early stopping |
| **`RLScalperAgent`** | `backend/btc/rl_scalper.py:24-249` | **Dueling Double DQN**: Action space (4): HOLD (0), BUY YES (1), BUY NO (2), CLOSE POSITION (3). Hidden dim=512 trunk with LayerNorm + SiLU. | 37 state features | Smooth L1 loss with PER importance sampling; AdamW (lr=3e-4) |
| **`ForexXGB`** | `backend/forex/ml_engine.py:20-83` | **XGBoost Classifier**: Predicts probability of price gaining 1 ATR before losing 1 ATR on EURUSD 15m candles. | 7 features: `rsi`, `bb_percent_b`, `ema_9_diff`, `ema_21_diff`, `atr`, `vol_ratio`, `hour_of_day` | Binary log loss (`n_estimators=100`, `max_depth=4`, `lr=0.05`) |

---

### 1.2 Feature Engineering & Normalization Pipeline

The feature pipeline is standardized in `FEATURE_KEYS` (`backend/btc/ml_engine.py:199-226`) and extracted via two unified functions:
1. `build_feature_row(df_ind, i)` (`backend/btc/ml_engine.py:322-511`): Historical training feature extraction using strictly bar $i-1$ and earlier.
2. `build_live_ml_features(...)` (`backend/btc/ml_engine.py:514-724`): Live production feature vector construction matching the training distribution.

#### Full 52-Feature Schema:
- **Momentum & Oscillators**: `rsi`, `bb_upper`, `bb_lower`, `bb_percent_b`, `ema_9`, `ema_21`, `ema_50`, `atr`, `price_vs_vwap`, `roc_15m`, `roc_1h`, `roc_4h`.
- **Order Flow & Microstructure**: `cvd_value`, `cvd_divergence` ($\frac{\text{CVD}}{\text{ATR} + 10^{-5}}$), `cvd_acceleration`, `orderbook_imbalance` (Coinbase Level 2 L2 imbalance), `upper_wick_ratio`, `lower_wick_ratio`, `body_to_range`, `vsa_absorption` ($\text{vol\_ratio} \times (1 - \text{body\_ratio})$), `sfp_score` (Swing Failure Pattern liquidity swipe score).
- **Derivatives & Macro**: `funding_rate` (Binance Futures), `open_interest`, `fng_value` (Alternative.me Crypto Fear & Greed), `ndq_roc` (Nasdaq 100), `dxy_roc` (US Dollar Index).
- **Temporal & Regime**: `is_weekend`, `hour_of_day` (EST), `volume_15m_ratio` ($\frac{\text{Volume}}{\text{3-Day Rolling Volume Mean}}$), `high_24h`, `low_24h`, `volume_24h`, `range_24h_pos` ($\frac{P_{\text{close}} - \text{Low}_{24h}}{\text{High}_{24h} - \text{Low}_{24h}}$), `vol_regime_percentile` (24-hour rolling ATR rank percentile).
- **Kalshi Market State & Time-Decay**: `minutes_remaining` (countdown to 15m expiration), `kalshi_yes_prob` (live implied probability), `kalshi_book_imbalance` (Kalshi top-of-book depth ratio), `delta_to_target` ($\frac{P_{\text{close}} - \text{Strike}}{\text{Strike}} \times 100$), `vol_time_z_score` ($\frac{P_{\text{close}} - \text{Strike}}{\text{ATR} \cdot \sqrt{\text{minutes\_remaining} / 15}}$), `heuristic_score`.
- **LSTM Sequence Lag Features (25 features)**: 5 historical lags (lags 4 down to 0) across 5 core indicators: `bb_percent_b_lag_{k}`, `rsi_lag_{k}`, `volume_15m_ratio_lag_{k}`, `roc_15m_lag_{k}`, `cvd_divergence_lag_{k}`.

#### Stationarity Normalization (`normalize_features` in `backend/btc/ml_engine.py:286-320`):
To prevent catastrophic failure when Bitcoin transitions between price regimes (e.g., $60,000 to $110,000), features undergo strict stationarity transforms:
- Moving averages and Bollinger Bands are expressed as relative fractional deviations from `ema_50`:
  $$\text{norm}[k] = \frac{\text{raw}[k]}{\text{ema\_50}} - 1.0$$
- `atr` and `price_vs_vwap` are expressed as a percentage of `ema_50`:
  $$\text{norm}[\text{atr}] = \frac{\text{raw}[\text{atr}]}{\text{ema\_50}} \times 100.0$$
- Non-stationary unbounded metrics (`volume_24h`, `open_interest`) use logarithmic dampening: $\log(1 + \max(0, x))$.
- `cvd_value` uses signed log transformation: $\text{copysign}(\log(1 + |x|), x)$.
- RSI lags are scaled from $[0, 100]$ to $[0, 1]$.

---

### 1.3 Training Pipelines & Caching Mechanisms

#### A. Historical Market Self-Training (`MLEngine.self_train_on_historical_market`)
- **Code Path**: `backend/btc/ml_engine.py:1125-1303`
- **Data Source**: Deep historical 15m candles (up to 20,000 bars from `fetch_15m_candles_history()` or 1m candles for `MOMENTUM_SURFER`).
- **Labeling Logic**:
  $$\text{Label} = 1 \iff \text{Close}_{\text{interval}} \ge \text{Target} \quad (\text{Open}_{\text{interval}})$$
- **Sample Weighting**: Linear recency weighting (`backend/btc/ml_engine.py:857-862`):
  $$w_i = 1.0 + \frac{i}{N - 1} \quad (w_i \in [1.0, 2.0])$$
- **Validation Split**: 80% train / 20% holdout (minimum 20 holdout bars).
- **Out-of-Fold Stacking**: In `GodTierEnsemble.fit()`, a 5-fold `StratifiedKFold` generates out-of-fold predictions (`oof_xgb`, `oof_rf`, `oof_dnn`) before fitting the meta-learner `LogisticRegression(C=0.5)` to eliminate in-sample memorization leakage (`backend/btc/ml_ensemble.py:140-201`).
- **Model Serialization**: Cached as joblib pickles in `backend/data/model_cache/{asset}_{style}_{time_filter}_model.pkl`.
- **Cache Invalidation & Expiration**:
  1. Rolling retraining schedule: Cache expires after 7 days (`MAX_CACHE_AGE_SECONDS = 7 * 86400`, line 1133).
  2. Dimension compatibility check (`_is_model_compatible` line 1010-1026): verifies `scaler.n_features_in_ == len(FEATURE_KEYS)` and `is_normalized == True`. If features were added/modified, disk cache is automatically purged and retrained.

#### B. Live Trades Retraining Pipeline (`MLEngine.train`)
- **Code Path**: `backend/btc/ml_engine.py:1027-1123`
- **Source**: `trades_history.json` / `trades.db`.
- **Cold-Start Protection**: If fewer than 300 live trades are available, the engine refuses to overwrite the rich historical model cache, preventing sample starvation (`backend/btc/ml_engine.py:1070-1082`).

#### C. Priced RL Training Pipeline (`train_rl_priced.py`)
- **Code Path**: `backend/scripts/train_rl_priced.py:1-306`
- **Source**: 27,876 settled contracts from `kalshi_btc15m_history.jsonl` paired with `coinbase_btc15m_history.csv`.
- **Target Function**: Exact contract profit after taker fee:
  $$R(\text{PASS}) = 0.0$$
  $$R(\text{YES}) = \mathbb{I}(\text{YES settled}) - P_{\text{yes\_ask}} - \text{Fee}(P_{\text{yes\_ask}})$$
  $$R(\text{NO}) = \mathbb{I}(\text{NO settled}) - (1 - P_{\text{yes\_bid}}) - \text{Fee}(1 - P_{\text{yes\_bid}})$$
- **Walk-Forward Validation**: 70% train / 15% validation / 15% out-of-sample test. Model is only saved with `"enabled": true` if the test period demonstrated positive net profit after fees.

---

## 2. Prediction Probabilities, Confidence Scores, Expected Values & Signal Conversion

### 2.1 Multi-Stage Signal Transformation Flow

```mermaid
flowchart TD
    A[Raw Market Data: Spot Candles, Orderbooks, CVD, News, Kalshi Quote] --> B[Feature Extraction: 52 Stationary Features]
    B --> C[ML Inference: GodTierEnsemble or RLAgent]
    C --> D[Calibrated Model Probability: P_model]
    
    A --> E[Heuristic Pattern Engine: SMC Sweeps, Bollinger, Climax, Thrust]
    E --> F[Heuristic Direction & Candidate Score: P_heur 60%-82%]
    
    D --> G{Signal Isolation Mode}
    F --> G
    
    G -->|AI_ONLY| H[Direct Model Probability: P_final = P_model]
    G -->|CHART_ONLY| I[Direct Heuristic Probability: P_final = P_heur]
    G -->|BLEND| J[Weighted Confluence Blend: P_blend = 0.4*P_heur + 0.6*P_model]
    
    J --> K{Model Conflict Check: |P_heur - P_model| >= 15% and P_model < 50%?}
    K -->|Yes: Conflict| L[ML Veto -> PASS 50%]
    K -->|No: Agreement| M[Blended Probability P_final]
    
    H --> N[Safety & Market Structure Gates]
    I --> N
    M --> N
    
    N --> O{Physical Chart Conflict? Spot > $25 off strike against trend?}
    O -->|Yes| P[Block -> PASS]
    O -->|No| Q{CVD Divergence or Orderbook Wall Block?}
    Q -->|Yes| R[Block -> PASS]
    Q -->|No| S{Strike Pin Deadzone? |Delta| <= $18 and ATR <= $45?}
    S -->|Yes| T[Block -> PASS]
    S -->|No| U{Expected Value Gate: P_win > Ask + Fees + 5%?}
    U -->|No: Negative EV| V[Block -> PASS]
    U -->|Yes: Positive EV| W[EXECUTE ORDER: Size via Kelly Criterion / MaxCap]
```

### 2.2 Confluence Blending Mathematical Logic

In `backend/btc/analyzer/contract_eval.py:755-807`:
1. **Directional Mapping**:
   If candidate heuristic setup predicts `YES`/`ABOVE`:
   $$\text{ml\_prob\_for\_pred\_dir} = \text{ml\_prob} \times 100.0$$
   If candidate heuristic setup predicts `NO`/`BELOW`:
   $$\text{ml\_prob\_for\_pred\_dir} = (1.0 - \text{ml\_prob}) \times 100.0$$
2. **Dynamic Sample-Weight Scaling** (`backend/btc/ml_engine.py:822-835`):
   When the ML model has few live training samples ($N < 300$), its blend weight ramps linearly to protect against small-sample instability:
   $$W_{\text{ml}} = W_{\text{base}} \times \max\left(0.0, \min\left(1.0, \frac{N - 10}{300 - 10}\right)\right), \quad W_{\text{base}} = 0.60$$
   $$W_{\text{heur}} = 1.0 - W_{\text{ml}}$$
3. **Blended Confidence Score**:
   $$P_{\text{blended}} = (P_{\text{heur}} \times W_{\text{heur}}) + (\text{ml\_prob\_for\_pred\_dir} \times W_{\text{ml}})$$
4. **Model Veto (Conflict Resolution)** (`contract_eval.py:771-780`):
   If $\text{ml\_prob\_for\_pred\_dir} < 50.0\%$ (model opposes trade) and $|P_{\text{heur}} - \text{ml\_prob\_for\_pred\_dir}| \ge 15.0\%$:
   $$\text{Action} \leftarrow \text{PASS}, \quad \text{Grade} \leftarrow \text{"GRADE C / PASS"}, \quad P_{\text{blended}} \leftarrow 50.0\%$$

---

### 2.3 Expected Value ($EV$), Fees, and Kelly Criterion Sizing

#### Kalshi Taker Fee Structure (`backend/btc/fees.py:9-20`):
Kalshi's official taker fee formula per contract:
$$\text{Fee}(P, C) = \left\lceil 0.07 \times C \times P \times (1.0 - P) \times 100 \right\rceil / 100.0$$
Where $P \in [0.0, 1.0]$ is the contract price and $C$ is contract quantity.

#### Expected Value & Edge Formulation:
1. **In `fees.py:25-32` (`entry_edge_cents`)**:
   $$\text{Edge}_{\text{cents}} = \left( P_{\text{win}} - P_{\text{ask}} - 0.07 \times P_{\text{ask}} \times (1.0 - P_{\text{ask}}) \right) \times 100.0$$
2. **In `contract_eval.py:1055-1073` (SNIPER Negative EV Gate)**:
   $$\text{Required EV Floor} = P_{\text{ask}} + 0.05$$
   $$\text{If } P_{\text{win}} \le \text{Required EV Floor} \implies \text{PASS / NO BID (NEGATIVE EV)}$$
3. **In `rl_agent.py:401-429` (RL Fee Gate)**:
   $$\text{Edge}_{\text{yes}} = P(\text{YES}) - P_{\text{yes\_ask}} - \text{Fee}(P_{\text{yes\_ask}})$$
   $$\text{Trade Allowed } \iff \text{Edge} \ge \text{min\_edge} \quad (\text{default } \$0.02)$$

#### Kelly Criterion Position Sizing (`backend/btc/auto_executor/executor.py:1029-1048`):
When `useKellyCriterion` is enabled:
$$\text{Edge} = P_{\text{win}} - P_{\text{market}}$$
If $\text{Edge} \le 0 \implies \text{Trade Aborted (-EV Setup)}$.  
Fractional Kelly dampening factor:
$$f^*_{\text{damp}} = \min\left(1.0, \max\left(0.25, \frac{\text{Edge}}{0.15}\right)\right)$$
$$\text{Contracts} = \max\left(1, \left\lfloor \frac{\text{MaxCap} \times f^*_{\text{damp}}}{P_{\text{unit}}} \right\rfloor\right)$$

---

## 3. Model Calibration, Confidence Thresholds & Evaluation Metrics

### 3.1 Probability Calibration Implementations

1. **PlattCalibrator (`backend/btc/ml_engine.py:23-67`)**:
   - Logistic regression operating on raw log-odds (logits):
     $$\text{logit}(p) = \log\left(\frac{p}{1 - p}\right)$$
     $$P_{\text{calibrated}} = \frac{1}{1 + \exp(-(A \cdot \text{logit}(p) + B))}$$
   - **Monotonicity Law (`ml_engine.py:49-53`)**: Checks $A > 0$ (`lr.coef_[0, 0] > 0`). If $A \le 0$, calibration is aborted (`is_fitted = False`) and raw probabilities are retained. This prevents catastrophic inverse probability mapping on noisy holdout slices.
2. **Newton's Method Platt Fit (`backend/btc/rl_agent.py:65-77` & `calibrate_rl.py`)**:
   - Closed-form 1D logistic regression solver utilizing Newton-Raphson optimization with L2 regularization ($\lambda = 10^{-3}$) to fit parameters $(a, b)$.
3. **Market-Anchored Calibration (`backend/btc/rl_agent.py:388-400`)**:
   - Prevents the agent from buying mispriced contracts where the model's unconditioned base rate differs from the strike geometry:
     $$P(\text{YES}) = \text{clip}\left(P_{\text{kalshi\_mid}} + (P_{\text{cal}} - \text{BaseRate}), 0.01, 0.99\right)$$
4. **Live Calibration Drift Monitor (`backend/btc/auto_executor/risk_manager.py:79-161`)**:
   - Periodically partitions the trailing 100 settled trades into 10 decile buckets ($[0, 0.1), [0.1, 0.2), \dots, [0.9, 1.0]$).
   - Computes bucket error $\text{diff} = \bar{p}_{\text{pred}} - \text{WR}_{\text{realized}}$.
   - If $|\text{diff}| > 8.0\%$ across 3 or more populated buckets, flags systematic over/under-confidence and triggers an asynchronous background retraining thread (`ml_engine.train(force=True)`).

---

### 3.2 Confidence Thresholds by Trading Style

Configured in `backend/data/trading_config.json` and `backend/btc/auto_executor/executor.py:911-965`:

| Trading Style / Mode | Primary Decision Engine | Minimum Confidence Floor | Entry Timing Window | Special Strategy Gates |
| :--- | :--- | :--- | :--- | :--- |
| **`SNIPER`** | Confluence Blend (`contract_eval.py`) | Grade A+: 70%<br>Grade A: 65%<br>Grade B: 60%<br>Global default: 64% | Rollover ($0 \le t_{\text{elapsed}} \le 60\text{s}$) | Negative EV Gate ($P_{\text{win}} > \text{Ask} + 5\%$), Strike Pin Gate ($|\Delta| > \$18$), Chart Alignment |
| **`PREDICTION`** | Direct ML / RL (`ml_prob`) with $\pm 5\%$ chart nudge | $58.0\%$ ($|P_{\text{yes}} - 50| \ge 8.0\%$) | Mid-candle ($90\text{s} \le t_{\text{elapsed}} \le 720\text{s}$) | Waits 90s for candle opening noise to settle; orderbook bid/ask wall checks |
| **`MOMENTUM_SURFER`** | 1m high-res breakout / ML | 60% (if $t \le 60\text{s}$),<br>75% (mid-candle) | Rapid entry ($t_{\text{left}} \ge 180\text{s}$) | Requires 1m candle alignment and high volume acceleration |
| **`AMBUSH`** | Exhaustion / Mean-Reversion | Grade A: 65% | Counter-trend ($t_{\text{left}} \ge 180\text{s}$) | Blocked if CVD accelerating in direction of move ($|\text{accel}| > 0.1$) or opposing 1H macro trend |
| **`CHOP`** | Bollinger Band Extremes (`chop_engine.py`) | Base $+ 6.0\%$ extra floor | Mean reversion ($t_{\text{left}} \ge 180\text{s}$) | Fades Upper BB if RSI $> 65$ and NO Ask $\in [40\text{¢}, 60\text{¢}]$; fades Lower BB if RSI $< 35$ and YES Ask $\in [40\text{¢}, 60\text{¢}]$ |
| **`CAPITAL_GUARD`** | Volatility Compression Check | N/A (Always PASS) | Low volatility deadzone | Active when $\text{ADX} < 18$ and $\text{VolRatio} < 0.85$; preserves capital |
| **`AUTO`** | Dynamic Regime Router (`classify_auto_regime`) | Dynamically routed | Evaluated per regime | Routes to CHOP, AMBUSH, MOMENTUM_SURFER, CAPITAL_GUARD, or SNIPER |

---

### 3.3 Known Evaluation Metrics & Empirical Findings

The repository contains three empirical evaluation records:

#### 1. Walk-Forward Rolling Evaluation (`backend/data/backtest_report.json`)
- **Dataset**: 480 15m candles (5 days), 330 out-of-sample test samples.
- **Evaluated Window**: 100 bars.
- **Accuracy**: $47.27\%$
- **Brier Score**: $0.32785$
- **Log Loss**: $0.90819$
- **Calibration Pathology Observed**:
  - The model demonstrated severe **inverse calibration**:
    - Bucket $0-10\%$ predicted probability $\to$ realized win rate of $75.0\%$ ($\text{diff} = -67.92\%$).
    - Bucket $80-90\%$ predicted probability $\to$ realized win rate of $32.0\%$ ($\text{diff} = +51.89\%$).
    - Bucket $90-100\%$ predicted probability $\to$ realized win rate of $33.33\%$ ($\text{diff} = +57.96\%$).
  - **Root Cause**: Small sample size (100 bars) combined with rapid crypto regime changes caused severe uncalibrated inversion. This empirical failure motivated the introduction of the 20,000-bar training window (`OPTIMAL_TRAINING_WINDOW_BARS`) and the strict positive-slope monotonicity enforcement in `PlattCalibrator`.

#### 2. Re-Evaluation on Historical Trade Ledger (`backend/data/previous_trades_backtest_results.json`)
- **Dataset**: 578 closed/settled historical trades evaluated against the retrained `GodTierEnsemble` with Platt calibration.
- **Overall Model Win Rate**: $72.66\%$ (420 wins, 158 losses) vs. Historical Baseline of $49.13\%$ ($\Delta = +23.53\%$).
- **Profit Factor**: $2.65$
- **Brier Score**: $0.2120$
- **Log Loss**: $0.6155$
- **High Conviction Tier ($\ge 60\%$)**: 214 trades, $84.11\%$ win rate (180 wins, 34 losses), generating $+\$30,245.76$ simulated PnL.
- **Lower Conviction Tier ($< 60\%$)**: 364 trades, $65.93\%$ win rate (240 wins, 124 losses), generating $+\$23,952.37$ simulated PnL.

#### 3. Out-of-Sample Scalper Evaluation (`backend/data/model_cache/rl_scalper.json`)
- **Dataset**: 22,450 train episodes, 3,962 held-out test trades.
- **Test Net Profit Per Traded Market**: $-\$0.0333$ per contract.
- **95% Confidence Interval**: $[-\$0.0447, -\$0.0227]$.
- **Conclusion**: Demonstrates that high-frequency intraday scalping on Kalshi is statistically unprofitable due to the $7\%$ taker fee drag and adverse selection on execution fills.

---

## 4. Market Data Ingestion, Feeds & Historical Formats

### 4.1 Kalshi API Feeds & Order Book Handling

- **Client Modules**:
  - `backend/btc/kalshi_client.py:1-271`: Public data ingestion (unauthenticated).
  - `backend/btc/kalshi_trader.py:1-1378`: Authenticated trading and portfolio synchronization.
- **Endpoints Used**:
  - `GET /trade-api/v2/markets?series_ticker=KXBTC15M&status=open`: Active contract discovery.
  - `GET /trade-api/v2/markets/{ticker}`: Contract settlement verification and final result determination (`yes` or `no`).
  - `GET /trade-api/v2/markets/{ticker}/trades`: Public trade tape polling (cached for 1.5s).
  - `GET /trade-api/v2/portfolio/balance`: Live cash and collateral balance.
  - `GET /trade-api/v2/portfolio/positions`: Real-time position tracking.
  - `POST /trade-api/v2/portfolio/events/orders`: IOC limit order execution.
- **Order Book Depth & Basis Risk**:
  - **No Multi-Level Book Ladder**: Kalshi’s public API provides strictly **top-of-book quotes** (`yes_bid`, `yes_ask`, `no_bid`, `no_ask`, `yes_bid_size`, `yes_ask_size`). Depth ladders are unavailable.
  - **Paper Depth Simulation**: To prevent unrealistic paper fills, `_simulated_book_depth` (`backend/btc/kalshi_trader.py:41-54`) uses a deterministic SHA-256 hash of `(ticker, side, minute)` to simulate realistic liquidity depth between 8 and 60 contracts, with a $3\%$ probability of a complete missed IOC fill (`PAPER_NO_FILL_CHANCE = 0.03`) and a $\$0.01$ latency tax (`PAPER_LATENCY_TAX_DOLLARS`).
  - **Index Basis Risk**: Kalshi `KXBTC15M` contracts settle against the **CF Benchmarks Bitcoin Real Time Index (BRTI)** at expiration. Spot feeds (Coinbase, Kraken, Binance) may diverge from BRTI near strike pins, causing basis spread risk.

---

### 4.2 External Market Data Feeds

1. **Spot Candle Multi-Exchange Engine (`backend/btc/data_fetcher.py:72-170` & `backend/engine/multi_asset_fetcher.py:11-100`)**:
   - Primary: Coinbase Exchange API (`/products/BTC-USD/candles`).
   - Fallback 1: Kraken API (`/0/public/OHLC`, pair `XBTUSD`).
   - Fallback 2: Binance.US API (`/api/v3/klines`, symbol `BTCUSDT`).
   - Fallback 3: Yahoo Finance (`yfinance` Ticker `BTC-USD`).
2. **Coinbase Level 2 Orderbook (`backend/btc/data_fetcher.py:874-922` & `backend/btc/orderbook.py:7-45`)**:
   - Fetches L2 orderbook via `https://api.exchange.coinbase.com/products/BTC-USD/book?level=2`.
   - Aggregates bid and ask volume within $0.5\%$ depth from the mid-price.
   - Detects the largest bid wall and ask wall prices and sizes.
3. **Binance Futures Funding Rate & Open Interest (`backend/btc/data_fetcher.py:503-541`)**:
   - Queries `fapi.binance.com/fapi/v1/premiumIndex` (funding rate) and `openInterest`.
   - Cached for 10s (extended to 120s if geo-blocked or rate-limited).
4. **Binance Forced Liquidation WebSocket Stream (`backend/btc/liquidation_stream.py:1-84`)**:
   - Connects to `wss://fstream.binance.com/ws/btcusdt@forceOrder`.
   - Accumulates a rolling 15-minute window of long and short liquidations in USD.
   - Triggers cascade protection gates in `contract_eval.py` if $> \$2,000,000$ in liquidations occur in 15 minutes.
5. **FinBERT NLP News Sentiment Engine (`backend/btc/news_fetcher.py:1-285`)**:
   - Integrates HuggingFace pipeline `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis` for local CPU/GPU financial sentiment inference.
   - Augments with weighted crypto domain dictionaries (`BULLISH_KEYWORDS`, `BEARISH_KEYWORDS`).
6. **Crypto Fear & Greed Index (`backend/btc/data_fetcher.py:549-580`)**:
   - Fetches daily sentiment from `https://api.alternative.me/fng/?limit=1` (cached for 1 hour).

---

### 4.3 Historical Data Formats & Storage

1. **`historical_candles_btc_15m.csv`** (`backend/data/`):
   - 20,002 lines of 15m historical candles from Binance.US / Kraken.
   - Format: `time,open,high,low,close,volume` (Unix timestamp integer, floats).
2. **`coinbase_btc15m_history.csv`** (`backend/data/`):
   - 32,265 lines of Coinbase BTC-USD 15m candles covering extended history.
3. **`kalshi_btc15m_history.jsonl`** (`backend/data/`):
   - 27,876 settled Kalshi markets stored in JSON Lines format.
   - Record schema:
     ```json
     {
       "ticker": "KXBTC15M-26JUL271845-45",
       "open_ts": 1785191400,
       "close_ts": 1785192300,
       "strike": 64547.43,
       "exp_value": "64160.27",
       "result": "no",
       "c": [
         {"off": 60, "ask": 0.39, "bid": 0.38, "ask_lo": 0.37, "bid_hi": 0.5, "vol": 163771.92},
         {"off": 120, "ask": 0.29, "bid": 0.28, "ask_lo": 0.28, "bid_hi": 0.39, "vol": 131988.99},
         {"off": 180, "ask": 0.39, "bid": 0.38, "ask_lo": 0.28, "bid_hi": 0.42, "vol": 81389.21},
         {"off": 240, "ask": 0.44, "bid": 0.43, "ask_lo": 0.39, "bid_hi": 0.45, "vol": 67659.18}
       ]
     }
     ```
4. **`trades_history.json` & `trades.db`** (`backend/data/`):
   - Atomic JSON file and SQLite database (`TradeDB` in `backend/btc/trade_db.py`).
   - Every trade record preserves full `market_snapshot` containing all 52 `raw_features` at prediction time, execution metrics, slippage, and official settlement outcome.

---

## 5. Comprehensive Code Path Index

| Component | File Path | Class / Function / Global | Line Numbers | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Platt Calibrator** | `backend/btc/ml_engine.py` | `PlattCalibrator` | Lines 23–67 | Monotonic 1D logistic regression on log-odds logits |
| **XGBoost Single Model** | `backend/btc/ml_engine.py` | `XGBoostModel` | Lines 69–194 | Standardized XGBoost classifier pipeline with L1 heuristic |
| **Feature Schema Keys** | `backend/btc/ml_engine.py` | `FEATURE_KEYS` | Lines 199–226 | List of 52 feature identifiers |
| **Feature Stationarity** | `backend/btc/ml_engine.py` | `normalize_features` | Lines 286–320 | Stationarity normalization relative to `ema_50` |
| **Historical Feature Row** | `backend/btc/ml_engine.py` | `build_feature_row` | Lines 322–511 | Extract features for bar $i$ using only bars $< i$ |
| **Live Feature Builder** | `backend/btc/ml_engine.py` | `build_live_ml_features` | Lines 514–724 | Unified live 52-feature construction |
| **ML Engine Orchestrator** | `backend/btc/ml_engine.py` | `MLEngine` | Lines 727–1341 | Core engine managing `GodTierEnsemble`, training, caching |
| **SHAP / Tree Reasoning** | `backend/btc/ml_engine.py` | `predict_with_reasoning` | Lines 751–821 | Extract top 3 tree feature contributions (`pred_contribs`) |
| **Confidence Weight Ramp** | `backend/btc/ml_engine.py` | `get_ml_confidence_weight`| Lines 822–835 | Ramp ML weight from 0 to 0.60 based on sample size |
| **Historical Self-Train** | `backend/btc/ml_engine.py` | `self_train_on_historical_market` | Lines 1125–1303 | Train model on up to 20,000 historical 15m intervals |
| **Dual ML Day/Night** | `backend/btc/dual_ml_engine.py` | `DualMLEngine` | Lines 10–99 | Route inference between day and night engines |
| **GodTier Ensemble Swarm**| `backend/btc/ml_ensemble.py`| `GodTierEnsemble` | Lines 80–273 | Stacking XGBoost + RF + PyTorch LSTM via Logistic Regression |
| **PyTorch LSTM Network** | `backend/btc/ml_ensemble.py`| `PyTorchLSTM` | Lines 15–57 | Dual-branch neural network (LSTM sequence + FC tabular) |
| **QR-DQN Network** | `backend/btc/rl_agent.py` | `DuelingDQN` | Lines 103–182 | 51-quantile dueling network with LSTM tape reading |
| **Prioritized Replay** | `backend/btc/rl_agent.py` | `PrioritizedReplayBuffer` | Lines 187–276 | TD-error proportional sampling with beta IS correction |
| **RL Agent Policy** | `backend/btc/rl_agent.py` | `RLAgent` | Lines 282–596 | Double DQN agent with market-anchored calibration |
| **RL Contract Evaluation**| `backend/btc/rl_agent.py` | `evaluate_contract` | Lines 368–452 | Market-implied prob shift + fee gate |
| **Priced RL DQN** | `backend/btc/rl_priced.py` | `PricedDQN` | Lines 239–295 | NumPy Dueling Q-Net trained on historical Kalshi net PnL |
| **RL Scalper Agent** | `backend/btc/rl_scalper.py` | `RLScalperAgent` | Lines 135–243 | Continuous 4-action intraday scalper DQN |
| **Chop Regime Evaluator** | `backend/btc/chop_engine.py` | `evaluate_chop_contract` | Lines 46–98 | Low volatility Bollinger Band mean reversion evaluator |
| **Forex ML Engine** | `backend/forex/ml_engine.py` | `load_or_train_xgb_model` | Lines 20–83 | EURUSD XGBoost directional model |
| **Thresholds Config** | `backend/btc/analyzer/config.py` | `THRESHOLDS` | Lines 13–56 | Blending weights (0.4/0.6), conflict cap (15%), CVD limits |
| **Contract Evaluator** | `backend/btc/analyzer/contract_eval.py`| `evaluate_next_15m_contract` | Lines 30–1198 | Primary decision engine combining heuristics, ML & gates |
| **Strike Pin Filter** | `backend/btc/analyzer/contract_eval.py`| `evaluate_next_15m_contract` | Lines 109–127 | Dead zone filter: $|\text{Spot} - \text{Strike}| \le \$18$ and $\text{ATR} \le \$45$ |
| **Confluence Blending** | `backend/btc/analyzer/contract_eval.py`| `evaluate_next_15m_contract` | Lines 755–807 | Blend heuristic prob with ML prob; apply conflict veto |
| **Negative EV Gate** | `backend/btc/analyzer/contract_eval.py`| `evaluate_next_15m_contract` | Lines 1055–1073 | Block SNIPER trade if $P_{\text{win}} \le \text{Ask} + 0.05$ |
| **Prediction Style Logic**| `backend/btc/analyzer/contract_eval.py`| `evaluate_next_15m_contract` | Lines 1111–1175 | ML-dominant style requiring $\ge 58\%$ confidence |
| **Multi-Timeframe Analyzer**| `backend/btc/analyzer/confluence.py` | `analyze_btc` | Lines 56–969 | Multi-timeframe confluence scoring (-100 to +100) |
| **Auto Executor Loop** | `backend/btc/auto_executor/executor.py`| `check_and_execute_rollover` | Lines 600–1245 | Main autonomous execution cycle at 15m rollover |
| **Position Sizing & Kelly**| `backend/btc/auto_executor/executor.py`| `check_and_execute_rollover` | Lines 1020–1048 | Kelly Criterion edge calculation and MaxCap clamping |
| **Risk Budget Manager** | `backend/btc/auto_executor/risk_manager.py`| `check_risk_budget` | Lines 42–78 | Daily loss ceiling, max daily trades, 3-loss circuit breaker |
| **Calibration Drift Check**| `backend/btc/auto_executor/risk_manager.py`| `check_live_calibration_drift`| Lines 79–161 | 10-bucket calibration evaluation and auto-retrain trigger |
| **Walk-Forward Backtest** | `backend/btc/backtest.py` | `run_walkforward_backtest`| Lines 37–189 | Rolling out-of-sample backtesting (Brier, LogLoss, Accuracy) |
| **Calibration Diagnostics**| `backend/btc/backtest.py` | `analyze_calibration_overconfidence`| Lines 191–214 | Detect systematic overconfidence ($>8\%$ across $\ge 3$ buckets) |
| **Kalshi Public Client** | `backend/btc/kalshi_client.py` | `get_kalshi_15m_market` | Lines 39–200 | Discover active contract, extract strike, odds, imbalance |
| **Kalshi Trading Client** | `backend/btc/kalshi_trader.py` | `KalshiTrader` | Lines 56–1378 | RSA-signed execution, balance, positions, order placement |
| **Coinbase L2 Orderbook** | `backend/btc/data_fetcher.py` | `get_coinbase_orderbook_imbalance`| Lines 874–922 | Level 2 book bid/ask wall volume and imbalance ratio |
| **Liquidation Stream** | `backend/btc/liquidation_stream.py`| `_binance_force_order_stream` | Lines 29–55 | WebSocket feed for rolling 15m long/short liquidations |
| **FinBERT NLP Engine** | `backend/btc/news_fetcher.py` | `_get_finbert` | Lines 26–42 | DistilRoBERTa financial news sentiment pipeline |
| **Kalshi Fee Calculations**| `backend/btc/fees.py` | `kalshi_order_fee` | Lines 12–20 | 7% taker fee schedule and net PnL accounting |
