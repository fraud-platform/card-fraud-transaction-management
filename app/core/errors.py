"""
Domain-specific exceptions for the Transaction Management API.

These exceptions represent business logic violations and are mapped
to appropriate HTTP status codes in the API layer.
"""

from typing import Any


class TransactionManagementError(Exception):
    """Base exception for all transaction management domain errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(TransactionManagementError):
    """
    Raised when input data fails validation.

    Examples:
    - Invalid card_id format
    - Required field missing
    - Data type mismatch
    - Business rule validation failure

    HTTP Status: 400 Bad Request
    """

    pass


class NotFoundError(TransactionManagementError):
    """
    Raised when a requested resource does not exist.

    Examples:
    - Transaction ID not found
    - Rule match not found

    HTTP Status: 404 Not Found
    """

    pass


class UnauthorizedError(TransactionManagementError):
    """
    Raised when user lacks valid authentication.

    Examples:
    - Missing JWT token
    - Invalid JWT token
    - Token expired

    HTTP Status: 401 Unauthorized
    """

    pass


class ForbiddenError(TransactionManagementError):
    """
    Raised when user is authenticated but not allowed to perform action.

    Examples:
    - Insufficient permissions/roles
    - Accessing resource outside user's scope

    HTTP Status: 403 Forbidden
    """

    pass


class ConflictError(TransactionManagementError):
    """
    Raised when operation conflicts with current state.

    Examples:
    - Duplicate transaction_id
    - Version conflict
    - Status transition not allowed
    - Unique constraint violation

    HTTP Status: 409 Conflict
    """

    pass


class PCIComplianceError(TransactionManagementError):
    """
    Raised when PCI compliance rules are violated.

    Examples:
    - PAN-like pattern detected in card_id
    - Raw PAN detected in payload

    HTTP Status: 422 Unprocessable Entity
    """

    pass


ERROR_STATUS_MAP = {
    ValidationError: 400,
    NotFoundError: 404,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    ConflictError: 409,
    PCIComplianceError: 422,
}


def get_status_code(error: Exception) -> int:
    """
    Get the HTTP status code for a given exception.

    Args:
        error: The exception instance

    Returns:
        HTTP status code (defaults to 500 for unknown errors)
    """
    return ERROR_STATUS_MAP.get(type(error), 500)
