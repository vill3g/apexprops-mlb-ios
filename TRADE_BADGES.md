# Trade Badges Quick Reference Guide

## Badge Legend

### Row 1: Trade Mode (Required - Always Shows)

```
🔴 LIVE                              🔵 PAPER
Red background                       Cyan background
Real money                           Simulated trading
High risk                            Risk-free testing
```

---

### Row 2: Execution Source (Required - Always Shows)

```
👤 MANUAL                            🤖 AUTO
Amber background                     Violet background
Manually executed                    Autonomous AI execution
By trader                            By algorithm
```

OR if machine gun style:
```
🤖 AUTO (MG)
Violet background
Autonomous execution
Machine gun rapid-fire style
```

---

### Row 3: Strategy Type (Optional - Only If Applicable)

```
⚡ SCALP                             🔄 REVERSE
Fuchsia background                   Indigo background
High-frequency scalping              CVD divergence reversal
Quick profit targets                 Momentum reversal setup
```

---

### Row 4: Exit Reason (Optional - Only For Closed Trades)

```
🎯 TP EXIT                           🛑 SL EXIT
Emerald (green) background           Rose (red) background
Take-profit reached                  Stop-loss triggered
Closed with profit/target            Closed with loss/trigger
```

OR

```
🚪 MANUAL EXIT                       ⏰ EXPIRY
Orange background                    Slate gray background
Trader manually closed               Reached expiration
Mid-trade closure                    Timed out / settled
```

---

## Example Trade Cards

### Example 1: Successful Auto Scalp Trade

```
┌─────────────────────────────────────────────────────┐
│ #1  KXBTC15M  🔵 PAPER  🤖 AUTO  ⚡ SCALP  🎯 TP EXIT │
├─────────────────────────────────────────────────────┤
│ Target Strike: $45,250  |  BID UP  |  $45.2 → $46.1  │
│ Size: 2ct ($92.00) → +$18.25 (19.8%)                 │
├─────────────────────────────────────────────────────┤
│ 🧠 PREDICTION METRICS:  AI MODEL                     │
│ Model Conviction: 72% ████████░                      │
│ Catalysts: • Technical Momentum Confluence           │
├─────────────────────────────────────────────────────┤
│ 📋 SETTLEMENT DATA:                  ✓ Prediction Correct │
│ Settlement Price: $46.10  │  Source: KALSHI OFFICIAL │
│ Settled At: 2024-09-15 02:30:45 PM ET                │
└─────────────────────────────────────────────────────┘

Key Indicators:
🔵 PAPER  = Simulated (not real money)
🤖 AUTO   = Autonomous execution
⚡ SCALP  = High-frequency scalp trade
🎯 TP EXIT = Took profit at target
✓ Correct = AI prediction was accurate
```

### Example 2: Lost Manual Trade

```
┌─────────────────────────────────────────────────────┐
│ #3  KXBTC15M  🔴 LIVE  👤 MANUAL  🛑 SL EXIT        │
├─────────────────────────────────────────────────────┤
│ Target Strike: $45,100  |  BID DOWN  |  $45.0 → $44.8 │
│ Size: 1ct ($45.00) → -$10.50 (-23.3%)                │
├─────────────────────────────────────────────────────┤
│ 🧠 PREDICTION METRICS:  MANUAL DIRECTIVE            │
│ Model Conviction: 58% █████░░░░                      │
│ Catalysts: • Support Level Bounce  • Volume Spike    │
├─────────────────────────────────────────────────────┤
│ 📋 SETTLEMENT DATA:                  ✗ Prediction Incorrect │
│ Settlement Price: $44.80  │  Source: KALSHI OFFICIAL │
│ Settled At: 2024-09-15 02:15:30 PM ET                │
└─────────────────────────────────────────────────────┘

Key Indicators:
🔴 LIVE    = Real money (loss is real)
👤 MANUAL  = Trader initiated the trade
🛑 SL EXIT = Hit stop-loss level
✗ Incorrect = AI model disagreed with outcome
```

### Example 3: Open Reversal Trade

```
┌─────────────────────────────────────────────────────┐
│ #2  KXBTC15M  🔵 PAPER  🤖 AUTO  🔄 REVERSE        │
├─────────────────────────────────────────────────────┤
│ Target Strike: $45,350  |  BID UP  |  $45.2 → $45.8  │
│ Size: 3ct ($135.60) → +$18.00 (+13.3%)               │
├─────────────────────────────────────────────────────┤
│ 🧠 PREDICTION METRICS:  REVERSAL PATTERN            │
│ Model Conviction: 81% ████████░░                     │
│ Catalysts: • CVD Divergence  • Trend Reversal Box    │
├─────────────────────────────────────────────────────┤
│ [No Settlement Panel - Trade Still Open]            │
└─────────────────────────────────────────────────────┘

Key Indicators:
🔵 PAPER    = Simulated trade
🤖 AUTO     = Autonomous execution
🔄 REVERSE  = CVD divergence reversal setup
No Settlement = Trade is still in progress (not closed)
```

---

## Badge Combinations (What You'll See)

### Complete Closed Trade (All Badges)
```
🔴 LIVE + 👤 MANUAL + 🎯 TP EXIT = 3 badges
(Real money manually executed with take-profit exit)
```

### Typical Auto Scalp (Most Common)
```
🔵 PAPER + 🤖 AUTO + ⚡ SCALP = 3 badges
(Or with exit: 🔵 PAPER + 🤖 AUTO + ⚡ SCALP + 🎯 TP EXIT = 4 badges)
```

### Reversal Strategy
```
🔵 PAPER + 🤖 AUTO + 🔄 REVERSE = 3 badges
(May or may not have exit badge depending on status)
```

