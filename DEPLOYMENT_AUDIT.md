# Deployment Audit — kalshi-ai-trader

Audited 2026-09-27 against a fresh snapshot of the code on the desktop. Report only; no code was changed.
Scope: security, money/trading correctness, deployment readiness, tests, hosting recommendation.
RL Scalper logic was intentionally excluded (being trained elsewhere).

Test suite on this snapshot: **120 passed, 10 failed, 4 skipped** (details in section 5).

---

## 0. Do today (live on moneyprinter.ngrok.app right now)

| # | Issue | Where | Fix |
|---|---|---|---|
| S1 | **Anyone can forge a login for any account (including the owner).** Tokens signed with the old hard-coded secret `super-secret-default-key-change-me` are still accepted until **Oct 10 2026** (`LEGACY_JWT_ACCEPT_UNTIL` in `.env`). The refresh middleware then hands back a real 90-day token. | `backend/auth/security.py:29,51-68,148-153`, `backend/main.py:289-306` | Set `LEGACY_JWT_ACCEPT_UNTIL=0` in `.env` and restart. Active users were already re-issued new-secret tokens by the migration, so they stay logged in; only tokens untouched since the migration would be rejected. Later: delete the legacy branch. |
| S2 | **Master API token is weak and guessable.** 11 characters, `/api/admin/verify` confirms guesses with no rate limit, token also accepted in the URL (`?token=`) and stored in localStorage. It grants full owner control. | `.env APP_API_TOKEN`, `security.py:71-93`, `admin_routes.py:116-120`, `app.js:425` | Replace with 32+ random bytes, rate-limit `/api/admin/verify`, stop accepting it via URL. |
| S3 | **Registration is effectively open.** Invite code defaults to `KALSHI2026` and `SAAS_INVITE_CODE` is not set in `.env`. | `security.py:20` | Set a random `SAAS_INVITE_CODE` in `.env`. |
| S4 | **Private data tracked in git.** The git index still tracks `users.db` (password hashes + encrypted Kalshi keys), `trades.db`, `token.txt`, per-user trade histories, guest data, several other `.db` files. `.gitignore` lists them but they were never `git rm --cached`. Remote: `github.com/vill3g/apexprops-mlb-ios` (visibility unverified). | git index | Confirm the repo is private. Run `git rm --cached` for those paths and commit. If the repo was ever public, rotate `APP_API_TOKEN`, token.txt and the Kalshi API key. |

---

## 1. Security

### Critical
- **C-LAN. "Local/LAN client = owner" with no login.** `backend/auth/dependencies.py:9-19,31-37` treats any request from `127.*`, `10.*`, `192.168.*`, `fe80:` as the owner. Today, behind ngrok, uvicorn resolves the real client IP, so it's *probably* safe from the internet — but anyone on your Wi-Fi is owner, and **on any cloud host / load balancer / Docker, every visitor arrives from a 10.x/172.x address and becomes owner** (LIVE trading, admin, user deletion). Blocks any move off the PC. Fix: remove IP-based trust; require login or the master token.

### High
- **H-IDOR. Any logged-in user or guest can read any other user's trade history** via `GET /api/engine/BTC/trade/history?user=7` (also `user_id=`, `guest=`). `backend/routes/engine.py:917-941`, `main.py:241-243`. Fix: drop the target param or require admin.
- **H-KEYFALLBACK. A user's LIVE force-trade can run on the owner's Kalshi account.** If a user's stored key fails to decrypt, the trader is built with an empty key and falls back to `backend/kalshi_credentials.json` (owner's plaintext key). If `SAAS_ENCRYPTION_KEY` is ever missing, `security.py:96-103` silently generates a new one → *every* LIVE user's force-trade uses the owner's money. `auth/routes.py:1379-1380`, `btc/kalshi_trader.py:55-60,87-95`. Fix: fail hard when decryption fails; no credential fallback for per-user traders; refuse to start without the encryption key.
- **H-REBIND. DNS rebinding.** Origin check accepts any origin matching the Host header and there's no allowed-hosts list; combined with C-LAN a malicious web page can act as owner via your browser. `main.py:265-282`. Fix: `TrustedHostMiddleware` with an explicit host list.

