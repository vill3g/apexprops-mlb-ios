# Comprehensive Codebase Logic Audit: 15-Minute Interval Trading & EV Analysis

**Date**: 2026-10-03  
**Auditor**: `explorer_logic_1` (Teamwork Explorer / Quantitative Systems Auditor)  
**Target System**: ShadowTrader AI (Python Trading Backend)  
**Scope**: `contract_eval.py`, `auto_executor/executor.py`, `saas_broadcaster.py`, `stop_manager.py`, `saas_settler.py`, `fees.py`, `loss_analyzer.py`, `indicators.py`  
**Constraint**: Read-only investigation. No source files modified.

---

## Executive Summary

ShadowTrader AI is designed to autonomously trade 15-minute event contracts (specifically CFTC-regulated Kalshi binary options such as `KXBTC15M`, `KXETH15M`, and forex series). A rigorous, line-by-line audit of the backend engines revealed that the system suffers from **structural negative mathematical expectancy ($\mathbb{E} < 0$)** driven by a combination of:
1. **Fee-blind and mathematically inverted Kelly Criterion position sizing** that enters sub-break-even trades while asserting positive edge.
2. **An Asymmetric Payoff Trap in early exits** (`TAKE_PROFIT`, `TRAILING_STOP`, and `DYNAMIC_STOP_LOSS`) that caps winning trades at $+15\text{c}$ to $+21\text{c}$ (after double taker fees) while absorbing $-35\text{c}$ to $-50\text{c}$ on losses, raising the required breakeven win rate from the native $50\%$ to over **$70\%$**.
3. **A Multi-Entry / DCA Death Spiral** that re-enters decaying binary options within 4–8 minutes of expiry or averages down into rapidly declining options.
4. **"Force Trade on PASS" logic (`ignorePass` / `oneShotAiStartTrade`)** that literally executes trades based on an even/odd Unix second coin-flip (`time.time() % 2 == 0`) while bypassing all edge and safety gates.
5. **Omission of the 4-cent ($0.04) slippage buffer** and exchange taker fees from edge calculations.
6. **Quadruple-counting of technical indicators** between heuristic setups and ML feature sets, inflating marginal 51% coin-flips into false 75–80% confidence grades.
7. **Dollar vs. Cent unit mismatch** in Kalshi market-structure gates (`k_yes >= 62.0` comparing dollars to cents), rendering institutional orderbook edge checks permanently dead.

Below is the complete forensic audit detailing the architecture, call chains, exact file paths, line numbers, mathematical proofs, and concrete drop-in code remedies.

---

## 1. 15-Minute Interval Decision Logic & Call Chain

### 1.1 Architecture & Call Topology

The trade decision cycle is orchestrated via a tiered execution pipeline:

```
[backend/worker.py: run_worker()] (Main loop, 2.0s sleep)
  │
  ├── FastExitWatcher (Daemon thread, 1.5s interval)
  │     └── backend/saas_settler.py: fast_exit_check()
  │
  └── For each asset in [BTC, ETH, GOLD, SOL, DOGE, EURUSD, ...]:
        │
        ├── get_auto_executor(asset) [backend/core/registry.py]
        │
        ├── ae.check_and_execute_rollover() [auto_executor/executor.py:612]
        │     ├── Countdown check: get_candle_countdown("15m") [sec_left, sec_elapsed]
        │     ├── Window check: is_rollover_window (0-60s) or is_prediction_window (30-55s)
        │     ├── Market Fetch: kalshi_trader.get_active_15m_market(min_seconds_left=180)
        │     ├── Regime Router: classify_auto_regime() [auto_executor/shared.py:39]
        │     ├── Analyzer Call: evaluate_next_15m_contract() [analyzer/contract_eval.py:30]
        │     ├── Sizing & Kelly: check_risk_budget() & Kelly EV formula [executor.py:1042]
        │     └── Order Dispatch: kalshi_trader.place_order() [executor.py:1107]
        │
        ├── ae.evaluate_and_execute_saas_users() [auto_executor/saas_broadcaster.py:335]
        │     ├── Cached Active Users (15s TTL) & Cached Candles (8s TTL)
        │     ├── Deduplication & Multi-Entry Filter (inflight_orders, 3-entry max)
        │     ├── Grouped Regime & Contract Evaluation
        │     └── ThreadPoolExecutor (Parallel user order placement)
        │
        └── ae.check_settlements() / settle_saas_trades() [settlement.py & saas_settler.py]
```

### 1.2 Rollover Window Timing and Interval Boundary Flaws

In `backend/btc/auto_executor/executor.py` (lines 638–657):
```python
638: countdown_info = _pkg_obj("get_candle_countdown", get_candle_countdown)(timeframe="15m")
639: sec_left = countdown_info.get("seconds_left", 900)
640: sec_elapsed = 900 - sec_left
641: 
642: trading_style = str(self.ai_settings.get("tradingStyle", "SNIPER")).upper()
643: is_rollover_window = sec_elapsed <= 60 or sec_left >= 840
644: is_prediction_window = 30 <= sec_elapsed <= 55 or 845 <= sec_left <= 870
645: 
646: if trading_style in ["MOMENTUM_SURFER", "AMBUSH", "AUTO"]:
647:     window_valid = sec_left >= 180  # No entries within 3 minutes of contract expiry
648: elif trading_style == "PREDICTION":
649:     window_valid = (sec_elapsed >= 90 and sec_left >= 180)
650: else:
651:     window_valid = is_prediction_window if self.prediction_mode else is_rollover_window
```

#### Flaw Formulations:
1. **Loop Sleep vs Window Width Race Condition**:
   - `backend/worker.py` iterates over 10 assets sequentially, sleeping `time.sleep(0.5)` between each, totaling at least 5 seconds of sleep per iteration, plus 10–25 seconds of network overhead fetching order books, funding rates, and indicator data.
   - For `SNIPER` with `prediction_mode = True`, `is_prediction_window` is restricted to $30 \le \text{sec\_elapsed} \le 55$ (a 25-second window). If the worker loop reaches an asset at second 28 and finishes its round at second 58, **the entire trade window is skipped**, causing missed signals on high-conviction intervals.
2. **Premature Entry in AUTO / MOMENTUM_SURFER Mode**:
   - For `trading_style == "AUTO"`, `window_valid = sec_left >= 180`. This condition evaluates to `True` immediately at second 0 of the new candle.
   - Because `current_interval_id == self.last_traded_interval` is checked, the executor fires on the very first loop iteration ($0 \le \text{sec\_elapsed} \le 10$).
   - At second 5, the new 15-minute candle has no volume, no price discovery, and no candle structure. Yet, `executor.py` places the trade immediately at the open without waiting for opening noise or direction to stabilize.

