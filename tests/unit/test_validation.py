"""Unit tests for validation module."""

import pytest
from mc.utils.validation import validate_case_number, validate_ticket_id


def test_validate_case_number_success():
    """Test validation with valid 8-digit case number."""
    result = validate_case_number("12345678")
    assert result == "12345678"


def test_validate_case_number_with_int():
    """Test validation accepts integer input."""
    result = validate_case_number(12345678)
    assert result == "12345678"


def test_validate_case_number_with_whitespace():
    """Test validation strips whitespace."""
    result = validate_case_number("  12345678  ")
    assert result == "12345678"


def test_validate_case_number_too_short():
    """Test validation rejects case number that's too short."""
    with pytest.raises(ValueError) as exc_info:
        validate_case_number("123")

    error_msg = str(exc_info.value)
    assert "Invalid case number: '123'" in error_msg
    assert "must be exactly 8 digits" in error_msg
    assert "Example: 12345678" in error_msg


def test_validate_case_number_too_long():
    """Test validation rejects case number that's too long."""
    with pytest.raises(ValueError) as exc_info:
        validate_case_number("123456789")

    error_msg = str(exc_info.value)
    assert "Invalid case number: '123456789'" in error_msg
    assert "must be exactly 8 digits" in error_msg


def test_validate_case_number_non_numeric():
    """Test validation rejects non-numeric input."""
    with pytest.raises(ValueError) as exc_info:
        validate_case_number("abcd1234")

    error_msg = str(exc_info.value)
    assert "Invalid case number: 'abcd1234'" in error_msg
    assert "must be exactly 8 digits" in error_msg


def test_validate_case_number_mixed_characters():
    """Test validation rejects mixed alphanumeric input."""
    with pytest.raises(ValueError) as exc_info:
        validate_case_number("1234-567")

    error_msg = str(exc_info.value)
    assert "Invalid case number" in error_msg


def test_validate_case_number_empty():
    """Test validation rejects empty string."""
    with pytest.raises(ValueError) as exc_info:
        validate_case_number("")

    error_msg = str(exc_info.value)
    assert "Invalid case number" in error_msg


def test_validate_case_number_with_leading_zeros():
    """Test validation accepts case number with leading zeros."""
    result = validate_case_number("00012345")
    assert result == "00012345"


# --- validate_ticket_id tests ---


class TestValidateTicketIdAcceptsValidFormats:
    """Test that validate_ticket_id accepts valid PROJECT-123 format tickets."""

    @pytest.mark.parametrize(
        "ticket_id,expected",
        [
            ("MC-1", "MC-1"),
            ("MC-123", "MC-123"),
            ("OCPBUGS-12345", "OCPBUGS-12345"),
            ("A-1", "A-1"),  # single-char project prefix
            ("ABCDEFGHIJ-999", "ABCDEFGHIJ-999"),  # 10-char prefix (max)
        ],
    )
    def test_valid_ticket_ids(self, ticket_id: str, expected: str) -> None:
        """Valid PROJECT-NNN ticket IDs are returned unchanged."""
        assert validate_ticket_id(ticket_id) == expected


class TestValidateTicketIdNormalizesCase:
    """Test that validate_ticket_id normalizes lowercase input to uppercase."""

    @pytest.mark.parametrize(
        "ticket_id,expected",
        [
            ("mc-123", "MC-123"),
            ("ocpbugs-456", "OCPBUGS-456"),
            ("Mc-1", "MC-1"),
            ("aBcDeF-99", "ABCDEF-99"),
        ],
    )
    def test_lowercase_normalized_to_uppercase(self, ticket_id: str, expected: str) -> None:
        """Lowercase project prefixes are normalized to uppercase."""
        assert validate_ticket_id(ticket_id) == expected


class TestValidateTicketIdRejectsInvalidFormats:
    """Test that validate_ticket_id rejects malformed ticket IDs."""

    def test_rejects_empty_string(self) -> None:
        """Empty string is rejected."""
        with pytest.raises(ValueError, match="Invalid ticket ID"):
            validate_ticket_id("")

    def test_rejects_digits_only(self) -> None:
        """Digits-only input is rejected (no project prefix)."""
        with pytest.raises(ValueError, match="Invalid ticket ID"):
            validate_ticket_id("12345")

    def test_rejects_no_hyphen(self) -> None:
        """Input without a hyphen separator is rejected."""
        with pytest.raises(ValueError, match="Invalid ticket ID"):
            validate_ticket_id("MC123")

    def test_rejects_missing_number_after_hyphen(self) -> None:
        """Project prefix with hyphen but no number is rejected."""
        with pytest.raises(ValueError, match="Invalid ticket ID"):
            validate_ticket_id("MC-")

    def test_rejects_missing_project_prefix(self) -> None:
        """Hyphen followed by digits but no project prefix is rejected."""
        with pytest.raises(ValueError, match="Invalid ticket ID"):
            validate_ticket_id("-123")

    def test_rejects_prefix_longer_than_10_chars(self) -> None:
        """Project prefix exceeding 10 characters is rejected."""
        with pytest.raises(ValueError, match="Invalid ticket ID"):
            validate_ticket_id("ABCDEFGHIJK-1")  # 11-char prefix

    def test_rejects_non_alpha_prefix(self) -> None:
        """Project prefix containing non-alphabetic characters is rejected."""
        with pytest.raises(ValueError, match="Invalid ticket ID"):
            validate_ticket_id("MC2-123")

    def test_rejects_whitespace_only(self) -> None:
        """Whitespace-only input is rejected."""
        with pytest.raises(ValueError, match="Invalid ticket ID"):
            validate_ticket_id("   ")
