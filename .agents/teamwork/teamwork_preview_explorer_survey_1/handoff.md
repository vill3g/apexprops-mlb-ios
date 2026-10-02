# Handoff Report: Trading Styles & Strategy Logic Exploration

## 1. Observation

Direct code observations from `C:\Users\Vill3\Desktop\kalshi-ai-trader`:

1. **Auto 2.0 Regime Classification** (`backend/btc/auto_executor/shared.py:39–205`):
   - `classify_auto_regime` evaluates indicators on 15m candle streams (`vol_ratio`, `bb_bandwidth`, `adx`, `rsi`, `atr`, 1h macro trend via EMA-9 vs EMA-21, real-time liquidation totals from `liquidation_stream.py`).
   - Maps market states into 4 primary execution routes:
     - `STRONG_MOMENTUM` $\rightarrow$ `MOMENTUM_SURFER` (`is_liq_cascade` $\ge \$1.5\text{M}$ or `vol_ratio >= 1.4 and adx >= 25.0 and abs(rsi - 50.0) >= 8.0` or MTF aligned).
     - `SQUEEZE_BREAKOUT` $\rightarrow$ `AMBUSH` (`bb_width < 0.020 and vol_ratio >= 1.25` with candle expansion).
     - `CHOP_DEADZONE` $\rightarrow$ `CAPITAL_GUARD` (`adx < 18.0 and vol_ratio < 0.85 and bb_width < 0.018` or `adx < 16.0 and vol_ratio < 0.90`).
     - `TREND_CONTINUATION` / `NORMAL_MARKET` $\rightarrow$ `SNIPER` (`adx >= 20.0 and abs(rsi - 50.0) >= 5.0 and vol_ratio >= 0.9`).

2. **`CAPITAL_GUARD` Execution Logic** (`backend/btc/analyzer/contract_eval.py:56–73`):
   - Quote:
     ```python
     if trading_style == "CAPITAL_GUARD":
         return {
             "recommendation": "PASS / CHOP DEADZONE (CAPITAL GUARD)",
             "direction": "PASS",
             "action_type": "PASS",
             "probability_percent": 50.0,
             "predicted_probability": 0.5,
             "conviction_grade": "PASS / CHOP DEADZONE (CAPITAL GUARD)",
             "conviction_badge": "🛡️ CAPITAL GUARD (PASS)",
             "primary_edge": "Low-volatility compression deadzone (ADX < 18, Vol < 0.85). Preserving capital for high-edge expansion.",
         }
     ```

3. **`SNIPER` Entry Timing, Candlestick Resolution, and EV Gating**:
   - `backend/btc/auto_executor/executor.py:629–642`:
     ```python
     is_rollover_window = sec_elapsed <= 60 or sec_left >= 840
     is_prediction_window = 30 <= sec_elapsed <= 55 or 845 <= sec_left <= 870
     ```
   - `backend/btc/analyzer/contract_eval.py:84–86`:
     ```python
     c = df_ind.iloc[-2] if n >= 2 else df_ind.iloc[-1]
     p = df_ind.iloc[-3] if n >= 3 else df_ind.iloc[-2]
     ```
   - `backend/btc/analyzer/contract_eval.py:1055–1073`:
     ```python
     min_ev = kalshi_ask + 0.05
     current_prob = float(prob) / 100.0
     if current_prob <= min_ev:
         pred = "PASS / NO BID (NEGATIVE EV)"
         direction = "PASS"
     ```

4. **`MOMENTUM_SURFER` 1m High-Resolution Data & Conviction Floors**:
   - `backend/btc/auto_executor/executor.py:704–706`:
     ```python
     if effective_style == "MOMENTUM_SURFER":
         df_eval = fetch_candles(self.asset, timeframe="1m", limit=350)
         df_ind_eval = add_all_indicators(df_eval)
     ```
   - `backend/btc/auto_executor/executor.py:940–943`:
     ```python
     min_conf = 60.0 if sec_elapsed <= 60 else 75.0
     actual_win_conf = max(actual_conf, 100.0 - actual_conf)
     meets_conviction = (actual_win_conf >= min_conf)
     ```

5. **`AMBUSH` Anti-Exhaustion & CVD Acceleration Gating** (`backend/btc/analyzer/contract_eval.py:1074–1110`):
   - Blocks fades into active momentum where `cvd_acceleration < -0.1` (dump) or `> +0.1` (pump), or when counter to the 1-Hour macro trend.

