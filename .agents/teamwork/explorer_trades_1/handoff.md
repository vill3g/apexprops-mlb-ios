# Handoff Report: Empirical Trade Data Analysis (M2)

**Agent:** `explorer_trades_1`  
**Milestone:** M2 — Trade Data Analysis  
**Working Directory:** `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_trades_1`  
**Deliverable File:** `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_trades_1\trade_analysis.md`  

---

## 1. Observation

1. **Trade Database Locations & Volumes**:
   - `backend/data/users.db`: 2,151 trades across 5 user accounts (`trades` table).
   - `backend/data/trades.db`: 747 trades (`trades` table).
   - `backend/data/market_results.json`: 1,050 ground-truth final settlement outcomes (`YES` or `NO`).
   - `backend/data/trades_history.json`: 744 trade records with execution snapshots.
   - `backend/data/users/{2,4,5,7,205}/trades_history.json`: 2,056 individual user trade records with multi-entry tags (`is_second_entry`, `is_third_entry`, `reentry_index`).

2. **Global Portfolio Metrics**:
   - In `users.db`: 2,150 closed trades yielded 1,112 wins (51.72%), 1,020 losses, 18 flats. Net P&L: **-$814.90**, Gross Profit: $5,292.21, Gross Loss: $6,107.11, Profit Factor: **0.87**, Average Win: **$4.76**, Average Loss: **-$5.99**, Payoff Ratio: **0.79**, Expectancy: **-$0.38 / trade**, Max Drawdown: **$912.10**.
   - In `users.db` LIVE trades: 711 trades yielded 352 wins (49.51%), 349 losses. Net P&L: **-$163.31**, Profit Factor: **0.76**, Expectancy: **-$0.23 / trade**, Max Drawdown: **$195.56**.
   - In `trades.db`: 747 trades yielded 375 wins (50.20%), 357 losses. Net P&L: **-$7,350.19**, Profit Factor: **0.80**, Max Drawdown: **$13,219.04**.

3. **Natural Settlement vs Early Stop-Out Performance**:
   - In `users.db`, natural contract settlement (`SETTLEMENT`) had **275 trades**, **76.0% Win Rate**, Net P&L **+$1,829.88** (Avg Win: $11.38, Avg P&L: **+$6.65 / trade**).
   - In `users.db`, early stop loss (`STOP_LOSS`) had **860 trades**, **0.8% Win Rate**, Net P&L **-$5,021.44** (Avg Loss: **-$5.84 / trade**).
   - In `users.db`, early take profit (`TAKE_PROFIT`) had **817 trades**, **96.2% Win Rate**, Net P&L **+$2,386.08** (Avg Win: **+$2.92 / trade**).
   - In `trades.db`, `NATURAL_SETTLEMENT` had **350 trades**, **60.0% Win Rate**, Net P&L **+$1,142.39**, while `CONTRACT_STOP_LOSS` had **130 trades**, Net P&L **-$14,998.27**.

4. **Trailing Stop Logic & Counterfactual Settlement**:
   - In `backend/saas_settler.py` lines 849–852 and `backend/btc/auto_executor/stop_manager.py` lines 362–370:
     `trail_threshold = max(max_seen_bid - ts_distance, max_seen_bid * (1.0 - ts_distance))` with `ts_distance = 0.06` (6.0%).
   - On a contract priced at $0.50 that reaches $0.68, the trailing threshold is $0.64 (a drop of only 4 cents). Kalshi bid-ask spread is typically 2 to 5 cents.
   - Cross-referencing 856 stopped-out trades in `users.db` against `market_results.json`: **164 stopped-out trades (19.2%)** would have settled as **WINNERS** ($1.00 full value) at expiration.
   - Cross-referencing 816 early take-profit trades: **581 trades (71.2%)** would have won at expiration anyway, forfeiting **+$708.64** in upside payout.

5. **Multi-Entry & Scaling Mechanics**:
   - Entry 1 (Initial / Base): 1,525 trades | 49.05% Win Rate | Net P&L: -$473.40 | Avg Win: $4.03 | Avg Loss: **-$4.60** | Avg P&L: **-$0.31**.
   - Entry 2 (Second Scale): 468 trades | 58.76% Win Rate | Net P&L: -$260.74 | Avg Win: $6.36 | Avg Loss: **-$10.41 (2.26x larger)** | Avg P&L: **-$0.56**.
   - Entry 3 (Third Scale): 157 trades | 56.69% Win Rate | Net P&L: -$80.76 | Avg Win: $5.94 | Avg Loss: **-$8.97** | Avg P&L: **-$0.51**.
   - Single-entry sequences: 819 sequences | Avg P&L: **-$0.57 / seq**.
   - Two-entry sequences: 324 sequences | Avg P&L: **-$1.39 / seq (2.4x worse)**.
   - Three-entry sequences: 156 sequences | Avg P&L: **-$1.54 / seq (2.7x worse)**.
   - "Re-entry after stop loss" (`saas_settler.py:960`): In 141 sequences where Trade 1 exited via `STOP_LOSS`, Trade 2 won only **36.9%** of the time, losing **-$379.67** (Avg -$2.69/trade), bringing combined sequence loss to **-$1,128.27**.

6. **Entry Timing within 15-Minute Candle**:
   - Phase 01 Open (0–3 min): 1,421 trades | 50.5% Win Rate | Net P&L: -$132.34 | Avg P&L: -$0.09.
   - Phase 02 Mid-Early (3–6 min): **271 trades** | 49.4% Win Rate | Net P&L: **-$586.91** | Avg P&L: **-$2.17** | Profit Factor: **0.49** | Stop Loss Rate: **45.0%**.
   - Minute 4 specifically: 99 trades | **41.4% Win Rate** | Net P&L: **-$347.20** | Avg Loss: **-$9.60** | Stop Loss Rate: **51.5%**.

