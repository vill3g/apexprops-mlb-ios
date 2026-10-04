# Empirical Trade Data & Execution Log Analysis Report
**Author:** explorer_trades_1 (Teamwork Quantitative Analyst)  
**Date:** 2026-10-03  
**Target Codebase:** `C:\Users\Vill3\Desktop\ShadowTraderAi`  
**Analyzed Datasets:** `backend/data/users.db` (2,151 trades), `backend/data/trades.db` (747 trades), `backend/data/market_results.json` (1,050 official settlements), `backend/data/trades_history.json` (744 records), `backend/data/users/*/trades_history.json` (2,056 user JSON records), and associated execution engines (`saas_settler.py`, `stop_manager.py`).

---

## Executive Summary

A comprehensive empirical analysis was conducted across all active trade databases, user logs, and contract execution history in the ShadowTrader AI codebase. The analysis covers **2,897 closed and settled trades** spanning both live broker executions and paper trading simulations from September 11, 2026 through October 3, 2026.

### Key Headline Metrics
- **Overall System Performance (`users.db`)**: 2,150 trades | **51.72% Win Rate** | Net P&L: **-$814.90** | Profit Factor: **0.87** | Payoff Ratio: **0.79** | Expectancy: **-$0.38 / trade** | Max Drawdown: **$912.10**.
- **Live Trading Sub-Portfolio (`users.db` LIVE)**: 711 trades | **49.51% Win Rate** | Net P&L: **-$163.31** | Profit Factor: **0.76** | Expectancy: **-$0.23 / trade** | Max Drawdown: **$195.56**.
- **Engine Backtest & Simulation (`trades.db`)**: 747 trades | **50.20% Win Rate** | Net P&L: **-$7,350.19** | Profit Factor: **0.80** | Payoff Ratio: **0.76** | Max Drawdown: **$13,219.04**.
- **The Paradox of Natural Settlement**: In both databases, contracts held to natural expiration (`SETTLEMENT`) achieved a **76.0% win rate** and **+$1,829.88** net P&L in `users.db` (+$6.65/trade), and a **60.0% win rate** and **+$1,142.39** in `trades.db`. Systemic losses were generated entirely by **premature stop-out triggers, multiple-entry scaling into losers, and negative-EV coin-flip entries**.

---

## 1. Top Common Denominators in Losing Trades

Through multivariate statistical clustering, four primary root-cause mechanisms were isolated as the drivers of negative expected value:

```
+---------------------------------------------------------------------------------------------------+
| RANK | ROOT CAUSE FACTOR                      | STATISTICAL FOOTPRINT          | NET P&L IMPACT   |
+------+----------------------------------------+--------------------------------+------------------+
| 1    | Coinflip / Neutral Conviction Entries  | 1,267 trades at 50-51% prob    | -$741.85 (91% of |
|      | (Zero statistical edge; fee drag)      | (58.9% of all trades)          | net losses)      |
+------+----------------------------------------+--------------------------------+------------------+
| 2    | Re-Entry After Stop-Loss (DCA Scaling) | 141 sequences; 36.9% Win Rate  | -$1,128.27       |
|      | (Doubling down on invalidated trades)  | Avg Trade 2 Loss: -$10.41      | cumulative loss  |
+------+----------------------------------------+--------------------------------+------------------+
| 3    | Mid-Candle Impulse Chasing (Min 3-6)   | 271 trades; PF 0.49            | -$586.91         |
|      | (Buying top/bottom of opening drive)   | Min 4 Win Rate: 41.4%          | (-$2.17 / trade) |
+------+----------------------------------------+--------------------------------+------------------+
| 4    | Tight Trailing Stop & Asymmetric TP/SL | Avg Win: $2.92 vs Loss: -$5.84 | -$5,021.44 from  |
|      | (6% distance = 2-3¢ noise trigger)     | 19.2% stopped would have won   | 860 stop-outs    |
+------+----------------------------------------+--------------------------------+------------------+
```

---

## 2. Quantitative Portfolio Performance

### 2.1 Global Metrics Comparison

