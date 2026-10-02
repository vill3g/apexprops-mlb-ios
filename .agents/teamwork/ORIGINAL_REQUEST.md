# Original User Request

## 2026-09-30T19:03:32Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Full team

Evaluate the Kalshi AI Trader application to determine its expected profitability. Both analyze the strategies conceptually and run historical tests to verify them empirically.

Working directory: `C:\Users\Vill3\Desktop\kalshi-ai-trader`
Integrity mode: benchmark

## Requirements

### R1. Strategy & Risk Assessment
Analyze the core logic of the trading styles (e.g., SNIPER, CAPITAL_GUARD, AUTO) and the Machine Learning prediction engine. Evaluate the theoretical trading edge, slippage assumptions, and risk-reward ratio.

### R2. Empirical Backtesting
Execute a historical backtest or simulate trades using the application's existing data or custom simulation scripts to empirically verify theoretical profitability over a sustained period.

### R3. Final Profitability Report
Produce a definitive, data-backed report concluding whether the application is statistically likely to be profitable. Include key metrics like expected Win Rate, Profit Factor, and Max Drawdown.

## Acceptance Criteria

### Verification & Quality
- [ ] A programmatic backtest or simulation script is successfully run and its raw metric output is logged.
- [ ] The theoretical assessment identifies at least one specific market regime vulnerability or edge case in the current logic.
- [ ] The final report provides a definitive "Profitable" or "Not Profitable" conclusion based explicitly on the quantitative backtest data.

## 2026-10-01T02:00:51Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Small, focused team

This is a single self-contained fix; keep it small and focused. The Kalshi AI Trader bot is failing to execute automated trades natively. Despite recent patches to the ML conviction pipeline, trades are still not being placed. Investigate the execution path, find the root cause, and implement a permanent fix so the bot trades autonomously.

Working directory: C:\Users\Vill3\Desktop\kalshi-ai-trader
Integrity mode: development

## Requirements

### R1. Execution Pipeline Audit
Deeply trace the live trade execution path (`worker.py`, `saas_broadcaster.py`, `contract_eval.py`, and the RL pipeline) to identify the exact blockage, gate, or silent error preventing trade orders from reaching the Kalshi API during new 15-minute intervals.

### R2. Permanent Logic Fix
Implement the necessary code changes to ensure that when the AI evaluates an interval with a valid conviction (i.e., not exactly 50%), the trade is properly routed and executed without requiring manual overrides.

## Acceptance Criteria

### Execution Verification
- [ ] A programmatic test or live worker run demonstrates a trade successfully passing all logic gates and being submitted to the broker API.
- [ ] The fix resolves the issue without breaking the `SaaS Edge Gate` or other critical risk management systems.
