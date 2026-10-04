# Task Assignment: Multiple-Entry & Scaling Strategy Audit

Working Directory: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_scaling_1
Project Root: C:\Users\Vill3\Desktop\ShadowTraderAi
Authoritative Request: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\ORIGINAL_REQUEST.md (see 2026-10-03T22:04:04Z entry)
Scope Document: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\orchestrator_4\PROJECT.md

## Objective
Perform an in-depth codebase audit of the Python backend trading engines (`auto_executor.py`, `contract_eval.py`, position managers, risk managers) focusing specifically on:
1. Multiple-entry and scaling mechanics (averaging down, pyramiding, DCA logic, entry triggers).
2. Position sizing math (Kelly criterion, fixed fraction, risk limits).
3. Trailing stop logic, distance calculations, stop loss triggers, take profit, and exit hierarchy.
4. Capital exposure and drawdowns caused by scaling into losing trades or high-gamma binary contracts.
5. Identify specific mathematical or logical flaws in the multiple-entry/scaling mechanics causing negative EV.
6. Identify exact file paths, line numbers, and function names where the problematic logic resides.

## Constraints & Requirements
- STRICT: Do NOT modify any source code files in the codebase. Read-only investigation.
- Provide concrete evidence: cite exact file paths, function names, line numbers, code snippets, and mathematical formulas.
- Output your findings to: `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_scaling_1\scaling_audit.md`
- Also write your standard `handoff.md` and `progress.md`.
