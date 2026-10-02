import sqlite3; conn = sqlite3.connect('backend/data/users.db'); c = conn.cursor(); c.execute('SELECT role FROM users WHERE id=7'); print(c.fetchone())