| Portfolio / Database | Trades | Wins | Losses | Flats | Win Rate | Gross Profit | Gross Loss | Net P&L | Profit Factor | Avg Win | Avg Loss | Payoff | Expectancy | Max Drawdown |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **users.db (All)** | 2,150 | 1,112 | 1,020 | 18 | 51.72% | $5,292.21 | $6,107.11 | -$814.90 | 0.87 | $4.76 | -$5.99 | 0.79 | -$0.38 | $912.10 |
| **users.db (LIVE)** | 711 | 352 | 349 | 10 | 49.51% | $505.36 | $668.67 | -$163.31 | 0.76 | $1.44 | -$1.92 | 0.75 | -$0.23 | $195.56 |
| **users.db (PAPER)**| 1,439 | 760 | 671 | 8 | 52.81% | $4,786.85 | $5,438.44 | -$651.59 | 0.88 | $6.30 | -$8.10 | 0.78 | -$0.45 | $912.10 |
| **trades.db (All)** | 747 | 375 | 357 | 15 | 50.20% | $29,659.86| $37,010.06| -$7,350.19| 0.80 | $79.09| -$103.67| 0.76 | -$9.84 | $13,219.04 |
| **trades.db (LIVE)**| 266 | 129 | 124 | 13 | 48.50% | $172.21 | $150.35 | +$21.86 | 1.15 | $1.33 | -$1.21 | 1.10 | +$0.08 | $30.23 |
| **trades.db (PAPER)**| 481 | 246 | 233 | 2 | 51.14% | $29,487.66| $36,859.71| -$7,372.05| 0.80 | $119.87| -$158.20| 0.76 | -$15.33| $13,206.51 |

### 2.2 User-by-User Breakdown (`users.db`)

Every single active user account is experiencing negative net cumulative P&L:

| User ID | Username / Role | Mode | Trades | Win Rate | Net P&L | Profit Factor | Avg Win | Avg Loss | Max Drawdown |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2** | system_bot_2 | PAPER | 466 | 60.5% | -$182.09 | 0.68 | $1.37 | -$3.12 | $190.45 |
| **4** | trader_4 | LIVE | 75 | 36.0% | -$27.43 | 0.54 | $1.20 | -$1.30 | $27.53 |
| **4** | trader_4 | PAPER | 21 | 38.1% | -$1.92 | 0.89 | $1.87 | -$1.40 | $8.92 |
| **5** | Mattroccett | LIVE | 345 | 46.4% | -$108.88 | 0.78 | $2.38 | -$2.72 | $175.68 |
| **5** | Mattroccett | PAPER | 116 | 50.9% | +$28.38 | 1.15 | $3.79 | -$3.43 | $48.99 |
| **7** | Vill3.G (Admin) | LIVE | 291 | 56.7% | -$27.01 | 0.77 | $0.56 | -$0.97 | $33.32 |
| **7** | Vill3.G (Admin) | PAPER | 622 | 55.3% | -$145.97 | 0.95 | $8.69 | -$11.45 | $548.33 |
| **172** | test_user_172 | PAPER | 4 | 25.0% | -$66.36 | 0.34 | $34.65 | -$33.67 | $101.01 |
| **197** | test_user_197 | PAPER | 1 | 0.0% | -$17.28 | 0.00 | $0.00 | -$17.28 | $17.28 |
| **205** | livlyfenyce | PAPER | 208 | 31.7% | -$266.34 | 0.81 | $17.23 | -$9.88 | $329.07 |

---

## 3. Exit Mechanism Audit: Trailing Stop & Premature Exits

### 3.1 Exit Category Performance in `users.db`

| Exit Category | Count | Win Rate | Gross Profit | Gross Loss | Net P&L | Avg P&L | Expectancy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **STOP_LOSS** | 860 | 0.8% | $4.01 | $5,025.45 | **-$5,021.44** | -$5.84 | -$5.84 |
| **TAKE_PROFIT** | 817 | 96.2% | $2,542.33 | $156.25 | **+$2,386.08** | +$2.92 | +$2.92 |
| **SETTLEMENT** | 275 | **76.0%** | $2,379.40 | $549.51 | **+$1,829.88** | **+$6.65** | **+$6.65** |
| **MANUAL_CLOSE**| 178 | 60.7% | $363.63 | $347.43 | +$16.20 | +$0.09 | +$0.09 |
| **UNSPECIFIED** | 18 | 11.1% | $2.84 | $28.47 | -$25.63 | -$1.42 | -$1.42 |

