"""Error formatting and display utilities for MC CLI.

This module provides functions for formatting exceptions into user-friendly
messages and handling CLI errors with appropriate exit codes and logging.
"""

import sys
import logging
import traceback
from typing import cast

from mc.exceptions import MCError


logger = logging.getLogger(__name__)


def format_error_message(error: Exception) -> str:
    """Format exception for user-friendly display.

    Converts an exception into a formatted message suitable for display
    to end users. If the error has a 'suggestion' attribute (as MCError
    subclasses do), the suggestion is appended on a new line.

    Args:
        error: The exception to format

    Returns:
        Formatted error message string, potentially multi-line
    """
    message = str(error)

    # Add suggestion if available (MCError subclasses have this)
    if hasattr(error, 'suggestion') and error.suggestion:
        message += f"\n{error.suggestion}"

    return message


def handle_cli_error(error: Exception, debug: bool = False) -> int:
    """Handle CLI error with proper logging, output, and exit code.

    This function centralizes error handling for the CLI by:
    1. Logging the error with appropriate level and detail
    2. Printing user-friendly message to stderr
    3. Optionally printing full traceback in debug mode
    4. Returning appropriate exit code

    Args:
        error: The exception to handle
        debug: Whether to enable debug mode (full tracebacks, debug logging)

    Returns:
        Appropriate exit code for the error (from error.exit_code if available, else 1)
    """
    # Log error with full details (exc_info includes traceback in logs)
    logger.error("Error: %s", error, exc_info=debug)

    # Print user-friendly message to stderr
    error_msg = format_error_message(error)
    print(f"Error: {error_msg}", file=sys.stderr)

    # Print full traceback in debug mode
    if debug:
        print("\nTraceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    # Return appropriate exit code
    if hasattr(error, 'exit_code'):
        return cast(int, error.exit_code)

    return 1  # Generic error code