6. **`PREDICTION` Style Noise Filter** (`backend/btc/auto_executor/executor.py:635–640` & `backend/btc/analyzer/contract_eval.py:1132–1140`):
   - Waits 90 seconds after open (`sec_elapsed >= 90 and sec_left >= 180`).
   - Requires minimum probability divergence: $|P(\text{YES}) - 50.0| \ge 8.0\%$ (confidence $\ge 58.0\%$).

7. **`CHOP` Engine Setup & Corridor** (`backend/btc/chop_engine.py:46–98` & `contract_eval.py:694–724`):
   - Overbought/oversold band touches with RSI extremes ($>65$ or $<35$).
   - Price corridor: Kalshi ask must be within $40¢ - 60¢$ sweet spot (with time-decay tolerance).
   - Extra confidence floor: $\text{CHOP\_EXTRA\_CONFIDENCE\_FLOOR} = 6.0\%$.

8. **Position Sizing (Binary Half-Kelly)** (`backend/btc/auto_executor/saas_broadcaster.py:888–897`):
   - P_win: $p_{\text{win}} = \text{conf} / 100.0$, Ask: $b = \text{market\_price}$.
   - Binary Kelly: $f^* = (p_{\text{win}} - b) / (1.0 - b)$.
   - Half-Kelly: $\text{kelly\_frac} = \min(1.25, \max(0.25, 0.50 \times f^*))$.
   - Dollar risk: $\text{risk\_amount} = \max(0.50, \text{trade\_size\_dollars} \times \text{kelly\_frac})$.

9. **Order Types & Execution Protocol** (`backend/btc/kalshi_trader.py:1196–1230`):
   - Endpoint: `POST /trade-api/v2/portfolio/events/orders`.
   - Order type: Limit order priced to cross the book with slippage buffer:
     $$\text{Limit Price} = \min(0.99, \max(0.01, \text{market\_price} + \text{slippage\_buffer}))$$
     (default `slippage_buffer = 0.04`).
   - Time-in-Force: `immediate_or_cancel` (IOC).
   - `post_only: False`, `reduce_only: False` (entries) / `True` (exits).
   - Paper latency tax: $0.01 (`PAPER_LATENCY_TAX_DOLLARS = 0.01`).

10. **Exit Hierarchy & Stop Management** (`backend/btc/auto_executor/stop_manager.py:329–432`):
    - Take-Profit: $\ge 50\%$ gain (`take_profit_pct`).
    - Trailing Stop: Activated at $\ge +35\%$ peak, trails at $6\%$, floor at entry $\times 1.02$.
    - Contract Mid-Price Stop: $\le -50\%$ loss, evaluated on mid-price to avoid spread stop-outs.
    - Structural Spot Invalidation: $<2.0\text{m}$ left with deficit $> \$35$, or $\ge 2.0\text{m}$ left with 15m EMA-21 cross and $|\text{CVD}| > 10$.
    - Position Reversal: Opposite flip if stopped out with $\ge 6\text{m}$ left, opposite ask $\le \$0.65$, opposite conf $\ge 75\%$.

11. **Taker Fee & Expectancy Math** (`backend/btc/fees.py:9–38`):
    - Taker fee: $\lceil 0.07 \times \text{Price} \times (1 - \text{Price}) \times 100 \rceil / 100$.
    - At $\$0.50$, fee is $\$0.02$ per leg. Zero fee at settlement.
    - Breakeven win-rate held to settlement at $\$0.50$: $52.0\%$. Breakeven win-rate with early market-bid exit and $4¢$ spread: $\approx 58.0\% - 61.0\%$.

---

## 2. Logic Chain

1. **Premise**: Strategy profitability depends on whether the theoretical directional edge exceeds all transaction frictions (taker fees + bid-ask spread + execution slippage + timing decay).
2. **Observation 1 & 3**: In `SNIPER`, edge is gained by requiring 100% agreement between institutional chart setups (sweeps, order blocks) and ML inference at candle rollover, while filtering out negative EV ($P(\text{win}) \le \text{Ask} + 0.05$) and strike-pin noise ($|\Delta| \le \$18$, $\text{ATR} \le \$45$).
3. **Observation 1 & 2**: In `CAPITAL_GUARD`, the strategy actively avoids negative expectancy by emitting a strict `PASS` during compression deadzones ($\text{ADX} < 18$, $\text{Vol Ratio} < 0.85$). This prevents the "chop bleed" that historical analysis flagged as the leading cause of loss.
4. **Observation 4, 5, 6, 7**: `AUTO` acts as a dynamic router that matches execution latency and data granularity to the regime:
   - Runaway breakouts get 1m high-speed tracking via `MOMENTUM_SURFER`.
   - Squeezes get CVD-filtered breakout entries via `AMBUSH`.
   - Noise-heavy opens get delayed by 90s in `PREDICTION`.
   - Compression gets faded in `CHOP` or passed in `CAPITAL_GUARD`.