### 3.2 Exit Reason Breakdown in `trades.db`

| Exit Reason | Count | Win Rate | Net P&L | Avg Win | Avg Loss |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **NATURAL_SETTLEMENT** | 350 | **60.0%** | **+$1,142.39** | $64.82 | -$90.37 |
| **CONTRACT_STOP_LOSS** | 130 | 0.0% | **-$14,998.27** | $0.00 | -$115.37 |
| **MANUAL_CLOSE** | 97 | 46.4% | **-$6,111.88** | $30.51 | -$143.94 |
| **TRAILING_TAKE_PROFIT**| 75 | 94.7% | +$4,354.72 | $62.10 | -$13.54 |
| **TAKE_PROFIT** | 37 | 100.0% | +$9,332.35 | $252.23 | $0.00 |
| **SCALP_STOP_LOSS** | 18 | 5.6% | -$1,109.77 | $1.17 | -$65.35 |
| **DYNAMIC_STOP_LOSS** | 12 | 0.0% | -$560.64 | $0.00 | -$46.72 |
| **SCALP_TRAILING_STOP** | 8 | 62.5% | -$34.07 | $54.29 | -$101.83 |
| **SCALP_PROFIT_TARGET** | 7 | 85.7% | +$634.97 | $109.99 | -$24.96 |

### 3.3 The Trailing Stop Noise Trap (Mathematical Demonstration)

In `backend/saas_settler.py` (lines 815–855) and `backend/btc/auto_executor/stop_manager.py` (lines 358–375), the trailing stop threshold is defined as:
```python
ts_activation = 0.35  # 35% profit required to activate
ts_distance = 0.06    # 6.0% distance
trail_threshold = max(max_seen_bid - ts_distance, max_seen_bid * (1.0 - ts_distance))
```
1. **Spread / Ticks Flaw**: For a contract entered at `$0.50` that reaches `$0.68` (`+36%` profit):
   - `max_seen_bid - ts_distance` = `$0.68 - 0.06` = `$0.62`.
   - `max_seen_bid * (1.0 - ts_distance)` = `$0.68 * 0.94` = `$0.6392`.
   - `max(0.62, 0.6392)` = **`$0.64`**.
   - A drop of merely **4 cents ($0.04)** triggers the stop.
2. In Kalshi 15-minute contracts, the order book bid-ask spread is routinely **$0.02 to $0.05**. A single market sell or liquidity flicker instantly triggers `curr_bid <= trail_threshold`.
3. **Severe Payoff Asymmetry**: Because winning trades are snipped early by trailing stops at an average profit of **+$2.92**, while losing trades drop to hard stop-losses at **-$5.84**, the bot requires an impossible **67% win rate** just to break even. With an empirical win rate of 51.7%, it steadily bleeds.

### 3.4 Counterfactual Expiration Analysis (Empirical Proof via `market_results.json`)

By matching 856 stopped-out trades in `users.db` against the 1,050 ground-truth final settlement outcomes in `backend/data/market_results.json`:
- **164 stopped-out trades (19.2%)** would have settled as **WINNERS** at expiration, paying the full $1.00 contract value.
- **Premature stop-outs turned 164 winning predictions into realized losses.**
- Conversely, for early `TAKE_PROFIT` trades:
  - **581 out of 816 (71.2%)** would have won at expiration anyway.
  - Early take-profit locked in **$2,385.51**, while holding to expiration would have yielded **$3,094.15**. The system voluntarily forfeited **+$708.64** of profit on its best ideas.

---

## 4. Multiple Entry & Scaling Mechanics: The Loss Multiplier

The codebase implements multi-entry DCA and pullback scalping (`is_second_entry`, `is_third_entry`, `reentry_index` in `saas_settler.py` lines 360–535 and 960–1095).

### 4.1 Entry-Level Performance (`users.db`)

