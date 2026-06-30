# app/core/exception_handlers.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.core.exceptions import (
    DomainException,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    InsufficientPermissionsError,
    ValidationError,
)

def setup_exception_handlers(app):
    """Register all exception handlers."""
    
    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError):
        #logger.warning(f"Invalid credentials attempt: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": exc.message or "Invalid credentials"}
        )
    
    @app.exception_handler(UserAlreadyExistsError)
    async def user_exists_handler(request: Request, exc: UserAlreadyExistsError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.message or "User already exists"}
        )
    
    @app.exception_handler(InsufficientPermissionsError)
    async def permissions_handler(request: Request, exc: InsufficientPermissionsError):
        #logger.warning(f"Permission denied: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": exc.message or "Insufficient permissions"}
        )
    
    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exc.message}
        )
    
    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException):
        #logger.error(f"Unhandled domain exception: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": exc.message or "Internal server error"}
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        #logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred"}
        )
    
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        #logger.warning(f"Rate limit exceeded: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many requests. Please try again later."}
        )




