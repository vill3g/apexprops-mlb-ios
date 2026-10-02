# Comprehensive Analysis of Trading Styles & Strategy Logic

## Executive Summary

The **Kalshi AI Trader** is an automated trading system designed for Kalshi binary event contracts—primarily the 15-minute series (`KXBTC15M`, `KXETH15M`, etc.), with supplementary modules for forex and prop predictions. Binary event contracts settle at either **$1.00** (if the underlying index settles $\ge$ strike for YES, or $<$ strike for NO) or **$0.00** (worthless).

The codebase features an adaptive execution architecture governed by **Auto 2.0 Regime Classification**, routing between structural confluence sniping (`SNIPER`), momentum/liquidation surfing (`MOMENTUM_SURFER`), squeeze/exhaustion breakouts (`AMBUSH`), capital protection in deadzones (`CAPITAL_GUARD`), pure probability models (`PREDICTION`), band-fading mean reversion (`CHOP`), and high-frequency intraday momentum scalping (`SCALP` / `RL_SCALPER`).

Below is an exhaustive, code-grounded investigation of every style, its mathematical formulations, execution parameters, edge assumptions, and regime vulnerabilities.

---

## 1. Inventory of Trading Styles and Execution Modes

| Trading Style / Mode | Primary Function | Candle Timeframe & Resolution | Execution Window / Trigger Timing | Core Signal Engine |
| :--- | :--- | :--- | :--- | :--- |
| **`SNIPER`** | Structural trend continuation & multi-indicator confluence | 15m candles (evaluates finalized candle at index `-2`) | Rollover only (first 60s of 15m interval: `sec_elapsed <= 60` or `sec_left >= 840`) | Institutional SMC + Chart Setups + Dual ML / DQN Ensemble (`BLEND` 100% agreement) |
| **`CAPITAL_GUARD`** | Capital preservation in deadzones | 15m candles | Triggered dynamically in chop deadzones | Emits disciplined `PASS` (0% edge, 50% probability) |
| **`AUTO`** | Meta-strategy regime classifier (Auto 2.0) | 15m candles + real-time order flow & liquidations | Evaluated continuously at candle rollover & mid-candle | Microstructure classifier routing to `MOMENTUM_SURFER`, `AMBUSH`, `CAPITAL_GUARD`, or `SNIPER` |
| **`MOMENTUM_SURFER`** | High-velocity trend & liquidation cascade exploitation | 1m candles (`limit=350`) | Mid-candle allowed (`sec_left >= 180s`, SaaS cutoff `240s`) | 1m tape reading, liquidation cascades, `CHART_ONLY` isolation |
| **`AMBUSH`** | Bollinger squeeze breakouts & limit exhaustion fades | 15m active candle | Mid-candle allowed (`sec_left >= 180s`) | Bollinger compression breakouts with CVD acceleration filters |
| **`PREDICTION`** | Direct neural network probability forecasting | 15m active candle | Delayed entry (`sec_elapsed >= 90s` and `sec_left >= 180s`) | Dueling QR-DQN / PyTorch ML Ensemble with 58% conviction floor |
| **`CHOP`** | Mean-reverting Bollinger band-fading | 15m active candle | Bollinger extreme touches + 40c–60c ask sweet spot | Bollinger & RSI mean reversion (`CHOP_EXTRA_CONFIDENCE_FLOOR = 6.0%`) |
| **`SCALP` / `RL_SCALPER`** | Rapid intraday contract flips on price velocity / RL | 15m spot delta + rolling 60s window / Dueling QR-DQN | Active first 240s (`RL_SCALPER`) or cooldown 30s (`SCALP`) | Intraday spot threshold ($\ge 0.25\%$) + Confluence analyzer / RL Q-values |
| **`POSITION_REVERSAL`** | Post-stop bailout flip to opposite contract | 15m active candle | Following early dynamic stop-loss (`minutes_remaining >= 6.0m`) | Momentum check on opposite side ($\ge 75\%$ conf, ask $\le \$0.65$) |
| **`PROFIT_REENTRY` / `DCA`** | Multi-entry pyramid / DCA re-entry on same contract | 15m active candle | After take-profit or stop-loss (`minutes_remaining >= 3.5m - 4.0m`) | Pullback check ($\ge 3¢$ discount on win, $\ge 15\%$ on DCA) |
| **`FOREX_EXECUTOR`** | Spot FX paper/live executor | 15m candles | Continuous loop (15s sleep) | Technical indicators + pip ATR stop sizing + news circuit breaker |

