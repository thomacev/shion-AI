# app/core/security.py
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from app.core.redis import get_redis_client
import hashlib

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def _hash_token(token: str) -> str:
    """Hash the token for secure storage in Redis."""
    return hashlib.sha256(token.encode()).hexdigest()

async def is_token_blacklisted(token: str) -> bool:
    """Check if token is in blacklist (logout)."""
    redis_client = await get_redis_client()
    if redis_client:
        blacklist_key = f"token_blacklist:{_hash_token(token)}"
        return await redis_client.exists(blacklist_key) > 0
    return False


async def verify_token(token: str, expected_type: str = "access") -> dict | None:
    try:
        # Check if token is blacklisted
        if await is_token_blacklisted(token):
            return None
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != expected_type:
            #logger.warning(f"Token type mismatch: expected {expected_type}, got {payload.get('type')}")
            return None
        return payload
    except JWTError as e:
        #logger.warning(f"JWT decode error: {e}")
        return None