# Dispatch: Worker M1 (Strategy & Risk Assessment)

## 2026-09-30T19:19:17Z

## Identity & Role
- Archetype: teamwork_preview_worker
- Role: Strategy & Risk Assessment Worker
- Working directory: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_worker_m1
- Parent Orchestrator: orchestrator_1 (conversation ID: 69f1fc34-0f88-433d-8fc9-49626797374a)

## Mandatory Inputs (Read these first)
1. C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md
2. C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\PROJECT.md
3. C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_1\analysis.md
4. C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_2\analysis.md
5. C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_3\analysis.md

## Objective
Author the definitive Strategy & Risk Assessment report satisfying Requirement R1 and Acceptance Criterion 2.
Write the report to:
`C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\reports\R1_strategy_risk_assessment.md`

Your report MUST include:
1. **Core Trading Styles Logic**:
   - In-depth analysis of `SNIPER`, `CAPITAL_GUARD`, `AUTO`, `MOMENTUM_SURFER`, `AMBUSH`, `CHOP`, and `RL_SCALPER`.
   - Entry/exit criteria, stop-loss / take-profit mechanisms, position sizing formulas (True Binary Half-Kelly), order types (IOC limit with buffer), and time-in-force.
2. **Machine Learning Prediction Engine**:
   - `GodTierEnsemble` (XGBoost, Random Forest, PyTorch LSTM, meta Logistic Regression), `DualMLEngine` (day/night dispatch), feature pipeline (52 features, normalization relative to EMA-50), and Platt probability calibration.
   - Confluence blending (40% heuristic / 60% ML) and decision vetoes.
3. **Theoretical Trading Edge & Expectancy**:
   - Slippage assumptions ($0.04 buffer, paper latency tax, bid-ask spread).
   - Fee structure (Kalshi 7% taker fee on risk: $0.07 * P * (1-P)).
   - Required break-even win rate math (>52% held to settlement, >58-61% with early exit).
4. **Market Regime Vulnerabilities & Edge Cases**:
   - Identify and thoroughly explain at least 3 specific regime vulnerabilities:
     a) Chop deadzones and false breakouts if CAPITAL_GUARD is bypassed.
     b) Strike pinning noise ($|\Delta| \le \$18$, ATR $\le \$45$) turning expiration into a sub-second coin flip.
     c) Night session accuracy degradation (drop to ~46.5% win rate between 00:00-06:59 ET).
     d) Taker fee drag on scalping/early exits.
     e) Absence of a cumulative multi-day equity drawdown circuit breaker.

## Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Completion
Write `R1_strategy_risk_assessment.md`, update your `progress.md`, write `handoff.md`, and send a completion message to orchestrator_1.
