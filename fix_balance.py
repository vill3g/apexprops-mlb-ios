import re

js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

pattern = r"""                // Balance calculation
                let liveBalance = s.balance_dollars;
                if \(liveBalance !== undefined && liveBalance !== null\) \{
                    if \(currentMode === 'PAPER'\) \{
                        const baseCash = \(s.balance_dollars \|\| 500.0\) - parseFloat\(s.open_paper_value \|\| 0.0\);
                        liveBalance = baseCash \+ totalLiveOpenValue;
                    \} else \{
                        const pnlDiff = totalLiveOpenPnl - backendSnapOpenPnl;
                        liveBalance = \(s.balance_dollars \|\| 0.0\) \+ pnlDiff;
                    \}
                \}"""

replacement = """                // Balance calculation
                let liveBalance = s.balance_dollars;
                if (liveBalance !== undefined && liveBalance !== null) {
                    if (currentMode === 'PAPER') {
                        // Just show Available Cash for Paper so deductions are extremely obvious
                        liveBalance = (s.balance_dollars || 500.0) - parseFloat(s.open_paper_value || 0.0);
                    } else {
                        // Live mode uses Kalshi's Portfolio Value
                        const pnlDiff = totalLiveOpenPnl - backendSnapOpenPnl;
                        liveBalance = (s.balance_dollars || 0.0) + pnlDiff;
                    }
                }"""

js = re.sub(pattern, replacement, js)
with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
print("Updated dashboard.js to show Available Cash for PAPER mode!")
