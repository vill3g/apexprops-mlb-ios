import datetime
import logging
import os
import secrets
import time

import bcrypt
import jwt
from cryptography.fernet import Fernet
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

_ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# We need a robust encryption key for Fernet. If it doesn't exist, we will create one and save it to .env
ENCRYPTION_KEY = os.environ.get("SAAS_ENCRYPTION_KEY")
INVITE_CODE = os.environ.get("SAAS_INVITE_CODE", "KALSHI2026") # Default invite code

# ── JWT signing secret ────────────────────────────────────────────────
# Tokens used to be signed with a hard-coded public default, which let anyone
# forge a login for any user. We now sign with a private random secret stored
# in .env. Tokens signed with the old default are still accepted for a short
# migration window (and transparently re-issued with the new secret — see
# main.py) so nobody gets logged out. Set LEGACY_JWT_ACCEPT_UNTIL=0 in .env to
# end the migration window immediately.
_LEGACY_JWT_SECRET = "super-secret-default-key-change-me"
_LEGACY_GRACE_SECONDS = 14 * 86400


def _append_env(line: str) -> None:
    with open(_ENV_PATH, 'a') as f:
        f.write(f"\n{line}\n")


def _setup_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET", "").strip()
    if not secret or secret == _LEGACY_JWT_SECRET:
        secret = secrets.token_urlsafe(48)
        try:
            _append_env(f"JWT_SECRET={secret}")
            logger.warning("Generated new JWT_SECRET and saved to .env")
        except OSError as e:
            logger.error(f"Could not persist JWT_SECRET to .env: {e}")
        os.environ["JWT_SECRET"] = secret
    return secret


def _setup_legacy_cutoff() -> float:
    raw = os.environ.get("LEGACY_JWT_ACCEPT_UNTIL", "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            return 0.0
    cutoff = time.time() + _LEGACY_GRACE_SECONDS
    try:
        _append_env(f"LEGACY_JWT_ACCEPT_UNTIL={int(cutoff)}")
    except OSError as e:
        logger.error(f"Could not persist LEGACY_JWT_ACCEPT_UNTIL to .env: {e}")
    os.environ["LEGACY_JWT_ACCEPT_UNTIL"] = str(int(cutoff))
    return cutoff


JWT_SECRET = _setup_jwt_secret()
LEGACY_JWT_ACCEPT_UNTIL = _setup_legacy_cutoff()


def get_master_api_tokens() -> list:
    """Owner master tokens: APP_API_TOKEN from the environment/.env and the
    .local_token file used by the desktop launcher and phone link."""
    tokens = []
    env_tok = os.environ.get("APP_API_TOKEN", "").strip()
    if env_tok:
        tokens.append(env_tok)
    try:
        with open(os.path.join(_PROJECT_ROOT, ".local_token"), "r", encoding="utf-8") as f:
            file_tok = f.read().strip()
        if file_tok and file_tok not in tokens:
            tokens.append(file_tok)
    except OSError:
        pass
    return tokens


def is_valid_master_token(candidate) -> bool:
    import hmac
    if not candidate:
        return False
    candidate = str(candidate).strip()
    return any(hmac.compare_digest(candidate, t) for t in get_master_api_tokens())


def setup_encryption_key():
    global ENCRYPTION_KEY
    if not ENCRYPTION_KEY:
        key = Fernet.generate_key().decode('utf-8')
        _append_env(f"SAAS_ENCRYPTION_KEY={key}")
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
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=90),
        'iat': datetime.datetime.now(datetime.timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def decode_jwt_token(token: str):
    """Returns the payload, or None if invalid/expired.
    Payloads from tokens signed with the old default secret carry "_legacy": True."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        pass
    if time.time() < LEGACY_JWT_ACCEPT_UNTIL:
        try:
            payload = jwt.decode(token, _LEGACY_JWT_SECRET, algorithms=['HS256'])
            payload["_legacy"] = True
            return payload
        except jwt.InvalidTokenError:
            return None
    return None
