"""Welcome banner generation from case metadata.

This module formats Salesforce case metadata into readable welcome banners
displayed when entering container shells.
"""

import textwrap
from typing import Any


def format_field(value: str | None, max_width: int = 80) -> str:
    """Format and wrap text field to specified width.

    Args:
        value: Text to format (or None)
        max_width: Maximum line width for wrapping (default: 80)

    Returns:
        Formatted text, wrapped to max_width. Returns "N/A" for None values.
    """
    if value is None:
        return "N/A"
    
    # Handle empty strings
    if not value.strip():
        return "N/A"
    
    # Wrap text to specified width
    return textwrap.fill(value, width=max_width)


def generate_banner(case_metadata: dict[str, Any]) -> str:
    """Generate welcome banner from case metadata.

    Args:
        case_metadata: Case metadata dictionary with fields:
            - case_number: str
            - customer_name: str (optional)
            - description: str (optional)
            - summary: str (optional)
            - next_steps: str (optional)
            Note: 'comments' field is NOT displayed in banner per CONTEXT.md

    Returns:
        Formatted banner string with newlines
    """
    # Extract metadata with None handling
    case_number = case_metadata.get("case_number", "Unknown")
    customer_name = case_metadata.get("customer_name")
    description = case_metadata.get("description")
    summary = case_metadata.get("summary")
    next_steps = case_metadata.get("next_steps")
    
    # Format fields with wrapping
    customer_formatted = format_field(customer_name)
    description_formatted = format_field(description)
    summary_formatted = format_field(summary)
    next_steps_formatted = format_field(next_steps)
    
    # Build banner structure
    banner_lines = [
        "=================================================",
        f"Case: {case_number}",
        f"Customer: {customer_formatted}",
        f"Description: {description_formatted}",
    ]
    
    # Add summary section if available
    if summary and summary.strip():
        banner_lines.extend([
            "",
            "Summary:",
            summary_formatted,
        ])
    
    # Add next steps section if available
    if next_steps and next_steps.strip():
        banner_lines.extend([
            "",
            "Next Steps:",
            next_steps_formatted,
        ])
    
    banner_lines.append("=================================================")
    
    return "\n".join(banner_lines)
