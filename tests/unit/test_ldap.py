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
    """Test LDAP search rejects input shorter than 4 characters."""
    success, message = ldap_search("abc")

    assert success is False
    assert "must be between 4 and 15 characters" in message


def test_ldap_search_input_too_long():
    """Test LDAP search rejects input longer than 15 characters."""
    success, message = ldap_search("a" * 16)

    assert success is False
    assert "must be between 4 and 15 characters" in message


def test_ldap_search_command_not_found(mocker):
    """Test LDAP search handles missing ldapsearch command."""
    mocker.patch("subprocess.run", side_effect=FileNotFoundError)

    success, message = ldap_search("testuser")

    assert success is False
    assert "'ldapsearch' command not found" in message


def test_ldap_search_command_failed(mocker):
    """Test LDAP search handles subprocess command failure."""
    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["ldapsearch"],
        stderr="LDAP connection error"
    )
    mocker.patch("subprocess.run", side_effect=error)

    success, message = ldap_search("testuser")

    assert success is False
    assert "Error executing ldapsearch" in message


def test_ldap_search_no_results(mocker):
    """Test LDAP search handles no results case."""
    mock_result = Mock()
    mock_result.stdout = ""
    mock_result.returncode = 0

    mocker.patch("subprocess.run", return_value=mock_result)

    success, message = ldap_search("nonexistent")

    assert success is False
    assert "No results found" in message


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
    """Test search term for exactly 15 characters uses uid-only search."""
    search_term = "a" * 15
    mock_result = Mock()
    mock_result.stdout = f"dn: uid={search_term},dc=redhat,dc=com\nuid: {search_term}\n"
    mock_result.returncode = 0

    mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

    ldap_search(search_term)

    # Verify search term is uid-only (not including cn)
    call_args = mock_subprocess.call_args[0][0]
    # Search term should be "(uid=*aaa...*)"
    assert f"(uid=*{search_term}*)" in call_args


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