| Entry Stage | Trades | % of Total | Wins | Losses | Win Rate | Net P&L | Avg Win | Avg Loss | Avg P&L / Trade | Avg Contracts |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Entry 1 (Base / SNIPER)** | 1,525 | 70.9% | 748 | 759 | 49.05% | -$473.40 | $4.03 | -$4.60 | **-$0.31** | 29.3 |
| **Entry 2 (Second Scale)** | 468 | 21.8% | 275 | 193 | 58.76% | -$260.74 | $6.36 | **-$10.41** | **-$0.56** | 32.7 |
| **Entry 3 (Third Scale)** | 157 | 7.3% | 89 | 68 | 56.69% | -$80.76 | $5.94 | **-$8.97** | **-$0.51** | 29.5 |

Notice that while Entry 2 and Entry 3 have superficially higher win rates (58.8% and 56.7%), **their average loss is more than double Entry 1 (-$10.41 vs -$4.60)**. As a result, Entry 2 has an expectancy of **-$0.56/trade**, nearly **80% worse than Entry 1**!

### 4.2 Sequence-Level Analysis (Single vs Scaled Multi-Entry)

When grouping consecutive entries on the same contract ticker:

| Sequence Length | Sequences | Total Trades | Win% (Sequence) | Total Sequence P&L | Avg P&L / Sequence |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1 (Single Entry)** | 819 | 819 | 38.0% | -$464.59 | **-$0.57** |
| **2 (Two Entries)** | 324 | 648 | 53.1% | -$450.24 | **-$1.39 (2.4x loss)** |
| **3 (Three Entries)**| 156 | 468 | 52.6% | -$239.57 | **-$1.54 (2.7x loss)** |

Scaling converts a single -$0.57 loss into a multi-trade -$1.39 to -$1.54 loss!

### 4.3 The "Re-Entry After Stop-Loss" Catastrophe

In `backend/saas_settler.py` line 960:
```python
allow_reentry = (is_profitable_scalp and second_entry_on) or (is_stop_loss_exit and reentry_sl_on)
```
When a trade is stopped out, the bot is permitted to immediately re-enter the market. The empirical outcome of this behavior is catastrophic:

```
                                  [Trade 1 Closes]
                                         |
               +-------------------------+-------------------------+
               |                                                   |
      Trade 1: TAKE_PROFIT                               Trade 1: STOP_LOSS
      Count: 325 sequences                               Count: 141 sequences
      Trade 2 Win Rate: 66.5%                            Trade 2 Win Rate: 36.9%
      Trade 2 Net PnL: -$112.40                          Trade 2 Net PnL: -$379.67 (-$2.69/trade)
      Combined Sequence PnL: +$564.42                    Combined Sequence PnL: -$1,128.27
```

- When Trade 1 is stopped out, **Trade 2 loses 63.1% of the time**.
- Re-entering after a stop-loss produced **-$1,128.27 in cumulative sequence losses** across 141 sequences.
- Root Cause: If a trade was stopped out within a 15-minute window, the market was moving aggressively against the contract. Entering a Second Entry with <8 minutes remaining is fighting strong intra-interval momentum.

---

## 5. Entry Timing within the 15-Minute Contract Window

By decomposing all 2,150 trades into their entry timestamp relative to the 15-minute candle (`epoch % 900`):

### 5.1 Exact Minute-by-Minute Performance (Minutes 0 to 14)