### Open Trade (No Exit Badge)
```
🔴 LIVE + 🤖 AUTO (+ ⚡ SCALP if applicable)
(2-3 badges, no exit badge because still open)
```

---

## Statistics Bar Examples

### Low Automation (Manual Focus)
```
[🤖 Auto: 2]  [⚡ Scalp: 1]  [👤 Manual: 7]
```
**Interpretation:** 7 manual trades, 2 auto, mostly trading discretionary

### Balanced
```
[🤖 Auto: 5]  [⚡ Scalp: 3]  [👤 Manual: 2]
```
**Interpretation:** Mostly automated with some scalp trades and 2 manual

### Highly Automated
```
[🤖 Auto: 8]  [⚡ Scalp: 6]  [👤 Manual: 1]
```
**Interpretation:** 8 autonomous trades (6 scalps), 1 manual

---

## Settlement Data Examples

### Kalshi Official Settlement
```
Settlement Source: KALSHI OFFICIAL
Settlement Price: $45,250.75
```
**Meaning:** Kalshi exchange officially settled this contract at this price

### Legacy Exchange Candle
```
Settlement Source: LEGACY EXCHANGE CANDLE
Settlement Price: $45,248.50
```
**Meaning:** Used historical exchange candle data to determine settlement

---

## Color Quick Reference

| Badge | Primary Color | Text Color | Meaning |
|-------|--------------|-----------|---------|
| 🔴 LIVE | Red-600 | Red-100 | Real money, high stakes |
| 🔵 PAPER | Cyan-600 | Cyan-100 | Simulated, testing |
| 👤 MANUAL | Amber-600 | Amber-100 | Trader controlled |
| 🤖 AUTO | Violet-600 | Violet-100 | AI controlled |
| ⚡ SCALP | Fuchsia-600 | Fuchsia-100 | High frequency |
| 🔄 REVERSE | Indigo-600 | Indigo-100 | Reversal pattern |
| 🎯 TP EXIT | Emerald-600 | Emerald-100 | Profit target hit |
| 🛑 SL EXIT | Rose-600 | Rose-100 | Loss cut hit |
| 🚪 MANUAL EXIT | Orange-600 | Orange-100 | Manually closed |
| ⏰ EXPIRY | Slate-600 | Slate-100 | Time expired |

---

## Reading a Trade Card (Top to Bottom)

### Level 1: Identity (First Line)
**What:** Badge pill row
**Contains:** Trade mode, execution type, strategy type, exit reason
**Time to understand:** < 1 second
**Action:** Immediately identify trade type

### Level 2: Financials (Second Block)
**What:** 4-column grid
**Contains:** Strike, direction, entry/exit prices, size and P&L
**Time to understand:** 2-3 seconds
**Action:** Assess magnitude and outcome

### Level 3: Intelligence (Third Block)
**What:** Cyan panel with metrics
**Contains:** Model conviction, signal directive, catalysts
**Time to understand:** 3-5 seconds
**Action:** Understand reasoning and confidence

### Level 4: Settlement (Fourth Block - If Closed)
**What:** Slate panel with settlement details
**Contains:** Settlement price, source, timestamp, accuracy
**Time to understand:** 2-3 seconds
**Action:** Verify official closure and prediction accuracy

**Total Time to Fully Understand a Trade:** 10-15 seconds

---

## Tips for Quick Scanning

1. **Scan badges first** - 0.5 seconds to identify trade type
2. **Check P&L color** - Green means profit, Red means loss
3. **Look for ✓ or ✗** - Quick accuracy check on settled trades
4. **Count the badges** - More badges = more complex strategy
5. **Check statistics bar** - Get overall distribution in 1 second

---

## Common Scenarios

### Scenario: Find All Losing Scalp Trades
```
1. Look at statistics bar: ⚡ Scalp: X
2. Scan trade cards for:
   - Red left border (loss indicator)
   - ⚡ SCALP badge
   - Review settlement data for details
```

### Scenario: Compare Manual vs Auto Performance
```
1. Statistics bar shows: 👤 Manual: 5 vs 🤖 Auto: 8
2. Look at win/loss colors on each type
3. Check individual P&L values
4. Review settlement accuracy (✓ vs ✗)
```

### Scenario: Debug a Bad Trade
```
1. Find the trade (look for red left border = loss)
2. Check badges (was it auto? scalp? etc.)
3. Review settlement data (official price)
4. Check prediction accuracy (was AI correct?)
5. Review catalysts (what triggered it?)
```

---

## FAQ

**Q: Why don't open trades show settlement data?**
A: Settlement data is only available after the trade expires or closes. Open trades haven't settled yet.

**Q: Can a trade have multiple strategy badges?**
A: Yes! A trade can be both AUTO and SCALP, for example: 🤖 AUTO + ⚡ SCALP

**Q: What does "KALSHI OFFICIAL" settlement source mean?**
A: It means the Kalshi exchange officially settled the contract at that price.

**Q: Why is prediction accuracy sometimes blank?**
A: This happens on manual trades where prediction accuracy isn't calculated (trader decided, not AI).

**Q: How often is the statistics bar updated?**
A: It updates automatically every time you refresh or switch view (10 vs All).

---

## Keyboard Shortcuts (Browser Native)

- `Cmd+R` (Mac) or `Ctrl+R` (Windows) = Refresh page
- `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows) = Hard refresh (clear cache)
- Click the **⟳** button in header = Soft refresh trades only

---

**Last Updated:** September 15, 2024
**Version:** 2.0 (Enhanced Badges & Settlement)
