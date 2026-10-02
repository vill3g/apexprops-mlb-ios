
import re
with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

pattern = re.compile(r"// iOS Notifications for newly closed trades\s+if \(s\.recent_trades && Array\.isArray\(s\.recent_trades\)\) \{\s+s\.recent_trades\.forEach\(t => \{\s+const status = String\(t\.status \|\| ''\)\.toUpperCase\(\);\s+const tradeId = String\(t\.id\);\s+if \(status === 'CLOSED' \|\| status\.includes\('WIN'\) \|\| status\.includes\('LOSS'\)\) \{\s+if \(!knownCompletedTrades\.has\(tradeId\)\) \{\s+if \(!initialLoad\) \{\s+const pnl = parseFloat\(t\.pnl_dollars \|\| t\.pnl \|\| 0\);\s+const isWin = status\.includes\('WIN'\) \|\| pnl > 0;\s+const assetStr = t\.asset \|\| 'Asset';\s+if \(isWin\) \{\s+window\.iosNotify\('Trade Won! \?', \\ profit secured: \+\$\\, 'success'\);\s+\} else \{\s+window\.iosNotify\('Trade Closed', \\ loss incurred: -\$\\, 'error'\);\s+\}\s+\}\s+knownCompletedTrades\.add\(tradeId\);\s+\}\s+\}\s+\}\);\s+\}", re.DOTALL)

content = re.sub(pattern, "", content)

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

