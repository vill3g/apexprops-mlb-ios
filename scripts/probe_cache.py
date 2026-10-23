import sqlite3
c = sqlite3.connect('backend/data/quant_lab.db')
print(c.execute('select sport,count(*) from sports_history group by sport').fetchall())
for sp in ('UFC', 'NHL', 'NPB', 'KBO', 'SOC', 'EPL', 'MLS'):
    print(sp, c.execute("select ticker,name from sports_history where sport=? limit 4", (sp,)).fetchall())
