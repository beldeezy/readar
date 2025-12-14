from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
# from passlib.context import CryptContext  # disabled for dev
from app.core.config import settings

# DEV-ONLY: dummy password context that avoids bcrypt entirely.
class DummyPasswordContext:
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        # Always "succeeds" in dev. Replace with real bcrypt in prod.
        return True

    def hash(self, password: str) -> str:
        # Return a stable fake hash.
        return "fake-dev-hash"

pwd_context = DummyPasswordContext()

# NEW: helper to enforce bcrypt 72-byte limit safely
def _truncate_password(password: str) -> str:
    """
    Ensure the password is at most 72 bytes when UTF-8 encoded.
    Bcrypt ignores everything past 72 bytes, and passlib will raise
    if we don't truncate.
    """
    if password is None:
        return ""

    if not isinstance(password, str):
        password = str(password)

    raw = password.encode("utf-8")
    if len(raw) <= 72:
        return password

    truncated = raw[:72]
    # Drop any partial multibyte char at the end
    return truncated.decode("utf-8", errors="ignore")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    safe_plain = _truncate_password(plain_password)
    return pwd_context.verify(safe_plain, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    safe_password = _truncate_password(password)
    return pwd_context.hash(safe_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