---

## 2. Contract Evaluation, Filtering, and Selection Logic

### 2.1 Heuristic Setups vs ML/RL Model Blending

In `backend/btc/analyzer/contract_eval.py`:
- Lines 347–655 contain rule-based setups that output fixed, static win rates:
  - Bearish/Bullish Liquidity Sweeps: `prob = 82` (Lines 349, 364)
  - Order Block Defense: `prob = 75` (Lines 379, 387)
  - Ascending / Descending Triangles: `prob = 80` (Lines 417, 437)
  - Bollinger Extreme Rejection Pin: `prob = 78` (Lines 504, 513)
  - 3-Candle Climax Exhaustion: `prob = 74` (Lines 527, 545)
  - EMA Ribbon Dynamic Pullback: `prob = 70` (Lines 561, 569)
  - Dual Green/Red Momentum: `prob = 64` (Lines 581, 594)
- Then, in lines 762–800, `contract_eval.py` blends this heuristic probability with the live ML prediction:
  ```python
  774: effective_heuristic_weight = 1.0 - effective_ml_weight
  775: disagreement = abs(prob - ml_prob_for_pred_dir)
  776: blended_prob = (prob * effective_heuristic_weight) + (ml_prob_for_pred_dir * effective_ml_weight)
  ...
  800: prob = blended_prob
  ```

#### Algorithmic Flaw: Multicollinearity and Quadruple Counting:
1. `build_live_ml_features()` (`backend/btc/ml_engine.py`, lines 253–265) takes the technical indicators (`rsi`, `bb_upper`, `ema_9`, `cvd`) **AND `heuristic_score`** (the setup score) directly as input features for the PyTorch/XGBoost model.
2. The model outputs a probability `ml_prob` that **already incorporates** the chart setup.
3. `contract_eval.py` (line 776) blends the heuristic score *again* with the model output:
   $$\text{Prob}_{\text{blended}} = 0.40 \cdot \text{Heuristic} + 0.60 \cdot \text{ML}$$
4. Lines 842–858 add an Up/Down Pattern Watch nudge:
   $$\text{Prob} = \text{Prob} + \text{nudge} \quad (\approx +3\text{ to }+5\%)$$
5. Lines 860–869 add a Kalshi Whale Order Flow nudge:
   $$\text{Prob} = \text{Prob} + 5\%$$
6. Lines 1174–1180 (`PREDICTION` style) add another chart confirmation nudge:
   $$\text{Prob} = \text{Prob} + 5\%$$

**Impact**: An essentially random 50.5% market is systematically pumped into a "75% Grade A Setup." When this inflated probability is fed into Kelly position sizing, the engine allocates oversized capital to random market noise.

---

## 3. Mathematical & Logical Flaw Formulations (Negative EV Root Causes)

### 3.1 Flaw 1: Fee-Omitted & Lower-Clamped Kelly Criterion Position Sizing

#### Exact Locations:
- `backend/btc/auto_executor/executor.py`, lines 1042–1052 (`check_and_execute_rollover`)
- `backend/btc/auto_executor/executor.py`, lines 1346–1356 (`execute_manual_trade`)
- `backend/btc/auto_executor/saas_broadcaster.py`, lines 228–238, 263–272, 946–955, 1023–1033

#### Code in Codebase (`executor.py:1042-1052`):
```python
1042: use_kelly = bool(self.ai_settings.get("useKellyCriterion", False)) or bool(self.ai_settings.get("use_kelly_criterion", False))
1043: if use_kelly:
1044:     p_win = float(actual_conf) / 100.0 if actual_conf else 0.50
1045:     b_price = float(market_price)
1046:     if p_win <= b_price:
1047:         logger.info(f"[AutoExecutor] Kelly Criterion (-EV Setup): Skipping {side.upper()} @ ${b_price:.2f} (win prob {p_win*100:.1f}% <= price ${b_price:.2f})")
1048:         return None
1049:     edge = p_win - b_price
1050:     kelly_frac = min(1.0, max(0.25, edge / 0.15))
1051:     base_dollars = (max_cap if max_cap > 0 else (self.max_contracts * unit_price_est)) * kelly_frac
1052:     contracts_to_buy = max(1, int(base_dollars / unit_price_est))
```

#### Mathematical Proof of Negative EV:
For a binary option priced at $b$ (in dollars, $0 < b < 1$) paying $\$1.00$ on win and $\$0.00$ on loss, Kalshi charges an entry taker fee:
$$F_{\text{in}} = \left\lceil 0.07 \cdot b \cdot (1 - b) \cdot 100 \right\rceil / 100$$
At $b = 0.50$:
$$F_{\text{in}} = \lceil 0.07 \cdot 0.25 \cdot 100 \rceil / 100 = \lceil 1.75 \rceil / 100 = \$0.02$$

The True Expected Value of 1 contract with win probability $p$ is:
$$\mathbb{E}[\text{PnL}] = p \cdot (1 - b - F_{\text{in}}) - (1 - p) \cdot (b + F_{\text{in}}) = p - b - F_{\text{in}}$$

1. **Fee-Blind Negative EV Gate**:
   Line 1046 tests `if p_win <= b_price: return None`.
   It completely omits $F_{\text{in}}$.
   Suppose $p = 0.51$ (51% win probability) and $b = 0.50$:
   - Code checks: $0.51 > 0.50 \implies \text{Passed! Positive edge!}$
   - True Expected Value:
     $$\mathbb{E}[\text{PnL}] = 0.51 - 0.50 - 0.02 = -\$0.01 \quad (\mathbf{-2.0\%\text{ ROI on Capital}})$$
   The engine executes a mathematically guaranteed negative-expectancy trade.

2. **The 25% Lower Bound Allocation Clamp**:
   Line 1050 defines `kelly_frac = min(1.0, max(0.25, edge / 0.15))`.
   Even when edge is $+0.001$ (or negative after fees), `max(0.25, ...)` forces allocation to **at least 25% of maximum capital**.
   Standard Kelly sizing formula for binary options is:
   $$f^* = \frac{p - b}{1 - b}$$
   As $p \to b$, $f^* \to 0$. By forcing a floor of $0.25$, the bot over-bets on razor-thin edges, accelerating account drawdown.

