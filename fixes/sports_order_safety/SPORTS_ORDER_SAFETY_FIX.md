# Fix: Sports auto-trader order safety (for Antigravity to implement)

**Written by:** Claude, 2026-10-06
**Target:** `backend/sports_bridge/executor.py` (the `SportsBridgeExecutor` run by `backend/worker.py`)
**Priority:** HIGH. This path places **real-money LIVE orders** with no protection against repeats.
**Ready-made patch:** `fixes/sports_order_safety/sports_order_safety.patch`. It was tested against
the repo as of 2026-10-06 21:30 ET: the 10 new tests pass, and no other test changes result
except the two updated pnl assertions.

---

## How to apply

1. Reload `backend/sports_bridge/executor.py` and `backend/database/order_intents.py` from disk
   before you start. Don't save an older editor buffer over them.
2. From the repo root, apply the patch:
   ```
   git apply --ignore-whitespace fixes/sports_order_safety/sports_order_safety.patch
   ```
3. If the patch doesn't apply because the files changed since, implement Changes 1–5 below by hand.
   Each one says exactly what to change and why.
4. Verify:
   ```
   python -m pytest tests/test_sports_order_safety.py tests/test_sports_dashboard.py tests/test_sports_live_execution.py tests/test_sports_trades_and_sizing.py tests/test_r2_r5_multi_universe_and_timestamps.py -q
   ```
   - Expected: everything passes except `test_sports_prediction_client`, which needs the local AI
     engine running on port 8057.
   - Then run the full suite: `python -m pytest -q tests`. The failure list should match what
     it was before the patch.

## Scope rules

- **Do not change** the crypto auto-trader (`saas_broadcaster.py`, `executor.py`, `saas_settler.py`)
  or anything RL-scalper related.
- **Do not change** user-initiated sports routes in `routes/engine.py` (manual trade, slip submit).
  This fix is only for the automated sports bridge.

---

## The bugs (verified against the code and reproduced by tests)

| # | Bug | Where (current code) | Consequence |
|---|---|---|---|
| A | **A LIVE order with an unknown outcome is bought again.** When `place_sports_order` returns `ambiguous: True` (the response was lost but Kalshi may have filled it), the executor just `continue`s. No trade record is written, so on the next 60s cycle the ticker isn't in `open_tickers` and the **same order is sent again**. | `_process_user`, LIVE branch after `kt.place_sports_order(...)` | Duplicate real-money positions. Test: 2 orders sent across 2 cycles. |
| B | **An uncertain fill is never tracked.** The Kalshi position sync in `saas_settler` only covers `KXBTC15M-`/`KXETH15M-`, so a sports fill from an ambiguous order never gets a trade record: no take-profit and no settlement record. | (nothing handles it) | An invisible open position. |
| C | **A market is bought again after its trade closes.** `open_tickers` only holds OPEN trades. After a take-profit closes, the bot can auto-buy the same game again. | `_process_user` | Unintended repeat entries. Test: 2 orders on the same market. |
| D | **Sizing ignores fees and can exceed the wager.** `count = max(1, int(wager / max_p))` always buys at least 1 contract, even when the wager can't afford one. The fee isn't included anywhere: not in sizing, the LIVE cash check, the paper deduction, recorded `cost`, or pnl. | `_process_user` sizing block; `_settle_open_trades` pnl | Overspending, and paper results look better than live. |
| E | **Settlement and take-profit aren't close-once.** They call `TradeStore.update_trade(...)` *after* crediting the paper balance. If the update fails, the next cycle credits again. A LIVE take-profit with no Kalshi session marks the trade CLOSED **without selling** the position. | `_settle_open_trades` | Possible double credit. The trade shows closed while still held on Kalshi (test reproduces this). |

---

## Change 1: `backend/database/order_intents.py`: add `list_unresolved()`

Add this function above `settle_outcome()`:

```python
def list_unresolved(account_key: str, prefix: str = "", min_age_seconds: float = 0.0) -> list:
    """Claims for this account whose order outcome is still unknown: 'ambiguous' (the response
    was lost) or 'sending' (the process died mid-order). Only claims older than
    min_age_seconds are returned, so an order that is being sent right now is left alone."""
    cutoff = time.time() - float(min_age_seconds or 0.0)
    try:
        conn = _connect()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM order_intents WHERE account_key = ? AND ticker LIKE ? "
                "AND state IN ('ambiguous', 'sending') AND updated_at <= ?",
                (account_key, f"{prefix}%", cutoff),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"[OrderIntents] Could not list unresolved intents for {account_key}: {e}")
        return []
```

