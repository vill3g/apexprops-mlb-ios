import sqlite3
import re
from backend.database.models import get_all_active_users
from backend.auth.security import decrypt_kalshi_key, encrypt_kalshi_key, update_user_kalshi_keys
from backend.btc.kalshi_trader import KalshiTrader

def fix_pem(pem_str: str) -> str:
    header_match = re.search(r'-----BEGIN [^-]+-----', pem_str)
    footer_match = re.search(r'-----END [^-]+-----', pem_str)
    if not header_match or not footer_match:
        return pem_str
    
    header = header_match.group(0)
    footer = footer_match.group(0)
    body = pem_str[header_match.end():footer_match.start()]
    body_clean = re.sub(r'\s+', '', body)
    
    lines = [header]
    for i in range(0, len(body_clean), 64):
        lines.append(body_clean[i:i+64])
    lines.append(footer)
    
    return '\n'.join(lines)

users = get_all_active_users()
for u in users:
    priv = decrypt_kalshi_key(u['kalshi_priv_key_encrypted'])
    if priv and ' ' in priv and '\n' not in priv:
        print(f"Fixing key for {u['username']}...")
        fixed_priv = fix_pem(priv)
        kt = KalshiTrader(key_id=u['kalshi_key_id'], private_key_pem=fixed_priv)
        if kt.is_authenticated():
            print("  Authenticated successfully after fix!")
            # Save it back
            update_user_kalshi_keys(u['id'], u['kalshi_key_id'], encrypt_kalshi_key(fixed_priv))
        else:
            print("  Still failed to authenticate.")