3. **Scope Variable Bug in `execute_manual_trade` (`executor.py:1348`)**:
   ```python
   1348: p_win = float(conf) / 100.0 if ('conf' in locals() and conf) else 0.50
   ```
   The variable `conf` is never declared or assigned in `execute_manual_trade`.
   Therefore, `'conf' in locals()` evaluates to `False` on every call.
   `p_win` is permanently hardcoded to `0.50`.
   As a result, whenever `market_price >= 0.50`, the trade is rejected with `-EV Setup (prob 50.0% <= price)`, and whenever `market_price < 0.50`, it sizes as if win probability is strictly 50%, completely ignoring the ML prediction.

---

### 3.2 Flaw 2: The Asymmetric Payoff Trap in Early Exits (TP/SL Payoff Inversion)

#### Exact Locations:
- `backend/btc/auto_executor/stop_manager.py`, lines 220–223, 345–356 (`TAKE_PROFIT`), lines 358–378 (`TRAILING_TAKE_PROFIT`), lines 381–395 (`CONTRACT_STOP_LOSS`), lines 411–435 (`STRUCTURAL_STOP_LOSS`)
- `backend/saas_settler.py`, lines 281–295 (`fast_exit_check`)

#### Code in Codebase (`stop_manager.py`):
```python
223: take_profit_percent = float(self.ai_settings.get("take_profit_pct", self.ai_settings.get("takeProfitPercent", 50.0)))
...
345: if take_profit_enabled and profit_pct >= take_profit_percent:
346:     close_res = self.close_specific_trade(trade_id, reason="TAKE_PROFIT", estimated_exit_price=bid_price)
...
358: ts_enabled = bool(self.ai_settings.get("trailing_stop_enabled", False))
359: ts_activation = float(self.ai_settings.get("trailing_stop_activation_pct", 35.0))
360: ts_distance = float(self.ai_settings.get("trailing_stop_distance_pct", 6.0)) / 100.0
...
381: stop_loss_pct = float(self.ai_settings.get("stop_loss_pct", self.ai_settings.get("stopLossPercent", 50.0)))
383: if sl_enabled and profit_pct <= -stop_loss_pct:
384:     close_res = self.close_specific_trade(trade_id, reason="CONTRACT_STOP_LOSS", estimated_exit_price=bid_price)
...
432: est_exit = round(max(0.01, min(0.35, entry_price - 0.25)), 2)
433: close_res = self.close_specific_trade(trade_id, reason="DYNAMIC_STOP_LOSS", estimated_exit_price=est_exit)
```

#### Mathematical Proof of Negative EV:
A natural 15-minute binary contract held to settlement has symmetric payoff around $0.50$:
- Settlement Win: $+(\$1.00 - \$0.50) = +\$0.50$ (Entry fee $0.02 \implies \text{Net } +\$0.48$).
- Settlement Loss: $-(\$0.50) = -\$0.50$ (Entry fee $0.02 \implies \text{Net } -\$0.52$).
- Natural Reward-to-Risk Ratio: $R = \frac{0.48}{0.52} = 0.923$.
- Required Breakeven Win Rate:
  $$W_{\text{breakeven}} = \frac{1}{1 + R} = \frac{1}{1 + 0.923} = 52.0\%$$

Now examine what happens when early TP and SL are active:
1. **Take Profit Upside Capping**:
   Entry price $b = \$0.50$.
   `take_profit_percent = 50.0%` triggers when bid reaches $\$0.75$.
   Gross gain $= \$0.25$.
   Taker entry fee $= \$0.02$.
   Taker exit fee at $\$0.75$:
   $$F_{\text{exit}} = \lceil 0.07 \cdot 0.75 \cdot 0.25 \cdot 100 \rceil / 100 = \lceil 1.3125 \rceil / 100 = \$0.02$$
   Net Realized Win:
   $$W_{\text{net}} = \$0.25 - \$0.02 - \$0.02 = +\mathbf{\$0.21}$$
2. **Trailing Stop Noise Harvesting**:
   `ts_activation = 35%` (activates at bid $=\$0.675$), with `ts_distance = 6%` ($0.06$).
   Normal Kalshi spread oscillation causes the bid to dip from $\$0.68$ to $\$0.62$.
   Exit executes at $\$0.62$.
   Net Realized Win $= \$0.12 - \$0.02 - \$0.02 = +\mathbf{\$0.08}$.
3. **Stop-Loss Execution Deficit**:
   When spot price moves against the contract, the Kalshi orderbook bid collapses (e.g., $0.50 \to 0.15$).
   Line 432 models salvage exit at $\text{entry} - 0.25 = \$0.25$ or worse.
   Net Realized Loss:
   $$L_{\text{net}} = -(\$0.50 - \$0.15) - \$0.02 - \$0.01 = -\mathbf{\$0.38} \text{ to } -\mathbf{\$0.52}$$
4. **Calculated Expectancy Inversion**:
   - Average Win: $\bar{W} \approx +\$0.18$.
   - Average Loss: $\bar{L} \approx -\$0.42$.
   - Payoff Ratio:
     $$R = \frac{\bar{W}}{\bar{L}} = \frac{0.18}{0.42} = \mathbf{0.428}$$
   - Required Win Rate to Break Even:
     $$W_{\text{breakeven}} = \frac{1}{1 + 0.428} = \frac{1}{1.428} = \mathbf{70.0\%}$$

**Conclusion**: The early exit management turns an instrument requiring a 52% win rate into a high-churn strategy requiring a **70% win rate**. A standard ML model predicting with 55–60% accuracy will experience rapid, monotonic account decay.

---

### 3.3 Flaw 3: Multi-Entry / DCA Death Spiral (Re-entering Decaying Options)

#### Exact Locations:
- `backend/btc/auto_executor/stop_manager.py`, lines 637–665, 752–780, 836–878 (`_attempt_profit_reentry`)
- `backend/saas_settler.py`, lines 352–500 (`trigger_saas_take_profit_reentry`)
- `backend/btc/auto_executor/saas_broadcaster.py`, lines 837–882

