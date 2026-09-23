import os
import bcrypt
import jwt
import datetime
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# We need a robust encryption key for Fernet. If it doesn't exist, we will create one and save it to .env
ENCRYPTION_KEY = os.environ.get("SAAS_ENCRYPTION_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-default-key-change-me")
INVITE_CODE = os.environ.get("SAAS_INVITE_CODE", "KALSHI2026") # Default invite code

def setup_encryption_key():
    global ENCRYPTION_KEY
    if not ENCRYPTION_KEY:
        key = Fernet.generate_key().decode('utf-8')
        env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
        with open(env_path, 'a') as f:
            f.write(f"\nSAAS_ENCRYPTION_KEY={key}\n")
        ENCRYPTION_KEY = key
        print("Generated new SAAS_ENCRYPTION_KEY and saved to .env")
    return ENCRYPTION_KEY

# Initialize on import
setup_encryption_key()
fernet = Fernet(ENCRYPTION_KEY.encode('utf-8'))

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def encrypt_kalshi_key(private_key: str) -> str:
    if not private_key:
        return ""
    return fernet.encrypt(private_key.encode('utf-8')).decode('utf-8')

def decrypt_kalshi_key(encrypted_key: str) -> str:
    if not encrypted_key:
        return ""
    try:
        return fernet.decrypt(encrypted_key.encode('utf-8')).decode('utf-8')
    except Exception as e:
        print(f"Decryption error: {e}")
        return ""

def create_jwt_token(user_id: int, username: str) -> str:
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7),
        'iat': datetime.datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def decode_jwt_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