---

## 2. Core Logic of Each Trading Style

### 2.1. `SNIPER`
- **Purpose**: High-conviction structural sniping designed to maximize win-rate by only entering at contract rollover when multiple independent analytical engines agree.
- **Code Locations**:
  - `backend/btc/analyzer/contract_eval.py`: Lines 75–87, 690–692, 1055–1073.
  - `backend/btc/auto_executor/executor.py`: Lines 629–642, 708–775, 954–961.
  - `backend/btc/auto_executor/shared.py`: Lines 51–53, 169–170, 185–192.
  - `backend/btc/ml_engine.py`: Lines 730, 749, 1349.
- **Entry Window**:
  - Only active during the first 60 seconds of a new 15-minute interval:
    $$\text{sec\_elapsed} \le 60 \quad \text{or} \quad \text{sec\_left} \ge 840$$
    (In prediction mode: $30 \le \text{sec\_elapsed} \le 55$).
- **Data Evaluated**:
  - Finalized historical candle at index `-2` (`c = df_ind.iloc[-2]`). Prevents mid-candle repainting.
- **Signal Confluence & Isolation**:
  - Routed to `BLEND` isolation mode (`contract_eval.py:690–692`).
  - Strict requirement: Chart technical setup (SMC, Liquidity Sweeps, Triangles, Bollinger Hammers, EMA Ribbons) and ML model **must both agree on direction**. If ML disagrees by $\ge 15\%$ (`THRESHOLDS["model_conflict_threshold"]`), the trade is vetoed (`PASS`).
- **Minimum Expected Value (EV) Filter**:
  - `contract_eval.py:1055–1073`:
    $$\text{min\_ev} = \text{kalshi\_ask} + 0.05$$
    If $\text{current\_prob} \le \text{min\_ev}$, the trade is blocked with `PASS / NO BID (NEGATIVE EV)`.
- **Strike Pin / Dead-Zone Filter**:
  - `contract_eval.py:109–127`: If $|\text{Spot} - \text{Strike}| \le \$18.00$ and $\text{ATR} \le \$45.00$ (without a $1.8\times$ volume breakout), emits `PASS (STRIKE PIN)`.

---

### 2.2. `CAPITAL_GUARD`
- **Purpose**: Zero-exposure capital protection mode activated during low-volatility deadzones to prevent bleed.
- **Code Locations**:
  - `backend/btc/analyzer/contract_eval.py`: Lines 56–74.
  - `backend/btc/auto_executor/shared.py`: Lines 54–56, 164–167, 180–183.
  - `backend/btc/auto_executor/executor.py`: Lines 742–760.
  - `backend/btc/auto_executor/saas_broadcaster.py`: Lines 513–531.
- **Trigger Conditions**:
  - Activated by `classify_auto_regime` when either:
    1. $\text{ADX} < 18.0$ **and** $\text{Vol Ratio} < 0.85$ **and** $\text{Bollinger Bandwidth (BBW)} < 0.018$, **or**
    2. $\text{ADX} < 16.0$ **and** $\text{Vol Ratio} < 0.90$.
- **Behavior**:
  - Bypasses all ML inference, order placement, and position sizing.
  - Returns a clean `PASS / CHOP DEADZONE (CAPITAL GUARD)` payload with probability $50.0\%$.

---

### 2.3. `AUTO` (Auto 2.0 Adaptive Market Regime Classifier)
- **Purpose**: Continuous classification of market microstructure, routing dynamically to the best-fit style.
- **Code Locations**:
  - `backend/btc/auto_executor/shared.py`: Lines 39–205 (`classify_auto_regime`).
  - `backend/btc/auto_executor/executor.py`: Lines 693–702.
  - `backend/btc/auto_executor/saas_broadcaster.py`: Lines 491–498.