#### Code in Codebase (`stop_manager.py` & `saas_broadcaster.py`):
```python
# stop_manager.py:736-745
736: if chart_conflict:
737:     if is_stop_loss:
738:         side = "yes" if side == "no" else "no"
739:         direction = "ABOVE" if side == "yes" else "BELOW"
740:         min_conf = float(self.ai_settings.get("minConf", 60.0))
741:         conf = max(60.0, min_conf)
742:         is_side_flipped = (side != closed_side)
743:         logger.warning(f"[AutoExecutor] Re-entry auto-pivot: Chart conflict detected on stop-loss. Auto-pivoting side to {side.upper()} to ride physical chart trend against ML advice (synthetic conf {conf}%).")

# saas_broadcaster.py:877-881
877: initial_entry_price = float(prior_entries[-1].get("entry_price") or 0.50)
878: dca_target_max = initial_entry_price * 0.85
879: if market_price > dca_target_max:
880:     logger.info(f"... skipped DCA re-entry #{entry_num}: ask ${market_price:.2f} is not discounted >= 15% ...")
881:     return
```

#### Logical & Mathematical Flaws:
1. **The Post-TP Re-entry Trap**:
   - Trade 1 enters at $\$0.50$, exits on TP at $\$0.75$, netting $+\$0.21$.
   - The engine immediately executes Re-entry #2 on the same contract at $\$0.70$ with only 5 minutes remaining before expiry.
   - At 5 minutes to expiry, binary options exhibit extreme gamma risk. If BTC retraces by even $\$20$, the contract drops from $\$0.70$ to $\$0.00$, losing $\$0.72$ (with entry fee).
   - Net Interval Outcome: $+\$0.21 - \$0.72 = -\mathbf{\$0.51}$. A winning interval is transformed into a major loss.
2. **DCA on Decaying Out-of-the-Money Options (`saas_broadcaster.py:878`)**:
   - The DCA rule requires that the contract ask price drops below $85\%$ of the initial entry price ($0.50 \times 0.85 = \$0.425$).
   - In a 15-minute binary contract, the price drops to $\$0.42$ precisely because the underlying spot has moved away from the strike, and theta decay is accelerating toward zero.
   - Averaging down on an option with minutes to expiry compounds risk into a dying asset.
3. **Synthetic Confidence Fabrication on Stopped Trades (`stop_manager.py:741`)**:
   - When a stop loss is hit, line 741 literally fabricates `conf = max(60.0, min_conf)`.
   - It synthesizes a false confidence score of 60% out of thin air, reverses the trade direction, and fires an immediate second order against the ML model's prediction.

---

### 3.4 Flaw 4: "Force Trade on PASS" (`ignorePass` / `oneShotAiStartTrade`) Bypasses All Gates and Flips Coins

#### Exact Locations:
- `backend/btc/auto_executor/executor.py`, lines 822–858, 918–923
- `backend/btc/auto_executor/saas_broadcaster.py`, lines 730–768, 822–830, 897–905

#### Code in Codebase (`saas_broadcaster.py:752-764` & `897-905`):
```python
752: else:
753:     # Extreme fallback: look at physical chart trend and short-term momentum
754:     c_eval = df_ind_target.iloc[-1]
755:     c_close = float(c_eval["close"])
756:     ema_9 = float(c_eval.get("ema_9", c_close))
757:     ema_21 = float(c_eval.get("ema_21", c_close))
758:     trend = str(c_eval.get("trend_1h", "FLAT")).upper()
759:     if trend in ["UP", "BULLISH"] or (ema_9 > ema_21 and ema_21 > 0):
760:         side = "yes"
761:     elif trend in ["DOWN", "BEARISH"] or (ema_9 < ema_21 and ema_21 > 0):
762:         side = "no"
763:     else:
764:         side = "yes" if int(time.time()) % 2 == 0 else "no"
765:     conf = 51.0
...
897: if not is_auto_force and not is_one_shot and u_source != "RL_SCALPER" and bool(user.get("edge_gate_enabled", 1)):
898:     min_edge = float(user.get("min_edge_cents", 0.0) or 0.0)
899:     edge = entry_edge_cents(conf, market_price)
900:     if edge <= min_edge:
901:         return
```

#### Logical Flaw:
- Line 764: The system executes live orders based on `time.time() % 2 == 0` (even seconds buy YES, odd seconds buy NO).
- Line 897: `if not is_auto_force and not is_one_shot`: The entire `edge_gate` check is explicitly bypassed.
- Line 823: `if is_ignore_pass_tech or is_auto_force or is_one_shot`: The chart conflict guard is bypassed.
- Line 920: `if is_forced_pass or is_reverse: meets_conviction = True`: All conviction thresholds are bypassed.
- **Mathematical Expectancy**: Pure 50/50 coin-flip minus taker fee ($0.02) and slippage buffer ($0.04):
  $$\mathbb{E} = 0.50 \cdot (1.0 - 0.50) - 0.50 \cdot 0.50 - 0.02 - 0.04 = -\mathbf{\$0.06\text{ per contract}} \quad (\mathbf{-12.0\%\text{ ROI per trade}})$$

---

### 3.5 Flaw 5: Disconnect Between 4-Cent Slippage Buffer and Edge Gate

#### Exact Locations:
- `backend/btc/fees.py`, lines 25–31 (`entry_edge_cents`)
- `backend/btc/auto_executor/executor.py`, line 1092 (`slippageBufferDollars = 0.04`)
- `backend/btc/auto_executor/saas_broadcaster.py`, lines 240, 249, 273, 281, 897–905, 957, 986, 1034, 1042

#### Code in Codebase (`fees.py:25-31`):
```python
25: def entry_edge_cents(prob_percent: float, ask: float) -> float:
26:     """Expected profit per contract, in cents, of buying one contract at `ask` when that side
27:     wins with probability prob_percent, after the taker entry fee. Held to settlement there is
28:     no exit fee. Positive = the price is cheaper than the forecast says it is worth."""
29:     p = float(prob_percent) / 100.0
30:     a = min(max(float(ask), 0.0), 1.0)
31:     return round((p - a - TAKER_FEE_RATE * a * (1.0 - a)) * 100.0, 1)
```

#### Mathematical Flaw:
1. `entry_edge_cents` evaluates edge at the displayed top-of-book ask price $a$.
2. The order is placed via `kalshi_trader.place_order(slippage_buffer_dollars=0.04)`.
3. In Kalshi's matching engine, an IOC order with a $0.04$ buffer executes at any price up to $a + 0.04$.
4. Example:
   - Ask $a = \$0.50$, Forecast Win Probability $p = 52.5\%$.
   - `entry_edge_cents(52.5, 0.50) = (0.525 - 0.50 - 0.0175) * 100 = +0.75\text{ cents}`.
   - Edge Gate allows trade: $+0.75\text{c} > 0.0\text{c}$.
   - Order executes at $a_{\text{fill}} = \$0.53$ due to allowable slippage.
   - Realized Entry Cost: $\$0.53 + \$0.02 = \$0.55$.
   - True Realized EV: $0.525 - 0.55 = -\mathbf{\$0.025}$ (**Negative EV**).
