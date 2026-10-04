# Worker M3 Dispatch: Asset & Route Integrity (Zero 404s)

You are worker_m3_r2.
Role: teamwork_preview_worker
Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m3_r2
Project root: C:\Users\Vill3\Desktop\ShadowTraderAi
Mandatory reference: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: C:\Users\Vill3\Desktop\ShadowTraderAi\PROJECT.md
Survey findings: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_3\survey_report.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Exclusively Owned Files:
- backend/routes/ui.py
- static/login.html
- static/trades.html
- static/manifest.json
- static/js/app.js
- update_ipa.py
- backend/main.py

Tasks:
1. In `backend/routes/ui.py`: Fix `/favicon.ico` route. Point `ico_path` to `os.path.join(STATIC_DIR, "favicon.ico")` (which exists on disk, 15KB) instead of missing `assets/app_icon.ico`, eliminating the 404 error.
2. In `static/login.html`: Replace missing `./assets/favicon.svg` (lines 50, 292) and `./assets/app_icon.ico` (line 51). Update logo image tag at line 292 to point to `./assets/icon.png` (which exists on disk, 327KB) and update favicon links to `./favicon.ico` and `./assets/icon.png`.
3. In `static/trades.html`: Replace missing `./assets/favicon.svg` and `./assets/app_icon.ico` (lines 7-8) with `./favicon.ico` and `./assets/icon.png`.
4. In `static/manifest.json`: Convert any absolute `/static/assets/...` paths to relative `./assets/...` so they load correctly inside Capacitor WKWebView.
5. In `static/js/app.js:629-641, 660-670`: Fix flawed promise error handling. Replace `.catch(() => fetch('/static/data/...'))` with explicit status check `if (!tRes || !tRes.ok)` before parsing `.json()` to ensure fallback works and no unhandled 404 promise rejection crashes occur for `data/top5.json`, `data/props.json`, and `data/pitchers.json`.
6. In `backend/main.py`: Mount a root route for `/sw.js` (pointing to `static/sw.js`) and inject the `Service-Worker-Allowed: /` header so the service worker scope covers root `/` and `/saas_dashboard.html`.
7. In `update_ipa.py`: Exclude the dead 8.3 MB `ai_avatar.gif` from the iOS build bundle, reducing IPA size.
8. Verify all static asset links across HTML/CSS/JS exist on physical disk with zero 404s.

Verification:
- Run tests: `& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/test_audit_e2e_suite.py -k "asset or favicon or static"`
- Document verified commands and results in your handoff report at `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m3_r2\handoff.md`.
- Send a completion message via send_message to orchestrator `4b83425a-da72-44a8-8209-c598c907adb5`.

## 2026-10-02T18:13:32Z
Received dispatch message. Exclusively owned files:
- backend/routes/ui.py
- static/login.html
- static/trades.html
- static/manifest.json
- static/js/app.js
- update_ipa.py
- backend/main.py
Tasks 1-8 assigned for Milestone 3 (Asset & Route Integrity - Zero 404s).

