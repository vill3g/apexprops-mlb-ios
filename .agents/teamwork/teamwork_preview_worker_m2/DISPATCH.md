# Dispatch: Worker M2 (Empirical Backtest Execution & Logging)

## Identity & Role
- Archetype: teamwork_preview_worker
- Role: Empirical Backtest & Execution Worker
- Working directory: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_worker_m2
- Parent Orchestrator: orchestrator_1 (conversation ID: 69f1fc34-0f88-433d-8fc9-49626797374a)

## Mandatory Inputs (Read these first)
1. C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md
2. C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\PROJECT.md
3. C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3\analysis.md
4. C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3\handoff.md

## Objective
Execute historical backtests and simulation scripts programmatically, capture raw output logs, audit in-sample vs out-of-sample performance, and author the definitive report satisfying Requirement R2 and Acceptance Criterion 1.

Write the report to:
`C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\reports\R2_empirical_backtest_report.md`

Your tasks:
1. **Fix minor codebase blocking bugs (if necessary for clean script runs)**:
   - Check and fix the IndentationError in `backend/btc/auto_executor/saas_broadcaster.py:228-236` if it impedes imports.
   - Check and fix any missing keys in `backend/btc/ml_engine.py` or `kalshi_trader.py:1079` if needed.
   - Run tests using `.venv\Scripts\pytest.exe` or `.venv\Scripts\python.exe` to verify.
2. **Execute Historical Backtests & Simulations Programmatically**:
   - Run rolling walk-forward backtest via `.venv\Scripts\python.exe backend/btc/backtest.py --days 5 --windows 100` (and inspect deeper windows like 90 days in `backend/data/backtest_report.json`).
   - Run RL walk-forward backtest via `.venv\Scripts\python.exe backend/scripts/backtest_rl.py`.
   - Run trade replay evaluator via `.venv\Scripts\python.exe backend/scripts/evaluate_previous_trades.py`.
3. **Capture and Log Raw Terminal Outputs**:
   - Include exact command lines, execution timestamps, and raw stdout/stderr output in your report.
4. **Quantitative Performance Metrics**:
   - Extract and summarize: Total trades/candles evaluated, Win Rate (out-of-sample vs in-sample), Profit Factor, Max Drawdown, Net PnL, Brier Score, Log Loss, and Calibration curves.
5. **Audit In-Sample Discrepancy & Static HTML Mocks**:
   - Document the difference between out-of-sample results (47.3% - 50.8% Win Rate, Profit Factor 0.89) and in-sample claims (72.66% Win Rate in `evaluate_previous_trades.py` due to zero taker fees and zero spread assumptions).
   - Document the static HTML strings in `backend/btc/backtester_sim.py:36-46` (71.4% WR, 2.14 PF, -11.2% Max Drawdown).

## 2026-09-30T19:19:17Z

<USER_REQUEST>
You are Worker M2 (Empirical Backtest Execution & Logging Worker).
Your working directory is: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_worker_m2
Your parent is orchestrator_1 (conversation ID: 69f1fc34-0f88-433d-8fc9-49626797374a).

MANDATORY FIRST STEP:
Read C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md, C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\PROJECT.md, and C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_worker_m2\DISPATCH.md. Also read Explorer Survey 3 analysis in .agents/teamwork/.

TASK:
Execute historical backtests and simulation scripts programmatically, capture raw output logs, audit in-sample vs out-of-sample performance, and author the definitive report satisfying Requirement R2 and Acceptance Criterion 1.
Save to: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\reports\R2_empirical_backtest_report.md

Tasks:
1. Fix minor codebase blocking bugs if necessary for clean script runs (e.g. IndentationError in saas_broadcaster.py:228-236, missing keys in ml_engine.py if needed). Run pytest to verify.
2. Programmatically execute the backtest scripts:
   - .venv\Scripts\python.exe backend/btc/backtest.py --days 5 --windows 100
   - .venv\Scripts\python.exe backend/scripts/backtest_rl.py
   - .venv\Scripts\python.exe backend/scripts/evaluate_previous_trades.py
3. Capture and log raw terminal execution logs with timestamps and exact command invocations.
4. Extract and analyze quantitative metrics: Out-of-sample Win Rate, Profit Factor, Net PnL, Max Drawdown, Log Loss, Brier Score, and Calibration bucket deviations.
5. Document the in-sample discrepancy (why evaluate_previous_trades.py shows 72.66% win rate due to omitting 7% taker fees and spread) and the static HTML mock in backend/btc/backtester_sim.py:36-46.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

OUTPUT:
Write C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\reports\R2_empirical_backtest_report.md.
Write handoff.md in your working directory. Send a message to orchestrator_1 when done.
</USER_REQUEST>