### Medium
- Regular users can see the owner's main-bot balance/trades (`engine.py:537-538,945-948,965`).
- Non-owner admins can switch the owner's main bot to LIVE and place trades (`dependencies.py:85-111` accepts any admin).
- Leaderboard is public and exposes usernames, roles, LIVE/PAPER mode and LIVE PnL (`routes.py:1460`, `ui.py:19`).
- Sessions: 90-day tokens, no revocation, no password change/reset; cookie is JS-readable, `SameSite=None`, and `login.html:311` rewrites it non-Secure.
- Login: no rate limit; usernames enumerable by timing; min password 6 chars (bcrypt cost 12 is fine).
- Owner identity = username `Vill3.G` (case-insensitive) — on a fresh DB whoever registers it first becomes owner (`models.py:324-347`). Set `SAAS_OWNER_USERNAME` or pin by user id.
- No security headers (CSP, X-Frame-Options, HSTS).

### Low
- Push subscription endpoint accepts any https URL and `/push/test` POSTs to it (limited SSRF), unbounded list (`push_notifications.py:76`).
- Self-XSS in saved profiles `onclick` (`dashboard.js:3918`).
- Profile uploads: well validated, but up to 15 MB decoded in memory; pictures at guessable public URLs.
- Dead fail-open auth code `main.py:190-223` (unused, would skip auth if `APP_API_TOKEN` unset).
- Public "refresh" flags trigger expensive work (`/api/picks/top5?refresh=true`, `/api/injuries?force_refresh=true`).

### Verified OK
Parameterized SQL everywhere (f-strings only for allow-listed column names); `/static` serves only `static/`; `backend/data` is not served; CORS is an explicit list; admin API routes check role server-side; trade close / profile delete limited to the caller's own records; tickets and usernames escaped before display; Kalshi keys never returned to the client.

---

## 2. Money / trading correctness

### Critical
- **M-DUP. A timed-out ("ambiguous") LIVE order doesn't mark the interval as traded, so the bot can place the same order again** seconds later and keep retrying through the entry window. No DB uniqueness on (user, ticker). `executor.py:1130-1138`, `saas_broadcaster.py:787-793`. Fix: write a pending row keyed (user, ticker) with a UNIQUE index before sending; treat ambiguous as "traded this interval".
- **M-AMBIG. Some possibly-filled failures are reported as clean rejections.** A retry that times out, or a `ConnectionError`/`RemoteDisconnected` after the request was sent, returns `success=False` without `ambiguous`. The fill later appears as an untracked MANUAL position (no stop-loss, not in daily limits) and the bot can buy again. `kalshi_trader.py:1176,1246`. Fix: any post-send exception → ambiguous → reconcile by `client_order_id`.

### High
- **LIVE records store contracts requested, not filled** (`saas_broadcaster.py:794-795`, `saas_settler.py:555-563`). 20 requested / 6 filled → PnL and risk computed on 20.
- **Second-entry uses the user's *current* mode and ignores the AI switch** (`saas_settler.py:555`). A PAPER trade hitting take-profit after the user switched to LIVE (or turned AI off) places a real order; sizing also ignores slippage buffer and fee.
- **Stop-loss / take-profit / trailing never fire for ETH users** — settler always fetches the BTC market (`saas_settler.py:221,276,356`).
- **Owner bot paper balance can be double-credited / new trades lost**: web process and worker both rewrite the same JSON history and `paper_balance.json` with thread-only locks (`executor.py:2`, `paper_balance.py:10`). Fix: cross-process lock or move to SQLite.
- **Startup clean-up can double-credit paper payouts** after 30-day archiving, because it closes trades in JSON only and bypasses `close_if_open` (`trade_repository.py:99-204`).

### Medium
- **`settlement.py` `is_win` bug is real**: block at :125-146 sits outside the official-result branch → NameError with 1 pending trade, and with several pending trades a later one reuses the previous `is_win` → false "Won" push + premature `+count` credit, then credited again at real settlement. Official WIN also sends two pushes.
- AI-off / mode switch can take up to 15 s to reach the worker (cache lives in the worker; invalidation runs in the web process) — `shared.py:55`, `models.py:360,375`. Admin broadcast toggle only saves the BTC config.
- Partial LIVE exit closes the trade with `count=filled`, stranding the rest on Kalshi with no stop and no PnL (`saas_settler.py:496-510`).
- Unfilled-order auto-retry can exceed the user's trade size and skips price-range/edge checks (`kalshi_trader.py:1128-1135`).
- SQLite: no rollback on error in thread-local connections; `insert_trade`/`update_trade` swallow exceptions; no `busy_timeout` pragma; `credit_user_paper_balance` can fail *after* `close_if_open` committed → paper payout lost (PLAUSIBLE, not reproduced).

