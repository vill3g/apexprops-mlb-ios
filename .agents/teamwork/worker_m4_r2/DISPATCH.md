# Worker M4 Dispatch: Auto Trader Logic & UI State Synchronization

You are worker_m4_r2.
Role: teamwork_preview_worker
Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m4_r2
Project root: C:\Users\Vill3\Desktop\ShadowTraderAi
Mandatory reference: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: C:\Users\Vill3\Desktop\ShadowTraderAi\PROJECT.md
Survey findings: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_survey_3\survey_report.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Exclusively Owned Files:
- backend/btc/auto_executor/executor.py
- backend/btc/auto_executor/saas_broadcaster.py
- backend/routes/engine.py
- static/saas_dashboard.html

Tasks:
1. In `backend/btc/auto_executor/executor.py` (lines 1228-1240) and `saas_broadcaster.py` (lines 963-964):
   Prevent runaway loops on Kalshi HTTP 429 or rejections. When an order fails with HTTP 429 or non-retryable rejection, record interval failure / backoff (`self.last_traded_interval = current_interval_id`) so the engine does NOT re-evaluate and re-submit orders every 1 second for the same candle!
2. In `backend/btc/auto_executor/executor.py` (lines 1056-1068):
   Fix `execDelay` lock release race condition. Ensure the interval is flagged as inflight/attempted before releasing any lock, and ensure `time.sleep(exec_delay)` does not freeze worker execution for other assets or permit concurrent threads to trade the same interval.
3. In `backend/btc/auto_executor/executor.py` (line 1098):
   Extend `order_intents.claim` protection to paper trading (`intent_key = f"paper:{intent_key}"`) so duplicate orders cannot execute for the same interval.
4. In `static/saas_dashboard.html`:
   Fix Auto Trader UI wiring:
   - In `toggleAutoTrader(enabled)`, update `header-auto-toggle` (the actual toggle in the settings drawer) and immediately update `nav-auto-badge` in the header (`AUTO ON` vs `AUTO OFF`) with proper styling. Clean up dead references to non-existent `auto-trader-toggle` and `auto-trader-status`.
   - In `loadConfig()`, dynamically use `(window.currentAsset || 'BTC').toLowerCase()` instead of hardcoded `/api/engine/btc/trade/config`, preventing ETH/GOLD toggles from being overwritten.
   - Convert absolute `/static/assets/...` paths to `./assets/...` and change `<a href="/admin/mobile">` to `<a href="./admin_mobile.html">` for Capacitor WKWebView compatibility.
5. In `static/saas_dashboard.html`:
   Dynamic Island Glow:
   - Calibrate top offset so the glowing pill aligns with the physical Dynamic Island cutout instead of sitting at 59px overlapping header text and Open Trade PnL text.
   - Sync Dynamic Island state when 1-Shot Snipe executes (`toggleDynamicIslandSetting` should call `updateDynamicIsland()`).
6. In `backend/routes/engine.py:707, 804`:
   Ensure `api_btc_trade_config_get` inspects `user_id` so registered users receive their own executor config, matching `api_btc_trade_ai_settings_get`.
7. In `static/saas_dashboard.html`:
   Polling Deduplication & Battery Optimization:
   Wrap `loadDashboard()` and high-frequency polling with `if (document.hidden) return;` to prevent battery/network drain when the mobile app is backgrounded.

Verification:
- Run tests: `& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/test_audit_e2e_suite.py`
- Run existing autotrader tests: `& "C:\Users\Vill3\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests/ -k "toggle or autotrader or executor or config"`
- Document verified commands and results in your handoff report at `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m4_r2\handoff.md`.
- Send a completion message via send_message to orchestrator `4b83425a-da72-44a8-8209-c598c907adb5`.

## 2026-10-02T18:13:32Z
Received dispatch from 4b83425a-da72-44a8-8209-c598c907adb5:
You are worker_m4_r2.
Role: teamwork_preview_worker
Working directory: C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\worker_m4_r2
Project root: C:\Users\Vill3\Desktop\ShadowTraderAi
Implement all tasks listed in DISPATCH.md, verify with tests, document results in handoff.md, and send completion message via send_message to orchestrator conversation ID: 4b83425a-da72-44a8-8209-c598c907adb5.
