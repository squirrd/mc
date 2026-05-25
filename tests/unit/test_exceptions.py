"""Unit tests for MCError.__str__ — suggestion must appear in string representation.

MC-85: APIConnectionError messages lack VPN hint when callers use str(e).
The suggestion attribute was silently dropped because MCError inherited
Exception.__str__() which only returns the message.
"""

from __future__ import annotations

import pytest

from mc.exceptions import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    ConfigError,
    HTTPAPIError,
    MCError,
    SalesforceAPIError,
    ValidationError,
    WorkspaceError,
)


class TestMCErrorStrIncludesSuggestion:
    """MCError.__str__() must include the suggestion when present."""

    def test_str_with_suggestion_includes_both(self) -> None:
        """str(MCError) returns message + suggestion when suggestion is set."""
        error = MCError("Something went wrong", suggestion="Try: check your configuration")
        result = str(error)
        assert "Something went wrong" in result
        assert "check your configuration" in result

    def test_str_without_suggestion_returns_message_only(self) -> None:
        """str(MCError) returns only the message when no suggestion is set."""
        error = MCError("Plain error message")
        result = str(error)
        assert result == "Plain error message"

    def test_str_with_none_suggestion_returns_message_only(self) -> None:
        """str(MCError) returns only the message when suggestion is None."""
        error = MCError("Error occurred", suggestion=None)
        result = str(error)
        assert result == "Error occurred"

    def test_fstring_interpolation_includes_suggestion(self) -> None:
        """f-string interpolation of MCError must also include suggestion."""
        error = MCError("Connection failed", suggestion="Check: VPN is connected")
        result = f"Warning: {error}"
        assert "VPN" in result
        assert "Connection failed" in result


class TestAPIConnectionErrorStrIncludesSuggestion:
    """APIConnectionError inherits the __str__ fix from MCError."""

    def test_str_includes_vpn_hint(self) -> None:
        """The specific MC-85 scenario: VPN hint must appear in str(e)."""
        error = APIConnectionError(
            "Failed to connect to API for case 04448394",
            "Check: VPN connection and network access",
        )
        result = str(error)
        assert "VPN" in result
        assert "Failed to connect to API" in result


class TestSubclassStrInheritance:
    """All MCError subclasses inherit the __str__ behavior."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            AuthenticationError,
            APIError,
            APITimeoutError,
            APIConnectionError,
            ValidationError,
            WorkspaceError,
            ConfigError,
        ],
    )
    def test_subclass_str_includes_suggestion(
        self, exc_class: type[MCError]
    ) -> None:
        """Each subclass's str() must include suggestion when set."""
        error = exc_class("msg", suggestion="hint text here")
        result = str(error)
        assert "msg" in result
        assert "hint text here" in result

    @pytest.mark.parametrize(
        "exc_class",
        [
            AuthenticationError,
            APIError,
            APITimeoutError,
            APIConnectionError,
            ValidationError,
            WorkspaceError,
            ConfigError,
        ],
    )
    def test_subclass_str_without_suggestion(
        self, exc_class: type[MCError]
    ) -> None:
        """Each subclass's str() returns just message when no suggestion."""
        error = exc_class("only message")
        assert str(error) == "only message"


class TestHTTPAPIErrorStrIncludesSuggestion:
    """HTTPAPIError (custom __init__) also inherits __str__ behavior."""

    def test_str_includes_suggestion(self) -> None:
        error = HTTPAPIError("HTTP 401 error", suggestion="Try: mc auth login")
        result = str(error)
        assert "HTTP 401 error" in result
        assert "mc auth login" in result

    def test_str_without_suggestion(self) -> None:
        error = HTTPAPIError("HTTP 500 error")
        assert str(error) == "HTTP 500 error"


class TestSalesforceAPIErrorStrIncludesSuggestion:
    """SalesforceAPIError (custom __init__) also inherits __str__ behavior."""

    def test_str_includes_suggestion(self) -> None:
        error = SalesforceAPIError("SF error", suggestion="Check: credentials")
        result = str(error)
        assert "SF error" in result
        assert "credentials" in result

    def test_from_status_code_str_includes_suggestion(self) -> None:
        error = SalesforceAPIError.from_status_code(401, "Auth failed")
        result = str(error)
        assert "401" in result
        assert "SF_USERNAME" in result


class TestMCErrorBackwardsCompatibility:
    """Ensure the __str__ override does not break existing behavior."""

    @pytest.mark.backwards_compatibility
    def test_args_tuple_preserved(self) -> None:
        """Exception.args must still contain just the message."""
        error = MCError("the message", suggestion="the hint")
        assert error.args == ("the message",)

    @pytest.mark.backwards_compatibility
    def test_suggestion_attribute_still_accessible(self) -> None:
        """The suggestion attribute must still be accessible directly."""
        error = MCError("msg", suggestion="hint")
        assert error.suggestion == "hint"

    @pytest.mark.backwards_compatibility
    def test_raise_and_catch_message(self) -> None:
        """Catching MCError and converting to string must work."""
        with pytest.raises(MCError) as exc_info:
            raise MCError("boom", suggestion="fix it")
        assert "boom" in str(exc_info.value)
        assert "fix it" in str(exc_info.value)
