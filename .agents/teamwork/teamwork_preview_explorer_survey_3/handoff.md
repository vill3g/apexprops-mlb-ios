# Handoff Report — Explorer Survey 3: Risk, Slippage & Backtesting Harness

**Author**: Explorer Survey 3  
**Target Recipient**: Orchestrator (orchestrator_1)  
**Date**: 2026-09-30  
**Full Investigation Report**: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3\analysis.md`  

---

## 1. Observation

### 1.1 Empirical Backtest & Simulation Executions
1. **Walk-Forward XGBoost Backtest (`backend/btc/backtest.py`)**:
   - Command executed: `.venv\Scripts\python.exe backend/btc/backtest.py --days 5 --windows 100`
   - Result:
     - 480 15m candles evaluated (5 days). 330 out-of-sample test samples.
     - **Accuracy: 47.3%** (worse than random 50% coin-toss).
     - **Brier Score: 0.32785** (substantially worse than 0.2500 benchmark).
     - **Log Loss: 0.90819** (substantially worse than 0.69315 benchmark).
     - Verbatim calibration output:
       `[WARN] Systematic OVERCONFIDENCE detected across 3 buckets (predicted probabilities exceed realized win rates by >8%).`
       `Bucket 80-90%: Mean Pred P = 83.9%, Realized WR = 32.0% (Diff = +51.9%)`
       `Bucket 70-80%: Mean Pred P = 74.6%, Realized WR = 47.5% (Diff = +27.1%)`
       `Bucket 60-70%: Mean Pred P = 65.0%, Realized WR = 45.7% (Diff = +19.3%)`
   - Long-horizon report in `backend/data/backtest_report.json` (90 days, 8,640 candles, window 4000):
     - 4,590 out-of-sample samples: **Accuracy: 50.87%**, **Brier Score: 0.2520**, **Log Loss: 0.70126**.
     - Bucket 90-100%: Mean Pred P = 99.0%, Realized WR = 50.0% (Diff = +49.0%).

2. **RL Shadow Agent Backtest (`backend/scripts/backtest_rl.py`)**:
   - Command executed: `.venv\Scripts\python.exe backend/scripts/backtest_rl.py`
   - Result:
     - Replay on 586 real historical trades (`trades_history.json`): Original System Win Rate: **48.3%** (283W / 303L), RL Win Rate: **49.3%** (289W / 297L).
     - 60-Day Market Walk-Forward (5,709 intervals):
       - Overall Win Rate: **49.22%** (2,810W / 2,899L).
       - **Profit Factor: 0.89** (strictly < 1.0, net loss).
       - Simulated P&L: **-$158.68** (without fees; factoring 7% taker fee increases loss by ~$100+).
       - Night Session Win Rate (00:00-06:59 ET): **46.5%** (severe vulnerability).

3. **Historical Trade Replay Evaluator (`backend/scripts/evaluate_previous_trades.py`)**:
   - Command executed: `.venv\Scripts\python.exe backend/scripts/evaluate_previous_trades.py`
   - Result:
     - 578 evaluated trades from `trades.db`.
     - Current Model In-Sample Win Rate: **72.66%** vs. Historical Actual Win Rate: **49.13%** (-$604.09 actual PnL).
     - Code inspection (`backend/scripts/evaluate_previous_trades.py` lines 109-115) reveals that simulated PnL completely ignores Kalshi taker fees ($7\%$) and assumes zero bid-ask spread on NO contracts (`no_entry = 1.0 - entry_price`).

4. **Hardcoded HTML Mock (`backend/btc/backtester_sim.py`)**:
   - Lines 36–46 contain verbatim static HTML text:
     `<div class="text-xl font-bold text-emerald-400">71.4%</div>`
     `<div class="text-xl font-bold text-rose-400">-11.2%</div>`
     `<div class="text-xl font-bold text-cyan-400">2.14</div>`
   - It performs no trade simulation.

### 1.2 Risk Architecture & Codebase Observations
1. **Risk Limits**:
   - `backend/btc/auto_executor/risk_manager.py`:
     - Line 56: `len(today_trades) >= self.max_daily_trades` (default: 10).
     - Line 60: `effective_risk <= -abs(self.max_daily_risk)` (default: $25.00).
     - Line 73: `consecutive_losses >= 3` halts trading ("Circuit Breaker Activated: 3 consecutive losing trades").
   - Maximum Drawdown: **No continuous equity curve drawdown limit exists**. Daily risk resets at ET midnight.
2. **Execution & Slippage**:
   - `backend/btc/fees.py`: Line 9 `TAKER_FEE_RATE = 0.07`. Line 18: `raw = 0.07 * count * price * (1.0 - price)`.
   - `backend/btc/kalshi_trader.py`:
     - Line 35: `PAPER_LATENCY_TAX_DOLLARS = 0.01`.
     - Line 1041: `buf = 0.04` (clamped [0.00, 0.15]) added to limit price for IOC orders.
     - Line 1079: `filled_count = count_int` hardcoded, bypassing simulated depth on paper entries.
3. **Specific Code Defects & Unit Test Failures**:
   - `backend/btc/auto_executor/saas_broadcaster.py` (lines 228–236): Invalid 32-space indentation raises `IndentationError` during `pytest tests/test_risk_budget.py`.
   - `backend/btc/ml_engine.py` (lines 220–223 vs 445–510): `ndq_roc`, `dxy_roc`, `vsa_absorption`, `sfp_score` are in `FEATURE_KEYS` but missing from `build_feature_row()`, causing `tests/test_backtest.py` to fail.
   - `tests/test_paper_trading_realism.py`: 4 tests fail because line 1079 in `kalshi_trader.py` forces full fills and omits slippage buffer on paper entries.

---

## 2. Logic Chain

1. **Premise 1 (Break-Even Threshold)**: Kalshi charges a $7\%$ taker fee on contract risk ($0.07 \times P \times (1-P)$). At $P = 0.50$, the fee is $\$0.02$ per contract on entry and $\$0.00$ at settlement. A binary 50/50 option requires a realized win rate of $> 51.75\%$ just to cover fees and bid-ask spread (Observation 1.2.2).
2. **Premise 2 (Empirical Out-of-Sample Performance)**:
   - Rolling out-of-sample walk-forward evaluation across 5 days (330 samples) and 90 days (4,590 samples) yields win rates of **47.30% to 50.87%** (Observation 1.1.1).
   - Rolling 60-day RL walk-forward evaluation across 5,709 intervals yields a win rate of **49.22%** and a Profit Factor of **0.89** (Observation 1.1.2).
   - Real historical trades executed by the system in `trades_history.json` and `trades.db` achieved win rates of **48.30% to 49.13%** and net losses of **-$604.09** (Observation 1.1.2 & 1.1.3).
3. **Premise 3 (In-Sample Distortion)**: The only tool generating win rates $> 70\%$ (`evaluate_previous_trades.py` showing $72.66\%$) evaluates the model in-sample on the same trades it trained on, charges $\$0.00$ in taker fees, and assumes zero bid-ask spread on NO contracts (Observation 1.1.3).
4. **Premise 4 (Drawdown Vulnerability)**: Because risk limits reset every calendar day at midnight ET without tracking multi-day cumulative portfolio drawdowns, a continuous sub-50% win rate strategy will experience unbounded equity erosion (Observation 1.2.1).
5. **Deduction**: Because the empirical out-of-sample win rate ($47.3\% - 50.8\%$) is strictly below the break-even threshold ($>51.75\%$), the system is statistically expected to lose capital over sustained trading.

---

## 3. Caveats

1. **Offline Binance.US Candle Alignment**: Walk-forward tests were evaluated using 15m BTCUSDT candles from Binance.US / Coinbase spot markets. Kalshi contracts officially settle against the CF Benchmarks BRTI index. Any basis risk or index tracking difference between spot exchanges and BRTI at settlement could introduce small variations (+/- 0.5%), though not enough to overcome a sub-50% base accuracy.
2. **Asset Scope**: This survey focused primarily on BTC contracts (`KXBTC15M`), which represents the primary asset with recorded deep orderbook history (`kalshi_btc15m_history.jsonl`). ETH and Gold contracts share the identical executor code but were not individually backtested.
3. **Read-Only Constraint**: In accordance with the Explorer archetype, none of the identified code defects (`saas_broadcaster.py` indentation, `ml_engine.py` missing keys, or `kalshi_trader.py` paper realism) were modified in place.

---

## 4. Conclusion

1. **Profitability Verdict**: **NOT PROFITABLE**. The core strategies and ML prediction engine do not possess a statistically valid out-of-sample edge. Across all out-of-sample backtests and real historical trade logs, win rates remain between **47.3% and 49.3%**, resulting in a Profit Factor of **0.89** and negative net PnL. The advertised $>70\%$ win rates are artifacts of in-sample overfitting, zero-fee assumptions, and hardcoded HTML mocks.
2. **Execution Reality**: Real Kalshi taker fees ($7\%$) and bid-ask spreads create a negative friction that rapidly depletes capital at sub-52% win rates.
3. **Risk Architecture**: Daily risk limits and circuit breakers provide intraday protection, but the lack of a cumulative equity-curve max drawdown halt leaves capital exposed to multi-day drawdown decay.

---

## 5. Verification Method

To independently verify all observations and conclusions:

1. **Verify 5-Day Walk-Forward Out-of-Sample Accuracy**:
   ```powershell
   .venv\Scripts\python.exe backend/btc/backtest.py --days 5 --windows 100
   ```
   *Expected Output*: Accuracy $\approx 47.3\%$, Log Loss $> 0.90$, systematic overconfidence warnings.

2. **Verify 60-Day RL Walk-Forward & Historical Trade Replay**:
   ```powershell
   .venv\Scripts\python.exe backend/scripts/backtest_rl.py
   ```
   *Expected Output*: Walk-forward Win Rate $49.22\%$, Profit Factor $0.89$, Net PnL negative.

3. **Verify In-Sample Trade Replay**:
   ```powershell
   .venv\Scripts\python.exe backend/scripts/evaluate_previous_trades.py
   ```
   *Expected Output*: Demonstrates that in-sample win rate reaches $72.66\%$, but inspect lines 109–115 to confirm taker fees ($0.07$) are never subtracted.

4. **Inspect Hardcoded Mock Report**:
   Inspect `backend/btc/backtester_sim.py` lines 36–46 to confirm static string values for Win Rate (71.4%) and Max Drawdown (-11.2%).

5. **Verify Syntax & Regression Defects**:
   - Run `pytest tests/test_risk_budget.py` to confirm the `IndentationError` in `backend/btc/auto_executor/saas_broadcaster.py:228`.
   - Run `pytest tests/test_backtest.py` to confirm `'ndq_roc'` missing key failure.
   - Run `pytest tests/test_paper_trading_realism.py` to confirm 4 test failures from paper trading fill bypass in `kalshi_trader.py:1079`.
