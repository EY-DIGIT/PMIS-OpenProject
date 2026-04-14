"""
Security utilities for JWT and password handling.
"""
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from uuid import uuid4
from passlib.context import CryptContext
from jose import JWTError, jwt, ExpiredSignatureError
from .config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# def _prehash_password(password: str) -> str:
#     """
#     Pre-hash password with SHA256 to safely handle passwords > 72 bytes
#     (argon2's hard limit). Result is always 44 chars, well within limit.
#     """
#     digest = hashlib.sha256(password.encode("utf-8")).digest()
#     return base64.b64encode(digest).decode("utf-8")

def hash_password(password: str) -> str:
    """
    Hash a password using argon2.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token
        expires_delta: Optional token expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT access token.

    Args:
        token: JWT token to decode

    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def verify_access_token(token: str) -> Tuple[bool, bool, Optional[Dict[str, Any]]]:
    """
    Verify access token and indicate whether it's valid or expired.

    Returns a tuple: (is_valid, is_expired, payload_or_none)
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return True, False, payload
    except ExpiredSignatureError:
        # Token is expired but otherwise valid
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False}
            )
            return False, True, payload
        except JWTError:
            return False, True, None
    except JWTError:
        return False, False, None


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, str, datetime]:
    """
    Create a JWT refresh token with a `jti` claim.

    Returns: (token, jti, expires_at)
    """
    to_encode = data.copy()
    jti = uuid4().hex

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": jti
    })

    encoded = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded, jti, expire


def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a refresh token. Returns payload if valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None
