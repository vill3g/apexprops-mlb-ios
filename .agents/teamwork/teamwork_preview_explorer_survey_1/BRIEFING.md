# BRIEFING — 2026-09-30T19:10:00Z

## Mission
Explore and analyze the core logic of all trading styles (SNIPER, CAPITAL_GUARD, AUTO, MOMENTUM_SURFER, AMBUSH, PREDICTION, CHOP, SCALP/RL_SCALPER) in the Kalshi AI Trader codebase.

## 🔒 My Identity
- Archetype: teamwork_preview_explorer
- Roles: Trading Styles & Strategy Logic Explorer
- Working directory: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\teamwork_preview_explorer_survey_1
- Original parent: 69f1fc34-0f88-433d-8fc9-49626797374a
- Milestone: Strategy & Trading Styles Logic Exploration

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Analyze core logic of all trading styles (SNIPER, CAPITAL_GUARD, AUTO, etc.)
- Detail entry criteria, exit criteria, stop-loss / take-profit, position sizing, order types, time-in-force
- Identify theoretical edge, edge cases, vulnerabilities to market regimes
- Record exact code paths (files, classes, functions, line numbers)
- Write analysis to analysis.md, handoff report to handoff.md, communicate via send_message to parent

## Current Parent
- Conversation ID: 69f1fc34-0f88-433d-8fc9-49626797374a
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `backend/btc/auto_executor/shared.py` (Auto 2.0 regime classifier `classify_auto_regime`)
  - `backend/btc/auto_executor/executor.py` (execution loop, entry timing, sizing, Kelly formula, order dispatch)
  - `backend/btc/auto_executor/saas_broadcaster.py` (multi-tenant SaaS execution, True Binary Half-Kelly, DCA guards)
  - `backend/btc/auto_executor/stop_manager.py` (early bailout stops, trailing take-profit, position reversal, profit re-entry)
  - `backend/btc/analyzer/contract_eval.py` (confluence evaluation, setups, safety gates, ML/chart blending, style overrides)
  - `backend/btc/analyzer/config.py` (thresholds, weights)
  - `backend/btc/chop_engine.py` (CHOP evaluation wrapper and confidence floor)
  - `backend/btc/scalp_engine.py` (intraday price move & momentum scalping, dynamic ATR TP, smart trailing stop)
  - `backend/btc/rl_agent.py` & `backend/btc/rl_scalper.py` (Dueling QR-DQN with Platt calibration & EV gating)
  - `backend/btc/kalshi_trader.py` (order execution, IOC limit orders, slippage buffer, paper latency tax)
  - `backend/btc/fees.py` (Kalshi taker fee formula, net PnL, edge calculation)
  - `backend/btc/loss_analyzer.py` (loss categorization, dynamic regime penalties)
  - `backend/forex/auto_executor.py` (forex ATR pip-risk sizing)
- **Key findings**:
  - Found 8 distinct trading styles/modes: SNIPER, CAPITAL_GUARD, AUTO, MOMENTUM_SURFER, AMBUSH, PREDICTION, CHOP, SCALP/RL_SCALPER (+ REVERSAL & ONE_SHOT_AI modes).
  - Identified complete mathematical formulation for entry gating, Kelly sizing, slippage buffers, fee impact, and stop-loss logic.
  - Identified core vulnerabilities: illiquid Kalshi orderbooks (wide bid-ask spread), taker fee drag (7% per leg), strike pinning noise, and counter-trend cascade wipes.
- **Unexplored areas**: None for strategy/trading style logic.

## Key Decisions Made
- Proceeding to write comprehensive analysis.md and 5-component handoff report.

## Artifact Index
- analysis.md — Full analysis report
- handoff.md — 5-component handoff report
- progress.md — Liveness heartbeat
- BRIEFING.md — Persistent memory
