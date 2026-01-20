"""Placeholder test to verify test infrastructure works.

This test will be removed in Phase 2 when real tests are written.
Its purpose is to verify the test infrastructure is working correctly.
"""

import pytest


def test_fixtures_available(sample_case_number, mock_api_base_url, api_client):
    """Test that fixtures return expected types and values."""
    # Verify session fixtures work
    assert sample_case_number == "12345678"
    assert mock_api_base_url == "https://api.access.redhat.com/support/v1"

    # Verify api_client fixture works
    assert api_client is not None
    assert api_client.access_token == "fake_access_token"
    assert api_client.BASE_URL == "https://api.access.redhat.com/support/v1"


def test_factory_fixture(make_case_response):
    """Test factory fixture can create multiple responses with different parameters."""
    # Call factory multiple times with different parameters
    case1 = make_case_response("11111111", "First case", "Open")
    case2 = make_case_response("22222222", "Second case", "Closed")
    case3 = make_case_response("33333333")  # Use defaults

    # Assert correct structure
    assert case1["case_number"] == "11111111"
    assert case1["summary"] == "First case"
    assert case1["status"] == "Open"
    assert case1["account_number"] == "1234567"

    assert case2["case_number"] == "22222222"
    assert case2["summary"] == "Second case"
    assert case2["status"] == "Closed"

    assert case3["case_number"] == "33333333"
    assert case3["summary"] == "Default summary"
    assert case3["status"] == "Open"
