"""Custom exception hierarchy for MC CLI.

This module defines domain-specific exceptions with appropriate exit codes
following Unix sysexits.h conventions.
"""

import requests


class MCError(Exception):
    """Base exception for all MC CLI errors.

    All custom exceptions in the MC CLI inherit from this base class,
    allowing for consistent error handling and exit code management.

    Attributes:
        exit_code: The exit code to use when this error causes program termination
        suggestion: Optional user-facing suggestion for resolving the error
    """

    exit_code = 1  # Generic error

    def __init__(self, message: str, suggestion: str | None = None) -> None:
        """Initialize MCError.

        Args:
            message: Human-readable error message
            suggestion: Optional suggestion for fixing the error (e.g., "Try: mc auth login")
        """
        super().__init__(message)
        self.suggestion = suggestion


class AuthenticationError(MCError):
    """Authentication failed.

    Raised when authentication operations fail, including:
    - Missing or expired access token
    - Invalid offline token
    - Permission denied errors

    Exit code 65 (EX_DATAERR): Data format error.
    """

    exit_code = 65  # EX_DATAERR from sysexits.h


class APIError(MCError):
    """Base exception for API-related errors.

    Raised for general API failures that don't fit specific subcategories.

    Exit code 69 (EX_UNAVAILABLE): Service unavailable.
    """

    exit_code = 69  # EX_UNAVAILABLE from sysexits.h


class HTTPAPIError(APIError):
    """HTTP error from API.

    Raised when the API returns an HTTP error response.
    Includes helper method to create user-friendly errors from response objects.

    Attributes:
        status_code: HTTP status code from the response
        response: Original requests.Response object
    """

    def __init__(self, message: str, suggestion: str | None = None) -> None:
        """Initialize HTTPAPIError.

        Args:
            message: Human-readable error message
            suggestion: Optional suggestion for fixing the error
        """
        super().__init__(message, suggestion)
        self.status_code: int | None = None
        self.response: requests.Response | None = None

    @classmethod
    def from_response(cls, response: requests.Response) -> 'HTTPAPIError':
        """Create HTTPAPIError from HTTP response with helpful message.

        Maps common HTTP status codes to user-friendly error messages
        with actionable suggestions.

        Args:
            response: The HTTP response object from requests

        Returns:
            HTTPAPIError instance with appropriate message and status code
        """
        status_messages = {
            401: "Authentication failed. Try: mc auth login",
            403: "Access forbidden. Check: Your account has case access permissions",
            404: "Resource not found. Check: Case number is correct",
            429: "Rate limited. Try: Wait a moment and retry",
            500: "API server error. Try: Retry in a few minutes",
            503: "API temporarily unavailable. Try: Retry in a few minutes"
        }

        # Get user-friendly message or default
        suggestion = status_messages.get(response.status_code)
        if suggestion:
            message = f"HTTP {response.status_code} error (endpoint: {response.url})"
            error = cls(message, suggestion)
        else:
            message = f"HTTP {response.status_code} error (endpoint: {response.url})"
            error = cls(message)

        # Store response details
        error.status_code = response.status_code
        error.response = response

        return error


class APITimeoutError(APIError):
    """API request timed out.

    Raised when an API request exceeds the configured timeout period.
    """

    pass


class APIConnectionError(APIError):
    """Failed to connect to API.

    Raised when network connectivity issues prevent reaching the API,
    including DNS failures, refused connections, and network unreachable errors.
    """

    pass


class ValidationError(MCError):
    """Input validation failed.

    Raised when user-provided input fails validation, including:
    - Invalid case numbers
    - Bad command arguments
    - Malformed configuration values

    Exit code 2: Command line syntax error.
    """

    exit_code = 2  # Command line syntax error


class WorkspaceError(MCError):
    """Workspace operation failed.

    Raised when workspace creation or management operations fail,
    typically due to permission issues or filesystem problems.

    Exit code 73 (EX_CANTCREAT): Can't create output file/directory.
    """

    exit_code = 73  # EX_CANTCREAT from sysexits.h


class FileOperationError(MCError):
    """File operation failed.

    Raised when file operations fail, including:
    - Permission denied
    - Disk full
    - File not found
    - I/O errors

    Exit code 74 (EX_IOERR): Input/output error.
    """

    exit_code = 74  # EX_IOERR from sysexits.h
