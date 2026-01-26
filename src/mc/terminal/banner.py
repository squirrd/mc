"""Welcome banner generation from case metadata.

This module formats Salesforce case metadata into readable welcome banners
displayed when entering container shells.
"""

import textwrap
from typing import Any


def format_field(value: str | None, max_width: int = 80, prefix: str = "") -> str:
    """Format and wrap text field to specified width.

    Args:
        value: Text to format (or None)
        max_width: Maximum line width for wrapping (default: 80)
        prefix: Prefix to add before first line (e.g., "Description: ")

    Returns:
        Formatted text, wrapped to max_width. Returns "N/A" for None values.
        If prefix is provided, it's included even for N/A values.
    """
    # Determine the actual value to use
    if value is None or not value.strip():
        actual_value = "N/A"
    else:
        actual_value = value

    # If no prefix, just wrap normally
    if not prefix:
        return textwrap.fill(actual_value, width=max_width) if actual_value != "N/A" else "N/A"

    # Calculate indent for continuation lines to align with first line
    indent = " " * len(prefix)

    # Wrap text with prefix on first line, indent on subsequent lines
    return textwrap.fill(
        actual_value,
        width=max_width,
        initial_indent=prefix,
        subsequent_indent=indent
    )


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

    # Format fields with wrapping (include prefixes for proper wrapping)
    customer_formatted = format_field(customer_name, prefix="Customer: ")
    description_formatted = format_field(description, prefix="Description: ")
    summary_formatted = format_field(summary)
    next_steps_formatted = format_field(next_steps)

    # Build banner structure
    banner_lines = [
        "=================================================",
        f"Case: {case_number}",
        customer_formatted,
        description_formatted,
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
