# app/api/auth.py
from fastapi import APIRouter, Depends, status, Body, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user_schema import UserRegisterSchema, UserResponseSchema
from app.core.dependencies import get_db, get_current_user, oauth2_scheme
from app.services import auth_service

router = APIRouter(tags=["auth"])

@router.post("/register", status_code=status.HTTP_201_CREATED,response_model=UserResponseSchema)
async def register(request: Request,user_data: UserRegisterSchema, db: AsyncSession = Depends(get_db)):
    return await auth_service.register_user(user_data, db)

@router.post("/login")
async def login(request: Request,credentials: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    return await auth_service.authenticate_user(credentials.username, credentials.password, db)

@router.post("/refresh")
async def refresh(refresh_token: str = Body(..., embed=True)):
    return await auth_service.refresh_access_token(refresh_token)

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user=Depends(get_current_user),
    token: str = Depends(oauth2_scheme)
):
    """
    Logout endpoint that blacklists the current token.
    
    The token will be added to a blacklist in Redis and rejected for future use
    until it naturally expires.
    """
    await auth_service.logout(token)