- **Classification Hierarchy**:
  1. **`STRONG_MOMENTUM` $\rightarrow$ `MOMENTUM_SURFER`**:
     - Liquidation cascade: $\text{Liquidation Total} \ge \$1,500,000$, **or**
     - Volume Momentum: $\text{Vol Ratio} \ge 1.4$, $\text{ADX} \ge 25.0$, $|\text{RSI} - 50| \ge 8.0$, **or**
     - MTF Alignment: $\text{Vol Ratio} \ge 1.25$, $\text{ADX} \ge 24.0$, aligned with 1-hour EMA-9 vs EMA-21 trend.
  2. **`SQUEEZE_BREAKOUT` $\rightarrow$ `AMBUSH`**:
     - $\text{BBW} < 0.020$ with $\text{Vol Ratio} \ge 1.25$ and (Price outside bands or range expansion $\ge 0.7 \times \text{ATR}$), **or**
     - Pure breakout: $\text{Vol Ratio} \ge 1.35$ with candle range expansion.
  3. **`CHOP_DEADZONE` $\rightarrow$ `CAPITAL_GUARD`**:
     - Ultra-low volatility deadzone ($\text{ADX} < 18$, $\text{Vol Ratio} < 0.85$, $\text{BBW} < 0.018$).
  4. **`TREND_CONTINUATION` $\rightarrow$ `SNIPER`**:
     - Steady structural trend: $\text{ADX} \ge 20.0$, $|\text{RSI} - 50| \ge 5.0$, $\text{Vol Ratio} \ge 0.9$.
  5. **`NORMAL_MARKET` (Fallback) $\rightarrow$ `SNIPER`**:
     - Standard conditions default to disciplined `SNIPER` confluence.

---

### 2.4. `MOMENTUM_SURFER`
- **Purpose**: Exploits rapid trend surges and liquidation cascades where immediate execution is required.
- **Code Locations**:
  - `backend/btc/analyzer/contract_eval.py`: Lines 75–82, 686–688.
  - `backend/btc/auto_executor/executor.py`: Lines 704–706, 939–943.
  - `backend/btc/auto_executor/saas_broadcaster.py`: Lines 499–502, 688–695.
  - `backend/btc/ml_engine.py`: Lines 1217–1240.
- **Resolution & Data**:
  - Pulls 350 bars of **1-minute candles** (`fetch_candles(self.asset, timeframe="1m", limit=350)`).
  - Evaluates live active candle (`df_ind.iloc[-1]`).
- **Timing & Dynamic Conviction**:
  - Allowed mid-candle up to 3 minutes before expiration (`sec_left >= 180s`; in SaaS broadcaster `sec_left >= 240s`).
  - Dynamic conviction floor:
    $$\text{min\_conf} = \begin{cases} 60.0\% & \text{if } \text{sec\_elapsed} \le 60s \\ 75.0\% & \text{if } \text{sec\_elapsed} > 60s \end{cases}$$
- **Signal Isolation**:
  - Uses `CHART_ONLY` isolation in `contract_eval.py:686–688` (bypasses ML model vetoes because heavy order flow is treated as a pure technical tape read).

---

### 2.5. `AMBUSH`
- **Purpose**: Captures explosive volatility expansion out of Bollinger Band squeezes while guarding against limit exhaustion traps.
- **Code Locations**:
  - `backend/btc/analyzer/contract_eval.py`: Lines 75–82, 686–688, 1074–1110.
  - `backend/btc/auto_executor/shared.py`: Lines 48–50, 176–179.
- **Execution & Isolation**:
  - Evaluates active candle mid-interval (`sec_left >= 180s`). Uses `CHART_ONLY` isolation.
- **Specialized CVD & Macro Gates** (`contract_eval.py:1074–1110`):
  - **CVD Acceleration Veto**:
    - If fading a dump (buying YES on red candle) but $\text{CVD Acceleration} < -0.1$: **BLOCKED** (`PASS (NO ABSORPTION)`). Real aggressive market sellers are hitting bids with no passive limit absorption.
    - If fading a pump (buying NO on green candle) but $\text{CVD Acceleration} > +0.1$: **BLOCKED**. Real aggressive buyers are hitting asks.
  - **1-Hour Macro Trend Veto**:
    - If fading a pump but 1-Hour trend is `BULLISH`: **BLOCKED** (`PASS (MACRO CONFLICT)`).
    - If fading a dump but 1-Hour trend is `BEARISH`: **BLOCKED**.

