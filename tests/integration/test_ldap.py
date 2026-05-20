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


@pytest.mark.integration
class TestMC14LdapEmailSearchEmailStripAcceptance:
    """Acceptance test for MC-14: email-strip slice

    Feature added: 2026-05-20
    Scope: full-stack
    Source: jira:MC-14
    Slice: email-strip

    Feature description:
    Accept email addresses (user@redhat.com) as LDAP search input by stripping
    the @redhat.com domain suffix and using the local part (kerberos ID) as the
    actual search term passed to LDAP.

    Acceptance criterion:
    When input ends with @redhat.com, strip the domain suffix and use the local
    part as the search term. ldap_search("user@redhat.com") produces the same
    LDAP filter as ldap_search("user").

    This test covers:
    1. Email input is normalized to the kerberos ID before LDAP filter construction
    2. The LDAP filter produced for email input matches the filter for the bare uid

    Expected: ldap_search("jsmith@redhat.com") invokes ldapsearch with the same
    filter string as ldap_search("jsmith").
    """

    def test_mc_14_ldap_email_search_email_strip_acceptance(self) -> None:
        """ldap_search('jsmith@redhat.com') must produce the same LDAP filter as ldap_search('jsmith')."""
        from mc.integrations.ldap import ldap_search

        captured_filters: list[str] = []

        def capture_subprocess_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            """Capture the LDAP filter from the ldapsearch command args."""
            # The filter is the last argument in the ldapsearch command
            captured_filters.append(command[-1])
            return subprocess.CompletedProcess(
                args=command, returncode=0,
                stdout="dn: uid=jsmith,ou=users,dc=redhat,dc=com\nuid: jsmith\ncn: John Smith\n",
                stderr="",
            )

        # Call with bare uid
        with patch("mc.integrations.ldap.subprocess.run", side_effect=capture_subprocess_run):
            ldap_search("jsmith")

        # Call with email
        with patch("mc.integrations.ldap.subprocess.run", side_effect=capture_subprocess_run):
            ldap_search("jsmith@redhat.com")

        assert len(captured_filters) == 2, f"Expected 2 captured filters, got {len(captured_filters)}"
        bare_filter = captured_filters[0]
        email_filter = captured_filters[1]
        assert bare_filter == email_filter, (
            f"LDAP filter mismatch: ldap_search('jsmith') produced {bare_filter!r} "
            f"but ldap_search('jsmith@redhat.com') produced {email_filter!r}. "
            f"Email domain was not stripped."
        )


@pytest.mark.integration
class TestMC14LdapEmailSearchCliArgUpdateAcceptance:
    """Acceptance test for MC-14: cli-arg-update slice

    Feature added: 2026-05-20
    Scope: full-stack
    Source: jira:MC-14
    Slice: cli-arg-update

    Feature description:
    Update CLI argument help text for the ldap/who command to indicate that
    email addresses (user@redhat.com) are accepted as input, not just UIDs.

    Acceptance criterion:
    mc ldap --help shows that email is accepted as input. The help text for the
    uid argument mentions email or @redhat.com.

    This test covers:
    1. The CLI help text for the ldap subcommand mentions email acceptance
    2. Running mc ldap --help outputs text that includes a reference to email

    Expected: The help text for 'mc ldap' mentions that email (e.g. user@redhat.com)
    is accepted as input.
    """

    def test_mc_14_ldap_email_search_cli_arg_update_acceptance(self) -> None:
        """mc ldap --help must indicate that email addresses are accepted."""
        result = subprocess.run(
            ["uv", "run", "mc", "ldap", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        help_output = result.stdout
        assert help_output, "mc ldap --help produced no output"

        help_lower = help_output.lower()
        assert "email" in help_lower or "@redhat.com" in help_lower, (
            f"LDAP help text does not mention email acceptance. "
            f"Current help text:\n{help_output}"
        )
