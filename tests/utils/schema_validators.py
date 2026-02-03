"""Schema validation helpers for unit tests.

These utilities allow validating API responses against Pydantic schemas,
ensuring that responses contain all required fields with correct types.

Example:
    from tests.utils.schema_validators import validate_response_schema
    from app.schemas.worklist import WorklistItem

    response_dict = {"review_id": uuid7(), "status": "PENDING", ...}
    validated = validate_response_schema(response_dict, WorklistItem)
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError


def validate_response_schema(
    response_dict: dict[str, Any], schema_class: type[BaseModel]
) -> BaseModel:
    """Validate a response dictionary against a Pydantic schema.

    Args:
        response_dict: The response data to validate
        schema_class: The Pydantic schema class to validate against

    Returns:
        The validated Pydantic model instance

    Raises:
        AssertionError: If validation fails
    """
    try:
        # Convert UUID objects to strings for JSON compatibility
        sanitized = _sanitize_uuids(response_dict)
        return schema_class(**sanitized)
    except ValidationError as e:
        raise AssertionError(
            f"Response schema validation failed against {schema_class.__name__}:\n"
            f"{str(e)}\n\n"
            f"Response data:\n{response_dict}"
        ) from e


def _sanitize_uuids(data: Any) -> Any:
    """Convert UUID objects to strings for JSON serialization.

    Pydantic can handle UUIDs, but when we're working with mock data
    that might contain UUID objects, we need to convert them properly.
    """
    if isinstance(data, UUID):
        return str(data)
    elif isinstance(data, dict):
        return {k: _sanitize_uuids(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_uuids(item) for item in data]
    return data


def assert_has_fields(response_dict: dict[str, Any], *required_fields: str) -> None:
    """Assert that a response dict contains all required fields.

    Args:
        response_dict: The response data to check
        *required_fields: Field names that must be present

    Raises:
        AssertionError: If any required field is missing
    """
    missing = [f for f in required_fields if f not in response_dict]
    if missing:
        raise AssertionError(
            f"Response missing required fields: {missing}\n"
            f"Available fields: {list(response_dict.keys())}\n"
            f"Response: {response_dict}"
        )


def assert_field_type(response_dict: dict[str, Any], field: str, expected_type: type) -> None:
    """Assert that a field has the expected type.

    Args:
        response_dict: The response data to check
        field: The field name to check
        expected_type: The expected type

    Raises:
        AssertionError: If the field is missing or has wrong type
    """
    if field not in response_dict:
        raise AssertionError(f"Field '{field}' not found in response")

    actual_value = response_dict[field]

    # Handle Optional types
    actual_type = type(actual_value)
    if actual_value is None:
        return  # None is valid for Optional types

    # Check for UUID specifically (common issue)
    if expected_type == UUID or (
        hasattr(expected_type, "__origin__") and UUID in expected_type.__args__
    ):
        if not isinstance(actual_value, (UUID, str)):
            raise AssertionError(
                f"Field '{field}' has wrong type. Expected UUID or str, got {actual_type}"
            )
        return

    # Standard type check
    if not isinstance(actual_value, expected_type):
        # Allow int -> float conversion
        if expected_type is float and isinstance(actual_value, int):
            return
        raise AssertionError(
            f"Field '{field}' has wrong type. Expected {expected_type}, got {actual_type}"
        )


class ResponseValidator:
    """Helper class for validating API responses in tests.

    Example:
        validator = ResponseValidator(WorklistItem)
        validator.assert_valid(response_dict)
        validator.assert_has_field("review_id")
        validator.assert_has_field("decision_reason")
    """

    def __init__(self, schema_class: type[BaseModel]):
        """Initialize the validator with a schema class.

        Args:
            schema_class: The Pydantic schema to validate against
        """
        self.schema_class = schema_class

    def assert_valid(self, response_dict: dict[str, Any]) -> BaseModel:
        """Validate response against the schema.

        Returns:
            The validated model instance

        Raises:
            AssertionError: If validation fails
        """
        return validate_response_schema(response_dict, self.schema_class)

    def assert_has_field(self, response_dict: dict[str, Any], field: str) -> None:
        """Assert that a field exists in the response."""
        assert_has_fields(response_dict, field)

    def assert_has_fields(self, response_dict: dict[str, Any], *fields: str) -> None:
        """Assert that multiple fields exist in the response."""
        assert_has_fields(response_dict, *fields)

    def assert_field_type(
        self, response_dict: dict[str, Any], field: str, expected_type: type
    ) -> None:
        """Assert that a field has the expected type."""
        assert_field_type(response_dict, field, expected_type)

    def validate_and_return(self, response_dict: dict[str, Any]) -> BaseModel:
        """Validate and return the model instance.

        This is a convenience method that combines validation with
        returning the validated model for further assertions.

        Returns:
            The validated Pydantic model instance
        """
        return self.assert_valid(response_dict)