---

### 2.6. `PREDICTION`
- **Purpose**: Pure machine learning probability forecasting with temporal noise filtering.
- **Code Locations**:
  - `backend/btc/analyzer/contract_eval.py`: Lines 683–685, 1111–1175.
  - `backend/btc/auto_executor/executor.py`: Lines 635–640, 944–951.
  - `backend/btc/auto_executor/saas_broadcaster.py`: Lines 696–706.
- **Opening Noise Delay**:
  - Enforces a mandatory **90-second wait** after candle open:
    $$\text{sec\_elapsed} \ge 90s \quad \text{and} \quad \text{sec\_left} \ge 180s$$
    Prevents entering on opening tick chop and wide market-maker spreads.
- **Signal Isolation & Edge Floor**:
  - `AI_ONLY` isolation: Neural network/ensemble probability is the primary driver.
  - Applies a mild $\pm 5.0\%$ chart nudge based on physical technical direction.
  - **Minimum Conviction Gate**:
    $$|P(\text{YES}) - 50.0| \ge 8.0\% \implies \text{Confidence} \ge 58.0\%$$
    Probabilities between $42\%$ and $58\%$ are rejected as negative-expectancy coin flips.
  - **Order Book Wall Veto**: Blocked if Coinbase orderbook imbalance $\le -30\%$ for YES, or $\ge +30\%$ for NO.

---

### 2.7. `CHOP`
- **Purpose**: Counter-trend mean reversion designed to fade Bollinger Band extremes when prices are range-bound.
- **Code Locations**:
  - `backend/btc/chop_engine.py`: Lines 1–98 (`evaluate_chop_contract`).
  - `backend/btc/analyzer/contract_eval.py`: Lines 694–724.
  - `backend/btc/auto_executor/executor.py`: Lines 761–771, 952–953.
- **Entry Rules**:
  - Upper Band Fade: Close $\ge \text{BB}_{\text{upper}}$ and $\text{RSI} > 65 \implies \text{BID NO}$.
  - Lower Band Bounce: Close $\le \text{BB}_{\text{lower}}$ and $\text{RSI} < 35 \implies \text{BID YES}$.
- **Pricing Sweet Spot Filter**:
  - Kalshi ask must be centered in the $40¢ - 60¢$ corridor, with time-decay tolerance:
    $$\text{tolerance} = \min(0.35, \max(0.10, 0.10 + (840 - \text{sec\_left}) \times 0.000378))$$
    $$| \text{Ask} - 0.50 | \le \text{tolerance}$$
- **Conviction Floor**:
  - `CHOP_EXTRA_CONFIDENCE_FLOOR = 6.0%`. Requires $|\text{prob} - 50.0| \ge 6.0\%$ ($56\%$ or higher), and grade must contain substring `"CHOP"`.

---

### 2.8. `SCALP` / `RL_SCALPER`
- **Purpose**: Rapid micro-trades aiming for early take-profit exits on fast momentum moves or reinforcement-learned policies.
- **Code Locations**:
  - `backend/btc/scalp_engine.py`: Lines 18–541 (`ScalpEngine`).
  - `backend/btc/rl_scalper.py`: Lines 1–280.
  - `backend/btc/auto_executor/saas_broadcaster.py`: Lines 574–676.
- **Entry Rules**:
  - `ScalpEngine`:
    - Tracks price delta relative to 15m interval open (`interval_pct_change`) and rolling 60s window (`rolling_pct_change`).
    - Triggers if $|\Delta \%| \ge 0.25\%$ (`price_move_threshold`).
    - Validates direction against `analyze_btc()` confluence forecast (requires Grade $\ge \text{A}$).
    - Limits: 1 trade per 15m interval, 30s cooldown.
  - `RL_SCALPER`:
    - Evaluated exclusively during the first 4 minutes of the market (`sec_elapsed <= 240s`).
    - Uses Dueling QR-DQN policy network over orderbook features + current position state.
    - Max 3 entries per contract. Never enters while position is open.

---

## 3. Position Sizing Formulas

The system implements four distinct position sizing algorithms across single-user and multitenant modes:

### 3.1. Fixed Contract Sizing
- Code: `executor.py:1045`
$$\text{contracts} = \text{max\_contracts}$$

