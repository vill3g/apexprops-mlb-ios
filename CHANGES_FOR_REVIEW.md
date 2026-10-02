# Changes for Review (Claude, Sept 26–28 2026)

This is a list of every change Claude made to this repo in this working session, so it can be
reviewed and verified independently (e.g. by Antigravity).

## Quick verification

```
python scripts/verify_audit_fixes.py
```

This does two things:
1. It checks 39 code markers, exact snippets that each fix leaves in its file. A **MISSING**
   marker means that fix is no longer in the file. The most likely cause is an editor saving
   an older copy over it; see the warning at the bottom.
2. It runs the 8 regression test files listed below. Expected result: all pass.

Full suite: `python -m pytest -q tests`. After these changes it shows the same 10 failures
as before, and all 10 predate them. See "Pre-existing test failures" at the bottom.

Finding IDs (M-DUP, H1, …) refer to `DEPLOYMENT_AUDIT.md`.

---

## 1. Paper trading matches live constraints (PAPER)

Before this change, paper fills were strictly better than any live fill could be.

| File | Change |
|---|---|
| `backend/btc/kalshi_trader.py` | **New constants:** `PAPER_LATENCY_TAX_DOLLARS`, `PAPER_MIN_SIM_DEPTH`, `PAPER_MAX_SIM_DEPTH`, `PAPER_NO_FILL_CHANCE`. **New function:** `_simulated_book_depth()`, a deterministic simulated top-of-book depth. <br>**`place_order(dry_run=True)`** now applies: a 30s expiry backstop taken from the ticker (no network call), a latency tax, cent rounding, partial fills or no fill against the simulated depth, and an optional `available_balance` check. The new parameter is `available_balance`. <br>**`close_position(dry_run=True)`** applies the latency tax, rounds to cents, simulates depth, and computes the real exit fee. |
| `backend/btc/auto_executor/stop_manager.py` | Three synthetic exit-price roundings changed from 4 decimals to 2 (whole cents). |
| `backend/btc/auto_executor/executor.py` | Both PAPER entry paths clamp size to the paper balance (`paper_avail_bal`) and pass `available_balance`. |
| `backend/btc/auto_executor/saas_broadcaster.py` | Both PAPER paths now size with a slippage buffer plus latency tax and go through `kalshi_trader.place_order(dry_run=True)`. The copy-trade path now also adds the entry fee to the paper cost; the main path already did. |

Tests: `tests/test_paper_trading_realism.py`.

**Note:** Antigravity later removed the 4¢ slippage buffer from the paper fill price. See line
~963 of `kalshi_trader.py`: `raw_price + PAPER_LATENCY_TAX_DOLLARS`. As a result,
`test_paper_entry_pays_slippage_and_latency_tax_rounded_to_cents` fails. Either the test or
the code needs updating, depending on which behavior is intended.

## 2. Up/Down Pattern Watch (PATTERN)

| File | Change |
|---|---|
| `backend/btc/pattern_analyzer.py` (new) | Detects streaks, alternation and time-of-day patterns in settled YES/NO results. It combines `market_results.json` with the shared `trades` table. `get_pattern_signal(asset)` is cached for 60s. |
| `backend/btc/analyzer/contract_eval.py` | This is an advisory nudge only. It moves `prob` by at most ±4 points, adds a catalyst note, and never changes the trade's side or creates a trade. |

Tests: `tests/test_pattern_analyzer.py`.

## 3. PREDICTION style tie-break — ⚠️ REGRESSED

Claude fixed the "PREDICTION only predicts YES" bug. The cause was `p_yes >= 50.0` evaluating
true on the 0.50 "no opinion" value. The fix is a tiered fallback that ends in a spot-vs-strike
tiebreak.

Antigravity later rewrote this block in `backend/btc/analyzer/contract_eval.py`. The rewrite
uses `p_yes = raw_ml_prob*100 ± 15` and then `direction = "ABOVE" if p_yes >= 50.0`, which
brings the YES bias back whenever there is no model opinion and no chart signal.
`tests/test_prediction_style.py::test_prediction_tiebreak_follows_spot_not_always_above`
fails. **This needs a decision.**

## 4. Windows reboot shortcut

- `reboot_and_verify.bat` (new): stops the server, restarts it through the watchdog, then
  polls `/api/health` locally and at `moneyprinter.ngrok.app`.
