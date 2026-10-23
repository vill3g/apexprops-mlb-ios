# Dispatch: challenger_2

## Objective
Empirical Invariance, Dynamic Win Probability Calibration & Kelly Wager Math Verification.

## Inputs
- Project Root: `C:\Users\Vill3\Desktop\kalshi-ai-trader`
- Original Request: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md`
- Orchestrator Dispatch: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\orchestrator_9\DISPATCH.md`
- Scope: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\orchestrator_9\SCOPE.md`
- Worker Handoff: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_1\handoff.md`

## Verification Scope
1. Dynamic Invariance & Sensitivity Sweep:
   - Compile strategies with `StrategyCoder.generate_code` and `StrategyCoder.compile_strategy`.
   - Sweep across 50 distinct combinations of `cur_price` (from 0.05 to 0.95), `rsi` (from 10 to 90), and detected regimes.
   - Assert mathematically that the returned `confidence`, `calibrated_win_prob`, and `kelly_fraction` are non-static and vary smoothly across inputs.
   - Verify that NO output ever equals flat 75.0% unless coincidentally resulting from continuous math.
2. Kelly Mathematical Bounds & Edge Gating:
   - Verify that when model edge is negative ($P_{\text{win}} \le C_{\text{eff}}$), `kelly_fraction == 0.0` and `f_star == 0.0`.
   - Verify that `kelly_fraction` is capped at 0.20 (20% bankroll cap) even when edge is large.
   - Verify that Kalshi taker fee is properly accounted for in effective cost ($C_{\text{eff}}$).
3. Regime Guard Verification:
   - When a strategy specifies `target_regimes = ["COMPRESSION_MEAN_REVERSION"]`, test snapshots with `market_regime = "TREND_EXPANSION_MOMENTUM"` and confirm that `evaluate_signal` returns `action: "PASS"` with `reason: "regime_mismatch"`.
   - Confirm that when the regime matches, the strategy executes `action: "BUY"`.
4. Provide a clear, explicit verdict: `APPROVE` or `REQUEST_CHANGES`.

## Output
Write your report to: `C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\challenger_2\handoff.md`.
Notify orchestrator via `send_message`.


## 2026-10-13T03:46:16Z
[Message] timestamp=2026-10-13T03:46:16Z sender=bc91cecc-5501-4832-bd5f-b7b2dd3a837a priority=MESSAGE_PRIORITY_HIGH
content=You are challenger_2.
Working directory: C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\challenger_2
Project root: C:\Users\Vill3\Desktop\kalshi-ai-trader

MANDATORY: Read ORIGINAL_REQUEST.md at:
C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\ORIGINAL_REQUEST.md
before starting work.

Read your dispatch instructions at:
C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\challenger_2\DISPATCH.md
And reference worker handoff at:
C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\worker_1\handoff.md

Your role is Empirical Invariance & Kelly Math Verification:
1. Run sensitivity sweeps across 50 combinations of market prices, indicators, and regimes. Prove mathematically that win probability and Kelly fractions are dynamic, continuous, and non-static.
2. Verify Kelly math: confirm kelly_fraction == 0.0 when edge <= 0, and confirm kelly_fraction is capped at 0.20.
3. Verify regime guards: confirm strategies PASS on conflicting regimes and BUY on matching regimes.
4. Record findings and explicit verdict (APPROVE or REQUEST_CHANGES) in:
   C:\Users\Vill3\Desktop\kalshi-ai-trader\.agents\teamwork\challenger_2\handoff.md
When done, notify orchestrator (conversation ID: bc91cecc-5501-4832-bd5f-b7b2dd3a837a) via send_message.