### 3.2. Dollar-Cap Sizing
- Code: `executor.py:1020–1044`
$$\text{unit\_price\_est} = \min(0.99, \max(0.01, \text{market\_price} + 0.04))$$
$$\text{contracts} = \max\left(1, \left\lfloor \frac{\text{max\_cap}}{\text{unit\_price\_est}} \right\rfloor\right)$$

### 3.3. True Binary Options Kelly & Half-Kelly Sizing
- Code: `executor.py:1029–1040` (Single-user) and `saas_broadcaster.py:888–897` (SaaS Multitenant).
- **Mathematical Derivation**:
  In a binary contract paying $\$1.00$ on success, priced at $b$ ($0 < b < 1$), the net profit on a win is $1 - b$, and loss on failure is $b$.
  Expected profit per dollar wagered is:
  $$\mathbb{E}[\text{return}] = \frac{p \cdot (1 - b) - (1 - p) \cdot b}{b} = \frac{p - b}{b}$$
  The classic Kelly fraction $f^*$ for a binary bet with odds $(1-b)/b$ is:
  $$f^* = \frac{p \cdot \frac{1 - b}{b} - (1 - p)}{\frac{1 - b}{b}} = \frac{p - b}{1 - b}$$

- **Single-User Approximation** (`executor.py:1036–1039`):
  $$\text{edge} = p_{\text{win}} - b_{\text{price}}$$
  $$\text{If } p_{\text{win}} \le b_{\text{price}} \implies \text{Skip (-EV)}$$
  $$\text{kelly\_frac} = \min\left(1.0, \max\left(0.25, \frac{\text{edge}}{0.15}\right)\right)$$
  $$\text{base\_dollars} = \text{max\_cap} \times \text{kelly\_frac}$$

- **SaaS Multitenant True Half-Kelly (Pillar 6)** (`saas_broadcaster.py:888–897`):
  $$f^* = \frac{p_{\text{win}} - b_{\text{price}}}{1.0 - b_{\text{price}}}$$
  $$\text{kelly\_frac} = \min(1.25, \max(0.25, 0.50 \times f^*))$$
  $$\text{risk\_amount} = \max(0.50, \text{trade\_size\_dollars} \times \text{kelly\_frac})$$
  $$\text{contracts} = \left\lfloor \frac{\text{risk\_amount}}{\text{market\_price} + 0.04} \right\rfloor$$
  *Fee safety loop*: Contracts are iteratively decremented if $\text{cost} + \text{fee} > \text{risk\_amount}$.

### 3.4. Forex Pip-Value Dynamic Sizing
- Code: `backend/forex/auto_executor.py:65–84`
$$\text{risk\_amount} = \text{balance} \times \frac{\text{RISK\_PCT}}{100}$$
$$\text{exact\_units} = \frac{\text{risk\_amount}}{\text{pips\_to\_sl} \times \text{pip\_value\_per\_unit}}$$
Rounded to the nearest micro lot (1,000 units).

---

## 4. Order Types, Time-in-Force, and Execution Mechanics

### 4.1. Order Specification
- **API Endpoint**: Kalshi Trade API v2: `POST /trade-api/v2/portfolio/events/orders` (`kalshi_trader.py:1196–1230`).
- **Order Type**: Limit Order crossing top-of-book.
- **Time-in-Force (TIF)**: `"immediate_or_cancel"` (IOC).
  - Ensures immediate fills or zero resting queue risk.
- **Flags**:
  - `post_only`: `False` (Taker order).
  - `reduce_only`: `False` for entries; `True` for exits (`close_position`).
  - `self_trade_prevention_type`: `"taker_at_cross"`.
  - `cancel_order_on_pause`: `True`.

### 4.2. Pricing and Slippage Buffer
- Because Kalshi v2 event order books are quoted exclusively on the **YES price scale**:
  - For **YES** orders:
    $$\text{book\_price} = \min(0.99, \max(0.01, \text{market\_price} + \text{slippage\_buffer}))$$
  - For **NO** orders:
    $$\text{book\_price} = 1.0 - \min(0.99, \max(0.01, \text{market\_price} + \text{slippage\_buffer}))$$
    and `side = "ask"`.
