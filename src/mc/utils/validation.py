"""Input validation utilities."""

from __future__ import annotations

import re

_TICKET_ID_PATTERN = re.compile(r"^[A-Z]{1,10}-\d+$")


def validate_ticket_id(ticket_id: str) -> str:
    """
    Validate and normalize a Jira ticket ID.

    Accepts PROJECT-123 format where the project prefix is 1-10 uppercase
    letters followed by a hyphen and one or more digits. Lowercase input
    is normalized to uppercase.

    Args:
        ticket_id: Ticket ID string to validate (e.g. "MC-123", "OCPBUGS-456")

    Returns:
        Normalized (uppercased) ticket ID string.

    Raises:
        ValueError: If the ticket ID does not match the expected format.
    """
    normalized = ticket_id.strip().upper()
    if not _TICKET_ID_PATTERN.match(normalized):
        raise ValueError(
            f"Invalid ticket ID: '{ticket_id}'. "
            f"Expected format: PROJECT-123 (1-10 letter prefix, hyphen, digits). "
            f"Example: MC-42"
        )
    return normalized


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
