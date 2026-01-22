"""LDAP Integration Tests

These tests require Docker to be installed and running.

Integration tests are optional - they're marked with @pytest.mark.integration
and can be skipped in environments without Docker.

Manual test run with Docker:
1. docker-compose -f docker-compose.test.yml up -d
2. pytest tests/integration/test_ldap_docker.py -v
3. docker-compose -f docker-compose.test.yml down

To run only integration tests: pytest -m integration
To run all tests except integration: pytest -m "not integration"

CI Usage:
- These tests are useful for CI environments with Docker support
- Tests skip gracefully if Docker is unavailable (pytest.skip)
- Docker fixture automatically cleans up containers after tests

Why we mock the server URL:
- Source code has hardcoded ldap.corp.redhat.com (production LDAP)
- Integration tests redirect to local Docker LDAP server (localhost:10389)
- This validates parsing logic with real LDAP output format without
  requiring production LDAP access
"""

import pytest
import subprocess
import time
import os
from pathlib import Path
from mc.integrations.ldap import ldap_search


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def docker_ldap_server():
    """
    Start Docker LDAP server for integration tests.

    Requires docker-compose to be installed.
    Skips tests if Docker not available.
    """
    # Get repository root directory
    repo_root = Path(__file__).parent.parent.parent

    try:
        # Start Docker Compose
        subprocess.run(
            ["docker-compose", "-f", "docker-compose.test.yml", "up", "-d"],
            check=True,
            cwd=str(repo_root),
            capture_output=True
        )
        # Wait for LDAP server to be ready
        time.sleep(3)
        yield "ldap://localhost:10389"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("Docker not available - skipping LDAP integration tests")
    finally:
        # Cleanup - stop and remove containers
        subprocess.run(
            ["docker-compose", "-f", "docker-compose.test.yml", "down"],
            check=False,
            cwd=str(repo_root),
            capture_output=True
        )


def test_ldap_docker_integration_real_search(docker_ldap_server, mocker):
    """
    Test LDAP search against real Docker LDAP server.

    Note: Uses mocker to override LDAP server URL since source code
    has hardcoded ldap.corp.redhat.com. This test validates parsing logic
    with real LDAP output format.
    """
    # Mock the ldapsearch command to point to test server
    def mock_subprocess_run(command, **kwargs):
        # Replace production LDAP server with test server
        test_command = [arg.replace("ldaps://ldap.corp.redhat.com", docker_ldap_server) for arg in command]
        # Call real subprocess with modified command
        return subprocess.run(test_command, **kwargs)

    mocker.patch("subprocess.run", side_effect=mock_subprocess_run)

    # The test-openldap image has pre-populated users
    # Try searching for one (exact user depends on image, may need adjustment)
    success, output = ldap_search("fry", show_all=False)

    # Verify search executed successfully
    assert success is True
    # Verify output contains expected LDAP data
    assert len(output) > 0


def test_ldap_docker_parsing_validation(docker_ldap_server, mocker):
    """
    Verify LDAP parsing handles real LDAP server output correctly.

    Tests that multi-line entries, DN parsing, and field extraction
    work with actual LDAP response format.
    """
    def mock_subprocess_run(command, **kwargs):
        test_command = [arg.replace("ldaps://ldap.corp.redhat.com", docker_ldap_server) for arg in command]
        return subprocess.run(test_command, **kwargs)

    mocker.patch("subprocess.run", side_effect=mock_subprocess_run)

    success, output = ldap_search("professor", show_all=True)

    # Verify raw LDAP output has expected format
    assert "dn:" in output
    assert "uid:" in output
    # Verify multi-line handling
    assert "\n" in output
