from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

from app.core.config import settings


def get_identifier(request: Request) -> str:
    """
    Prioriza el usuario autenticado sobre la IP.
    request.state.user_id lo setea get_current_user() cuando hay un
    usuario válido — si el endpoint no requiere auth (login, register),
    esto va a ser None y cae directo a la IP.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_identifier,
    storage_uri=settings.REDIS_URL if settings.RATE_LIMIT_ENABLED else None,
    enabled=settings.RATE_LIMIT_ENABLED,
    strategy="fixed-window",
)