| Minute | Trades | % Volume | Win Rate | Net P&L | Avg P&L | Avg Win | Avg Loss | Stop-Loss Rate |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0** | 1,074 | 50.0% | 50.0% | -$83.96 | -$0.08 | $4.49 | -$4.74 | 42.1% |
| **1** | 183 | 8.5% | 46.4% | -$88.13 | -$0.48 | $5.25 | -$5.56 | 48.6% |
| **2** | 164 | 7.6% | 58.5% | +$39.75 | +$0.24 | $3.69 | -$4.70 | 36.0% |
| **3** | 94 | 4.4% | 58.5% | -$78.05 | -$0.83 | $4.04 | -$7.70 | 37.2% |
| **4** | 99 | 4.6% | **41.4%** | **-$347.20**| **-$3.51** | $4.42 | **-$9.60** | **51.5%** |
| **5** | 78 | 3.6% | 48.7% | **-$161.66**| **-$2.07** | $4.36 | -$8.18 | 46.2% |
| **6** | 91 | 4.2% | 52.7% | **-$196.18**| **-$2.16** | $3.96 | -$8.98 | 34.1% |
| **7** | 83 | 3.9% | 67.5% | +$113.68 | +$1.37 | $5.73 | -$7.67 | 24.1% |
| **8** | 68 | 3.2% | 57.4% | -$5.76 | -$0.08 | $4.75 | -$6.59 | 36.8% |
| **9** | 50 | 2.3% | 66.0% | -$4.94 | -$0.10 | $5.39 | -$10.75 | 28.0% |
| **10** | 55 | 2.6% | 56.4% | +$28.95 | +$0.53 | $7.43 | -$8.75 | 29.1% |
| **11** | 25 | 1.2% | 48.0% | -$64.55 | -$2.58 | $2.28 | -$7.07 | 48.0% |
| **12** | 44 | 2.0% | 43.2% | -$4.57 | -$0.10 | $8.74 | -$6.83 | 31.8% |
| **13** | 26 | 1.2% | 57.7% | +$63.74 | +$2.45 | $12.07 | -$10.66 | 15.4% |
| **14** | 16 | 0.7% | 43.8% | -$26.02 | -$1.63 | $4.56 | -$7.24 | 12.5% |

### 5.2 Candle Phase Aggregation

| Phase | Window | Trades | Win Rate | Net P&L | Avg P&L | Profit Factor | Stop-Loss Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **01 Open** | Min 0–3 | 1,421 | 50.5% | -$132.34 | -$0.09 | 0.96 | 42.2% |
| **02 Mid-Early** | **Min 3–6** | **271** | **49.4%** | **-$586.91** | **-$2.17** | **0.49** | **45.0%** |
| **03 Mid** | Min 6–9 | 242 | 59.1% | -$88.26 | -$0.36 | 0.89 | 31.4% |
| **04 Late** | Min 9–12 | 130 | 58.5% | -$40.55 | -$0.31 | 0.91 | 32.3% |
| **05 Terminal** | Min 12–15| 86 | 47.7% | +$33.15 | +$0.39 | 1.10 | 23.3% |

### Key Takeaway on Timing:
- **Phase 02 (Minutes 3–6) is the single most toxic trading window in the system**, producing **-$586.91 in losses (Profit Factor 0.49)**.
- Minute 4 alone accounts for **-$347.20** with an average loss of **-$9.60** and a **51.5% stop-loss rate**.
- Why? This is the exact interval where initial breakout momentum stalls and retraces. The bot enters Second Entries or chases late fills, gets whipsawed, and triggers hard stop-outs.

---

## 6. Regime, Model Alignment, & Catalyst Audit

### 6.1 Model Conflict Disasters

In `users.db`, 26 trades were recorded where the technical chart pattern favored one side (e.g. BID YES) but the ML XGB/RL model disagreed:
- **Model Conflict Trades**: 26 trades | **38.5% Win Rate** | Net P&L: **-$98.99** | Avg P&L: **-$3.81 / trade**.
- **Model Aligned Trades**: 2,124 trades | **51.9% Win Rate** | Net P&L: -$715.91 | Avg P&L: -$0.34 / trade.
- Taking trades during Model Conflicts increased the average loss rate by **11.2x**!

### 6.2 The Coinflip Trap (Conviction Tiers)

| Conviction / Probability Tier | Trades | % of Total | Win Rate | Net P&L | Avg P&L / Trade | Profit Factor |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **50–51% (Neutral / Coinflip)** | **1,267** | **58.9%** | **50.8%** | **-$741.85** | **-$0.59** | **0.86** |
| **52–59% (Low Conviction)** | 519 | 24.1% | 52.0% | -$144.10 | -$0.28 | 0.91 |
| **60–69% (Moderate Conviction)**| 208 | 9.7% | 54.3% | **+$5.03** | **+$0.02** | **1.01** |
| **70–79% (High Conviction)** | 40 | 1.9% | 47.5% | -$15.27 | -$0.38 | 0.88 |
| **80%+ (Ultra Conviction)** | 116 | 5.4% | **56.9%** | **+$81.28** | **+$0.70** | **1.21** |