### Low
- Daily risk limit checks existing exposure, not the new trade, so it can be exceeded by one trade (`trade_store.py:43`).
- Voided Kalshi markets leave trades OPEN forever; paper cost never refunded (`saas_settler.py:370`).

### Recent-change notes
- **PREDICTION style is YES-biased again.** `contract_eval.py` (edited after the tie-break fix) now uses `p_yes = raw_ml_prob*100` and `direction = "ABOVE" if p_yes >= 50`. `raw_ml_prob` defaults to exactly 0.50 when there's no model opinion, so with no chart signal every tie goes YES. Regression test `test_prediction_tiebreak_follows_spot_not_always_above` fails.
- **Copy-trade PAPER path omits the entry fee** (`saas_broadcaster.py:258`, `_broadcast_trade_to_users`). Low impact today: its callers are commented out (`stop_manager.py:549,728`). The main SaaS path (:815) was already corrected to add the fee.
- Paper fills no longer include the 4¢ slippage buffer (intentional change in `kalshi_trader.py:963`); `test_paper_entry_pays_slippage_and_latency_tax_rounded_to_cents` should be updated to match.

---

## 3. Deployment readiness

### Blockers (for any move off the PC)
1. **Fresh install crashes on import**: `beautifulsoup4` missing from `requirements.txt` (`main.py:318 → engine/international_model.py → data/npb_client.py:11`). Also missing: `psutil` (watchdog); optional-but-silent: `pywebpush` (push alerts silently off), `transformers`.
2. **C-LAN auth** (section 1) makes every visitor owner behind a cloud proxy.
3. **Secrets generated at runtime.** If `JWT_SECRET` / `SAAS_ENCRYPTION_KEY` are missing, new ones are silently created and appended to `.env` → everyone logged out and every stored Kalshi key unreadable. Web + worker starting together can generate *different* keys. These two values must always move with `users.db`.
4. **Code and state share folders.** `backend/data/` holds 11 `.py` modules next to the databases; other state is written into `backend/btc/*.json`, `backend/kalshi_credentials.json`, `static/data/injuries.json`. Only `USERS_DB_PATH` / `USERS_DATA_DIR` are configurable, so you can't just mount a persistent volume over a data dir.

### High
- Launcher/watchdog are Windows-only (`.venv\Scripts\python.exe`, `ngrok.exe`, `taskkill`, `CREATE_NO_WINDOW`); watchdog's own lock is commented out.
- **Never run two hosts at once** — the worker singleton lock is per-machine; PC + server would both trade the same Kalshi accounts. Also run exactly **one** uvicorn worker (scalp engine thread starts per process; forex engine can run in both web and worker).
- Web and worker must share one filesystem (both need `users.db`).
- **Backups never leave the machine** and skip `model_cache` (holds the runtime-trained `rl_agent.pth` / `rl_calibration.json` behind the default `RL_DQN` strategy), `kalshi_credentials.json`, `btc/*.json`, `.local_token`.
- `render.yaml` is stale and unsafe: free plan (sleeps), web only (no worker → nothing trades or settles), no disk (users.db wiped each deploy, secrets regenerated).

### Medium
- `/api/health` is static — doesn't check DB or worker heartbeat; no alerting.
- Logs: stdout piped to one rotating file; access logs off.
- No graceful shutdown; in-flight order registry is memory-only.
- Port default 8056 in `config.py:17` vs 8058 used by the launcher; default CORS origins localhost-only.
- Pin Python 3.12 (`numpy==1.26.4` has no 3.13 wheels).
- `except ImportError` fallbacks in `btc/analyzer/config.py:39-56` hide real import errors.

### Low
- Git index tracks 364 root files (78 `patch_*`, 45 `fix_*`, etc.) whose deletions were never committed; any git-based deploy ships them.
- Bulky files: `kalshi_btc15m_history.jsonl` 14 MB, `static/data/injuries.json` 6.4 MB, `pytest_out.txt`, logs.
- `tests/conftest.py` only isolates `users.db`; tests can still write real `btc/*.json`.

---

## 4. Hosting recommendation: small Linux VPS

