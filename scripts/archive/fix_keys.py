import sqlite3
from backend.auth.security import decrypt_kalshi_key, encrypt_kalshi_key

def fix_pem(pem_str: str) -> str:
    # If it already has newlines, maybe it's fine
    if '\n' in pem_str.strip():
        # Check if lines are okay?
        return pem_str

    # It's a mangled string with spaces
    s = pem_str.replace('-----BEGIN RSA PRIVATE KEY-----', 'BEGIN_RSA')
    s = s.replace('-----END RSA PRIVATE KEY-----', 'END_RSA')
    s = s.replace('-----BEGIN PRIVATE KEY-----', 'BEGIN_PK')
    s = s.replace('-----END PRIVATE KEY-----', 'END_PK')
    
    # Remove all spaces
    s = s.replace(' ', '')
    
    # Now chunk the base64 part into 64-char lines
    # Find start and end markers
    if 'BEGIN_RSA' in s:
        start_marker = 'BEGIN_RSA'
        end_marker = 'END_RSA'
        real_start = '-----BEGIN RSA PRIVATE KEY-----'
        real_end = '-----END RSA PRIVATE KEY-----'
    elif 'BEGIN_PK' in s:
        start_marker = 'BEGIN_PK'
        end_marker = 'END_PK'
        real_start = '-----BEGIN PRIVATE KEY-----'
        real_end = '-----END PRIVATE KEY-----'
    else:
        return pem_str # Cannot fix

    start_idx = s.find(start_marker) + len(start_marker)
    end_idx = s.find(end_marker)
    b64_data = s[start_idx:end_idx]

    lines = [real_start]
    for i in range(0, len(b64_data), 64):
        lines.append(b64_data[i:i+64])
    lines.append(real_end)
    lines.append('')
    return '\n'.join(lines)

conn = sqlite3.connect('backend/data/users.db')
cursor = conn.cursor()
users = cursor.execute('SELECT id, kalshi_priv_key_encrypted FROM users WHERE kalshi_key_id IS NOT NULL').fetchall()
for uid, enc in users:
    if not enc: continue
    try:
        priv = decrypt_kalshi_key(enc)
        fixed_priv = fix_pem(priv)
        if fixed_priv != priv:
            new_enc = encrypt_kalshi_key(fixed_priv)
            cursor.execute('UPDATE users SET kalshi_priv_key_encrypted = ? WHERE id = ?', (new_enc, uid))
            print(f'Fixed key for user id {uid}')
    except Exception as e:
        print(f'Failed for uid {uid}: {e}')
conn.commit()
conn.close()
print('Done!')
