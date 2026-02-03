"""PCI Compliance — PAN Detection Service.

Provides explicit PAN (Primary Account Number) pattern detection
for PCI compliance. This is in addition to database constraints.

Patterns detected:
- 13-19 digit numbers matching Luhn algorithm
- Optional spaces or dashes for formatting
- Raw PANs (not tokenized with tok_ prefix)

Usage:
    detector = PanDetector()
    if detector.detect_pan(data):
        raise PanDetectedError("PAN detected in payload")
"""

from __future__ import annotations

import re
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

PAN_PATTERN = re.compile(r"^(?:[0-9]{4}[-\s]?){3}[0-9]{3,4}$")

MIN_PAN_LENGTH = 13
MAX_PAN_LENGTH = 19


@dataclass
class PanDetectionResult:
    """Result of PAN detection scan."""

    detected: bool
    field_path: str | None = None
    value_preview: str | None = None

    def __bool__(self) -> bool:
        return self.detected


class PanDetector:
    """Detects potential PAN patterns in data structures.

    This service provides explicit PCI compliance by detecting
    raw PAN patterns in addition to database constraints.

    Attributes:
        allowed_prefix: Prefix that indicates a tokenized card ID.
            Defaults to "tok_".
    """

    def __init__(self, allowed_prefix: str = "tok_"):
        self.allowed_prefix = allowed_prefix

    def detect_pan(self, data: dict[str, Any]) -> PanDetectionResult:
        """Scan data for potential PAN patterns.

        Args:
            data: Dictionary to scan for PAN patterns.

        Returns:
            PanDetectionResult with detection status and location.
        """
        for field_path, value in self._flatten_dict(data):
            if self._is_pan_value(value):
                return PanDetectionResult(
                    detected=True,
                    field_path=field_path,
                    value_preview=self._preview_value(value),
                )

        return PanDetectionResult(detected=False)

    def scan_all(self, *data_dicts: dict[str, Any]) -> list[PanDetectionResult]:
        """Scan multiple data structures for PAN patterns.

        Args:
            *data_dicts: Variable number of dictionaries to scan.

        Returns:
            List of detection results (empty if no PANs found).
        """
        results: list[PanDetectionResult] = []

        for data in data_dicts:
            for field_path, value in self._flatten_dict(data):
                if self._is_pan_value(value):
                    results.append(
                        PanDetectionResult(
                            detected=True,
                            field_path=field_path,
                            value_preview=self._preview_value(value),
                        )
                    )

        return results

    def _flatten_dict(self, data: dict[str, Any]) -> Generator[tuple[str, Any]]:
        """Recursively flatten a dictionary.

        Yields:
            Tuples of (dot-notation path, value).
        """
        yield from self._flatten_recursive(data, "")

    def _flatten_recursive(self, data: Any, prefix: str) -> Generator[tuple[str, Any]]:
        """Recursively flatten with prefix tracking."""
        if isinstance(data, dict):
            for key, value in data.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                yield from self._flatten_recursive(value, new_prefix)
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                new_prefix = f"{prefix}[{idx}]"
                yield from self._flatten_recursive(item, new_prefix)
        else:
            yield (prefix, data)

    def _is_pan_value(self, value: Any) -> bool:
        """Check if a value looks like a PAN.

        A value is considered a PAN if:
        1. It's a string
        2. It doesn't start with allowed_prefix (like "tok_")
        3. It matches the PAN pattern (13-19 digits with formatting)
        4. It passes the Luhn check
        """
        if not isinstance(value, str):
            return False

        if value.startswith(self.allowed_prefix):
            return False

        cleaned = value.replace(" ", "").replace("-", "")

        if not cleaned.isdigit():
            return False

        if not (MIN_PAN_LENGTH <= len(cleaned) <= MAX_PAN_LENGTH):
            return False

        return self._passes_luhn(cleaned)

    def _passes_luhn(self, number: str) -> bool:
        """Validate using Luhn algorithm.

        The Luhn algorithm is used to validate credit card numbers.
        """
        try:
            digits = [int(d) for d in number]
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]

            checksum = sum(odd_digits)
            for d in even_digits:
                doubled = d * 2
                checksum += sum(int(x) for x in str(doubled))

            return checksum % 10 == 0
        except (ValueError, OverflowError):
            return False

    def _preview_value(self, value: str) -> str:
        """Create a safe preview of a value for error messages."""
        if len(value) <= 8:
            return "***"
        return value[:4] + "***" + value[-4:]


def create_pan_detector() -> PanDetector:
    """Factory function to create a PanDetector instance."""
    return PanDetector()
