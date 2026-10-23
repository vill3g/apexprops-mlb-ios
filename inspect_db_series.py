import sqlite3

conn = sqlite3.connect('backend/data/kalshi_markets_cache.db')
cur = conn.cursor()
for prefix in ['KXNBA', 'KXNCAAF', 'KXMLB', 'KXNPB', 'KXATP', 'KXWTA', 'KXNFL', 'KXNHL', 'KXSOC', 'KXEPL', 'KXUFC']:
    cur.execute("SELECT series_ticker, count(ticker) FROM kalshi_markets WHERE series_ticker LIKE ? GROUP BY series_ticker", (prefix + '%',))
    print(prefix, cur.fetchall())