5. In addition, line 31 uses `TAKER_FEE_RATE * a * (1.0 - a)` without `math.ceil()`, underestimating the 1-contract taker fee ($0.0175$ vs actual charged $0.02$).

---

### 3.6 Flaw 6: SNIPER Negative EV Gate Is Bypassed in Other Modes

#### Exact Location:
- `backend/btc/analyzer/contract_eval.py`, lines 1107–1125

#### Code in Codebase (`contract_eval.py:1107-1125`):
```python
1107: if trading_style == "SNIPER" and iso_setting != "AI_ONLY" and kalshi_m and direction in ["ABOVE", "BELOW", "YES", "NO"]:
1108:     side_key = "yes_ask" if direction in ["ABOVE", "YES"] else "no_ask"
1109:     try:
1110:         kalshi_ask = float(kalshi_m.get(side_key) or 0.50)
1111:     except (ValueError, TypeError) as e:
1112:         kalshi_ask = 0.50
1113: 
1114:     min_ev = kalshi_ask + 0.05
1115:     current_prob = float(prob) / 100.0
1116:     
1117:     if current_prob <= min_ev:
1118:         catalysts.insert(0, f"⛔ Negative EV Block: ML Prob ({current_prob*100:.1f}%) <= Kalshi Ask ({kalshi_ask*100:.0f}c) + 5% Edge.")
1119:         pred = "PASS / NO BID (NEGATIVE EV)"
1120:         direction = "PASS"
1121:         grade = "PASS / POOR RISK REWARD"
1122:         badge = "⚪ PASS (NEGATIVE EV)"
1123:         prob = 50.0
```

#### Logical Flaw:
- Condition `trading_style == "SNIPER"` restricts this negative EV gate exclusively to SNIPER.
- In `AUTO` mode, whenever the market is routed to `MOMENTUM_SURFER`, `AMBUSH`, or `CHOP`, or whenever `iso_setting == "AI_ONLY"`, this check **never runs**.
- Positions are opened at ask prices far exceeding model win probabilities (e.g. buying at $0.65 with a 55% model probability), locking in negative expected value.

---

### 3.7 Flaw 7: Dollar vs Cent/Percentage Unit Mismatch in Kalshi Market Structure

#### Exact Locations:
- `backend/btc/analyzer/contract_eval.py`, lines 638–657
- `backend/btc/analyzer/config.py`, lines 25–26

#### Code in Codebase (`contract_eval.py:638-650`):
```python
638: if kalshi_m and "GRADE A" not in grade:
639:     k_yes = float(kalshi_m.get("yes_ask", 50) if kalshi_m.get("yes_ask") else 50)
640:     k_no = float(kalshi_m.get("no_ask", 50) if kalshi_m.get("no_ask") else 50)
641:     imbalance = float(kalshi_m.get("book_imbalance", 0.0) if kalshi_m.get("book_imbalance") else 0.0)
642: 
643:     if k_yes >= THRESHOLDS["kalshi_override_yes"] or imbalance >= THRESHOLDS["kalshi_imbalance_threshold"]:
644:         pred = "BID YES (ABOVE TARGET)"
...
```
And in `backend/btc/analyzer/config.py`:
```python
25: "kalshi_override_yes": 62.0,
26: "kalshi_override_no": 62.0,
```

#### Logical Flaw:
- In `backend/btc/kalshi_client.py` (lines 140–142), `kalshi_m["yes_ask"]` is stored in dollars: `0.52`.
- In `config.py`, `THRESHOLDS["kalshi_override_yes"]` is `62.0` (cents/percentage).
- Line 643 evaluates `0.52 >= 62.0`, which is **always False**.
- This entire price-override confluence check is dead code due to a unit mismatch between dollars ($0.0–1.0) and percentage (0–100).

---

### 3.8 Flaw 8: Ineffective Dead-Zone Filter and Fixed-Dollar Checks on Non-BTC Assets

#### Exact Locations:
- `backend/btc/analyzer/contract_eval.py`, lines 110–134 (`max_atr_threshold = target * (45.0 / 60000.0)`)
- `backend/btc/auto_executor/executor.py`, lines 1009–1017 (`delta_strike < -25.0`)
- `backend/btc/auto_executor/saas_broadcaster.py`, lines 814–820 (`delta_strike < -25.0`)
- `backend/btc/auto_executor/stop_manager.py`, lines 243 (`stopLossMoveDollars = 140.0`), 412 (`deficit > 35.0`)

#### Logical Flaws:
1. **Unreachable ATR Threshold on BTC**:
   - `max_atr_threshold = target * (45.0 / 60000.0)`. On BTC ($65k), this equals $\$48.75$.
   - Normal 15-minute ATR on Bitcoin is $\$150$–$\$350$.
   - Because the condition requires `atr <= 48.75` AND `delta <= 19.50`, the dead-zone filter almost never activates during normal market conditions. The bot continues entering trades when spot is $\$2$ from the strike, where settlement is an unpredictable 50/50 tick coin-flip.
2. **Fixed Dollar Thresholds on Non-BTC Assets**:
   - `delta_strike < -25.0`, `deficit > 35.0`, and `stopLossMoveDollars = 140.0` are hardcoded dollar amounts.
   - When trading `EURUSD` (price $\approx 1.08$), `SOL` ($\approx \$150$), or `DOGE` ($\approx \$0.15$), spot price will never deviate by $\$25.00$ or $\$140.00$.
   - Chart trend conflict checks and structural stop losses **never fire on non-BTC assets**, leaving positions unhedged and exposed to 100% loss at expiry.

---

### 3.9 Flaw 9: 15-Second Expiry Proximity Trade Entries

#### Exact Locations:
- `backend/btc/auto_executor/saas_broadcaster.py`, line 362 (`if sec_left < 15: return`), lines 713–714
- `backend/saas_settler.py`, lines 444–446 (`if remaining_sec < 15: return None`)
- `backend/btc/auto_executor/stop_manager.py`, lines 649–650 (`if minutes_remaining < 0.25: return None`)

#### Code in Codebase (`saas_broadcaster.py:361-363`):
```python
361: # Expiration Safety Guard: Never enter brand new trades within 180s (3 minutes) of expiration
362: if sec_left < 15:
363:     return
```