## Change 2: `backend/sports_bridge/executor.py`: imports and helpers

After the `from backend.database.models import (...)` block, add:

```python
from backend.database import order_intents
from backend.btc.fees import kalshi_order_fee, net_pnl
```

Add these above `def _generate_kalshi_market(...)`:

```python
SPORTS_INTENT_PREFIX = "sports:"
UNRESOLVED_MIN_AGE_SECONDS = 60          # a 'sending' claim this old = process died mid-order
UNRESOLVED_GIVE_UP_SECONDS = 15 * 60     # no position after this long = treat as unfilled


def _sports_intent_ticker(ticker: str) -> str:
    return f"{SPORTS_INTENT_PREFIX}{ticker}"


def _size_sports_order(wager: float, price: float) -> tuple:
    """(contracts, worst_case_cost). Worst-case fill (ask + 4c slippage buffer) plus the Kalshi
    taker fee must fit inside the wager. (0, 0.0) if it can't buy one contract."""
    max_p = min(0.99, max(0.01, float(price) + 0.04))
    count = int(float(wager) / max_p) if max_p > 0 else 0
    while count > 0 and (count * max_p + kalshi_order_fee(max_p, count)) > float(wager):
        count -= 1
    if count < 1:
        return 0, 0.0
    return count, round(count * max_p + kalshi_order_fee(max_p, count), 2)
```

The `sports:` prefix keeps sports claims separate from crypto claims in the shared
`order_intents` table.

## Change 3: `_process_user`: one automated LIVE entry per market, fee-aware sizing

1. Right after `avail_live_cash = float(bal_res.get("balance_dollars", 0.0))` (LIVE only), add:
   ```python
   try:
       self._reconcile_uncertain_sports_orders(user, kt)
   except Exception as rec_err:
       logger.error(f"[SportsBridge] Reconciling uncertain orders for user {uid} failed: {rec_err}")
   ```
2. Replace the sizing lines
   `max_p = ...; count = max(1, int(wager / max_p)); cost = round(price * count, 2)` with:
   ```python
   count, worst_cost = _size_sports_order(wager, price)
   if count < 1:
       continue
   cost = round(price * count + kalshi_order_fee(price, count), 2)
   ```
3. In the LIVE branch:
   - Change the cash check to `if avail_live_cash < worst_cost:`.
   - Wrap the order in a claim:
     ```python
     intent_key = order_intents.account_key_for_user(uid)
     intent_ticker = _sports_intent_ticker(ticker)
     if not order_intents.claim(intent_key, intent_ticker, "yes"):
         continue                      # already traded / attempted this market
     order_res = kt.place_sports_order(...)   # unchanged arguments
     outcome = order_intents.settle_outcome(intent_key, intent_ticker, order_res)
     if not order_res.get("success"):
         if outcome == "ambiguous":
             logger.error(... "LIVE order outcome UNKNOWN ... Not retrying; will reconcile" ...)
             open_tickers.add(ticker)
             open_sports_count += 1
             daily_trades_count += 1
             daily_risk_spent += worst_cost
             avail_live_cash -= worst_cost
         else:
             logger.warning(...)       # clean rejection: claim was released, may retry later
         continue
     ```
   - On success: `fill_count = int(float(order_res.get("count") or count))` and
     `actual_cost = round(fill_price * fill_count + kalshi_order_fee(fill_price, fill_count), 2)`.
4. In the PAPER branch, keep the code as is. `cost` now includes the fee, so the paper
   deduction does too.

**Claim semantics** (these reuse the existing `settle_outcome`):
- **Filled:** the claim is kept, so that market is never auto-bought again (fixes bug C). Claims
  are purged after 3 days.
- **Ambiguous:** the claim is kept and the order is never resent (fixes bug A).
- **Clean rejection:** the claim is released, so the pick may be retried on a later cycle, same
  as today.
- **Claim fails to write:** the order is skipped (fail closed).

## Change 4: new method `_reconcile_uncertain_sports_orders(self, user, kt)` (fixes bug B)

Add it just above `_settle_open_trades`. The full code is in the patch. The logic:

1. `pending = order_intents.list_unresolved(account_key_for_user(uid), prefix="sports:", min_age_seconds=60)`.
   If there are none, return.
