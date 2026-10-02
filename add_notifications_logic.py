import re
path = "static/js/dashboard.js"
with open(path, "r", encoding="utf-8") as f:
    js = f.read()

# We need to hook into the updateDashboard loop.
# Searching for `fillRecentExecutions(s.recent_trades);` or `const recentTrades = s.recent_trades || [];`
# Actually, let's inject it right after `if (data.ml_reasoning) { ... }` or at the end of the update loop.

hook_code = """
                // --- Notifications Logic ---
                if (window.userConfig) {
                    const notifyTrades = window.userConfig.notify_trade_results !== false;
                    const notifyTrends = window.userConfig.notify_market_trends !== false;
                    
                    window._prevTradeStates = window._prevTradeStates || {};
                    const currentTrades = s.recent_trades || [];
                    
                    if (notifyTrades && Object.keys(window._prevTradeStates).length > 0) {
                        currentTrades.forEach(t => {
                            const prev = window._prevTradeStates[t.id];
                            if (prev && prev === 'OPEN' && t.status !== 'OPEN') {
                                const isWin = t.status.includes('WIN') || (parseFloat(t.pnl_dollars || t.pnl || 0) > 0);
                                const pnlStr = parseFloat(t.pnl_dollars || t.pnl || 0).toFixed(2);
                                if (isWin) {
                                    showToast(`Trade Won! +$${pnlStr}`, 'success');
                                } else {
                                    showToast(`Trade Closed: -$${Math.abs(pnlStr)}`, 'warning');
                                }
                            }
                        });
                    }
                    // Update state map
                    currentTrades.forEach(t => { window._prevTradeStates[t.id] = t.status; });

                    if (notifyTrends && s.ml_reasoning && s.ml_reasoning.regime) {
                        const currentRegime = s.ml_reasoning.regime;
                        if (window._prevRegime && window._prevRegime !== currentRegime) {
                            showToast(`Market Trend Shift: ${currentRegime}`, 'info');
                        }
                        window._prevRegime = currentRegime;
                    }
                }
                // ---------------------------
"""

# Let's insert it right before `// Render Recent Executions` or `const container = document.getElementById('tradesContainer');`
pattern = r"(\s*)(// Render Recent Executions \(Sleek Mode-Aware Cards\) with State Diffing)"
replacement = r"\1" + hook_code.replace("\n", "\n\\1") + "\n\\1\\2"

js = re.sub(pattern, replacement, js)

with open(path, "w", encoding="utf-8") as f:
    f.write(js)
print("Added Notification logic to JS")
