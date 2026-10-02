import re

with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    code = f.read()

replacement = """def get_db_connection():
    if not hasattr(_thread_local, 'connection') or _thread_local.connection is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        _thread_local.connection = conn
    else:
        try:
            _thread_local.connection.execute('SELECT 1')
        except sqlite3.ProgrammingError:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            _thread_local.connection = conn
    return _thread_local.connection"""

code = re.sub(r'def get_db_connection\(\):.*?return _thread_local\.conn', replacement, code, flags=re.DOTALL)
code = re.sub(r'def get_db_connection\(\):.*?return _thread_local\.connection', replacement, code, flags=re.DOTALL)

with open('backend/database/models.py', 'w', encoding='utf-8') as f:
    f.write(code)