| Option | Verdict |
|---|---|
| **A. Stay on the Windows PC + ngrok** | Free and working, but power/internet outages, Windows Update reboots and sleep all stop a bot that must be always-on; backups on the same disk. OK short-term only. |
| **B. Linux VPS, 4 GB RAM** (Hetzner CX22 ≈ €5/mo; DigitalOcean/Lightsail ≈ $12–24/mo) | **Recommended.** Always on; one filesystem keeps today's SQLite + JSON layout unchanged; web + worker share the disk; still editable live over SSH / VS Code Remote. torch + xgboost need ~1.5–2 GB across both processes. |
| **C. Render / Railway / Fly** | Needs ~2 GB plans + disk (~$25+/mo), a disk can't be shared with a separate worker, the platform proxy triggers C-LAN, every edit is a redeploy, and blocker 4 needs refactoring first. |

### Migration steps (keeps all current users logged in)
1. Fix blockers: add `beautifulsoup4`, `psutil`, `pywebpush` to requirements; remove the LAN-owner shortcut; always set `APP_API_TOKEN`.
2. Clean git: commit deletions, `git rm --cached` private data; rotate secrets if the repo was ever public.
3. Create Ubuntu 24.04 VPS (4 GB), non-root `trader` user, ufw allowing 22/80/443, Python 3.12 venv, `pip install -r requirements.txt`.
4. Two systemd services with `Restart=always`, `WorkingDirectory=` repo root:
   - `uvicorn backend.main:app --host 127.0.0.1 --port 8058 --workers 1`
   - `python backend/worker.py`
5. Caddy in front: `yourdomain { reverse_proxy 127.0.0.1:8058 }` (automatic HTTPS). Or run ngrok on the VPS to keep `moneyprinter.ngrok.app`. Do **not** set `FORWARDED_ALLOW_IPS=*`.
6. Cutover: `stop_server.bat` on the PC and confirm the worker is gone → run backup → copy all of `backend/data/` (including `model_cache`), `.env` (same `JWT_SECRET`, `SAAS_ENCRYPTION_KEY`), `.local_token`, `backend/kalshi_credentials.json`, `backend/btc/*.json` → start services on the VPS. **Never run both hosts at once.**
7. In `.env` set `ALLOWED_ORIGINS`, `SAAS_INVITE_CODE`, `SAAS_OWNER_USERNAME`, `VAPID_SUBJECT`, `LEGACY_JWT_ACCEPT_UNTIL=0`; `chmod 600 .env`.
8. Nightly off-machine backup (cron → `backup_data.py` incl. `model_cache` → restic/rclone to B2/S3).
9. Make `/api/health` check DB + worker heartbeat; point UptimeRobot at it.
10. Disable PC autostart.

---

## 5. Test failures on this snapshot (10)

| Test | Cause |
|---|---|
| `test_prediction_style::test_prediction_tiebreak_follows_spot_not_always_above` | **Real regression** — PREDICTION YES bias (section 2). |
| `test_paper_trading_realism::test_paper_entry_pays_slippage_and_latency_tax_rounded_to_cents` | Intentional behavior change (slippage buffer removed from paper fill) — update test. |
| `test_force_trade_pass` (4) and `test_one_shot_ai_trade` (2) | Stale: patch `backend.btc.auto_executor.add_all_indicators`, which moved to `auto_executor/executor.py` after the package split. |
| `test_profitability_upgrades::test_manual_trade_not_blocked_above_60_cents` | Stale: patches the package-level `kalshi_trader`, not the copy imported in `executor.py:27`, so it hits the real market. |
| `test_analyzer_blend::test_heuristic_conflicts_with_ml_caps_confidence_and_downgrades` | Stale/flaky: patches module names that `confluence.py` imports directly; runs on live order-book data. |
| `test_backtest::test_run_walkforward_backtest_synthetic` | `KeyError 'xgbclassifier'` — likely environment-specific (sklearn/xgboost versions); rerun locally with `-x --tb=long`. |

---

## Suggested fix order
1. Section 0 (S1–S4) — today.
2. M-DUP, M-AMBIG, H-KEYFALLBACK, C-LAN, H-IDOR — before adding more LIVE users.
3. Filled-vs-requested counts, second-entry mode/AI check, `settlement.py` `is_win`, ETH stops, PREDICTION bias.
4. Deployment blockers + VPS migration.
5. Everything else.