2. Fetch `kt.get_positions()`. If that fails, return and try again next cycle.
3. For each pending claim (ticker = the claim's ticker minus the `sports:` prefix):
   - **Kalshi shows a YES position** (`kt._extract_side_position(pos, "YES") > 0`) **and there
     is no OPEN trade on that ticker:** insert a LIVE trade record.
     - `entry_price` = `saas_settler._position_avg_price(pos, held)`. If that's `None`, log
       "MANUAL VERIFICATION REQUIRED" and skip.
     - `count` = `int(held)`, and `cost` includes the fee.
     - Set `trading_style="SPORTS_AI"`, `reconciled_from_ambiguous=True`, and an ET timestamp
       string.
     - Then call `order_intents.mark(..., "filled_reconciled")`.
   - **Position shown and already tracked:** just mark it `filled_reconciled`.
   - **No position and the claim is older than 15 minutes:** mark it `no_fill_found`. The claim
     is kept, so the market still isn't re-bought.

## Change 5: `_settle_open_trades`: close once, then credit; pnl net of fees (fixes bugs D and E)

- **Final settlement:**
  - `exit_price = 1.0 if is_win else 0.0`
  - `pnl = net_pnl(entry_price, exit_price, contracts)`
  - Call `TradeStore.close_if_open(uid, t, {exit_price, pnl, "exit_reason": "SETTLEMENT", settled_at})` **first**.
    If it returns False, `continue`.
  - Only after that, for a PAPER win: `credit_user_paper_balance(uid, contracts * 1.0)`.
- **Take-profit:**
  - In the LIVE branch, if `get_authenticated_trader_for_user(user)` returns nothing, **`continue`**,
    so the trade stays OPEN. Don't mark it closed.
  - After a successful sell (or for PAPER): `pnl = net_pnl(entry_price, cur_price, contracts)`,
    then `close_if_open(...)` with `exit_reason=f"TAKE_PROFIT (+{gain_pct:.1f}%)"`, then credit
    PAPER only: `payout - kalshi_order_fee(cur_price, contracts)`.
- Replace both `TradeStore.update_trade(t_id, {...CLOSED...})` calls in these two places with
  `close_if_open`.

## Test changes

- **New file `tests/test_sports_order_safety.py`, 10 tests:**
  - An ambiguous order is never resent.
  - A clean rejection is retried.
  - A closed market isn't re-bought.
  - An ambiguous order counts against the open-trade cap.
  - Reconciliation records a fill once.
  - Sizing stays within the wager.
  - A too-small wager is skipped.
  - The paper deduction includes the fee.
  - A paper win is credited once, with net pnl.
  - A LIVE take-profit with no session stays OPEN.

  On the current code, 9 of the 10 fail. With the patch, all 10 pass.
- **`tests/test_sports_dashboard.py::test_sports_bridge_settle_kx_trades_both_sides`:** assert
  `net_pnl(0.60, 1.0, 10)` / `net_pnl(0.40, 0.0, 10)` instead of `4.0` / `-4.0`. Pnl is now
  net of the entry fee, the same as crypto trades.
- **`tests/test_sports_live_execution.py::test_sports_bridge_live_take_profit_close`:** assert
  `net_pnl(0.40, 0.65, 25)` instead of `round((0.65-0.40)*25, 2)`.

## Acceptance criteria

- [ ] `tests/test_sports_order_safety.py`: 10/10 pass.
- [ ] Sports suites pass, except `test_sports_prediction_client`, which needs port 8057.
- [ ] Full-suite failures match the pre-patch list. No new failures.
- [ ] `grep -n "order_intents.claim(intent_key, intent_ticker" backend/sports_bridge/executor.py` returns a match.
- [ ] `grep -n "count = max(1, int(wager" backend/sports_bridge/executor.py` returns nothing.
- [ ] `grep -n "TradeStore.update_trade(t_id" backend/sports_bridge/executor.py` returns nothing.

## Known, intentionally out of scope

- **Partial LIVE take-profit sells:** if `close_position` fills only part of the order, the
  trade is still recorded as fully closed. This is the same issue as the crypto audit item M3,
  and needs a separate fix.
- **Paper sports fills:** paper entries still fill at the quoted price. They don't use the
  simulated slippage and depth that crypto paper orders get.
- **Simulated settlement:** `_settle_open_trades` still settles legacy paper trades on fake
  `-MKT` tickers as a WIN whenever confidence was ≥ 55%. New auto-trades can't use those
  tickers, but the existing ones inflate paper results. Consider refunding them instead.
