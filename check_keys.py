import sqlite3
from backend.database.models import get_all_active_users
from backend.auth.security import decrypt_kalshi_key

users = get_all_active_users()
for u in users:
    print(f"User: {u['username']}")
    priv = decrypt_kalshi_key(u['kalshi_priv_key_encrypted'])
    print(f"Priv: {repr(priv[:50]) if priv else None}")