5. **Observation 8, 9, 10, 11**: Position sizing is constrained by binary Half-Kelly mathematical limits. Orders use IOC limit execution with a $4¢$ buffer to avoid getting trapped in resting book queues. Exits cut structural losses early (salvaging $15¢ - 35¢$ per contract) while letting winners run to $+50\%$ or trailing take-profit.
6. **Synthesis / Conclusion**: The core strategy logic is conceptually sound, highly defensive, and rigorously constructed with multi-layered safety gates. However, profitability in live trading is heavily sensitive to Kalshi contract liquidity (bid-ask spread) and taker fee friction (7% per leg), requiring an empirical win rate $\ge 52.0\%$ (held to settlement) or $\ge 58.0\%$ (actively scalped).

---

## 3. Caveats

1. **Network Live Liquidity**: We examined the static and simulated logic; actual orderbook depth and real-world slippage on Kalshi KXBTC15M contracts depend on live exchange market makers.
2. **ML Self-Training Convergence**: The ML models retrain on historical candle streams; performance depends on the quality of in-memory candle histories and feature stationarity across crypto macro regimes.
3. **Placeholder in CHOP Engine**: `backend/btc/chop_engine.py` explicitly notes that it is a conservative wrapper and suggests further tuning for mean-reversion at range extremes.

---

## 4. Conclusion

The Kalshi AI Trader codebase contains a sophisticated, multi-style autonomous trading system:
1. **Core Styles**: `SNIPER`, `CAPITAL_GUARD`, `AUTO`, `MOMENTUM_SURFER`, `AMBUSH`, `PREDICTION`, `CHOP`, and `SCALP` / `RL_SCALPER`.
2. **Risk & Execution Control**: IOC limit orders with $\$0.04$ book-crossing buffer, True Binary Half-Kelly sizing, 5-stage exit hierarchy (Hard TP, Trailing TP, Mid-Price SL, Structural Spot Invalidation, Expiration Settlement), and post-stop position reversals.
3. **Identified Regime Vulnerabilities**:
   - **Illiquid / Wide-Spread Markets**: Early exits (stops and scalps) hitting wide bids pay double taker fees plus the spread, degrading expectancy.
   - **Chop Bleed if Bypassed**: If `CAPITAL_GUARD` is overridden (`ignorePass`), false breakouts in low-ATR environments generate rapid consecutive losses.
   - **Strike Pinning Noise**: Expirations within $\$15$ of strike degenerate into sub-second tick coin-flips.
4. **Full details and code locations** are cataloged in `analysis.md`.

---

## 5. Verification Method

To independently verify the observations and findings in this report:

1. **Verify Trading Styles and Logic Files**:
   - View `backend/btc/auto_executor/shared.py` (Lines 39–205) for `classify_auto_regime`.
   - View `backend/btc/analyzer/contract_eval.py` (Lines 56–73, 1055–1175) for `CAPITAL_GUARD`, `SNIPER`, and `PREDICTION` logic.
   - View `backend/btc/auto_executor/executor.py` (Lines 629–642, 693–775, 1020–1047) for rollover execution and sizing.
   - View `backend/btc/auto_executor/saas_broadcaster.py` (Lines 888–897) for the True Binary Half-Kelly implementation.
   - View `backend/btc/auto_executor/stop_manager.py` (Lines 209–432) for structural stop-loss, trailing profit, and reversal rules.
   - View `backend/btc/kalshi_trader.py` (Lines 1000–1235) for IOC limit order submission.
   - View `backend/btc/fees.py` (Lines 12–38) for fee calculation and edge formulas.

2. **Run Codebase Test Suite**:
   Execute the test suite in the local virtual environment:
   ```powershell
   & "C:\Users\Vill3\Desktop\kalshi-ai-trader\.venv\Scripts\pytest.exe" "C:\Users\Vill3\Desktop\kalshi-ai-trader\tests"
   ```

3. **Invalidation Conditions**:
   - If `classify_auto_regime` routes to styles other than the 4 documented regimes.
   - If `SNIPER` is found to enter mid-candle without rollover conditions.
   - If position sizing does not enforce Half-Kelly or dollar caps.
