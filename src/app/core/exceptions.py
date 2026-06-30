# app/core/exceptions.py
"""
Custom domain exceptions.
These exceptions represent business logic errors, not HTTP errors.
"""

class DomainException(Exception):
    """Base exception for all domain errors."""
    def __init__(self, message: str = "A domain error occurred"):
        self.message = message
        super().__init__(self.message)


# Auth exceptions
class AuthenticationError(DomainException):
    """Raised when authentication fails."""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Raised when user credentials are invalid."""
    pass


class UserAlreadyExistsError(DomainException):
    """Raised when trying to register an existing user."""
    pass


class InsufficientPermissionsError(DomainException):
    """Raised when user lacks required permissions."""
    pass

# Resource exceptions
class ResourceNotFoundError(DomainException):
    """Generic resource not found."""
    pass


class ValidationError(DomainException):
    """Raised when business validation fails."""
    pass