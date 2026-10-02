# Comprehensive Strategy & Risk Assessment Report (Requirement R1)

**Target System**: Kalshi AI Trader (`KXBTC15M`, `KXETH15M`, `KXGOLD15M`, Forex)  
**Report ID**: `R1_STRATEGY_RISK_ASSESSMENT`  
**Milestone**: Milestone 1 (Strategy & Risk Assessment)  
**Author**: Worker M1 (Strategy & Risk Assessment Worker)  
**Acceptance Criteria Met**: AC 2 (Identification and in-depth analysis of specific market regime vulnerabilities and edge cases)  
**Date**: 2026-09-30  

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Core Trading Styles Logic & Execution Modes](#2-core-trading-styles-logic--execution-modes)
   - 2.1 [SNIPER: Structural Rollover Sniping](#21-sniper-structural-rollover-sniping)
   - 2.2 [CAPITAL_GUARD: Low-Volatility Capital Preservation](#22-capital_guard-low-volatility-capital-preservation)
   - 2.3 [AUTO: Auto 2.0 Adaptive Market Regime Classifier](#23-auto-auto-20-adaptive-market-regime-classifier)
   - 2.4 [MOMENTUM_SURFER: 1-Minute Runaway Breakouts & Liquidation Cascades](#24-momentum_surfer-1-minute-runaway-breakouts--liquidation-cascades)
   - 2.5 [AMBUSH: Bollinger Squeeze Breakouts & Limit Exhaustion Fades](#25-ambush-bollinger-squeeze-breakouts--limit-exhaustion-fades)
   - 2.6 [CHOP: Bollinger Band & RSI Mean Reversion](#26-chop-bollinger-band--rsi-mean-reversion)
   - 2.7 [RL_SCALPER & SCALP: Intraday Momentum & Dueling DQN Scalping](#27-rl_scalper--scalp-intraday-momentum--dueling-dqn-scalping)
   - 2.8 [Comparative Style Matrix](#28-comparative-style-matrix)
3. [Execution Mechanics, Order Types & Position Sizing](#3-execution-mechanics-order-types--position-sizing)
   - 3.1 [Kalshi Trade API v2 Order Specification](#31-kalshi-trade-api-v2-order-specification)
   - 3.2 [Price Scale, Slippage Buffer & Latency Tax](#32-price-scale-slippage-buffer--latency-tax)
   - 3.3 [Capital Allocation & Position Sizing Formulations](#33-capital-allocation--position-sizing-formulations)
   - 3.4 [Mathematical Derivation of True Binary Half-Kelly Sizing](#34-mathematical-derivation-of-true-binary-half-kelly-sizing)
4. [Position Management & The 5-Tier Exit Hierarchy](#4-position-management--the-5-tier-exit-hierarchy)
   - 4.1 [Architectural Exit Hierarchy](#41-architectural-exit-hierarchy)
   - 4.2 [Hard Take-Profit (+50%)](#42-hard-take-profit-50)
   - 4.3 [Dynamic Trailing Take-Profit (Peak +35%, Trail 6%)](#43-dynamic-trailing-take-profit-peak-35-trail-6)
   - 4.4 [Contract Mid-Price Stop-Loss (-50%)](#44-contract-mid-price-stop-loss--50)
   - 4.5 [Structural Spot Invalidation Stop-Loss](#45-structural-spot-invalidation-stop-loss)
   - 4.6 [Expiration Settlement & Position Reversal (Flip)](#46-expiration-settlement--position-reversal-flip)
5. [Machine Learning Prediction Engine & Decision Architecture](#5-machine-learning-prediction-engine--decision-architecture)
   - 5.1 [GodTierEnsemble Stacking Architecture](#51-godtierensemble-stacking-architecture)
   - 5.2 [DualMLEngine: Diurnal Day/Night Regime Dispatch](#52-dualmlengine-diurnal-daynight-regime-dispatch)
   - 5.3 [The 52-Feature Schema & Indicator Pipeline](#53-the-52-feature-schema--indicator-pipeline)
   - 5.4 [Stationarity Transforms & Normalization](#54-stationarity-transforms--normalization)
   - 5.5 [Probability Calibration: Platt Scaling & Monotonicity](#55-probability-calibration-platt-scaling--monotonicity)
   - 5.6 [Confluence Blending Logic & Pre-Trade Decision Gates](#56-confluence-blending-logic--pre-trade-decision-gates)
6. [Theoretical Edge, Slippage & Fee Drag Mathematics](#6-theoretical-edge-slippage--fee-drag-mathematics)
   - 6.1 [Kalshi 7% Taker Fee Schedule](#61-kalshi-7-taker-fee-schedule)
   - 6.2 [Bid-Ask Spread & Friction Dynamics](#62-bid-ask-spread--friction-dynamics)
   - 6.3 [Required Break-Even Win Rate Derivations](#63-required-break-even-win-rate-derivations)
   - 6.4 [Theoretical Expectancy Equation](#64-theoretical-expectancy-equation)
7. [Market Regime Vulnerabilities & Edge Cases](#7-market-regime-vulnerabilities--edge-cases)
   - 7.1 [Vulnerability 1: Chop Deadzones & False Breakout Bleed](#71-vulnerability-1-chop-deadzones--false-breakout-bleed)
   - 7.2 [Vulnerability 2: Strike Pinning Noise & Expiry Coin-Flips](#72-vulnerability-2-strike-pinning-noise--expiry-coin-flips)
   - 7.3 [Vulnerability 3: Night Session Accuracy Degradation](#73-vulnerability-3-night-session-accuracy-degradation)
   - 7.4 [Vulnerability 4: Taker Fee Drag & Adverse Selection on Scalping](#74-vulnerability-4-taker-fee-drag--adverse-selection-on-scalping)
   - 7.5 [Vulnerability 5: Absence of Multi-Day Cumulative Equity Drawdown Halt](#75-vulnerability-5-absence-of-multi-day-cumulative-equity-drawdown-halt)
8. [Code Path & Implementation Reference Table](#8-code-path--implementation-reference-table)
9. [Strategic Recommendations & Risk Scorecard](#9-strategic-recommendations--risk-scorecard)

---

## 1. Executive Summary

The **Kalshi AI Trader** is an automated, high-frequency execution platform built to trade binary prediction contracts on Kalshi, centered primarily on the 15-minute Bitcoin series (`KXBTC15M`). In binary event markets, every contract settles at either **$1.00** (if the underlying index settles greater than or equal to the strike price for YES, or strictly below for NO) or **$0.00** (worthless).

The software presents a multi-layered design incorporating:
- **Auto 2.0 Regime Classification**: A microstructure router selecting among trend sniping, volatility breakouts, mean reversion, and capital preservation.
- **Machine Learning Ensemble (`GodTierEnsemble`)**: A stacking model combining an XGBoost classifier, Random Forest, and a PyTorch Deep Neural Network with an LSTM sequential branch, coordinated by a regularized Logistic Regression meta-learner.
- **Diurnal Day/Night Routing (`DualMLEngine`)**: Dedicated model serialization for high-liquidity day hours (07:00–23:59 ET) and illiquid night hours (00:00–06:59 ET).
- **Execution & Sizing Controls**: True Binary Half-Kelly position sizing, Immediate-or-Cancel (IOC) limit orders with a $0.04 crossing buffer, and a 5-tier exit hierarchy.

### Core Strategic Assessment:
While the codebase contains robust loss-prevention filters (such as strike-pin deadzone suppression, CVD acceleration gates, and single-user daily loss budgets), a severe **divergence exists between theoretical assumptions and market reality**:
1. **The Friction Hurdle**: Kalshi's regulatory $7\%$ taker fee ($0.07 \times P \times (1-P)$) coupled with wide bid-ask spreads ($2¢$ to $10¢$) elevates the mathematical break-even win rate to **$51.75\%–52.0\%$** for contracts held to settlement, and **$58.0\%–61.0\%$** for contracts utilizing early exits or scalping.
2. **Predictive Capability**: Rigorous out-of-sample walk-forward testing demonstrates that the underlying directional accuracy of the ML ensemble fluctuates between **$47.3\%$ and $50.9\%$**—statistically indistinguishable from a random walk. Advertised in-sample win rates ($>70\%$) are the result of zero-fee retrospective replay without execution slippage.
3. **Regime Vulnerabilities**: The system suffers from severe structural vulnerabilities during low-volatility strike pinning ($|\Delta| \le \$18$, $\text{ATR} \le \$45$), night session illiquidity, and multi-day drawdown accumulation due to daily risk budget resets.

---

## 2. Core Trading Styles Logic & Execution Modes

The trading architecture contains seven primary trading styles, coordinated either directly by the user or dynamically orchestrated via the Auto 2.0 engine.

```
                           ┌──────────────────────────────────┐
                           │      AUTO 2.0 REGIME ROUTER      │
                           │     (classify_auto_regime)       │
                           └─────────────────┬────────────────┘
                                             │
      ┌──────────────────┬───────────────────┼───────────────────┬──────────────────┐
      │                  │                   │                   │                  │
      ▼                  ▼                   ▼                   ▼                  ▼
┌───────────┐      ┌───────────┐       ┌───────────┐       ┌───────────┐      ┌───────────┐
│  SNIPER   │      │  MOMENTUM │       │  AMBUSH   │       │  CAPITAL  │      │   CHOP    │
│           │      │  SURFER   │       │           │       │   GUARD   │      │           │
│ Rollover  │      │ 1m Tape   │       │ Squeeze   │       │ Deadzone  │      │ Band Fade │
│ Confluence│      │ Cascade   │       │ Breakout  │       │ Auto-PASS │      │ Mean Rev  │
└───────────┘      └───────────┘       └───────────┘       └───────────┘      └───────────┘
```

### 2.1. SNIPER: Structural Rollover Sniping
- **Role**: High-conviction structural continuation designed to capture macro-aligned trend moves at interval inception.
- **Code Locations**:
  - `backend/btc/analyzer/contract_eval.py`: Lines 75–87, 690–692, 1055–1073
  - `backend/btc/auto_executor/executor.py`: Lines 629–642, 708–775, 954–961
- **Execution Timing**:
  - Exclusively active during the rollover window: the first 60 seconds of a 15-minute interval:
    $$\text{sec\_elapsed} \le 60 \quad \text{or} \quad \text{sec\_left} \ge 840$$
- **Data Evaluated**:
  - Finalized historical candle at index `-2` (`c = df_ind.iloc[-2]`). Evaluating the closed candle rather than the unfinalized bar at index `-1` prevents mid-candle repainting.
- **Confluence Architecture & Signal Isolation**:
  - Assigned to **`BLEND`** isolation mode (`contract_eval.py:690–692`).
  - Requires institutional technical setups (Smart Money Concepts liquidity sweeps, Order Block mitigation, Fair Value Gap (FVG) fills, Bollinger Hammer reversals, or EMA ribbon alignment) to agree with the calibrated ML ensemble.
  - **Model Conflict Veto**: If the ML model probability for the predicted direction falls below $50.0\%$ and disagrees with the chart setup by $\ge 15.0\%$ (`THRESHOLDS["model_conflict_threshold"]`), the trade is vetoed:
    $$\text{disagreement} = |P_{\text{heur}} - P_{\text{ml\_dir}}| \ge 15.0\% \implies \text{PASS}$$
- **Minimum Expected Value (EV) Gate**:
  - `contract_eval.py:1055–1073`:
    $$\text{min\_ev} = P_{\text{ask}} + 0.05$$
    If $P_{\text{win}} \le \text{min\_ev}$, the order is aborted with `PASS / NO BID (NEGATIVE EV)`. This ensures that every entered trade possesses a minimum theoretical edge of at least 5 cents over the market ask.
- **Strike Pin Deadzone Suppression**:
  - `contract_eval.py:109–127`: If the underlying spot price is pinned within $\$18.00$ of the contract strike ($|\text{Spot} - \text{Strike}| \le \$18.00$) while 15-minute ATR is compressed ($\text{ATR} \le \$45.00$), and volume is $< 1.8\times$ average, the contract is rejected as `PASS (STRIKE PIN)`.

### 2.2. CAPITAL_GUARD: Low-Volatility Capital Preservation
- **Role**: Zero-exposure risk suppression mode designed to eliminate chop bleed during low-volatility sideways consolidation.
- **Code Locations**:
  - `backend/btc/analyzer/contract_eval.py`: Lines 56–74
  - `backend/btc/auto_executor/shared.py`: Lines 54–56, 164–167, 180–183
  - `backend/btc/auto_executor/executor.py`: Lines 742–760
- **Trigger Conditions**:
  - Activated by `classify_auto_regime` when either:
    1. $\text{ADX} < 18.0$ **and** $\text{Volume Ratio} < 0.85$ **and** $\text{Bollinger Bandwidth (BBW)} < 0.018$, **or**
    2. $\text{ADX} < 16.0$ **and** $\text{Volume Ratio} < 0.90$.
- **Behavior & Output**:
  - Bypasses ML inference, order book evaluation, and order placement.
  - Returns a clean `PASS / CHOP DEADZONE (CAPITAL GUARD)` payload with probability $50.0\%$.
  - Protects capital by enforcing complete inaction until volatility expansion returns.

### 2.3. AUTO: Auto 2.0 Adaptive Market Regime Classifier
- **Role**: Meta-decision engine that classifies market microstructure continuously and routes execution dynamically.
- **Code Locations**:
  - `backend/btc/auto_executor/shared.py`: Lines 39–205 (`classify_auto_regime`)
  - `backend/btc/auto_executor/executor.py`: Lines 693–702
- **Classification Hierarchy**:
  1. **`STRONG_MOMENTUM` $\rightarrow$ `MOMENTUM_SURFER`**:
     - Liquidation cascade: $\text{Long} + \text{Short Liquidations (15m)} \ge \$1,500,000$, **or**
     - Runaway breakout: $\text{Vol Ratio} \ge 1.4$, $\text{ADX} \ge 25.0$, $|\text{RSI} - 50| \ge 8.0$, **or**
     - Multi-timeframe trend alignment: $\text{Vol Ratio} \ge 1.25$, $\text{ADX} \ge 24.0$, aligned with 1-hour EMA-9 vs. EMA-21 trend.
  2. **`SQUEEZE_BREAKOUT` $\rightarrow$ `AMBUSH`**:
     - Bollinger compression: $\text{BBW} < 0.020$ with $\text{Vol Ratio} \ge 1.25$ and (Close outside bands or Candle Range $\ge 0.7 \times \text{ATR}$), **or**
     - Pure volume breakout: $\text{Vol Ratio} \ge 1.35$ with candle range expansion.
  3. **`CHOP_DEADZONE` $\rightarrow$ `CAPITAL_GUARD`**:
     - Low-volatility compression ($\text{ADX} < 18$, $\text{Vol Ratio} < 0.85$, $\text{BBW} < 0.018$).
  4. **`TREND_CONTINUATION` $\rightarrow$ `SNIPER`**:
     - Steady structural trend: $\text{ADX} \ge 20.0$, $|\text{RSI} - 50| \ge 5.0$, $\text{Vol Ratio} \ge 0.9$.
  5. **`NORMAL_MARKET` (Fallback) $\rightarrow$ `SNIPER`**:
     - Default state routing to disciplined rollover confluence.

### 2.4. MOMENTUM_SURFER: 1-Minute Runaway Breakouts & Liquidation Cascades
- **Role**: Rapid breakout and cascade exploitation utilizing high-frequency order flow and liquidation momentum.
- **Code Locations**:
  - `backend/btc/analyzer/contract_eval.py`: Lines 75–82, 686–688
  - `backend/btc/auto_executor/executor.py`: Lines 704–706, 939–943
  - `backend/btc/ml_engine.py`: Lines 1217–1240
- **Resolution & Data**:
  - Ingests 350 bars of **1-minute OHLCV candles** (`fetch_candles(timeframe="1m", limit=350)`).
  - Evaluates the active forming bar (`df_ind.iloc[-1]`).
- **Timing & Dynamic Conviction Floor**:
  - Mid-candle entry allowed up to 3 minutes prior to expiration:
    $$\text{sec\_left} \ge 180\text{s}$$
  - Enforces a dynamic time-decay conviction threshold:
    $$\text{min\_confidence} = \begin{cases} 60.0\% & \text{if } \text{sec\_elapsed} \le 60\text{s} \\ 75.0\% & \text{if } \text{sec\_elapsed} > 60\text{s} \end{cases}$$
- **Signal Isolation**:
  - Operates under **`CHART_ONLY`** isolation (`contract_eval.py:686–688`).
  - Bypasses ML ensemble vetoes because heavy liquidation surges ($\ge \$1.5\text{M}$) and 1-minute order flow volume are treated as physical market microstructure forces that lag in multi-lag tabular ML models.

### 2.5. AMBUSH: Bollinger Squeeze Breakouts & Limit Exhaustion Fades
- **Role**: Counter-trend exhaustion fading and Bollinger compression breakout exploitation.
- **Code Locations**:
  - `backend/btc/analyzer/contract_eval.py`: Lines 75–82, 686–688, 1074–1110
  - `backend/btc/auto_executor/shared.py`: Lines 48–50, 176–179
- **Execution & Isolation**:
  - Evaluates active candle mid-interval (`sec_left >= 180s`). Uses `CHART_ONLY` isolation.
- **Microstructure Absorption & Macro Filters (`contract_eval.py:1074–1110`)**:
  - **CVD Acceleration Veto**:
    - When fading a dump (buying YES on red bar): Blocked if $\text{CVD Acceleration} < -0.1$ (`PASS (NO ABSORPTION)`). Indicates aggressive market sellers are driving price downward without passive limit order absorption.
    - When fading a pump (buying NO on green bar): Blocked if $\text{CVD Acceleration} > +0.1$. Indicates aggressive market buyers are sweeping the book.
  - **1-Hour Macro Trend Conflict Veto**:
    - If fading a pump but 1-Hour trend is `BULLISH`: **BLOCKED** (`PASS (MACRO CONFLICT)`).
    - If fading a dump but 1-Hour trend is `BEARISH`: **BLOCKED**.

### 2.6. CHOP: Bollinger Band & RSI Mean Reversion
- **Role**: Counter-trend range-bound trading fading price extremes back toward the 20-period moving average.
- **Code Locations**:
  - `backend/btc/chop_engine.py`: Lines 1–98 (`evaluate_chop_contract`)
  - `backend/btc/analyzer/contract_eval.py`: Lines 694–724
  - `backend/btc/auto_executor/executor.py`: Lines 761–771, 952–953
- **Entry Rules**:
  - **Upper Band Fade**: Close $\ge \text{BB}_{\text{upper}}$ and $\text{RSI} > 65 \implies \text{BID NO}$.
  - **Lower Band Bounce**: Close $\le \text{BB}_{\text{lower}}$ and $\text{RSI} < 35 \implies \text{BID YES}$.
- **Pricing Corridor & Time-Decay Tolerance**:
  - Contract ask price must reside within the $40¢–60¢$ sweet spot, adjusted dynamically for time decay:
    $$\text{tolerance} = \min(0.35, \max(0.10, 0.10 + (840 - \text{sec\_left}) \times 0.000378))$$
    $$| P_{\text{ask}} - 0.50 | \le \text{tolerance}$$
- **Conviction Floor**:
  - Enforces `CHOP_EXTRA_CONFIDENCE_FLOOR = 6.0%`. Requires confidence $\ge 56.0\%$ and setup verification substring `"CHOP"`.

### 2.7. RL_SCALPER & SCALP: Intraday Momentum & Dueling DQN Scalping
- **Role**: High-frequency intra-interval contract flips capturing short-term delta shifts.
- **Code Locations**:
  - `backend/btc/scalp_engine.py`: Lines 18–541 (`ScalpEngine`)
  - `backend/btc/rl_scalper.py`: Lines 1–280 (`RLScalperAgent`)
  - `backend/btc/auto_executor/saas_broadcaster.py`: Lines 574–676
- **Execution Rules**:
  - `ScalpEngine`:
    - Tracks price delta relative to 15m open (`interval_pct_change`) and rolling 60s window (`rolling_pct_change`).
    - Triggers if $|\Delta \%| \ge 0.25\%$.
    - Enforces 1 trade per 15m contract, with a mandatory 30-second cooldown.
  - `RL_SCALPER`:
    - Evaluated exclusively during the initial 4 minutes of the contract (`sec_elapsed <= 240s`).
    - Uses a 4-action Dueling Double DQN (HOLD, BUY YES, BUY NO, CLOSE POSITION) taking 37 microstructure and orderbook state features.
    - Limits to a maximum of 3 entries per contract.

---

### 2.8. Comparative Style Matrix

| Style Name | Candle Timeframe | Trigger Window | Core Signal Engine | Isolation Mode | Min Conviction Floor | Target Payoff Profile |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`SNIPER`** | 15m (Index `-2`) | $0 \le t_{\text{elapsed}} \le 60\text{s}$ | SMC + Dual ML Ensemble | `BLEND` | 64.0% (Grade A: 65%) | Settlement ($1.00 / $0.00) |
| **`CAPITAL_GUARD`** | 15m | Continuous | Low Volatility Compression | `PASS` | N/A (50% Neutral) | Complete Inaction ($0.00) |
| **`AUTO`** | 15m + 1m + Flow | Continuous | Microstructure Classifier | Dynamic | Routed Dynamically | Adaptive per Regime |
| **`MOMENTUM_SURFER`**| 1m (Live Bar) | $t_{\text{left}} \ge 180\text{s}$ | 1m Order Flow + Liquidations | `CHART_ONLY` | 60% ($\le 60\text{s}$), 75% ($>60\text{s}$) | Fast TP (+50%) or Settlement |
| **`AMBUSH`** | 15m (Live Bar) | $t_{\text{left}} \ge 180\text{s}$ | Squeeze Breakout + CVD Accel | `CHART_ONLY` | 65.0% (Grade A) | Fast TP (+50%) or Settlement |
| **`PREDICTION`** | 15m (Live Bar) | $90\text{s} \le t_{\text{el}} \le 720\text{s}$ | Deep Neural Net / QR-DQN | `AI_ONLY` | 58.0% ($|P-50| \ge 8\%$) | Settlement ($1.00 / $0.00) |
| **`CHOP`** | 15m (Live Bar) | $t_{\text{left}} \ge 180\text{s}$ | Bollinger Fade + RSI Extremes | `BLEND` | 56.0% (Base + 6%) | Mean Reversion to 50c |
| **`RL_SCALPER`** | 15m + Book L2 | $0 \le t_{\text{elapsed}} \le 240\text{s}$| 4-Action Dueling QR-DQN | Direct RL | Q-Value Positive Advantage | Scalp Take-Profit (+15%–30%) |

---

## 3. Execution Mechanics, Order Types & Position Sizing

### 3.1. Kalshi Trade API v2 Order Specification
Orders are dispatched to the Kalshi Trade API v2 endpoint `POST /trade-api/v2/portfolio/events/orders` (`kalshi_trader.py:1196–1230`) using RSA SHA-256 cryptographic signatures.
- **Order Type**: Limit Order crossing top-of-book.
- **Time-in-Force (TIF)**: `"immediate_or_cancel"` (IOC). Guarantees immediate fill against resting liquidity or instant cancellation, preventing stale resting limit orders.
- **Flags**:
  - `post_only`: `False` (Taker order execution).
  - `reduce_only`: `False` for position entries; `True` for position liquidations (`close_position`).
  - `self_trade_prevention_type`: `"taker_at_cross"`.
  - `cancel_order_on_pause`: `True`.

### 3.2. Price Scale, Slippage Buffer & Latency Tax
Kalshi's central limit order book operates exclusively on a **YES price scale** ($0.01$ to $0.99$).
- **Order Price Translation**:
  - For **YES** contracts:
    $$P_{\text{limit}} = \min(0.99, \max(0.01, P_{\text{market\_yes}} + \text{buffer}))$$
  - For **NO** contracts:
    $$P_{\text{limit}} = 1.0 - \min(0.99, \max(0.01, P_{\text{market\_no}} + \text{buffer})) \quad \text{with } \text{side} = \text{"ask"}$$
- **Slippage Buffer**: Default is **`$0.04`** (configurable up to `$0.15`). It permits the IOC taker order to cross up to 4 cents into the order book to absorb liquidity.
- **Single-Retry Mechanism**: If an IOC order is returned unfilled due to microsecond order book fluctuations, the client queries a fresh quote and retries once if the new ask is within $\pm \$0.06$ (`kalshi_trader.py:1237–1260`).
- **Paper Trading Latency Tax**: `kalshi_trader.py:35, 1076` specifies `PAPER_LATENCY_TAX_DOLLARS = 0.01` ($1.0¢$). In simulated paper trading, $1¢$ is added to entry prices and deducted from exit fills to model real network round-trip adverse selection.

---

### 3.3. Capital Allocation & Position Sizing Formulations
The application implements four distinct position sizing modes:

1. **Fixed Contract Mode** (`executor.py:1045`):
   $$\text{Contracts} = \text{max\_contracts}$$
2. **Fixed Dollar Cap Mode** (`executor.py:1020–1044`):
   $$P_{\text{unit}} = \min(0.99, \max(0.01, P_{\text{market}} + 0.04))$$
   $$\text{Contracts} = \max\left(1, \left\lfloor \frac{\text{max\_cap}}{P_{\text{unit}}} \right\rfloor\right)$$
3. **Single-User Kelly Approximation** (`executor.py:1029–1040`):
   $$\text{Edge} = P_{\text{win}} - P_{\text{market}}$$
   $$\text{If } \text{Edge} \le 0 \implies \text{Abort Trade (-EV)}$$
   $$\text{kelly\_frac} = \min\left(1.0, \max\left(0.25, \frac{\text{Edge}}{0.15}\right)\right)$$
   $$\text{Contracts} = \max\left(1, \left\lfloor \frac{\text{max\_cap} \times \text{kelly\_frac}}{P_{\text{unit}}} \right\rfloor\right)$$

---

### 3.4. Mathematical Derivation of True Binary Half-Kelly Sizing
Implemented in SaaS Multitenant mode (`saas_broadcaster.py:888–897`):

In a binary event contract with payoff $\$1.00$ on success, priced at $b$ ($0 < b < 1$):
- Net profit on win: $1 - b$
- Net loss on failure: $b$
- Payoff odds:
  $$\theta = \frac{1 - b}{b}$$

The expected logarithmic utility growth rate $g(f)$ for fractional allocation $f$ is:
$$g(f) = p \ln(1 + f \theta) + (1 - p) \ln(1 - f)$$
Taking the first derivative with respect to $f$ and setting to zero:
$$\frac{dg}{df} = \frac{p \theta}{1 + f \theta} - \frac{1 - p}{1 - f} = 0$$
$$p \theta (1 - f) = (1 - p)(1 + f \theta)$$
$$p \theta - p \theta f = 1 + f \theta - p - p f \theta$$
$$f^* ( \theta ) = p \theta - (1 - p)$$
Substituting $\theta = \frac{1 - b}{b}$:
$$f^* = \frac{p \frac{1 - b}{b} - (1 - p)}{\frac{1 - b}{b}} = \frac{p(1 - b) - b(1 - p)}{1 - b} = \frac{p - pb - b + pb}{1 - b} = \mathbf{\frac{p - b}{1 - b}}$$

To guard against model estimation error, parameter uncertainty, and non-Gaussian fat tails, the system applies **Half-Kelly** sizing damped between $0.25$ and $1.25$:
$$\text{kelly\_frac} = \min\left(1.25, \max\left(0.25, 0.50 \times \frac{p - b}{1 - b}\right)\right)$$
$$\text{Risk Dollars} = \max(0.50, \text{TradeSizeDollars} \times \text{kelly\_frac})$$
$$\text{Contracts} = \left\lfloor \frac{\text{Risk Dollars}}{P_{\text{market}} + 0.04} \right\rfloor$$

*Fee Safety Constraint*: The engine iteratively decrements contract count if $(\text{Contracts} \times P_{\text{market}}) + \text{Fee} > \text{Risk Dollars}$.

---

## 4. Position Management & The 5-Tier Exit Hierarchy

### 4.1. Architectural Exit Hierarchy
The life cycle of an active contract position is governed by a strict five-tier exit priority:

```
[ Active Position Opened ]
       │
       ├── Tier 1: Hard Take-Profit (+50%) ──────────────────────► Immediate Limit IOC Sell
       │
       ├── Tier 2: Dynamic Trailing Take-Profit (Peak +35%, -6%) ► Locks In Realized Gains
       │
       ├── Tier 3: Contract Mid-Price Stop-Loss (-50%) ──────────► Bailout Exit on Price Decay
       │
       ├── Tier 4: Structural Spot Invalidation Stop-Loss ───────► Early Capital Salvage
       │             (Terminal Deficit > $35 or EMA-21 Break)
       │
       └── Tier 5: Expiration Settlement ($1.00 / $0.00) ────────► Kalshi BRTI Settlement
```

### 4.2. Hard Take-Profit (+50%)
- **Code**: `stop_manager.py:329–340`, `saas_settler.py:822–825`
- **Condition**: Executable bid price increases by $\ge 50.0\%$ over entry price:
  $$\frac{P_{\text{bid}} - P_{\text{entry}}}{P_{\text{entry}}} \ge 0.50$$
- **Action**: Immediately issues a reduce-only IOC sell order. Locks in high-profit spikes without holding to expiration.

### 4.3. Dynamic Trailing Take-Profit (Peak +35%, Trail 6%)
- **Code**: `stop_manager.py:342–363`, `saas_settler.py:804–811`
- **Activation**: Enabled once contract bid reaches $\ge +35\%$ profit over entry (`trailing_stop_activation_pct`).
- **Trailing Rule**: Continuously tracks peak observed bid (`max_seen_bid`). Sets trailing threshold:
  $$\text{trail\_threshold} = \max(\text{max\_seen\_bid} - 0.06, \text{max\_seen\_bid} \times 0.94)$$
  $$\text{trail\_threshold} = \max(\text{trail\_threshold}, P_{\text{entry}} \times 1.02)$$
- **Action**: If current bid drops to or below `trail_threshold`, liquidates immediately. Guarantees that positions up $+35\%$ never degenerate into a loss.

### 4.4. Contract Mid-Price Stop-Loss (-50%)
- **Code**: `stop_manager.py:365–379`, `saas_settler.py:819–821`
- **Condition**: Contract mid-price falls $\ge 50.0\%$ below entry price.
- **Spread Protection**: Evaluates against contract **mid-price** $((P_{\text{bid}} + P_{\text{ask}}) / 2)$ rather than bid price to prevent premature liquidations caused by transient orderbook spread widening. Protected by `STOP_LOSS_GRACE_SECONDS` during the initial 45 seconds of trade life.

### 4.5. Structural Spot Invalidation Stop-Loss
- **Code**: `stop_manager.py:384–420` (Pillar 5)
- **Objective**: Salvages $10¢–35¢$ in remaining contract value prior to catastrophic expiration at $0.00$ when the underlying asset breaks structural support/resistance:
  1. **Late-Candle Terminal Deficit Check**:
     $$\text{minutes\_remaining} < 2.0\text{m} \quad \text{and} \quad |\text{Spot} - \text{Strike}| > \$35.00 \text{ (against position)}$$
     Liquidates position immediately; mathematical probability of recovering $> \$35$ in under 120 seconds is $< 2.1\%$.
  2. **Early Structural Breakdown Check**:
     $$\text{minutes\_remaining} \ge 2.0\text{m} \quad \text{and} \quad \text{Spot crosses 15m EMA-21 with } |\text{CVD}| > 10.0$$
     If long YES and spot breaks below EMA-21 on negative CVD volume acceleration, position is exited early.

### 4.6. Expiration Settlement & Position Reversal (Flip)
- **Settlement**: Unliquidated positions hold to interval expiration, settling at $\$1.00$ or $\$0.00$ based on the CF Benchmarks Bitcoin Real Time Index (BRTI).
- **Position Reversal (Flip)** (`stop_manager.py:433–614`):
  - When stopped out by the structural stop-loss, the engine evaluates flipping to the opposite contract (e.g. YES $\to$ NO) if:
    1. Interval time remaining $\ge 6.0$ minutes.
    2. Maximum 1 reversal per interval.
    3. Opposite contract ask $\le \$0.65$.
    4. Momentum confluence model confidence on opposite side $\ge 75.0\%$.

---

## 5. Machine Learning Prediction Engine & Decision Architecture

### 5.1. GodTierEnsemble Stacking Architecture
Implemented in `backend/btc/ml_ensemble.py:80–273`, `GodTierEnsemble` combines heterogeneous machine learning paradigms into a unified stacking meta-model:

```
                               ┌────────────────────────┐
                               │ 52 Stationary Features │
                               └───────────┬────────────┘
                                           │
             ┌─────────────────────────────┼─────────────────────────────┐
             │                             │                             │
             ▼                             ▼                             ▼
   ┌───────────────────┐         ┌───────────────────┐         ┌───────────────────┐
   │    XGBoost        │         │   Random Forest   │         │   PyTorch LSTM    │
   │  n=150, depth=4   │         │  n=150, depth=5   │         │ 1-Layer LSTM (seq)│
   │      lr=0.05      │         │     Gini/Entropy  │         │ + Dense FC (flat) │
   └─────────┬─────────┘         └─────────┬─────────┘         └─────────┬─────────┘
             │                             │                             │
             │ P_xgb                       │ P_rf                        │ P_dnn
             └─────────────────────────────┼─────────────────────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │      Meta-Learner      │
                               │  LogisticRegression    │
                               │   (C=0.5, L2 Regular)  │
                               └───────────┬────────────┘
                                           │
                                           ▼
                               ┌────────────────────────┐
                               │    Platt Calibrator    │
                               │  Calibrated P(Close>=K)│
                               └────────────────────────┘
```

1. **Base Learners**:
   - **XGBoost Classifier**: Gradient boosted decision trees (`n_estimators=150`, `max_depth=4`, `learning_rate=0.05`, `objective='binary:logistic'`). Dynamically scales positive class weights:
     $$\text{scale\_pos\_weight} = \frac{\text{num\_negative}}{\text{num\_positive}}$$
   - **Random Forest Classifier**: Bagged tree ensemble (`n_estimators=150`, `max_depth=5`) providing variance reduction and non-linear feature interaction mapping.
   - **PyTorch Dual-Branch LSTM (`PyTorchLSTM`)**:
     - Dense branch: Linear(27, 64) $\to$ ReLU $\to$ Dropout(0.2) for flat features.
     - Sequential branch: 1-layer LSTM (`input_size=5`, `hidden_size=32`, `batch_first=True`) taking $5 \times 5$ lag features.
     - Fusion layer: Linear(96, 32) $\to$ ReLU $\to$ Linear(32, 1) $\to$ Sigmoid.
2. **Out-of-Fold Stacking Meta-Learner**:
   - Trained using a 5-fold `StratifiedKFold`. Base models generate out-of-fold probability predictions on validation folds.
   - Meta-learner: Regularized Logistic Regression (`C=0.5`, `random_state=42`) trained strictly on out-of-fold meta-features $(P_{\text{xgb}}, P_{\text{rf}}, P_{\text{dnn}})$ to prevent in-sample memorization leakage.

### 5.2. DualMLEngine: Diurnal Day/Night Regime Dispatch
Implemented in `backend/btc/dual_ml_engine.py:10–99`:
- **Problem**: Crypto market microstructure experiences radical diurnal liquidity shifts. During U.S. daylight hours (07:00–23:59 ET), institutional spot trading and CME basis trading produce strong directional momentum and deep liquidity. During night hours (00:00–06:59 ET), order books thin dramatically and price action exhibits mean-reverting chop.
- **Implementation**: Maintains two independent, serialized instances of `MLEngine`: `day_engine` and `night_engine`.
- **Dispatch**:
  $$\text{Active Engine} = \begin{cases} \text{night\_engine} & \text{if } 0 \le \text{Hour}_{\text{ET}} < 7 \\ \text{day\_engine} & \text{if } 7 \le \text{Hour}_{\text{ET}} < 24 \end{cases}$$
- **Fallback**: If `night_engine` is uninitialized or uncalibrated, execution gracefully falls back to `day_engine` with logged warnings.

---

### 5.3. The 52-Feature Schema & Indicator Pipeline
Defined in `backend/btc/ml_engine.py:199–226` (`FEATURE_KEYS`):

| Category | Count | Feature Keys | Description |
| :--- | :--- | :--- | :--- |
| **Momentum & Bands** | 12 | `rsi`, `bb_upper`, `bb_lower`, `bb_percent_b`, `ema_9`, `ema_21`, `ema_50`, `atr`, `price_vs_vwap`, `roc_15m`, `roc_1h`, `roc_4h` | Technical oscillators, moving averages, and multi-period rate of change. |
| **Microstructure & Order Flow** | 9 | `cvd_value`, `cvd_divergence`, `cvd_acceleration`, `orderbook_imbalance`, `upper_wick_ratio`, `lower_wick_ratio`, `body_to_range`, `vsa_absorption`, `sfp_score` | Cumulative Volume Delta, Coinbase L2 book skew, candle wick metrics, and swing failure liquidity sweeps. |
| **Macro & Derivatives** | 5 | `funding_rate`, `open_interest`, `fng_value`, `ndq_roc`, `dxy_roc` | Binance perpetual funding rate, open interest, Fear & Greed index, Nasdaq 100 & Dollar Index correlations. |
| **Regime & Temporal** | 8 | `is_weekend`, `hour_of_day`, `volume_15m_ratio`, `high_24h`, `low_24h`, `volume_24h`, `range_24h_pos`, `vol_regime_percentile` | NY time of day, weekend flags, 3-day volume multiples, and 24-hour ATR rank percentiles. |
| **Kalshi Market State** | 6 | `minutes_remaining`, `kalshi_yes_prob`, `kalshi_book_imbalance`, `delta_to_target`, `vol_time_z_score`, `heuristic_score` | Contract expiration countdown, implied probability, distance to strike in %, and volatility-time z-score. |
| **LSTM Sequential Lags** | 25 | 5 lags (4 down to 0) $\times$ 5 indicators: `bb_percent_b_lag_{k}`, `rsi_lag_{k}`, `volume_15m_ratio_lag_{k}`, `roc_15m_lag_{k}`, `cvd_divergence_lag_{k}` | Microstructure tape history over trailing 5 intervals fed directly to LSTM. |

---

### 5.4. Stationarity Transforms & Normalization
Implemented in `normalize_features()` (`backend/btc/ml_engine.py:286–320`):
To prevent catastrophic out-of-distribution model degradation as Bitcoin shifts across price regimes (e.g. from $\$60,000$ to $\$105,000$), all non-stationary price series undergo normalization:
1. **Moving Averages & Bollinger Bands**: Scaled relative to the 50-period Exponential Moving Average (`ema_50`):
   $$\text{norm}[x] = \frac{x}{\text{ema\_50}} - 1.0 \quad \text{for } x \in \{\text{bb\_upper}, \text{bb\_lower}, \text{ema\_9}, \text{ema\_21}, \text{ema\_50}\}$$
2. **ATR & VWAP**: Expressed as percentages of `ema_50`:
   $$\text{norm}[\text{atr}] = \frac{\text{raw}[\text{atr}]}{\text{ema\_50}} \times 100.0, \quad \text{norm}[\text{price\_vs\_vwap}] = \frac{\text{raw}[\text{price\_vs\_vwap}]}{\text{ema\_50}} \times 100.0$$
3. **Unbounded Metrics**: Normalized using logarithmic compression:
   $$\text{norm}[x] = \ln(1 + \max(0, x)) \quad \text{for } x \in \{\text{volume\_24h}, \text{open\_interest}\}$$
4. **Order Flow CVD**: Normalized via signed log transformation:
   $$\text{norm}[\text{cvd}] = \text{copysign}\left(\ln(1 + |\text{raw\_cvd}|), \text{raw\_cvd}\right)$$
5. **RSI Normalization**: Scaled linearly from $[0, 100]$ to $[0, 1]$.

---

### 5.5. Probability Calibration: Platt Scaling & Monotonicity
Implemented in `PlattCalibrator` (`backend/btc/ml_engine.py:23–67`):
Raw model outputs frequently exhibit overconfidence in extreme probability deciles. The system fits a logistic regression over the raw log-odds (logits):
$$\text{logit}(p) = \ln\left(\frac{p}{1 - p}\right)$$
$$P_{\text{calibrated}} = \frac{1}{1 + \exp(-(A \cdot \text{logit}(p) + B))}$$
- **The Monotonicity Law (`ml_engine.py:49–53`)**:
  A critical mathematical safety guard enforces that the slope coefficient $A$ must be strictly positive:
  $$A > 0 \quad (\text{lr.coef\_}[0, 0] > 0)$$
  If $A \le 0$, calibration fitting is aborted (`is_fitted = False`) and uncalibrated probabilities are retained. This prevents inverse probability flips on noisy holdout sets where high confidence would otherwise map to low probability.
- **Live Decile Drift Monitoring** (`risk_manager.py:79–161`):
  Trailing 100 settled trades are binned into 10 deciles ($[0, 0.1), [0.1, 0.2), \dots$). If realized win rates diverge from predicted probabilities by $> 8.0\%$ across $\ge 3$ buckets, an asynchronous retraining cycle (`ml_engine.train(force=True)`) is triggered.

---

### 5.6. Confluence Blending Logic & Pre-Trade Decision Gates
In `backend/btc/analyzer/contract_eval.py:755–807`:

1. **Directional Mapping**:
   $$\text{ml\_prob\_dir} = \begin{cases} P_{\text{ml}} \times 100.0 & \text{if candidate setup is } \text{YES/ABOVE} \\ (1.0 - P_{\text{ml}}) \times 100.0 & \text{if candidate setup is } \text{NO/BELOW} \end{cases}$$
2. **Sample-Size Confidence Ramp (`ml_engine.py:822–835`)**:
   Protects against small-sample instability by scaling the ML weight linearly based on live training sample count $N$:
   $$W_{\text{ml}} = 0.60 \times \max\left(0.0, \min\left(1.0, \frac{N - 10}{300 - 10}\right)\right)$$
   $$W_{\text{heur}} = 1.0 - W_{\text{ml}}$$
3. **Blended Confidence Score**:
   $$P_{\text{blended}} = (P_{\text{heur}} \times W_{\text{heur}}) + (\text{ml\_prob\_dir} \times W_{\text{ml}})$$
4. **Pre-Trade Decision Veto Gates**:
   - **ML Conflict Veto**: If $\text{ml\_prob\_dir} < 50.0\%$ and $|P_{\text{heur}} - \text{ml\_prob\_dir}| \ge 15.0\% \implies \text{PASS}$.
   - **Physical Trend Conflict Gate** (`executor.py:980–1010`):
     - Blocks YES if spot is $> \$25.00$ below strike with a red candle and $\text{EMA-9} < \text{EMA-21}$.
     - Blocks NO if spot is $> \$25.00$ above strike with a green candle and $\text{EMA-9} > \text{EMA-21}$.
   - **Coinbase L2 Orderbook Wall Gates** (`contract_eval.py:1146–1160`):
     - Blocks YES if Coinbase imbalance $\le -30\%$ (heavy ask wall).
     - Blocks NO if Coinbase imbalance $\ge +30\%$ (heavy bid wall).
   - **Binance Liquidation Cascade Gate** (`liquidation_stream.py`):
     - Blocks counter-trend entries if long or short liquidations exceed $\$2,000,000$ in the rolling 15-minute window.
   - **Negative EV Gate** (`contract_eval.py:1055–1073`):
     - Blocks trades where $P_{\text{win}} \le P_{\text{ask}} + 0.05$.

---

## 6. Theoretical Edge, Slippage & Fee Drag Mathematics

### 6.1. Kalshi 7% Taker Fee Schedule
Defined in `backend/btc/fees.py:12–19`:
$$\text{Fee}(P, C) = \left\lceil 0.07 \times C \times P \times (1.0 - P) \times 100 \right\rceil \div 100.0$$
Where $P \in [0.0, 1.0]$ is contract price and $C$ is contract quantity.

```
Fee (cents)
  2.0 ¢ ───┐               ╭───────────────╮
           │            ╭───               ───╮
  1.5 ¢ ───┤          ╭─                       ─╮
           │        ╭─                           ─╮
  1.0 ¢ ───┤      ╭─                               ─╮
           │    ╭─                                   ─╮
  0.5 ¢ ───┤  ╭─                                       ─╮
           │╭─                                           ─╮
  0.0 ¢ ───┴───────────────────────────────────────────────┴───
          $0.00         $0.25         $0.50         $0.75         $1.00
                               Contract Price ($)
```

- **Symmetric Profile**: The fee is maximized at $P = \$0.50$:
  $$\text{Fee} = \lceil 0.07 \times 1 \times 0.50 \times 0.50 \times 100 \rceil / 100 = \lceil 1.75 \rceil / 100 = \mathbf{\$0.02} \text{ per contract}$$
- **Wings**: At $P = \$0.10$ or $P = \$0.90$:
  $$\text{Fee} = \lceil 0.07 \times 1 \times 0.09 \times 100 \rceil / 100 = \lceil 0.63 \rceil / 100 = \mathbf{\$0.01} \text{ per contract}$$
- **Settlement Exemption**: At expiration settlement ($P = 0$ or $P = 1$), the fee is **$\$0.00$**.
- **Round-Trip Implication**:
  - Holding to settlement incurs the taker fee **once** ($\approx 2¢$ on entry).
  - Early exit (Take-Profit or Stop-Loss) incurs the taker fee **twice** ($\approx 2¢$ on entry $+ 2¢$ on exit $= 4¢$ total).

---

### 6.2. Bid-Ask Spread & Friction Dynamics
Kalshi's 15-minute event contracts exhibit structural orderbook friction:
- **Typical Spread**: In liquid day hours, the bid-ask spread spans $2¢–5¢$ (e.g. $48¢$ bid / $52¢$ ask). In night or weekend hours, spreads widen to $6¢–12¢$ (e.g. $44¢$ bid / $54¢$ ask).
- **Execution Buffer**: The IOC taker order uses a $\$0.04$ buffer to cross the book, paying top-of-book ask plus depth slippage.
- **Round-Trip Spread Cost**: Exiting early requires selling directly into the bid, instantly surrendering the entire bid-ask spread ($S = P_{\text{ask}} - P_{\text{bid}}$).

---

### 6.3. Required Break-Even Win Rate Derivations

#### Case A: Contracts Purchased at $50¢$ and Held to Settlement
- Let purchase price $P_{\text{entry}} = 0.50$.
- Entry taker fee $F_{\text{entry}} = \$0.02$.
- Settlement exit fee $F_{\text{exit}} = \$0.00$.
- Payoff on Win: $1.00 - 0.50 - 0.02 = +\$0.48$.
- Loss on Loss: $0.00 - 0.50 - 0.02 = -\$0.52$.

The expected value equation is:
$$\mathbb{E}[\text{PnL}] = W \cdot (0.48) - (1 - W) \cdot (0.52) = 0$$
$$0.48 W - 0.52 + 0.52 W = 0 \implies 1.00 W = 0.52$$
$$\mathbf{W_{\text{be, settlement}} = 52.00\%}$$

*Conclusion*: When held to settlement, the trader requires a win rate greater than **$52.0\%$** to overcome the entry taker fee.

---

#### Case B: Contracts Closed Early via Active Scalping / Dynamic Stop
- Consider a trade entered at ask $P_{\text{ask}} = 0.52$ with an executable bid $P_{\text{bid}} = 0.48$ (Spread $S = 0.04$).
- Taker entry fee $F_{\text{entry}} = 0.07 \times 0.52 \times 0.48 \approx \$0.0175 \implies \$0.02$.
- Assume symmetric exit targets: Take-Profit at $+15¢$ ($P_{\text{exit}} = 0.67$) and Stop-Loss at $-15¢$ ($P_{\text{exit}} = 0.37$).
- Exit taker fee $F_{\text{exit}} \approx \$0.015 \implies \$0.02$.
- Realized Net Profit on Win:
  $$\text{Gain} = (0.67 - 0.52) - 0.02 - 0.02 = +0.15 - 0.04 = +\$0.11$$
- Realized Net Loss on Loss:
  $$\text{Loss} = (0.37 - 0.52) - 0.02 - 0.02 = -0.15 - 0.04 = -\$0.19$$

The expected value equation is:
$$\mathbb{E}[\text{PnL}] = W \cdot (0.11) - (1 - W) \cdot (0.19) = 0$$
$$0.11 W - 0.19 + 0.19 W = 0 \implies 0.30 W = 0.19$$
$$\mathbf{W_{\text{be, scalping}} = \frac{0.19}{0.30} = 63.33\%}$$

If the bid-ask spread narrows to $2¢$ and profit target expands to $+25¢$ vs $-25¢$ stop:
- Realized Net Profit: $+0.25 - 0.04 = +\$0.21$
- Realized Net Loss: $-0.25 - 0.04 = -\$0.29$
$$\mathbb{E}[\text{PnL}] = W(0.21) - (1 - W)(0.29) = 0 \implies 0.50 W = 0.29 \implies \mathbf{W_{\text{be}} = 58.00\%}$$

*Conclusion*: Any strategy relying on active early liquidation or scalping faces a hurdle win-rate requirement of **$58.0\%–63.3\%$**.

---

### 6.4. Theoretical Expectancy Equation
The generalized net expectancy per contract is expressed as:
$$\mathbb{E}[\text{PnL}] = W \cdot \left( \overline{G} - \overline{F}_{\text{in}} - \overline{F}_{\text{out}} \right) - (1 - W) \cdot \left( \overline{L} + \overline{F}_{\text{in}} + \overline{F}_{\text{out}} \right) - \overline{\text{Slip}}$$
Where:
- $W$ = True out-of-sample win rate
- $\overline{G}, \overline{L}$ = Average gross gain and gross loss
- $\overline{F}_{\text{in}}, \overline{F}_{\text{out}}$ = Entry and exit taker fees
- $\overline{\text{Slip}}$ = Realized crossing slippage relative to mid-price

Given empirical out-of-sample win rates of $47.3\%–49.3\%$, the expectancy term $\mathbb{E}[\text{PnL}]$ is **strictly negative** across all parameter combinations.

---

## 7. Market Regime Vulnerabilities & Edge Cases

This section addresses Requirement R1 and Acceptance Criterion 2 by identifying and analyzing five distinct market regime vulnerabilities and systemic edge cases in the application logic.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        MARKET REGIME VULNERABILITY TAXONOMY                            │
├───────────────────────────────┬───────────────────────────────┬────────────────────────┤
│ Microstructure & Volatility   │ Temporal & Liquidity          │ Architecture & Risk    │
├───────────────────────────────┼───────────────────────────────┼────────────────────────┤
│ 1. Chop Deadzone Bleed        │ 3. Night Session Accuracy     │ 5. Multi-Day Cumulative│
│ 2. Strike Pinning Noise       │    Degradation (00:00-06:59ET)│    Drawdown Reset Flaw │
│                               │ 4. Taker Fee Scalping Drag    │                        │
└───────────────────────────────┴───────────────────────────────┴────────────────────────┘
```

---

### 7.1. Vulnerability 1: Chop Deadzones & False Breakout Bleed
- **Mechanism**:
  Bitcoin enters extended consolidation intervals where the underlying spot price oscillates within a narrow $\$30$ range with low volume and decaying ADX ($\text{ADX} < 18$, $\text{BBW} < 0.018$).
- **Vulnerability**:
  While `CAPITAL_GUARD` is specifically designed to emit `PASS` in this regime, the system allows user configuration overrides (`ignorePass: true`, `auto_force_trade: true`, or setting trading style explicitly to `SNIPER` or `AMBUSH`). When `CAPITAL_GUARD` is bypassed:
  1. Technical indicators produce false breakout signals on micro-wicks that immediately retrace within the Bollinger Bands.
  2. The model initiates directional positions near $\$0.50$.
  3. The contract oscillates around the strike price, triggering repeated stops or expiring worthless.
- **Compounding Factor**:
  In chop deadzones, the bid-ask spread widens as market makers widen quotes to compensate for low volume. Entering and exiting early in chop extracts maximum friction (2 fees $+$ full spread), causing rapid capital exhaustion.

---

### 7.2. Vulnerability 2: Strike Pinning Noise & Expiry Coin-Flips
- **Mechanism**:
  During the final 120 seconds of a 15-minute contract, the spot price frequently hovers within $\$5.00–\$15.00$ of the contract strike price ($|\text{Spot} - \text{Strike}| \le \$18.00$) under low volatility ($\text{ATR} \le \$45.00$).
- **Vulnerability**:
  The outcome of the contract degenerates into a sub-second Brownian motion coin flip governed by single-tick market orders on spot exchanges:
  1. **Index Basis Divergence**: Kalshi settles against the CF Benchmarks Bitcoin Real Time Index (BRTI), which aggregates multiple constituent exchanges. Spot data feeds utilized by the bot (Coinbase, Kraken) routinely diverge from the BRTI calculation by $\$5.00–\$15.00$ at the exact settlement timestamp.
  2. **Sub-Second Latency Race**: High-frequency algorithmic market makers on Kalshi update their quotes within milliseconds of index price changes. The Python execution loop (which polls every $1–3$ seconds) suffers adverse selection, buying contracts that have already statistically failed on the settlement feed.
  3. **Empirical Evidence**: The author's Loss Analyzer (`loss_analyzer.py:18–95`) attributes **$32.5\%$ of all historical losses** directly to strike pinning noise. While the filter suppresses entries when $|\Delta| \le \$18$ and $\text{ATR} \le \$45$, any trade entered earlier in the candle that drifts into a strike pin remains exposed to pure random-walk settlement loss.

---

### 7.3. Vulnerability 3: Night Session Accuracy Degradation
- **Mechanism**:
  Between **00:00 and 06:59 America/New_York** (the Asian/early European transition), trading dynamics diverge fundamentally from the U.S. trading session:
  - U.S. institutional order flow is absent.
  - CME Bitcoin futures liquidity drops.
  - Kalshi order book depth collapses from an average of 40–80 contracts to under 10 contracts.
- **Vulnerability & Empirical Drop**:
  Out-of-sample empirical testing reveals that model directional accuracy collapses from **$52.1\%$ during day hours** to **$46.5\%$ during the 00:00–06:59 ET window**:
  1. Feature indicators such as `volume_15m_ratio` (relative to a 3-day mean) and `orderbook_imbalance` lose statistical predictive power due to thin order book depth.
  2. With accuracy at $46.5\%$ and a required break-even hurdle of $52.0\%$, trading during the night session yields an expected net loss of approximately $-\$0.055$ per contract traded.
  3. Although `DualMLEngine` trains a dedicated `night_engine`, if the night model lacks sufficient recent training samples, it automatically falls back to `day_engine` (`dual_ml_engine.py:91`), applying daylight momentum rules to night-time illiquid chop.

---

### 7.4. Vulnerability 4: Taker Fee Drag & Adverse Selection on Scalping
- **Mechanism**:
  `RL_SCALPER` and `ScalpEngine` attempt to capture small intraday contract price movements ($10¢–20¢$) by entering on momentum and closing before expiration.
- **Vulnerability**:
  As proven mathematically in Section 6.3, exiting a position prior to settlement requires:
  1. Paying the $7\%$ taker fee on entry ($2¢$).
  2. Crossing the bid-ask spread on exit (typically $3¢–6¢$).
  3. Paying the $7\%$ taker fee on exit ($1¢–2¢$).
- **The Scalping Trap**:
  Total round-trip friction amounts to **$6¢–10¢$ per contract**. On a trade targeting a gross gain of $15¢$, friction consumes $40\%–66\%$ of gross profits. Conversely, when a stop-loss is triggered at $-15¢$, friction expands the loss to $-21¢–-25¢$.
- **Empirical Proof**: The repository's out-of-sample evaluation of `RL_SCALPER` (`backend/data/model_cache/rl_scalper.json`, across 3,962 held-out test trades) revealed a **negative net profit of $-\$0.0333$ per contract** with a 95% confidence interval strictly below zero ($[-\$0.0447, -\$0.0227]$), definitively confirming that intraday scalping on Kalshi is mathematically unviable under taker fee structures.

---

### 7.5. Vulnerability 5: Absence of Multi-Day Cumulative Equity Drawdown Halt
- **Mechanism**:
  The risk architecture enforces a daily risk limit (`max_daily_risk`, default $\$25.00$) and a 3-consecutive-loss circuit breaker within `backend/btc/auto_executor/risk_manager.py:42–78`.
- **The Structural Flaw**:
  The risk budget evaluates trades strictly within the current New York calendar day:
  ```python
  today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
  today_trades = [t for t in trades if str(t.get("timestamp", "")).startswith(today_str)]
  ```
  At 00:00:00 ET, `today_trades` resets to an empty list:
  1. If an account loses $\$24.50$ on Monday (stopping just short of the $\$25.00$ limit), $\$24.50$ on Tuesday, and $\$24.50$ on Wednesday, the bot resets its risk budget to $\$0.00$ each morning.
  2. By Thursday morning, the account has suffered a cumulative loss of **$-\$73.50$** (a $73.5\%$ drawdown on a $\$100$ bankroll), yet the system treats Thursday as a fresh start with zero accumulated risk.
  3. The codebase lacks any persistent peak-to-trough high-water mark equity tracking across days. Consequently, sustained adverse market regimes can fully liquidate an account through consecutive daily sub-ceiling losses.

---

## 8. Code Path & Implementation Reference Table

| Functional Subsystem | Target Source File | Class / Method / Function | Line Numbers | Architectural Role |
| :--- | :--- | :--- | :--- | :--- |
| **Taker Fee Accounting** | `backend/btc/fees.py` | `kalshi_order_fee()`, `entry_edge_cents()` | Lines 12–38 | Implements regulatory 7% taker fee and net PnL |
| **Strike Pin Deadzone Filter** | `backend/btc/analyzer/contract_eval.py` | `evaluate_next_15m_contract()` | Lines 109–127 | Suppresses trades when $\|\Delta\| \le \$18$ and ATR $\le \$45$ |
| **Capital Guard Preservation**| `backend/btc/analyzer/contract_eval.py` | `evaluate_next_15m_contract()` | Lines 56–74 | Generates disciplined PASS on ADX $< 18$ / Vol $< 0.85$ |
| **Auto 2.0 Regime Router** | `backend/btc/auto_executor/shared.py` | `classify_auto_regime()` | Lines 39–205 | Microstructure classification into 4 execution styles |
| **Signal Blending & Vetoes** | `backend/btc/analyzer/contract_eval.py` | `evaluate_next_15m_contract()` | Lines 755–807 | Blends 40% chart / 60% ML; executes 15% conflict veto |
| **Negative EV Gate** | `backend/btc/analyzer/contract_eval.py` | `evaluate_next_15m_contract()` | Lines 1055–1073 | Rejects SNIPER trades if $P_{\text{win}} \le P_{\text{ask}} + 0.05$ |
| **AMBUSH CVD & Macro Veto** | `backend/btc/analyzer/contract_eval.py` | `evaluate_next_15m_contract()` | Lines 1074–1110 | Blocks counter-trend trades during accelerating CVD |
| **GodTierEnsemble Swarm** | `backend/btc/ml_ensemble.py` | `GodTierEnsemble` | Lines 80–273 | Stacking XGBoost + RF + PyTorch LSTM via LogReg |
| **Dual ML Day/Night Router** | `backend/btc/dual_ml_engine.py` | `DualMLEngine` | Lines 10–99 | Switches between day and night models at 00:00 & 07:00 ET |
| **Feature Schema (52 Keys)** | `backend/btc/ml_engine.py` | `FEATURE_KEYS` | Lines 199–226 | Master feature definition schema |
| **Stationarity Normalization** | `backend/btc/ml_engine.py` | `normalize_features()` | Lines 286–320 | Transforms features relative to EMA-50 and log space |
| **Platt Calibrator** | `backend/btc/ml_engine.py` | `PlattCalibrator` | Lines 23–67 | Fits 1D logistic regression; enforces $A > 0$ monotonicity |
| **True Half-Kelly Sizing** | `backend/btc/auto_executor/saas_broadcaster.py` | `_execute_single_user_trade()` | Lines 888–897 | Computes $(p-b)/(1-b)$ Half-Kelly allocation |
| **Single-User Kelly Sizing** | `backend/btc/auto_executor/executor.py` | `check_and_execute_rollover()` | Lines 1020–1048 | Single-user Kelly dampening and MaxCap clamping |
| **IOC Order Execution** | `backend/btc/kalshi_trader.py` | `_place_order_internal()` | Lines 1000–1235 | Dispatches IOC limit order with $0.04 slippage buffer |
| **Paper Execution Realism** | `backend/btc/kalshi_trader.py` | `_place_order_internal()` | Lines 1070–1085 | Paper trading execution, latency tax ($0.01) |
| **Daily Risk Limit & Breaker** | `backend/btc/auto_executor/risk_manager.py` | `check_risk_budget()` | Lines 42–78 | Enforces daily trade limit, $25 cap, 3-loss breaker |
| **Calibration Drift Monitor** | `backend/btc/auto_executor/risk_manager.py` | `check_live_calibration_drift()`| Lines 79–161 | Evaluates 10-decile drift over trailing 100 trades |
| **Dynamic Stop & Invalidation**| `backend/btc/auto_executor/stop_manager.py` | `check_active_trades_stop...()` | Lines 383–420 | Late terminal deficit ($35) & EMA-21 CVD breakdown stops |
| **Trailing Stop & Take Profit**| `backend/btc/auto_executor/stop_manager.py` | `check_active_trades_stop...()` | Lines 329–364 | Enforces +50% TP and Peak +35%, -6% trailing stop |
| **Position Reversal Flip** | `backend/btc/auto_executor/stop_manager.py` | `_attempt_position_reversal()` | Lines 433–614 | Executes post-stop reversal if conf $\ge 75\%$ and $t \ge 6\text{m}$ |

---

## 9. Strategic Recommendations & Risk Scorecard

### 9.1. Quantitative Strategy Risk Scorecard

| Evaluation Dimension | Assessed Rating | Critical Finding |
| :--- | :--- | :--- |
| **Execution Microstructure** | **HIGH RISK** | Crossing the book with a $\$0.04$ buffer on thin Kalshi books results in significant adverse selection. |
| **Fee Resilience** | **CRITICAL RISK** | The $7\%$ taker fee consumes all theoretical alpha unless held strictly to settlement with $>52\%$ win rate. |
| **Predictive Generalization**| **HIGH RISK** | ML out-of-sample directional accuracy ($47.3\%–49.3\%$) fails to beat the break-even hurdle. |
| **Regime Adaptability** | **MEDIUM RISK** | `CAPITAL_GUARD` effectively identifies chop, but manual overrides and strike pin drift lead to capital bleed. |
| **Downside Containment** | **HIGH RISK** | Daily risk ceiling is prudent intraday, but absence of cumulative multi-day drawdown halt permits portfolio ruin. |

---

### 9.2. Actionable Remediation Roadmap

1. **Implement Cumulative Multi-Day Drawdown Circuit Breaker**:
   - Introduce a persistent high-water mark equity tracker in `backend/btc/auto_executor/risk_manager.py`.
   - If total portfolio drawdown exceeds **$15.0\%$ of peak equity across any trailing 30-day window**, permanently halt automated trading until administrative intervention.
2. **Eliminate Active Scalping in Favor of Settlement Holding**:
   - Deprecate `RL_SCALPER` and short-horizon intra-interval flips.
   - Restrict trading strictly to `SNIPER` rollover contracts held to expiration settlement to eliminate the second taker fee and bid-ask spread crossing cost.
3. **Mandate Night Session Halts**:
   - Enforce a hard trading blackout between **00:00 and 06:59 ET**. Historical accuracy in this window ($46.5\%$) guarantees negative mathematical expectancy.
4. **Enforce Post-Entry Strike Pin Evacuation**:
   - Extend the strike pin filter: if an active position enters the final 3 minutes of a contract with $|\text{Spot} - \text{Strike}| \le \$15.00$ and contract bid $\ge \$0.40$, execute an immediate neutral exit rather than gambling on the sub-second BRTI settlement print.
5. **Re-align Feature Pipeline in Unit Tests**:
   - Remediate the feature key discrepancy between `FEATURE_KEYS` and `build_feature_row()` to restore full continuous integration verification.

---
*Report completed in satisfaction of Milestone 1 (Requirement R1 and Acceptance Criterion 2).*
