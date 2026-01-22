"""Input validation utilities."""

import re


def validate_case_number(case_number: str | int) -> str:
    """
    Validate case number is exactly 8 digits.

    Args:
        case_number: Case number to validate (string or int)

    Returns:
        str: Validated case number (as string)

    Raises:
        ValueError: If format is invalid
    """
    # Normalize input
    case_str = str(case_number).strip()

    # Validate format
    if not re.match(r'^\d{8}$', case_str):
        raise ValueError(
            f"Invalid case number: '{case_number}'. "
            f"Case number must be exactly 8 digits. Example: 12345678"
        )

    return case_str
