from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from jose import jwt, JWTError
from passlib.context import CryptContext
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.redis import get_redis_client

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(data: dict, token_type: str, lifetime: timedelta) -> str:
    claims = {**data, "exp": datetime.now(timezone.utc) + lifetime,
              "type": token_type, "jti": str(uuid4())}
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(data: dict) -> str:
    return _create_token(data, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(data: dict) -> str:
    return _create_token(data, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


async def create_login_session(user_id: str) -> str:
    session_id = str(uuid4())
    client = await get_redis_client()
    try:
        await client.setex(f"auth_session:{session_id}",
                           settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, user_id)
    except RedisError as exc:
        raise ServiceUnavailableError("Authentication service temporarily unavailable") from exc
    return session_id


async def revoke_login_session(session_id: str) -> None:
    client = await get_redis_client()
    try:
        await client.delete(f"auth_session:{session_id}")
    except RedisError as exc:
        raise ServiceUnavailableError("Authentication service temporarily unavailable") from exc


async def verify_token(token: str, expected_type: str = "access") -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                             options={"require_exp": True, "require_sub": True})
        if payload.get("type") != expected_type:
            return None
        UUID(payload["sub"])
        UUID(payload["sid"])
    except (JWTError, KeyError, ValueError, TypeError, AttributeError):
        return None
    client = await get_redis_client()
    try:
        owner = await client.get(f"auth_session:{payload['sid']}")
    except RedisError as exc:
        raise ServiceUnavailableError("Authentication service temporarily unavailable") from exc
    return payload if owner == payload["sub"] else None
