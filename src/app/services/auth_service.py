# app/services/auth_service.py
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InsufficientPermissionsError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from app.core.logger import logger
from app.core.security import (
    create_access_token,
    create_login_session,
    create_refresh_token,
    hash_password,
    revoke_login_session,
    verify_password,
    verify_token,
)
from app.models.user import User
from app.schemas.user_schema import UserRegisterSchema, UserResponseSchema


async def register_user(
    user_data: UserRegisterSchema, db: AsyncSession
) -> UserResponseSchema:
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()
    if existing_user:
        logger.warning(
                    "Registration failed: Email already exists",
                    extra={"email": user_data.email}
                )        
        raise UserAlreadyExistsError("User already exists")
    try:
        new_user = User(
            email=user_data.email,
            password=hash_password(user_data.password),
            full_name=user_data.full_name,
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(
                    "User registered successfully",
                    extra={"user_id": str(new_user.id), "email": new_user.email}
                )
        return new_user
    except Exception:
        await db.rollback()
        logger.error(
                    "Unhandled exception during user registration",
                    extra={"email": user_data.email},
                    exc_info=True
                )        
        raise


async def authenticate_user(email: str, password: str, db: AsyncSession) -> dict:
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password):
        logger.warning(
                    "Authentication failed: Invalid credentials",
                    extra={"email": email}
                )        
        raise InvalidCredentialsError("Invalid email or password")

    if not user.is_active:
        logger.warning(
                    "Authentication failed: Inactive account",
                    extra={"user_id": str(user.id), "email": user.email}
                )
        raise InsufficientPermissionsError("User account is inactive")
    session_id = await create_login_session(str(user.id))
    claims = {"sub": str(user.id), "sid": session_id}
    access_token = create_access_token(data=claims)
    refresh_token = create_refresh_token(data=claims)

    logger.info(
            "User authenticated successfully",
            extra={"user_id": str(user.id)}
        )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def refresh_access_token(refresh_token: str, db: AsyncSession) -> dict:
    payload = await verify_token(refresh_token, expected_type="refresh")
    if not payload:
        logger.warning("Token refresh failed: Invalid or expired refresh token")        
        raise InvalidCredentialsError("Invalid or expired refresh token")

    user_id = payload.get("sub")
    user = await db.get(User, UUID(user_id))
    if user is None:
        raise InvalidCredentialsError("Invalid or expired refresh token")
    if not user.is_active:
        raise InsufficientPermissionsError("User account is inactive")
    new_access_token = create_access_token(data={"sub": user_id, "sid": payload["sid"]})
    logger.info(
            "Access token refreshed successfully",
            extra={"user_id": str(user_id)}
        )    
    return {"access_token": new_access_token, "token_type": "bearer"}


async def logout(token: str) -> None:
    payload = await verify_token(token, expected_type="access")
    if not payload:
        raise InvalidCredentialsError("Invalid or expired token")
    await revoke_login_session(payload["sid"])
    logger.info("Login session revoked", user_id=payload["sub"])
