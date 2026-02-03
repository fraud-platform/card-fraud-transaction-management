"""Unit tests for errors module."""

from app.core.errors import (
    ERROR_STATUS_MAP,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PCIComplianceError,
    TransactionManagementError,
    UnauthorizedError,
    ValidationError,
    get_status_code,
)


class TestTransactionManagementError:
    """Test base exception class."""

    def test_base_exception_creation(self):
        """Test creating base exception with message."""
        error = TransactionManagementError("Test error message")
        assert error.message == "Test error message"
        assert error.details == {}
        assert str(error) == "Test error message"

    def test_base_exception_with_details(self):
        """Test creating base exception with details."""
        error = TransactionManagementError("Test error", details={"key": "value", "extra": 123})
        assert error.message == "Test error"
        assert error.details == {"key": "value", "extra": 123}


class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_creation(self):
        """Test creating ValidationError."""
        error = ValidationError("Invalid input")
        assert isinstance(error, TransactionManagementError)
        assert error.message == "Invalid input"

    def test_validation_error_with_details(self):
        """Test ValidationError with field details."""
        error = ValidationError(
            "Field validation failed", details={"field": "card_id", "reason": "Invalid format"}
        )
        assert error.details["field"] == "card_id"


class TestNotFoundError:
    """Test NotFoundError exception."""

    def test_not_found_error_creation(self):
        """Test creating NotFoundError."""
        error = NotFoundError("Transaction not found")
        assert isinstance(error, TransactionManagementError)

    def test_not_found_error_with_id(self):
        """Test NotFoundError with resource ID."""
        error = NotFoundError("Transaction not found", details={"transaction_id": "txn_123"})
        assert error.details["transaction_id"] == "txn_123"


class TestUnauthorizedError:
    """Test UnauthorizedError exception."""

    def test_unauthorized_error_creation(self):
        """Test creating UnauthorizedError."""
        error = UnauthorizedError("Invalid token")
        assert isinstance(error, TransactionManagementError)
        assert "Invalid token" in error.message

    def test_unauthorized_error_with_www_authenticate(self):
        """Test UnauthorizedError with WWW-Authenticate header hint."""
        error = UnauthorizedError("Token expired", details={"WWW-Authenticate": "Bearer"})
        assert error.details.get("WWW-Authenticate") == "Bearer"


class TestForbiddenError:
    """Test ForbiddenError exception."""

    def test_forbidden_error_creation(self):
        """Test creating ForbiddenError."""
        error = ForbiddenError("Insufficient permissions")
        assert isinstance(error, TransactionManagementError)

    def test_forbidden_error_with_roles(self):
        """Test ForbiddenError with role information."""
        error = ForbiddenError(
            "Admin role required", details={"required_role": "admin", "user_roles": ["analyst"]}
        )
        assert error.details["required_role"] == "admin"


class TestConflictError:
    """Test ConflictError exception."""

    def test_conflict_error_creation(self):
        """Test creating ConflictError."""
        error = ConflictError("Duplicate transaction")
        assert isinstance(error, TransactionManagementError)

    def test_conflict_error_with_details(self):
        """Test ConflictError with conflict details."""
        error = ConflictError("Transaction already exists", details={"transaction_id": "txn_456"})
        assert error.details["transaction_id"] == "txn_456"


class TestPCIComplianceError:
    """Test PCIComplianceError exception."""

    def test_pci_error_creation(self):
        """Test creating PCIComplianceError."""
        error = PCIComplianceError("PAN detected in payload")
        assert isinstance(error, TransactionManagementError)

    def test_pci_error_with_field(self):
        """Test PCIComplianceError with field information."""
        error = PCIComplianceError(
            "PAN pattern detected", details={"field": "card_id", "value_preview": "4111****"}
        )
        assert error.details["field"] == "card_id"


class TestErrorStatusMap:
    """Test error status code mapping."""

    def test_validation_error_maps_to_400(self):
        """Test ValidationError maps to 400."""
        assert ERROR_STATUS_MAP[ValidationError] == 400

    def test_not_found_error_maps_to_404(self):
        """Test NotFoundError maps to 404."""
        assert ERROR_STATUS_MAP[NotFoundError] == 404

    def test_unauthorized_error_maps_to_401(self):
        """Test UnauthorizedError maps to 401."""
        assert ERROR_STATUS_MAP[UnauthorizedError] == 401

    def test_forbidden_error_maps_to_403(self):
        """Test ForbiddenError maps to 403."""
        assert ERROR_STATUS_MAP[ForbiddenError] == 403

    def test_conflict_error_maps_to_409(self):
        """Test ConflictError maps to 409."""
        assert ERROR_STATUS_MAP[ConflictError] == 409

    def test_pci_error_maps_to_422(self):
        """Test PCIComplianceError maps to 422."""
        assert ERROR_STATUS_MAP[PCIComplianceError] == 422


class TestGetStatusCode:
    """Test get_status_code function."""

    def test_known_error_returns_correct_code(self):
        """Test get_status_code returns correct code for known errors."""
        error = ValidationError("test")
        assert get_status_code(error) == 400

    def test_unknown_error_returns_500(self):
        """Test get_status_code returns 500 for unknown errors."""
        error = ValueError("Unknown error")
        assert get_status_code(error) == 500

    def test_base_error_returns_500(self):
        """Test get_status_code returns 500 for base exception."""
        error = TransactionManagementError("test")
        assert get_status_code(error) == 500
