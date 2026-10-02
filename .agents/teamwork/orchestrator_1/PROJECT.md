# Project: Kalshi AI Trader Expected Profitability Evaluation

## Architecture
- **Trading Styles**: `SNIPER` (candle rollover trend sniper), `CAPITAL_GUARD` (chop preservation pass), `AUTO` (regime classifier & router), `MOMENTUM_SURFER` (1m runaway trend tracker), `AMBUSH` (anti-exhaustion squeeze breakout), `CHOP` (range fade), `RL_SCALPER` / `SCALP` (continuous intraday).
- **ML Prediction Engine**: `GodTierEnsemble` (Stacking XGBoost + Random Forest + PyTorch LSTM via Logistic Regression meta-learner), `DualMLEngine` (day/night router), `RLAgent` / `PricedDQN`.
- **Risk & Execution**: True Binary Half-Kelly position sizing, IOC Limit orders with $0.04 book-crossing buffer, 5-tier exit hierarchy (Take Profit, Trailing Stop, Mid-price SL, Structural Invalidation, Settlement), daily risk limit ($25), 3-loss circuit breaker.
- **Friction & Expectancy**: Kalshi 7% taker fee on risk ($0.07 * P * (1-P)), bid-ask spread ($0.02 - $0.05), spot-to-BRTI basis risk.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Trading Styles Analysis | Logic, rules, parameters of SNIPER, CAPITAL_GUARD, AUTO, etc. | M1 | Survey 1 (DONE) |
| 2 | Theoretical Edge & Risk-Reward | Slippage assumptions, risk/reward ratios, fee threshold math | M1 | Survey 1, Survey 3 (DONE) |
| 3 | Market Regime Vulnerabilities | Chop bleed, illiquid books, strike pinning, night session decay | M1 | Survey 1, Survey 2, Survey 3 (DONE) |
| 4 | ML Prediction Engine Evaluation | Model architecture, 52 features, normalization, calibration | M1 | Survey 2 (DONE) |
| 5 | Empirical Backtesting Execution | Programmatic execution of walk-forward & trade replay scripts | M2 | Survey 3, Worker M2 (DONE) |
| 6 | Harness & Defect Remediation | Fix syntax/indentation/schema bugs in test scripts if needed for clean run | M2 | Worker M2 (DONE) |
| 7 | Raw Metric Output Logging | Capture out-of-sample Win Rate, Profit Factor, LogLoss, Drawdown | M2 | Worker M2 (DONE) |
| 8 | Discrepancy & Overfitting Audit | Document in-sample vs out-of-sample gap and hardcoded HTML mock | M2 | Worker M2, Auditor (DONE) |
| 9 | Final Profitability Report | Definitive "Profitable" or "Not Profitable" synthesis backed by quantitative data | M3 | Worker M3 (DONE) |
| 10 | E2E Acceptance Verification | Validate all 3 acceptance criteria via independent tests & audit | E2E Track | Reviewers, Challengers, Auditor (DONE) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Strategy & Risk Assessment (R1) | Deep conceptual analysis of styles, ML engine, theoretical edge, slippage, and regime vulnerabilities | Survey complete | DONE |
| M2 | Empirical Backtesting Execution (R2) | Execute backtest/simulation scripts, log raw outputs, calculate empirical win rate, profit factor, drawdown | M1 | DONE |
| M3 | Final Profitability Report (R3) | Synthesize findings into definitive data-backed report with clear Profitable/Not Profitable conclusion | M2 | DONE |
| E2E | Acceptance & Quality Track | Independent verification, adversarial challenger, and forensic audit | M1, M2, M3 | DONE (PASS) |

## Code Layout & Artifact Paths
- Metadata: `.agents/teamwork/`
- Strategy Assessment: `.agents/teamwork/reports/R1_strategy_risk_assessment.md`
- Backtest Raw Logs & Report: `.agents/teamwork/reports/R2_empirical_backtest_report.md`
- Final Profitability Report: `.agents/teamwork/reports/FINAL_PROFITABILITY_REPORT.md`
- Gate Matrix: `.agents/teamwork/orchestrator_1/GATE_STATUS.md`
- Backtesting scripts: `backend/btc/backtest.py`, `backend/scripts/backtest_rl.py`, `backend/scripts/evaluate_previous_trades.py`
