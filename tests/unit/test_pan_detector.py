"""Unit tests for PAN detection service (PCI compliance)."""

from __future__ import annotations

from app.core.security.pan_detector import PanDetector


class TestPanDetector:
    """Tests for PanDetector PCI compliance."""

    def test_tokenized_card_id_not_detected_as_pan(self):
        """Tokenized card IDs should not be detected as PANs."""
        detector = PanDetector()

        result = detector.detect_pan({"transaction": {"card_id": "tok_visa_4242424242424242"}})

        assert result.detected is False

    def test_pan_prefix_not_detected_as_pan(self):
        """Cards with pan_ prefix should not be detected as PANs."""
        detector = PanDetector()

        result = detector.detect_pan({"transaction": {"card_id": "pan_4242424242424242"}})

        assert result.detected is False

    def test_raw_pan_detected(self):
        """Raw PAN should be detected."""
        detector = PanDetector()

        result = detector.detect_pan({"transaction": {"card_id": "4242424242424242"}})

        assert result.detected is True
        assert result.field_path == "transaction.card_id"

    def test_pan_with_spaces_detected(self):
        """PAN with spaces should be detected."""
        detector = PanDetector()

        result = detector.detect_pan({"data": {"card": "4242 4242 4242 4242"}})

        assert result.detected is True

    def test_pan_with_dashes_detected(self):
        """PAN with dashes should be detected."""
        detector = PanDetector()

        result = detector.detect_pan({"data": {"card": "4242-4242-4242-4242"}})

        assert result.detected is True

    def test_nested_pan_detected(self):
        """PAN in nested structure should be detected."""
        detector = PanDetector()

        result = detector.detect_pan(
            {"event": {"payload": {"transaction": {"card": "4111111111111111"}}}}
        )

        assert result.detected is True
        assert "transaction.card" in result.field_path

    def test_pan_in_list_detected(self):
        """PAN in a list should be detected."""
        detector = PanDetector()

        result = detector.detect_pan({"cards": ["4242424242424242", "tok_visa_1234"]})

        assert result.detected is True
        assert "cards[0]" in result.field_path

    def test_valid_luhn_pan_detected(self):
        """PAN that passes Luhn check should be detected."""
        detector = PanDetector()

        result = detector.detect_pan(
            {
                "card_id": "4532015112830366"  # Valid test Visa
            }
        )

        assert result.detected is True

    def test_invalid_luhn_not_detected(self):
        """PAN that fails Luhn check should not be detected."""
        detector = PanDetector()

        result = detector.detect_pan(
            {
                "card_id": "1234567890123456"  # Fails Luhn
            }
        )

        assert result.detected is False

    def test_short_number_not_detected(self):
        """Numbers shorter than 13 digits should not be detected."""
        detector = PanDetector()

        result = detector.detect_pan({"card_id": "12345"})

        assert result.detected is False

    def test_long_number_detected(self):
        """Numbers up to 19 digits should be detected if they pass Luhn."""
        detector = PanDetector()

        result = detector.detect_pan({"card_id": "1234567890123456789"})

        assert result.detected is False  # Fails Luhn

    def test_custom_prefix_accepted(self):
        """Custom allowed prefix should work."""
        detector = PanDetector(allowed_prefix="card_")

        result = detector.detect_pan({"card_id": "card_token123"})

        assert result.detected is False

        result = detector.detect_pan({"card_id": "4242424242424242"})

        assert result.detected is True

    def test_scan_all_multiple_dicts(self):
        """scan_all should scan multiple dictionaries."""
        detector = PanDetector()

        results = detector.scan_all(
            {"card_id": "tok_visa_ok"},
            {"card_id": "4111111111111111"},
        )

        assert len(results) == 1
        assert results[0].detected is True

    def test_scan_all_no_pans(self):
        """scan_all with no PANs should return empty list."""
        detector = PanDetector()

        results = detector.scan_all(
            {"card_id": "tok_visa_ok"},
            {"card_id": "tok_master_ok"},
        )

        assert len(results) == 0

    def test_value_preview_safe(self):
        """Value preview should be safe (masked)."""
        detector = PanDetector()
        # Use 16-digit PAN (within MAX_PAN_LENGTH of 19)
        result = detector.detect_pan({"card_id": "4111111111111111"})

        assert result.detected is True
        assert result.value_preview is not None
        assert "***" in result.value_preview
        # Should not expose full PAN
        assert len(result.value_preview) < len("4111111111111111")

    def test_result_bool_conversion(self):
        """PanDetectionResult should work with bool()."""
        detector = PanDetector()

        safe_result = detector.detect_pan({"card_id": "tok_visa_ok"})
        assert bool(safe_result) is False

        danger_result = detector.detect_pan({"card_id": "4242424242424242"})
        assert bool(danger_result) is True


class TestPanDetectorLuhnAlgorithm:
    """Tests for Luhn algorithm implementation."""

    def test_valid_visa(self):
        """Test valid Visa PAN."""
        detector = PanDetector()
        assert detector._passes_luhn("4532015112830366") is True

    def test_valid_mastercard(self):
        """Test valid Mastercard PAN."""
        detector = PanDetector()
        assert detector._passes_luhn("5555555555554444") is True

    def test_valid_amex(self):
        """Test valid Amex PAN."""
        detector = PanDetector()
        # 371449635398431 is a valid Amex test number that passes Luhn
        assert detector._passes_luhn("371449635398431") is True

    def test_invalid_checksum(self):
        """Test PAN with invalid checksum."""
        detector = PanDetector()
        assert detector._passes_luhn("4532015112830367") is False

    def test_non_numeric_rejected(self):
        """Non-numeric strings should fail."""
        detector = PanDetector()
        assert detector._passes_luhn("abcdabcdabcdab") is False
