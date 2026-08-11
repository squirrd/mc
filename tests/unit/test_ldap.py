"""Unit tests for LDAP search functionality.

Tests cover:
- Happy path: single/multiple results, show_all flag
- Error scenarios: input validation, command not found, command failed, no results
- Search term logic: length-based search strategy
- Parsing: manager DN extraction from realistic LDAP output

Uses mocker.patch for subprocess mocking to avoid real LDAP calls.
"""

import io
import sys
import pytest
from unittest.mock import Mock
import subprocess
from mc.integrations.ldap import ldap_search, print_ldap_cards
from mc.exceptions import APIConnectionError, MCError, ValidationError


# Happy path tests


def test_ldap_search_successful_single_result(mocker):
    """Test successful LDAP search with single user result."""
    ldap_output = """dn: uid=testuser,ou=people,dc=redhat,dc=com
uid: testuser
cn: Test User
rhatJobTitle: Senior Engineer
manager: uid=manager1,ou=people,dc=redhat,dc=com
l: Raleigh
st: NC
co: USA
"""
    mock_result = Mock()
    mock_result.stdout = ldap_output
    mock_result.returncode = 0

    mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

    success, output = ldap_search("testuser")

    assert success is True
    assert "testuser" in output
    # Verify subprocess.run called with correct command structure
    assert mock_subprocess.called
    call_args = mock_subprocess.call_args
    assert call_args[0][0][0] == "ldapsearch"
    assert "-LLL" in call_args[0][0]
    assert "ldaps://ldap.corp.redhat.com" in call_args[0][0]


def test_ldap_search_multiple_results(mocker):
    """Test LDAP search with multiple user results."""
    ldap_output = """dn: uid=user1,ou=people,dc=redhat,dc=com
uid: user1
cn: User One

dn: uid=user2,ou=people,dc=redhat,dc=com
uid: user2
cn: User Two
"""
    mock_result = Mock()
    mock_result.stdout = ldap_output
    mock_result.returncode = 0

    mocker.patch("subprocess.run", return_value=mock_result)

    success, output = ldap_search("user")

    assert success is True
    assert "user1" in output
    assert "user2" in output


def test_ldap_search_with_show_all_flag(mocker, capsys):
    """Test LDAP search with show_all=True prints raw output."""
    ldap_output = """dn: uid=testuser,ou=people,dc=redhat,dc=com
uid: testuser
cn: Test User
"""
    mock_result = Mock()
    mock_result.stdout = ldap_output
    mock_result.returncode = 0

    mocker.patch("subprocess.run", return_value=mock_result)

    success, output = ldap_search("testuser", show_all=True)

    assert success is True
    # Verify raw output is returned
    assert output == ldap_output
    # Verify raw output was printed (not formatted cards)
    captured = capsys.readouterr()
    assert "dn: uid=testuser" in captured.out


# Error scenarios (with message validation)


def test_ldap_search_input_too_short():
    """Test LDAP search raises ValidationError for input shorter than 4 characters."""
    with pytest.raises(ValidationError, match="must be between 4 and 128 characters"):
        ldap_search("abc")


def test_ldap_search_input_too_long():
    """Test LDAP search raises ValidationError for input longer than 128 characters."""
    with pytest.raises(ValidationError, match="must be between 4 and 128 characters"):
        ldap_search("a" * 129)


def test_ldap_search_command_not_found(mocker):
    """Test LDAP search raises MCError when ldapsearch command is missing."""
    mocker.patch("subprocess.run", side_effect=FileNotFoundError)

    with pytest.raises(MCError, match="ldapsearch command not found"):
        ldap_search("testuser")


def test_ldap_search_command_failed(mocker):
    """Test LDAP search raises MCError on subprocess command failure."""
    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["ldapsearch"],
        stderr="LDAP connection error"
    )
    mocker.patch("subprocess.run", side_effect=error)

    with pytest.raises(MCError, match="LDAP search failed"):
        ldap_search("testuser")


def test_ldap_search_no_results(mocker):
    """Test LDAP search raises MCError when no results are found."""
    mock_result = Mock()
    mock_result.stdout = ""
    mock_result.returncode = 0

    mocker.patch("subprocess.run", return_value=mock_result)

    with pytest.raises(MCError, match="No LDAP results found"):
        ldap_search("nonexistent")


