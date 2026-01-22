"""Logging configuration and utilities for the MC CLI application."""

import json
import logging
import re
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Custom logging formatter that outputs JSON with structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as JSON.

        Args:
            record: LogRecord instance to format

        Returns:
            JSON string with timestamp, level, module, message, and exception
        """
        log_obj = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'module': record.name,
            'message': record.getMessage(),
        }

        # Include exception info if present
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive data from log messages."""

    # Patterns for sensitive data
    PATTERNS = [
        (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE), r'\1<REDACTED>'),
        (re.compile(r'(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)', re.IGNORECASE), r'\1<REDACTED>'),
        (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE), r'\1<REDACTED>'),
    ]

    @staticmethod
    def redact_token(token: str) -> str:
        """
        Show last 4 chars if token is >20 chars, otherwise fully redact.

        Args:
            token: String token to redact

        Returns:
            Redacted version showing only last 4 characters if long enough
        """
        if len(token) > 20:
            return f"...{token[-4:]}"
        return "<REDACTED>"

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Redact sensitive data from log record message.

        Args:
            record: LogRecord instance to filter

        Returns:
            True to allow the record to be logged
        """
        message = record.getMessage()

        # Apply regex patterns
        for pattern, replacement in self.PATTERNS:
            message = pattern.sub(replacement, message)

        # Update the record's message
        record.msg = message
        record.args = ()

        return True


def setup_logging(json_logs: bool = False, debug: bool = False, debug_file: str | None = None) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        json_logs: If True, output JSON format; otherwise human-readable text
        debug: If True, set level to DEBUG; otherwise INFO
        debug_file: Optional path to file for debug output

    Returns:
        Configured logger instance for 'mc' package
    """
    # Get or create root logger for application
    logger = logging.getLogger('mc')
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    if json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        # Human-readable format with timestamp, level, module, and message
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

    # Add sensitive data filter to handler
    handler.addFilter(SensitiveDataFilter())

    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    # Optionally configure file output for debug
    if debug and debug_file:
        file_handler = logging.FileHandler(debug_file)
        file_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
            )
        )
        file_handler.addFilter(SensitiveDataFilter())
        logger.addHandler(file_handler)

    return logger
