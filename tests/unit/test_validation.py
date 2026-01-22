"""Unit tests for validation module."""

import pytest
from mc.utils.validation import validate_case_number


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