7. **Model Conviction & Regime Traps**:
   - **Neutral / Coinflip Conviction (50–51%)**: 1,267 trades (58.9% of all trades) were placed at exact 50% or 51% probability with zero statistical edge, generating **-$741.85 in losses (91% of total portfolio net loss)**. Only trades with conviction `>= 60%` had positive expectancy.
   - **Model Conflict**: 26 trades were executed where chart setup conflicted with ML model. Win Rate: **38.5%** | Net P&L: **-$98.99** | Avg P&L: **-$3.81 / trade** (11.2x worse than aligned trades).
   - **Bullish Breakout Traps**: "Ascending Triangle Breakout" and "Breakout Pressure" lost **-$196.83** (45.8% Win Rate); "Dual Bullish Trend Alignment" lost **-$111.07** (35.6% Win Rate).

---

## 2. Logic Chain

1. **Premature Stop-Outs Destroy Edge**:
   - Observation 3 shows that trades allowed to hold to `SETTLEMENT` achieve a 76.0% win rate and +$6.65/trade expectancy.
   - Observation 4 shows that trailing stop distance is set to 6%, which equates to 2–4 cents on binary contracts.
   - Observation 4 shows that normal bid-ask spread (2–5 cents) triggers this distance prematurely, turning 164 winning trades (19.2% of stop-outs) into losses, and cutting 581 winning trades (71.2% of take-profits) off from their full $1.00 payout.
   - This creates an inverted payoff ratio (0.79) where average win is $2.92 and average loss is -$5.84, guaranteeing long-term account bleed.

2. **Scaling Multiplies Losses**:
   - Observation 5 shows that Entry 2 suffers an average loss of -$10.41 compared to -$4.60 for Entry 1, increasing average loss size by 126%.
   - Observation 5 shows that sequences with 2 or 3 entries lose 2.4x to 2.7x more money per sequence than single-entry sequences.
   - When a trade is stopped out, the market is demonstrating strong momentum against the contract; re-entering on the same contract loses 63.1% of the time, resulting in -$1,128.27 in losses across 141 sequences.

3. **Intra-Candle Retracement Trap**:
   - Observation 6 demonstrates that trading in Minutes 3–6 of the 15-minute candle generates 72% of all timing-related losses (-$586.91, PF 0.49).
   - During Minutes 3–6, the opening impulse has already exhausted, leading to false breakout traps and immediate stop-outs.

4. **Coin-Flip Churning**:
   - Observation 7 proves that 58.9% of trades enter at 50%–51% conviction, paying bid-ask spread and Kalshi taker fees without any predictive edge. This churn accounts for 91% of total net losses (-$741.85).

---

## 3. Caveats

- **Off-hours / Paper fill slippage**: In paper trading, fills use public order book quotes which may slightly underestimate real live market slippage on illiquid contracts. However, the live sub-portfolio (711 trades) confirmed the exact same dynamics (49.51% win rate, 0.76 profit factor, negative EV).
- **Synthetic market tickers**: A small number of synthetic test tickers (`*_SYNTH`, `*TEST*`) are present in `market_results.json` and were filtered or accounted for in the analysis.
- **No code modifications**: In compliance with the strict constraint, no codebase files or database records were modified. All analysis scripts were executed read-only in `.agents/teamwork/explorer_trades_1/`.

---

## 4. Conclusion

The ShadowTrader AI auto-trading system's negative profitability is **not** caused by an inability of the ML models to forecast 15-minute contract expiration (natural settlement has a 60–76% win rate with positive EV). Rather, the system is burdened by four critical execution-level flaws:
1. **Hyperactive, spread-blind trailing stops** (6% = 2–4¢) that prematurely trigger on bid-ask noise and produce an asymmetric 0.79 payoff ratio ($2.92 win vs $5.84 loss).
2. **Toxic multi-entry scaling and re-entry after stop-loss**, which doubles down on invalidated positions and doubles average loss size (-$10.41 vs -$4.60).
3. **Mid-candle chasing during Minutes 3–6**, which enters at local tops/bottoms right before mean-reversion pullbacks (Profit Factor 0.49).
4. **Indiscriminate execution on 50–51% conviction setups**, churning 58.9% of trade volume with zero edge and generating 91% of portfolio losses through spread and fees.

---

## 5. Verification Method

To independently verify all findings and replicate the statistical tables:

1. **Execute Comprehensive Portfolio Metrics**:
   ```powershell
   python C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_trades_1\analyze_comprehensive_metrics.py
   ```
2. **Execute Counterfactual Expiration Analysis**:
   ```powershell
   python C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_trades_1\analyze_counterfactual_stops.py
   ```
3. **Execute Multiple Entry & Scaling Analysis**:
   ```powershell
   python C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_trades_1\analyze_multiple_entries.py
   python C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_trades_1\analyze_scaling_context.py
   ```
4. **Execute Entry Timing Analysis**:
   ```powershell
   python C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_trades_1\analyze_entry_timing.py
   ```
5. **Execute Regime, Conviction, and Price Distribution Analysis**:
   ```powershell
   python C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_trades_1\analyze_regime_and_catalysts.py
   python C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_trades_1\analyze_price_distribution.py
   ```
6. **Files to Inspect**:
   - `C:\Users\Vill3\Desktop\ShadowTraderAi\.agents\teamwork\explorer_trades_1\trade_analysis.md`
   - `C:\Users\Vill3\Desktop\ShadowTraderAi\backend\data\users.db`
   - `C:\Users\Vill3\Desktop\ShadowTraderAi\backend\data\trades.db`
   - `C:\Users\Vill3\Desktop\ShadowTraderAi\backend\data\market_results.json`