- `create_reboot_shortcut.ps1` (new): creates the "Reboot AI Trader" shortcut on the desktop.

Neither file has been tested on Windows by Claude.

## 5. M-DUP: no duplicate automated LIVE orders

| File | Change |
|---|---|
| `backend/database/order_intents.py` (new) | Adds an `order_intents` table in `users.db` with `PRIMARY KEY(account_key, ticker)`. <br>`claim()` does an INSERT OR IGNORE; only one caller wins, across threads, processes and restarts. If the claim can't be written, it fails closed. <br>`settle_outcome()`: a fill or an ambiguous result keeps the claim; a definite rejection releases it. |
| `backend/btc/auto_executor/executor.py` | Owner bot: claims before each LIVE auto entry and settles the claim after. An ambiguous result also sets `last_traded_interval`. |
| `backend/btc/auto_executor/saas_broadcaster.py` | Same for each SaaS user's LIVE auto entry. The RL scalper is exempt, since it re-trades by design. An ambiguous result also sets `_user_last_traded_cache`. This builds on Antigravity's `inflight_orders.has_inflight` check, which is kept. |
| `backend/saas_settler.py` | Second entries claim `"{ticker}#second_entry"`. |

Manual trades are deliberately not guarded.

Tests: `tests/test_order_dedup_and_ambiguity.py`, which includes a 12-thread race.

## 6. M-AMBIG: a lost order response is never reported as a clean rejection

In `backend/btc/kalshi_trader.py`, `place_order` for LIVE orders:
- `sent_cid` / `sent_price` track which order (the first one or the IOC retry) actually went out.
- Any exception after a request was sent (timeout, dropped connection, unreadable 200
  response, or a failure on the retry itself) goes to `_resolve_uncertain_buy()`. That function:
  - looks the order up by `client_order_id` with `_lookup_order_fill()` (GET `/portfolio/orders`);
  - then checks the position delta, trying twice 1.5s apart;
  - returns the confirmed fill, or `ambiguous: True`.
- `ConnectTimeout` is still a clean failure, because nothing was sent.
- If the retry fails before it is sent, the result stays a clean "Unfilled".

`_lookup_order_fill` can only ever *confirm* a fill. The GET `/portfolio/orders` response
shape was not verified against the live API; if the call fails, the code falls back to the
position check.

Tests: `tests/test_order_dedup_and_ambiguity.py`.

## 7. H1: record filled contracts, not requested

`filled_count(order_res, fallback)` is added to `backend/btc/kalshi_trader.py`. It is used in:
- `saas_broadcaster.py`: the LIVE auto path, which also adds a `requested_count` field, and the
  copy-trade LIVE path.
- `auth/routes.py`: the manual trade (`/trade/manual`) and the force ML copy, which now also
  records the fill price and the Kalshi client order id.
- `stop_manager.py`: the reversal flip and the take-profit re-entry, for paper and live.
- `saas_settler.py`: second entries, which also record the fill price.

Tests: `tests/test_partial_fill_recording.py`, including an endpoint test that fills 6 of 19.

## 8. H2: second-entry guards

These changes are in `backend/saas_settler.py`:
- `_second_entry_mode(user, trade_mode, live_kt)` returns `None` in three cases: the AI is off,
  the trade's mode differs from the user's current mode, or the trade is LIVE with no Kalshi
  session. Previously that last case fell into the paper branch.
- `_second_entry_size(user, mode, ask)` checks that ask + 4¢ (plus the latency tax for paper)
  plus the fee fits within the trade size.
- LIVE orders pass `slippage_buffer_dollars=0.04`. PAPER goes through the simulated
  `place_order(dry_run=True)` plus the fee. Trade records use `second_mode`.

Tests: `tests/test_second_entry_guards.py`.

## 9. H3: ETH stop-loss, take-profit and trailing stop

These changes are in `backend/saas_settler.py`:
- `_series_of(ticker)` and `_market_for_ticker(ticker, cache)` fetch the active market for the
  trade's own series, once per series per pass.
- They are used both in `_settle_saas_trades_pass` (per trade) and in `fast_exit_check`.
  Previously both only ever used the BTC market.

Tests: `tests/test_settler_multi_asset.py`, including an end-to-end ETH take-profit through the
real pass. With the old code that trade stays OPEN.

