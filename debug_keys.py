import sqlite3
import os
from backend.auth.security import decrypt_kalshi_key
from backend.btc.kalshi_trader import KalshiTrader
from backend.database.models import get_all_active_users

users = get_all_active_users()
print(f'Found {len(users)} active users')

for u in users:
    print(f"User: {u['username']}")
    priv = decrypt_kalshi_key(u['kalshi_priv_key_encrypted'])
    if not priv:
        print('  Failed to decrypt private key!')
        continue
    
    try:
        kt = KalshiTrader(key_id=u['kalshi_key_id'], private_key_pem=priv)
        print('  Authenticated:', kt.is_authenticated())
        bal = kt.get_balance()
        print('  Balance:', bal)
    except Exception as e:
        print('  Exception:', e)
