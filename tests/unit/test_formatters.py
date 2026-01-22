"""Unit tests for string formatters."""

import pytest
from mc.utils.formatters import shorten_and_format


@pytest.mark.parametrize("input_str,expected", [
    # Basic alphanumeric
    ("Simple Test", "Simple_Test"),
    ("OneWord", "OneWord"),

    # Long strings get truncated (22 char limit after joining with underscores)
    ("Very Long Account Name That Exceeds Limit", "Very_Long_Account_Name"),
    ("This is an extremely long summary that should be shortened", "This_is_an_extreme_lon"),

    # Hyphens converted to underscores
    ("Test-With-Hyphens", "Test_With_Hyphens"),
    ("Multi-Word-Hyphen-Name", "Multi_Word_Hyphen_Name"),

    # Special characters removed/replaced
    ("Special@Characters#Here!", "Special"),
    ("Test (Parentheses)", "Test_Parent"),
    ("Email@Domain.com", "Email_D"),

    # Edge cases
    ("", ""),
    ("   ", ""),  # Only spaces
    ("___", ""),  # Only underscores after processing
    ("a", "a"),   # Single character

    # Multiple spaces collapsed
    ("Multiple    Spaces", "Multipl_Spaces"),

    # Word length trimming (7 chars per word)
    ("VeryLongWord AnotherLongWord", "VeryLon_Another"),

    # Real-world examples
    ("Red Hat Inc", "Red_Hat_Inc"),
    ("Test Summary", "Test_Summary"),
    ("Customer-Name-With-Dashes", "Custome_Name_With_Dash"),
])
def test_shorten_and_format_variations(input_str, expected):
    """Test string formatting with various inputs."""
    result = shorten_and_format(input_str)
    assert result == expected
