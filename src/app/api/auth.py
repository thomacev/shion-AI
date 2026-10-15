# app/api/auth.py
from fastapi import APIRouter, Depends, status, Body, Request, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user_schema import UserRegisterSchema, UserResponseSchema
from app.core.dependencies import get_db, get_current_user
from app.services import auth_service
from app.core.rate_limit import limiter
from app.core.config import settings
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponseSchema)
@limiter.limit("5/hour")
async def register(
    request: Request, user_data: UserRegisterSchema, db: AsyncSession = Depends(get_db)
):
    return await auth_service.register_user(user_data, db)


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    credentials: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.authenticate_user(
        credentials.username, credentials.password, db
    )

    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=not settings.DEBUG,  # Secure exige HTTPS — en local (DEBUG=true) se relaja
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/auth/refresh",  # el navegador solo la manda a este path — reduce exposición
    )

    return tokens


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Body(default=None, embed=True),
    db: AsyncSession = Depends(get_db),
):
    token = refresh_token or request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    tokens = await auth_service.refresh_access_token(token, db)

    response.set_cookie(
        key="access_token", value=tokens["access_token"], httponly=True,
        secure=not settings.DEBUG, samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return tokens

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout endpoint that blacklists the current token.

    El token se lee de request.state, resuelto por get_current_user —
    funciona igual si vino por header Authorization o por cookie httpOnly,
    sin duplicar la lógica de dónde buscarlo.
    """
    await auth_service.logout(request.state.access_token)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/auth/refresh")