- **Slippage Buffer**: Default is **`$0.04`** (configurable up to `$0.15`).
- **Fast IOC Single-Retry**:
  - `kalshi_trader.py:1237–1260`: If an IOC limit order is unfilled due to sub-second book movement, the engine force-refreshes the market quote and retries once if the new ask is within $\pm \$0.06$ of the original price.
- **Paper Trading Latency Tax**:
  - `kalshi_trader.py:35, 1076`: `PAPER_LATENCY_TAX_DOLLARS = 0.01`. A $\$0.01$ penalty is added to simulated entry prices and subtracted from simulated exits to model network round-trip slippage.

---

## 5. Exit Criteria, Stop-Loss, and Take-Profit

The exit engine operates across four layers:

```
[ Active Position ]
       │
       ├── 1. Hard Take-Profit (+50%) ───────────────────────► [ Immediate Limit IOC Sell ]
       │
       ├── 2. Dynamic Trailing Take-Profit (Peak +35%, Trail 6%) ► [ Locks in Profit ]
       │
       ├── 3. Contract Mid-Price Stop-Loss (-50%) ───────────► [ Bailout Exit ]
       │
       ├── 4. Structural Spot Invalidation Stop-Loss ────────► [ Early Capital Salvage ]
       │         (Terminal Deficit > $35 or EMA-21 Break)
       │
       └── 5. Expiration Settlement ($1.00 or $0.00) ────────► [ Kalshi Index Settlement ]
```

### 5.1. Hard Take-Profit
- Code: `stop_manager.py:329–340`, `saas_settler.py:822–825`.
- Trigger: Realized contract bid exceeds entry price by $\ge 50.0\%$ (`take_profit_pct`):
  $$\frac{\text{curr\_bid} - \text{entry\_price}}{\text{entry\_price}} \ge \text{take\_profit\_pct}$$
- Requires `curr_bid > entry_price`. Verified against a fresh quote (`_fresh_quote`).

### 5.2. Dynamic Trailing Take-Profit
- Code: `stop_manager.py:342–363`, `saas_settler.py:804–811`.
- Activation: Activated once max seen bid reaches $\ge +35\%$ profit (`trailing_stop_activation_pct`).
- Trailing Distance: $6\%$ (`trailing_stop_distance_pct`).
- Threshold:
  $$\text{trail\_threshold} = \max(\text{max\_seen\_bid} - 0.06, \text{max\_seen\_bid} \times 0.94)$$
  $$\text{trail\_threshold} = \max(\text{trail\_threshold}, \text{entry\_price} \times 1.02)$$
- Exits immediately if bid falls to or below `trail_threshold`.

### 5.3. Contract Price Stop-Loss
- Code: `stop_manager.py:365–379`, `saas_settler.py:819–821`.
- Trigger: Loss $\ge 50\%$ from entry (`stop_loss_pct`).
- Evaluated against contract **mid-price** $(\text{bid} + \text{ask}) / 2$ to prevent instant stop-outs from wide spreads.
- Protected by `STOP_LOSS_GRACE_SECONDS` to prevent stopping out on opening volatility.

### 5.4. Structural Spot Invalidation Stop-Loss (Pillar 5)
- Code: `stop_manager.py:384–420`.
- Protects against catastrophic zero-settlement by salvaging $10¢ - 35¢$ in remaining contract value when the underlying chart breaks:
  1. **Terminal Deficit Check**:
     $$\text{minutes\_remaining} < 2.0 \quad \text{and} \quad |\text{Spot} - \text{Strike}| > \$35.00 \text{ (against position)}$$
  2. **Early Structural Breakdown**:
     $$\text{minutes\_remaining} \ge 2.0 \quad \text{and} \quad \text{Spot crosses 15m EMA-21 with } |\text{CVD}| > 10.0$$
- Triggers immediate reduce-only IOC sell.

### 5.5. Position Reversal (Flip)
- Code: `stop_manager.py:433–614`.
- If stopped out by structural stop-loss, attempts to flip to the opposite contract if:
  1. Time remaining $\ge 6.0$ minutes.
  2. Max 1 reversal per interval.
  3. Opposite ask $\le \$0.65$.
  4. Model confluence confidence on opposite side $\ge 75.0\%$.