#### Execution & EV Flaw:
- The code comment explicitly states: *"Never enter brand new trades within 180s (3 minutes) of expiration"*, but the code checks `if sec_left < 15: return`.
- At 16–60 seconds before expiry:
  - Market makers pull liquidity, widening spreads from 2 cents to 15–30 cents.
  - Network request latency (1–3 seconds) and Kalshi order matching delays mean orders placed at second 885 fill at second 888 or expire before execution.
  - Any trade executed with $< 3\text{ minutes}$ left pays massive spread penalties and incurs guaranteed negative EV.

---

### 3.10 Flaw 10: Disconnected Loss Diagnosis & Dynamic Regime Feedback

#### Exact Locations:
- `backend/btc/loss_analyzer.py`, lines 18–95 (`diagnose_loss`), lines 114–130 (`calculate_regime_penalties`)

#### Code in Codebase (`loss_analyzer.py:114-118`):
```python
114: # Count loss categories from trade histories or internal list
115: categories = [t.get("loss_analysis", {}).get("category", "") for t in losses if t.get("loss_analysis")]
116: chop_count = sum(1 for c in categories if "CHOPPY" in c or "PIN" in c)
117: breakout_count = sum(1 for c in categories if "FALSE_BREAKOUT" in c)
```

#### Logical Flaw:
- The method `diagnose_loss()` in `loss_analyzer.py` is **never called anywhere in the active codebase** upon trade settlement.
- Losing trades stored in `trades_history.json` and SQLite `TradeStore` never contain a `"loss_analysis"` dictionary.
- In `calculate_regime_penalties()`, `categories` is always empty, `chop_count` is always 0, and `breakout_count` is always 0.
- The dynamic regime protection that was intended to reduce confidence and increase RSI margins during chop or false breakouts is completely disconnected and dead.

---

### 3.11 Flaw 11: Active Candle vs Finalized Candle Feature Alignment

#### Exact Locations:
- `backend/btc/analyzer/contract_eval.py`, lines 78–88, lines 252–265, lines 1074–1105

#### Code in Codebase (`contract_eval.py:78-88`):
```python
78: now_epoch = int(time.time())
79: is_mid_candle = (now_epoch % 900) > 120
80: if trading_style in ["MOMENTUM_SURFER", "AMBUSH", "BLEND"] or (trading_style == "AUTO" and is_mid_candle):
81:     c = df_ind.iloc[-1]
82:     p = df_ind.iloc[-2] if n >= 2 else df_ind.iloc[-1]
83:     p2 = df_ind.iloc[-3] if n >= 3 else df_ind.iloc[-2]
84: else:
85:     c = df_ind.iloc[-2] if n >= 2 else df_ind.iloc[-1]
86:     p = df_ind.iloc[-3] if n >= 3 else df_ind.iloc[-2]
87:     p2 = df_ind.iloc[-4] if n >= 4 else df_ind.iloc[-3]
```

#### Analytical Flaw:
- When evaluated at rollover (`sec_elapsed <= 120`) in `SNIPER` or `AUTO` mode:
  - Chart indicators (`rsi`, `upper_wick`, `lower_wick`, `range_closure`) are computed on candle `iloc[-2]` (the old, finalized candle).
  - Strike distance `delta_target_pts = c_close - target` (line 929) computes the difference between **the old candle's close from 15 minutes ago** and the new Kalshi strike, instead of using current spot price.
  - Meanwhile, `build_live_ml_features()` (line 253) passes `c=active_cand` (`iloc[-1]`).
  - The heuristic rules evaluate candle $t-1$, the ML model evaluates candle $t$, and their outputs are blended together despite referencing different market points.

---

## 4. Master Vulnerability Catalog & Code Locations

| # | Vulnerability / Algorithmic Flaw | Primary File Path | Line Numbers | Function / Method Name | Impact on P&L / EV |
|---|----------------------------------|-------------------|--------------|------------------------|-------------------|
| **1** | Fee-Blind & Clamped Kelly EV Formulation | `backend/btc/auto_executor/executor.py`<br>`backend/btc/auto_executor/saas_broadcaster.py` | `executor.py:1042-1052`<br>`executor.py:1346-1356`<br>`saas:228-238, 946-955` | `check_and_execute_rollover`<br>`execute_manual_trade`<br>`_execute_single_user_trade` | Critical (-EV trades entered; 25% lower size clamp over-bets) |
| **2** | Asymmetric Payoff Trap in Early Exits | `backend/btc/auto_executor/stop_manager.py`<br>`backend/saas_settler.py` | `stop_manager.py:220-435`<br>`saas_settler.py:281-295` | `check_active_trades_stop_and_reversal`<br>`fast_exit_check` | Critical (Caps wins at $+21\text{c}$, takes losses at $-42\text{c}$; requires 70% breakeven WR) |
| **3** | Multi-Entry & DCA Death Spiral | `backend/btc/auto_executor/stop_manager.py`<br>`backend/saas_settler.py`<br>`backend/btc/auto_executor/saas_broadcaster.py` | `stop_manager.py:637-878`<br>`saas_settler.py:352-500`<br>`saas:837-882` | `_attempt_profit_reentry`<br>`trigger_saas_take_profit_reentry` | High (Averages down on decaying options near expiry; wipes out wins) |
| **4** | Force Trade Coin-Flip & Safety Bypass | `backend/btc/auto_executor/executor.py`<br>`backend/btc/auto_executor/saas_broadcaster.py` | `executor.py:822-858`<br>`saas:752-768, 897-905` | `check_and_execute_rollover`<br>`_execute_single_user_trade` | High (Flips `time.time()%2` coin-flips; completely bypasses edge gates) |
| **5** | Omission of 4¢ Slippage in Edge Gate | `backend/btc/fees.py`<br>`backend/btc/auto_executor/saas_broadcaster.py` | `fees.py:25-31`<br>`saas:897-905, 1092` | `entry_edge_cents`<br>`_execute_single_user_trade` | High (Allows trades that become negative EV after 4¢ allowable slippage) |
| **6** | Heuristic Probability Inflation & Quadruple Counting | `backend/btc/analyzer/contract_eval.py` | `contract_eval.py:347-655, 774-800, 842-869, 1169-1180` | `evaluate_next_15m_contract` | High (Multi-counts same indicators, turning 51% noise into fake 75% confidence) |
| **7** | SNIPER Negative EV Gate Bypassed in AUTO/AI_ONLY | `backend/btc/analyzer/contract_eval.py` | `contract_eval.py:1107-1125` | `evaluate_next_15m_contract` | High (Trades with prob < ask allowed in AUTO, MOMENTUM_SURFER, AMBUSH) |
| **8** | Dollar vs Cent Unit Mismatch in Kalshi Gate | `backend/btc/analyzer/contract_eval.py`<br>`backend/btc/analyzer/config.py` | `contract_eval.py:638-657`<br>`config.py:25-26` | `evaluate_next_15m_contract` | Medium (Compares $0.52 >= 62.0; market structure edge permanently dead) |
| **9** | Fixed-Dollar Thresholds on Non-BTC Assets | `backend/btc/analyzer/contract_eval.py`<br>`backend/btc/auto_executor/stop_manager.py` | `contract_eval.py:110-134`<br>`stop_manager.py:243, 412` | `evaluate_next_15m_contract`<br>`check_active_trades_stop_and_reversal` | High (Stop losses and dead-zone filters never trigger on Forex, SOL, DOGE) |
| **10** | 15-Second Expiry Proximity Trade Entries | `backend/btc/auto_executor/saas_broadcaster.py`<br>`backend/saas_settler.py` | `saas:362, 713-714`<br>`saas_settler.py:444` | `evaluate_and_execute_saas_users`<br>`trigger_saas_take_profit_reentry` | High (Enters illiquid binary options 16s before expiry, suffering wide spreads) |
| **11** | Disconnected Loss Diagnosis Feedback Loop | `backend/btc/loss_analyzer.py` | `loss_analyzer.py:18-95, 114-130` | `diagnose_loss`<br>`calculate_regime_penalties` | Medium (Loss analysis never populated; dynamic chop penalties inoperative) |

