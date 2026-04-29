"""Regression test for MC-40: mc ldap silently fails when not connected to VPN

Bug discovered: 2026-04-20
Platform: Both
Severity: minor
Source: jira:MC-40

Problem:
When the LDAP server is unreachable (e.g., user is not connected to VPN),
the mc who / mc ldap command exits silently with no output and no error.
The ldapsearch subprocess fails with exit code 255, but the error is caught,
returned as a tuple, and discarded by the CLI wrapper function.

Steps to reproduce:
1. Disconnect from VPN
2. Run mc who david
3. Observe: only an INFO log line appears, then the command exits silently

Expected: An error message indicating the LDAP server is unreachable, with a suggestion to check VPN
Actual:   Silent exit with no output

This test ensures the bug does not regress.
"""
from __future__ import annotations

import subprocess

import pytest
from unittest.mock import patch

from mc.cli.commands.other import ls as ldap_ls
from mc.exceptions import MCError


@pytest.mark.integration
class TestLdapSilentFailRegression:
    """MC-40: mc ldap must raise an error when LDAP server is unreachable."""

    def test_ldap_silent_fail_regression(self) -> None:
        """When ldapsearch fails (e.g., no VPN), ls() must raise MCError, not fail silently."""
        with patch("mc.integrations.ldap.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                255, cmd="ldapsearch", stderr="Can't contact LDAP server (-1)"
            )
            with pytest.raises(MCError):
                ldap_ls("david")

    def test_ldap_unreachable_error_mentions_vpn(self) -> None:
        """Error suggestion should mention checking VPN connectivity."""
        with patch("mc.integrations.ldap.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                255, cmd="ldapsearch", stderr="Can't contact LDAP server (-1)"
            )
            with pytest.raises(MCError) as exc_info:
                ldap_ls("david")
            assert exc_info.value.suggestion is not None
            assert "vpn" in exc_info.value.suggestion.lower()