---

## 6. Fee Structure and Mathematical Expectancy

### 6.1. Kalshi Taker Fee Schedule
- Code: `backend/btc/fees.py:12–19`.
- Kalshi charges a taker fee per contract according to the regulatory schedule:
  $$\text{Fee per contract} = \left\lceil 0.07 \times \text{Price} \times (1.0 - \text{Price}) \times 100 \right\rceil \div 100$$
- At a $\$0.50$ contract price:
  $$\text{Fee} = 0.07 \times 0.50 \times 0.50 = \$0.0175 \implies \$0.02 \text{ per contract}$$
- **At settlement, the fee is $\$0.00$**.
- If a trade is opened and held to settlement, fee is paid **once** ($\approx 2¢$).
- If a trade is closed early (Take-Profit or Stop-Loss), the fee is paid **twice** ($\approx 4¢$), in addition to crossing the bid-ask spread ($\approx 4¢ - 10¢$).

### 6.2. Breakeven Win-Rate Analysis
- For a contract purchased at $p = \$0.50$ held to settlement:
  $$\mathbb{E}[\text{PnL}] = W \cdot (1.00 - 0.50) - (1 - W) \cdot 0.50 - 0.02 = W - 0.52$$
  $$\text{Breakeven Win Rate } W_{\text{be}} = \mathbf{52.0\%}$$
- For a trade that actively scalps / exits early at an average bid-ask spread of $4¢$:
  $$\mathbb{E}[\text{PnL}] = W \cdot (\text{Profit}) - (1 - W) \cdot (\text{Loss}) - \text{Spread} - 2 \times \text{Fee}$$
  The effective hurdle rate rises to **$56.0\% - 61.0\%$** depending on hold time.

---

## 7. Theoretical Edge, Edge Cases, and Regime Vulnerabilities

### 7.1. Theoretical Sources of Edge
1. **Multi-Source Confluence**: Combines institutional Smart Money Concepts (liquidity sweeps, order block defense, FVG imbalances) with dual-timeframe momentum (1H EMA-50/21 alignment) and order flow (CVD, Coinbase orderbook imbalances).
2. **Dynamic Machine Learning Gating**: Dueling QR-DQN and XGBoost models calibrated via Platt scaling, requiring $P(\text{Win}) > \text{Ask} + \text{Fees} + \text{Edge}$.
3. **Loss-Prevention Filters**:
   - Strike Pin Dead-Zone filter ($|\Delta| \le \$18$, $\text{ATR} \le \$45$) eliminates coin flips.
   - Dynamic early stop-loss rescues $20\% - 40\%$ of capital instead of suffering $100\%$ zero-settlement.
   - Half-Kelly sizing mathematically protects against gambler's ruin.

### 7.2. Edge Cases and Vulnerabilities to Market Regimes

#### Vulnerability 1: Illiquid Order Books and Wide Bid-Ask Spreads
- **Mechanism**: Kalshi 15m crypto event contracts frequently exhibit thin liquidity with wide spreads (e.g. $40¢$ bid / $60¢$ ask).
- **Vulnerability**: An IOC taker order crossing the book with a $\$0.04$ buffer pays a severe liquidity penalty. Furthermore, early exits (stop-loss / take-profit) must hit the executable bid, instantly giving up the spread. In illiquid markets, early exits can turn what would have been a winning hold into a realized loss.

#### Vulnerability 2: Sideways Range-Bound Chop Bleed
- **Mechanism**: When spot price fluctuates within a narrow $\$30$ range around the strike price with low ATR.
- **Vulnerability**: If `CAPITAL_GUARD` is bypassed (e.g., user enables `ignorePass` or `auto_force_trade`), false breakouts trigger repeated entries. The position flip-flops around the strike, causing consecutive losses.

#### Vulnerability 3: Strike Pinning Noise at Rollover Expiry
- **Mechanism**: When spot price settles within $\$5 - \$10$ of the contract strike price during the final 60 seconds.
- **Vulnerability**: Contract outcomes become entirely dependent on sub-second tick latency between Coinbase/Kraken index feeds and Kalshi settlement. The theoretical prediction edge drops to exactly $50\%$ (random walk), but taker fees ensure a negative expectancy.