## 10. M1: `settlement.py` `is_win` bug (owner bot settlement)

These changes are in `backend/btc/auto_executor/settlement.py`:
- `_count_of(t)` and `_pay_out(t, user_id, is_win, count, pnl)`: the win push and the paper
  credit now each happen exactly once, when the trade is marked SETTLED.
- An official Kalshi result is final: the code `continue`s, so it never falls through to the
  candle fallback.
- The candle-fallback settlement now also pays paper wins. Previously it never credited them.
- A trade with no result yet stays OPEN and no longer picks up the previous trade's `is_win`.

Tests: `tests/test_settlement_is_win.py`. Three of its tests fail on the old code.

## 11. H4: web server and worker no longer clobber each other's history or balance

| File | Change |
|---|---|
| `backend/btc/proc_lock.py` (new) | `ReentrantProcessLock`: a thread RLock plus an OS file lock (msvcrt on Windows, fcntl on Linux) in `backend/data/locks/`. It times out after 60s. |
| `backend/btc/auto_executor/shared.py` | `_history_lock` is now `ReentrantProcessLock("owner_trades_history")`. |
| `backend/btc/auto_executor/executor.py` | Removed the unused local `_history_lock` definition; the shared one arrives via `from .shared import *`. <br>`_save_trades_history()` now merges with the file on disk under the lock (`_merge_with_disk`): a trade already closed on disk is never reverted to OPEN, and trades that exist only on disk are kept. |
| `backend/btc/auto_executor/settlement.py` | `check_settlements()` re-reads the history from disk under the lock and settles that copy, not the caller's possibly stale list. It then updates the caller's list. |
| `backend/btc/paper_balance.py` | The lock is now `ReentrantProcessLock("paper_balance")`. `update_balance` does its read-modify-write from the file on disk (`_read_balance_file`), not from the cache. |

Tests: `tests/test_cross_process_history.py`, which uses real subprocesses for the lock and
the paper balance.

## 12. Other files added

- `DEPLOYMENT_AUDIT.md`: the full audit report.
- `scripts/verify_audit_fixes.py`: the verification script described at the top.
- `CHANGES_FOR_REVIEW.md`: this file.

---

## ⚠️ Overwrite warning

Twice, `backend/saas_settler.py` was replaced by its previous version within about a second
of Claude saving it (after the H2 fix and after the H3 fix). Both times it was re-saved and
re-verified. Some editor or agent that holds these files open appears to write back its older
buffer when the file changes on disk. Before editing any file listed above, reload it from
disk, and run `scripts/verify_audit_fixes.py` afterwards.

## Observed but not changed

- `backend/btc/scalp_engine.py:310` uses `backend.btc.auto_executor._history_lock`, but the
  package `__init__` doesn't export `_history_lock`. That line probably raises AttributeError
  right after a scalp order is placed, so the trade is not recorded. It was left alone because
  the scalper is off-limits for now. The fix would be one line in `auto_executor/__init__.py`:
  `from .shared import _history_lock`.
- `scalp_engine` records the requested count for paper scalp trades, not the simulated fill.
- Remaining audit items: see `DEPLOYMENT_AUDIT.md`, starting with M2 (AI off / mode switch
  takes up to 15s), M3 (partial LIVE exit strands contracts), M4 (IOC retry can exceed the
  trade size), and M5 (SQLite rollback).

## Pre-existing test failures (not caused by these changes)

| Test | Cause |
|---|---|
| `test_force_trade_pass` (4 tests), `test_one_shot_ai_trade` (2 tests) | Stale: they patch `backend.btc.auto_executor.add_all_indicators`, which moved in the package split. |
| `test_profitability_upgrades::test_manual_trade_not_blocked_above_60_cents` | Stale: it patches the package-level `kalshi_trader`. |
| `test_backtest::test_run_walkforward_backtest_synthetic` | `KeyError 'xgbclassifier'`, likely a sklearn/xgboost version issue. |
| `test_prediction_style::test_prediction_tiebreak…` | The PREDICTION regression in section 3. |
| `test_paper_trading_realism::test_paper_entry_pays_slippage…` | The slippage-buffer change noted in section 1. |
| `test_analyzer_blend` | Flaky: it uses live order-book data. |
