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



class InvalidCredentialsError(AuthenticationError):
    """Raised when user credentials are invalid."""



class UserAlreadyExistsError(DomainException):
    """Raised when trying to register an existing user."""



class InsufficientPermissionsError(DomainException):
    """Raised when user lacks required permissions."""



# Resource exceptions
class ResourceNotFoundError(DomainException):
    """Generic resource not found."""



class ValidationError(DomainException):
    """Raised when business validation fails."""


class LLMServiceError(DomainException):
    """Raised when there is an error interacting with the LLM service."""


class DocumentTooLargeError(DomainException):
    """Raised when a document exceeds the maximum allowed size."""


class ServiceUnavailableError(DomainException):
    """A required infrastructure service is temporarily unavailable."""


class ResourceBusyError(DomainException):
    """Another request is already processing this resource."""


class RetryableLLMServiceError(LLMServiceError):
    """Temporary provider failure eligible for a bounded retry."""