def test_ldap_search_unreachable_suggests_vpn(mocker):
    """Test that LDAP connection failure suggests checking VPN."""
    error = subprocess.CalledProcessError(
        returncode=255,
        cmd=["ldapsearch"],
        stderr="Can't contact LDAP server (-1)"
    )
    mocker.patch("subprocess.run", side_effect=error)

    with pytest.raises(APIConnectionError) as exc_info:
        ldap_search("testuser")

    assert exc_info.value.suggestion is not None
    assert "vpn" in exc_info.value.suggestion.lower()


# Search term logic tests


def test_ldap_search_term_length_4_chars(mocker):
    """Test search term for exactly 4 characters uses uid-only search."""
    mock_result = Mock()
    mock_result.stdout = "dn: uid=abcd,dc=redhat,dc=com\nuid: abcd\n"
    mock_result.returncode = 0

    mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

    ldap_search("abcd")

    # Verify search term is uid-only (not including cn)
    call_args = mock_subprocess.call_args[0][0]
    # Search term should be "(uid=*abcd*)"
    assert "(uid=*abcd*)" in call_args


def test_ldap_search_term_length_5_to_14_chars(mocker):
    """Test search term for 5-14 characters uses uid OR cn search."""
    mock_result = Mock()
    mock_result.stdout = "dn: uid=testuser,dc=redhat,dc=com\nuid: testuser\n"
    mock_result.returncode = 0

    mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

    ldap_search("testuser")  # 8 chars

    # Verify search term includes both uid and cn
    call_args = mock_subprocess.call_args[0][0]
    # Search term should be "(|(uid=*testuser*)(cn=*testuser*))"
    assert "(|(uid=*testuser*)(cn=*testuser*))" in call_args


def test_ldap_search_term_length_15_chars(mocker):
    """Test search term for exactly 15 characters uses uid+cn search (MC-178 fix)."""
    search_term = "a" * 15
    mock_result = Mock()
    mock_result.stdout = f"dn: uid={search_term},dc=redhat,dc=com\nuid: {search_term}\n"
    mock_result.returncode = 0

    mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

    ldap_search(search_term)

    # After MC-178 fix: 15 chars falls in 5-128 range, so uses uid+cn filter
    call_args = mock_subprocess.call_args[0][0]
    assert f"(|(uid=*{search_term}*)(cn=*{search_term}*))" in call_args


# MC-178 regression: long names must not be rejected


@pytest.mark.backwards_compatibility
def test_ldap_search_long_name_passes_validation(mocker):
    """MC-178: ldap_search must accept names longer than 15 chars (e.g. 'Arjjun Somasundaran').

    The old upper bound of 15 rejected legitimate full names. The new upper bound
    is 128 to accommodate full names, email local parts, etc.
    """
    long_name = "ArjjunSomasundar"  # 16 chars -- was rejected by old limit of 15
    mock_result = Mock()
    mock_result.stdout = (
        f"dn: uid={long_name},ou=people,dc=redhat,dc=com\nuid: {long_name}\n"
        f"cn: Arjjun Somasundaran\n"
    )
    mock_result.returncode = 0

    mocker.patch("subprocess.run", return_value=mock_result)

    # This must NOT raise ValidationError -- 16 chars is within the valid range (4-128)
    success, output = ldap_search(long_name)
    assert success is True
    assert long_name in output


# Parsing tests (realistic output)


def test_print_ldap_cards_manager_parsing(capsys):
    """Test manager DN parsing extracts UID correctly."""
    ldap_output = """dn: uid=employee,ou=people,dc=redhat,dc=com
uid: employee
cn: Test Employee
manager: uid=manager1,ou=people,dc=redhat,dc=com
rhatJobTitle: Engineer
"""

    print_ldap_cards(ldap_output)

    captured = capsys.readouterr()
    # Verify manager UID extracted from DN format
    assert "Manager" in captured.out
    assert "manager1" in captured.out
    # Verify full DN is NOT shown
    assert "ou=people,dc=redhat,dc=com" not in captured.out