#### Vulnerability 4: Violent Liquidation Cascades and Slip Traps
- **Mechanism**: Flash crashes or short squeezes where spot price moves $\$500+$ in under two minutes.
- **Vulnerability**: Counter-trend mean-reversion setups (e.g., `CHOP` or oversold hammers) will attempt to catch the falling knife. While liquidation filters exist ($>\$2\text{M}$ liquidations block counter-trend entries), WebSocket feed lag or REST timeouts can fail to deliver real-time liquidation data, leading to severe drawdown.

#### Vulnerability 5: Overfitting / Drift in Machine Learning Engines
- **Mechanism**: The PyTorch ensemble and Dueling DQN retrain on rolling historical data (7-day cadence).
- **Vulnerability**: Crypto regime shifts (e.g., from high-volatility trend to ETF-dominated range) cause feature distributions (RSI, ATR, CVD) to drift. If calibrated on trend regimes, the models overpredict directional probability during consolidation.

---

## 8. Exact Code Path Reference Table

| Component / Style | Target File | Class / Function | Key Line Numbers |
| :--- | :--- | :--- | :--- |
| **`AUTO` Regime Classifier** | `backend/btc/auto_executor/shared.py` | `classify_auto_regime()` | Lines 39–205 |
| **`CAPITAL_GUARD` Filter** | `backend/btc/analyzer/contract_eval.py` | `evaluate_next_15m_contract()` | Lines 56–74 |
| **`SNIPER` Entry & EV Gate** | `backend/btc/analyzer/contract_eval.py` | `evaluate_next_15m_contract()` | Lines 75–87, 1055–1073 |
| **`MOMENTUM_SURFER` Execution** | `backend/btc/auto_executor/executor.py` | `check_and_execute_rollover()` | Lines 704–706, 939–943 |
| **`AMBUSH` Anti-Exhaustion** | `backend/btc/analyzer/contract_eval.py` | `evaluate_next_15m_contract()` | Lines 1074–1110 |
| **`PREDICTION` Delay & Floor** | `backend/btc/analyzer/contract_eval.py` | `evaluate_next_15m_contract()` | Lines 1111–1175 |
| **`CHOP` Engine & Sweet Spot** | `backend/btc/chop_engine.py` | `evaluate_chop_contract()` | Lines 46–98 |
| **`SCALP` Engine Monitoring** | `backend/btc/scalp_engine.py` | `ScalpEngine._monitor()` | Lines 106–233 |
| **`RL_SCALPER` Entry & Policy** | `backend/btc/auto_executor/saas_broadcaster.py` | `_execute_single_user_trade()` | Lines 574–676 |
| **Kelly & Half-Kelly Sizing** | `backend/btc/auto_executor/saas_broadcaster.py` | `_execute_single_user_trade()` | Lines 888–897 |
| **Dollar Cap & Position Sizing**| `backend/btc/auto_executor/executor.py` | `check_and_execute_rollover()` | Lines 1020–1047 |
| **Order Placement (IOC Limit)**| `backend/btc/kalshi_trader.py` | `KalshiTrader._place_order_internal()` | Lines 1000–1235 |
| **Dynamic Stop & Invalidation** | `backend/btc/auto_executor/stop_manager.py` | `check_active_trades_stop_and_reversal()` | Lines 209–432 |
| **Position Reversal Flip** | `backend/btc/auto_executor/stop_manager.py` | `_attempt_position_reversal()` | Lines 433–614 |
| **Take-Profit & Trailing Stop** | `backend/btc/auto_executor/stop_manager.py` | `check_active_trades_stop_and_reversal()` | Lines 329–363 |
| **SaaS Multitenant Settlement** | `backend/saas_settler.py` | `settle_all_users_continuous()` | Lines 760–860 |
| **Loss Diagnosis & Penalties** | `backend/btc/loss_analyzer.py` | `LossAnalyzer.diagnose_loss()` | Lines 18–95, 96–139 |
| **Taker Fee & Net PnL** | `backend/btc/fees.py` | `kalshi_order_fee()`, `entry_edge_cents()` | Lines 12–38 |
| **Forex Micro-Lot Execution** | `backend/forex/auto_executor.py` | `forex_trading_loop()` | Lines 22–95 |
