## 2026-10-02T17:40:43Z

# Worker M2 Dispatch: Frontend HTML/CSS Structure & iOS Smoothness

You are worker_m2.
Role: teamwork_preview_worker
Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m2
Project root: C:\Users\Vill3\Desktop\ShadowTraderAi
Mandatory reference: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: C:\Users\Vill3\Desktop\ShadowTraderAi\PROJECT.md
Survey findings: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_2\survey_report.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Exclusively Owned Files:
- static/saas_dashboard.html
- static/trades.html
- capacitor.config.json
- static/css/dashboard.css
- static/css/app.css

Tasks:
1. In `static/saas_dashboard.html`: Fix the critical unclosed `<div id="settingsDrawer">` tag! Insert the missing `</div>` immediately following `#settingsPanel`'s close (around line 6097) before the trailing scripts and modals.
2. In `static/saas_dashboard.html`: Add iOS bottom safe area support (`env(safe-area-inset-bottom)`). Update sticky buttons (in update announcement modal, trade details modal, and settings drawer bottom) and `<main>` container so elements do not collide with the iOS home indicator bar.
3. In `static/saas_dashboard.html`: Fix corrupted Tailwind CSS glassmorphism classes where `backdrop-blur` was stripped (lines 531, 656, 1011, 1660, 5299) by restoring `backdrop-blur-2xl`, `backdrop-blur-xl`, `backdrop-blur-sm`.
4. In `static/saas_dashboard.html`: Remove/retire the obsolete `#updateAlertModal` containing broken FontAwesome icons and duplicate text, consolidating update notifications into `#updateAnnouncementModal`. Remove unused `https://s3.tradingview.com/tv.js` script tag (line 413).
5. In `static/saas_dashboard.html`: Fix void meta tags in `<head>` (lines 5-7) removing XML self-closing slashes.
6. In `static/trades.html`: Add `viewport-fit=cover` to meta viewport and add safe-area top padding (`env(safe-area-inset-top)`) to prevent header clipping on notch/Dynamic Island iPhones.
7. In `capacitor.config.json`: Change `"contentInset": "always"` to `"automatic"` to prevent double safe-area gap in iOS WKWebView.
8. In `static/saas_dashboard.html`: Link `app.css` or ensure custom safe-area CSS utilities are loaded.

Verification:
- Parse `saas_dashboard.html` with an HTML parser (e.g. Python BeautifulSoup / html.parser) and verify ZERO unclosed tags or structural errors.
- Run frontend contract tests: `& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/test_frontend_contracts.py`
- Document test outcomes and verified commands in your handoff report at `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m2\handoff.md`.
- Send a completion message via send_message to orchestrator `64adbb8f-6e60-424a-a1e3-00b93642f92a`.
