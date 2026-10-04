# Explorer Survey 3 Dispatch

You are explorer_survey_3.
Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_3
Project root: C:\Users\Vill3\Desktop\ShadowTraderAi
Mandatory reference: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\ORIGINAL_REQUEST.md

Mission: Survey the codebase with a focus on Asset & Route Integrity (R3) and Auto Trader Logic & UI Integration (R4).
Specifically investigate:
- Static assets integrity: inventory all image, icon, splash screen, audio, font, JS/CSS references in HTML/CSS/JS and verify whether they actually exist on disk in the project. Identify any broken links or potential 404s.
- Route integrity and navigation in browser and iOS Capacitor wrapper.
- Auto Trader logic in backend: execution loop, rate limiting, order placement guards, runaway loop prevention, API spamming risks.
- Auto Trader UI integration: Dynamic Island glow, settings toggles, state sync between frontend UI and backend endpoints (`/api/...`).

Output:
Write a comprehensive report to `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_3\survey_report.md` and `handoff.md`.
Include:
- Exact file paths, line numbers, and architectural findings.
- Inventory of existing asset, route, and auto-trader issues/bugs found.
- Concrete recommendations for fixes and verification.
