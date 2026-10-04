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

## 2026-10-02T17:19:38Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Full team

Comprehensive audit of the ShadowTrader AI codebase to find errors, performance issues, and UX bugs, ensuring the app runs smoothly, quickly, and error-free on iOS and Web. The team should actively fix the issues they find.

Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi
Integrity mode: benchmark

## Requirements

### R1. Backend Stability & Error Handling
Audit the Python backend (including trading engines and API routes) for rate limit vulnerabilities (e.g., Kalshi 429s), unhandled exceptions, and logic errors. Implement robust error handling and retries.

### R2. Frontend UI/UX and iOS Smoothness
Audit the web frontend (`static/saas_dashboard.html`, JS, CSS) for console errors, unclosed HTML tags, overlapping UI elements (especially iOS safe-area issues), and performance bottlenecks.

### R3. Asset & Route Integrity
Verify that all static assets (images, icons, splash screens) load correctly without 404s, and that all navigation functions seamlessly within both the browser and the iOS Capacitor wrapper.

### R4. Auto Trader Logic & UI Integration
Audit the Auto Trader functionality. Ensure the backend execution logic works flawlessly without runaway loops or API spamming. Verify the frontend UI (including the Dynamic Island glow and settings toggles) correctly syncs state with the backend.

## Acceptance Criteria

### Backend Verification (Agent-as-Judge)
- [ ] A reviewer agent verifies the backend server starts without errors and the server watchdog logs show stable execution without crashing.
- [ ] A reviewer agent confirms that API rate limits are caught and handled gracefully in the codebase without terminating the process.
- [ ] A reviewer agent confirms the Auto Trader backend logic executes securely without runaway loops.

### Frontend Verification (Agent-as-Judge)
- [ ] A reviewer agent parses `saas_dashboard.html` and verifies there are no unclosed tags or structural HTML errors.
- [ ] A reviewer agent confirms all static asset paths have been verified to exist on disk, ensuring zero 404s for images, JS, and CSS files.
- [ ] A reviewer agent verifies the Auto Trader UI components correctly reflect their enabled/disabled states.

## 2026-10-02T18:08:00Z

RESUME EXECUTION: A system crash occurred during Milestone 3 and Milestone 4. Review the existing `PROJECT.md`, `progress.md`, and test suites. Milestones 1 and 2 were completed. Pick up where the previous team left off and finish M3, M4, and the final Agent-as-Judge verification.

# Teamwork Project Prompt — Draft

> Requested team: Full team

Comprehensive audit of the ShadowTrader AI codebase to find errors, performance issues, and UX bugs, ensuring the app runs smoothly, quickly, and error-free on iOS and Web. The team should actively fix the issues they find.

Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi
Integrity mode: benchmark

## Requirements

### R1. Backend Stability & Error Handling
Audit the Python backend (including trading engines and API routes) for rate limit vulnerabilities (e.g., Kalshi 429s), unhandled exceptions, and logic errors. Implement robust error handling and retries.

### R2. Frontend UI/UX and iOS Smoothness
Audit the web frontend (`static/saas_dashboard.html`, JS, CSS) for console errors, unclosed HTML tags, overlapping UI elements (especially iOS safe-area issues), and performance bottlenecks.

### R3. Asset & Route Integrity
Verify that all static assets (images, icons, splash screens) load correctly without 404s, and that all navigation functions seamlessly within both the browser and the iOS Capacitor wrapper.

### R4. Auto Trader Logic & UI Integration
Audit the Auto Trader functionality. Ensure the backend execution logic works flawlessly without runaway loops or API spamming. Verify the frontend UI (including the Dynamic Island glow and settings toggles) correctly syncs state with the backend.

## Acceptance Criteria

### Backend Verification (Agent-as-Judge)
- [ ] A reviewer agent verifies the backend server starts without errors and the server watchdog logs show stable execution without crashing.
- [ ] A reviewer agent confirms that API rate limits are caught and handled gracefully in the codebase without terminating the process.
- [ ] A reviewer agent confirms the Auto Trader backend logic executes securely without runaway loops.

### Frontend Verification (Agent-as-Judge)
- [ ] A reviewer agent parses `saas_dashboard.html` and verifies there are no unclosed tags or structural HTML errors.
- [ ] A reviewer agent confirms all static asset paths have been verified to exist on disk, ensuring zero 404s for images, JS, and CSS files.
- [ ] A reviewer agent verifies the Auto Trader UI components correctly reflect their enabled/disabled states.


## 2026-10-03T22:04:04Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Full team

Evaluate the ShadowTrader AI auto-trading logic, specifically analyzing the 15-minute interval trading and the multiple-entry/scaling strategy. The goal is to identify algorithmic flaws and generate a detailed evaluation report with actionable recommendations to make the system profitable, without altering the existing code.

Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi
Integrity mode: benchmark

## Requirements

### R1. Codebase Logic Audit
Analyze the Python backend trading engines (`contract_eval.py`, `auto_executor.py`, etc.) focusing specifically on the 15-minute interval decision logic and multiple-entry/scaling mechanics to identify structural flaws causing negative EV (Expected Value).

### R2. Trade Data Analysis
Read existing trade databases and logs using Python data analysis tools to find common denominators in recent losing trades (e.g., incorrect trailing stop distances, trading against dominant trends, poor entry timing).

### R3. Evaluation Report Deliverable
Produce a comprehensive evaluation report artifact containing concrete, actionable code recommendations and logic adjustments to make the strategy profitable. The team must **not** actively modify the existing codebase.

## Acceptance Criteria

### Report Verification (Agent-as-Judge)
- [ ] A reviewer agent confirms the report identifies at least two specific mathematical or logical flaws in the current interval or multiple-entry strategy.
- [ ] A reviewer agent verifies the report cites exact file paths and specific functions where the problematic logic resides.
- [ ] A reviewer agent confirms the report provides concrete, actionable pseudocode or code snippets to fix the identified issues, rather than vague conceptual advice.