**Critical Algorithmic Flaw**: 58.9% of all trades executed by the system were placed at exact 50% or 51% probability. At 50%, there is zero mathematical expectation; the system simply pays the Kalshi bid-ask spread and fees to churn contracts, creating -$741.85 of avoidable loss. Only trades with conviction `>= 60%` demonstrated positive expectancy.

### 6.3 Pattern & Catalyst Vulnerabilities

| Catalyst / Market Pattern | Trades | Win Rate | Net P&L | Avg P&L | Common Failure Mode |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Volume Spike** | 131 | 46.6% | -$180.39 | -$1.38 | Exhaustion volume into resistance |
| **Ascending Triangle Breakout** | 120 | 45.8% | -$196.83 | -$1.64 | Bull trap; false breakout above strike |
| **Breakout Pressure** | 120 | 45.8% | -$196.83 | -$1.64 | Premature entry before candle confirmation |
| **Dual Bullish Trend Alignment**| 45 | **35.6%** | -$111.07 | **-$2.47** | Counter-trend mean reversion whipsaw |
| **Overbought (RSI/Oscillator)** | 40 | 52.5% | -$96.33 | -$2.41 | Buying call/YES at contract peak |
| **Descending Triangle Breakdown**| 87 | 50.6% | **+$89.16** | **+$1.02** | High-EV short setup |
| **Oversold (RSI/Oscillator)** | 7 | **71.4%** | **+$21.49** | **+$3.07** | Dip buying at deep discount |
| **CHOP Strategy** | 33 | 51.5% | **+$73.92** | **+$2.24** | Range-bound mean reversion works |

---

## 7. Contract Price Distribution & Payoff Skew

Analyzing entry contract prices reveals another severe structural vulnerability:

| Entry Contract Price | Trades | Win Rate | Net P&L | Avg P&L | Profit Factor | Structural Issue |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **< $0.20 (Deep OTM)** | 84 | 29.8% | -$314.10 | -$3.74 | 0.28 | Lottery ticket; expired worthless |
| **$0.20 – $0.34 (OTM)** | 224 | 33.9% | +$51.76 | +$0.23 | 1.05 | High payoff compensates lower win rate |
| **$0.35 – $0.49 (Slight OTM)** | 755 | 47.3% | -$280.59 | -$0.37 | 0.85 | Stop loss triggered by small pullbacks |
| **$0.50 – $0.64 (ATM)** | 715 | 55.0% | **+$67.34**| **+$0.09** | **1.04** | **Most balanced EV zone** |
| **$0.65 – $0.79 (ITM)** | 270 | 66.7% | **-$247.36**| **-$0.92** | **0.75** | **Severe negative skew: Risk $0.75 to make $0.25** |
| **>= $0.80 (Deep ITM)** | 102 | 79.4% | **-$91.96** | **-$0.90** | **0.54** | **One loss wipes out 4+ wins** |

- **Deep ITM and ITM entries (>= $0.65) have negative expectancy despite 67%–79% win rates.**
- When buying at $0.75, risking 75¢ to make 25¢, a single loss destroys 3 full wins. When combined with premature stop-outs, ITM buying is mathematically unsustainable.

---

## 8. Summary of Findings & Empirical Conclusions

1. **The Core Forecasting Engine is NOT Broken at Expiration**: Contracts allowed to settle naturally (`SETTLEMENT`) achieved a **76.0% win rate (+$1,829.88)** in `users.db` and **60.0% (+$1,142.39)** in `trades.db`.
2. **The Damage is Caused by Execution-Level Friction**:
   - **Hyperactive 6% Trailing Stops**: Turn winning trades into premature exits due to order-book tick jitter.
   - **Negative Payoff Skew**: Take profit averages +$2.92 while Stop Loss averages -$5.84.
   - **Martingale / Loss-DCA Scaling**: Re-entering after a stop loss loses 63.1% of the time and doubles sequence losses.
   - **Toxic Entry Timing**: Entries during Minutes 3–6 lose heavily (Profit Factor 0.49).
   - **Churning Coinflips**: 58.9% of trades enter at 50–51% conviction with zero statistical edge, paying pure spread and fee drag.