---

## 5. Concrete Remediation Blueprint & Actionable Code Patches

To transition the trading engine from negative expected value ($\mathbb{E} < 0$) to positive expected value ($\mathbb{E} > 0$), the following surgical fixes must be implemented.

### 5.1 Remediation 1: Fee- & Slippage-Adjusted Kelly Criterion Formulation

Replace the naive Kelly check in `auto_executor/executor.py` (lines 1042–1052 and 1346–1356) and `saas_broadcaster.py` with rigorous binary options half-Kelly sizing that incorporates exchange taker fees and execution slippage buffers:

```python
# PROPOSED REMEDIATION for executor.py & saas_broadcaster.py
def calculate_binary_kelly_size(
    win_prob: float, 
    ask_price: float, 
    max_capital: float, 
    slippage_buffer: float = 0.04,
    fractional_multiplier: float = 0.50  # Half-Kelly for risk conservation
) -> dict:
    """
    Computes true fee- and slippage-adjusted Expected Value (EV) and Half-Kelly sizing
    for a $1.00 binary contract.
    """
    p = float(win_prob)
    # Conservative execution assumption: assume worst-case fill within slippage corridor
    effective_entry = min(0.99, float(ask_price) + slippage_buffer)
    
    # Kalshi taker entry fee: ceil(0.07 * count * p * (1-p)) dollars
    fee_in = math.ceil(0.07 * effective_entry * (1.0 - effective_entry) * 100.0) / 100.0
    
    # Net profit upon winning (held to settlement, zero exit fee)
    net_win = 1.0 - effective_entry - fee_in
    # Net loss upon losing
    net_loss = effective_entry + fee_in
    
    # True Expected Value per contract in dollars
    ev = (p * net_win) - ((1.0 - p) * net_loss)
    
    # Strict EV Gate: If expected value <= 0, abort immediately (zero position)
    if ev <= 0.005:  # Require at least +0.5 cents positive EV per contract
        return {"contracts": 0, "ev": ev, "edge_percent": 0.0, "reason": "NEGATIVE_OR_NEGLIGIBLE_EV"}
    
    # True Binary Kelly fraction: f* = (p * b - q) / b where b = net_win / net_loss
    b_odds = net_win / net_loss
    q = 1.0 - p
    f_star = (p * b_odds - q) / b_odds
    
    if f_star <= 0:
        return {"contracts": 0, "ev": ev, "edge_percent": 0.0, "reason": "KELLY_ZERO_OR_NEGATIVE"}
        
    # Scale by fractional multiplier (Half-Kelly) and cap to maximum 20% portfolio risk
    f_allocated = min(0.20, f_star * fractional_multiplier)
    
    dollars_to_risk = max_capital * f_allocated
    contracts = int(dollars_to_risk / effective_entry)
    
    return {
        "contracts": max(1, contracts),
        "ev": round(ev, 4),
        "edge_percent": round((ev / effective_entry) * 100.0, 2),
        "f_star": round(f_star, 4),
        "effective_entry": effective_entry
    }
```

---

### 5.2 Remediation 2: Elimination of the Asymmetric Payoff Trap in Binary Contracts

Binary contracts are non-linear, path-independent derivatives whose fair value naturally converges to $\$1.00$ or $\$0.00$ at $T_{\text{expiry}}$. Overlaying early scalping exits creates structural negative EV.

**Remediation Rule**:
1. **Hold to Settlement as Primary Baseline**: Disable default early `take_profit` and `trailing_stop` on contracts where the trade has positive structural thesis.
2. **Asymmetric Risk-Reward Alignment**: If take-profit is utilized, it must **never exit below the full binary payoff ($>\$0.88$)** unless an explicit structural invalidation occurs.
3. **Minimum Time-to-Expiry Threshold ($T_{\text{cutoff}}$)**:
   In `saas_broadcaster.py:362`, enforce a hard 180-second ($3\text{ minute}$) cutoff:
   ```python
   # PROPOSED FIX for saas_broadcaster.py:362 and stop_manager.py:649
   EXPIRATION_ENTRY_CUTOFF_SECONDS = 180  # Hard 3-minute cutoff
   if sec_left < EXPIRATION_ENTRY_CUTOFF_SECONDS:
       logger.debug(f"[AutoExecutor] Expiration Proximity Gate: {sec_left}s remaining < 180s minimum. Skipping entry.")
       return
   ```

---

### 5.3 Remediation 3: Disabling Destructive Multi-Entry DCA

Replace the DCA dip re-entry in `saas_broadcaster.py` (lines 877–881) and `stop_manager.py`:
- In binary contracts, **never average down into a declining contract within the same 15-minute interval**.
- When a contract drops 15% below entry, its probability of expiring in the money has decreased. Buying more contracts compounds losses.
- Single-entry discipline: Limit each 15-minute contract interval to **exactly 1 entry per account**.

```python
# PROPOSED FIX for saas_broadcaster.py:416-433
# Enforce strict 1-trade per contract discipline:
interval_trades = [t for t in loaded_hist if t.get("ticker") == current_interval_id]
if interval_trades:
    logger.debug(f"[SaaS Broadcast] User {user.get('username')} already traded interval {current_interval_id}. Multiple entry disabled.")
    with _user_last_traded_lock:
        _user_last_traded_cache[(uid, self.asset)] = current_interval_id
    continue
```

---

### 5.4 Remediation 4: Fixing Unit Mismatch in Kalshi Market-Structure Gate

In `backend/btc/analyzer/contract_eval.py` (lines 639–650):
Convert `yes_ask` and `no_ask` from dollars to cents before comparing against thresholds:

```python
# PROPOSED FIX for contract_eval.py:639-650
if kalshi_m and "GRADE A" not in grade:
    # Ensure quotes are scaled to 0-100 cents / percentage scale
    k_yes_raw = float(kalshi_m.get("yes_ask", 0.50) or 0.50)
    k_no_raw = float(kalshi_m.get("no_ask", 0.50) or 0.50)
    
    # Normalize: if values are in dollars (0.0 - 1.0), multiply by 100
    k_yes = k_yes_raw * 100.0 if k_yes_raw <= 1.0 else k_yes_raw
    k_no = k_no_raw * 100.0 if k_no_raw <= 1.0 else k_no_raw
    imbalance = float(kalshi_m.get("book_imbalance", 0.0) or 0.0)

    if k_yes >= THRESHOLDS["kalshi_override_yes"] or imbalance >= THRESHOLDS["kalshi_imbalance_threshold"]:
        pred = "BID YES (ABOVE TARGET)"
        grade = "GRADE B+ SETUP"
        badge = "⚠️ 3-STAR B+ (64%)"
        prob = max(prob, 64) if "YES" in pred else 64
        catalysts.append(f"Market Implied Bullish Edge: Order book odds favor YES ({k_yes:.1f}%)")
```

---

### 5.5 Remediation 5: Universal Negative EV Gate Across All Strategies

Move the EV Gate out of the `SNIPER`-only block in `contract_eval.py` (lines 1107–1125) and make it a **global mandatory gate** executed for all trading styles (`AUTO`, `MOMENTUM_SURFER`, `AMBUSH`, `CHOP`, `PREDICTION`):

```python
# PROPOSED FIX for contract_eval.py:1107
# Global Negative EV Gate - Mandatory for ALL strategies and isolation modes
if kalshi_m and direction in ["ABOVE", "BELOW", "YES", "NO"]:
    side_key = "yes_ask" if direction in ["ABOVE", "YES"] else "no_ask"
    ask_raw = float(kalshi_m.get(side_key) or 0.50)
    ask_dollars = ask_raw if ask_raw <= 1.0 else ask_raw / 100.0
    
    # Calculate exchange taker entry fee
    taker_fee = math.ceil(0.07 * ask_dollars * (1.0 - ask_dollars) * 100.0) / 100.0
    # Include 4-cent slippage corridor in minimum required win probability
    slippage_allowance = 0.04
    breakeven_p = ask_dollars + taker_fee + slippage_allowance
    
    model_p = float(prob) / 100.0
    
    if model_p < breakeven_p:
        catalysts.insert(0, f"⛔ Negative EV Filter: Model Prob ({model_p*100:.1f}%) < Breakeven Requirement ({breakeven_p*100:.1f}% = {ask_dollars*100:.0f}c ask + {taker_fee*100:.1f}c fee + {slippage_allowance*100:.0f}c slippage). Trade aborted.")
        pred = "PASS / NO BID (NEGATIVE EV)"
        direction = "PASS"
        grade = "PASS / NEGATIVE EV"
        badge = "⚪ PASS (NEGATIVE EV)"
        prob = 50.0
```

---

### 5.6 Remediation 6: Asset-Normalized Volatility and Strike Delta Thresholds

Replace fixed dollar values (`$15`, `$25`, `$35`, `$140`) in `contract_eval.py`, `executor.py`, and `stop_manager.py` with asset-relative ATR multiples:

```python
# PROPOSED FIX for contract_eval.py, executor.py, and stop_manager.py
# Normalized Strike Delta Guard:
# Instead of hardcoded $25.00:
normalized_delta_threshold = atr * 0.35  # Dynamic threshold proportional to current asset volatility

if direction == "ABOVE" and delta_strike < -normalized_delta_threshold:
    if (c_close < c_open) and (c_ema9 < c_ema21) and not is_oversold_bounce:
        chart_conflict = True
        conflict_reason = f"Spot is {abs(delta_strike):.4f} below strike (exceeds 0.35 ATR {normalized_delta_threshold:.4f}) with bearish momentum."
```

---

## 6. Verification and Proof of Audit Integrity

The analysis and findings documented in this report can be verified independently using the following codebase inspection commands:

1. **Verify Fee-Blind Kelly Logic**:
   Inspect `executor.py` lines 1042–1052 and `saas_broadcaster.py` lines 228–238:
   Notice `if p_win <= b_price:` lacks taker fee accounting.
2. **Verify Coin-Flip Force Trade**:
   Inspect `saas_broadcaster.py` line 764:
   Confirm `side = "yes" if int(time.time()) % 2 == 0 else "no"`.
3. **Verify Asymmetric Early TP/SL Exits**:
   Inspect `stop_manager.py` lines 345–395 and `saas_settler.py` lines 281–295:
   Confirm TP caps at $+50\%$ of contract price, while trailing stop triggers at $+35\%$ activation with $6\%$ trailing drop.
4. **Verify Unit Mismatch**:
   Inspect `contract_eval.py` line 643 (`k_yes >= THRESHOLDS["kalshi_override_yes"]`) against `config.py` line 25 (`"kalshi_override_yes": 62.0`) and `kalshi_client.py` line 140 (`yes_ask = ... / 100.0`).
5. **Verify Dead Loss Diagnosis Loop**:
   Search pattern `diagnose_loss` across `backend/`. Confirm zero call sites outside of its definition in `loss_analyzer.py:18`.

---
*Report complete and artifact generated at `.agents/teamwork/explorer_logic_1/logic_audit.md`.*
