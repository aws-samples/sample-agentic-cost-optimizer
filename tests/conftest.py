"""Shared fixtures for test suite."""

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    return Mock()


@pytest.fixture
def mock_journal():
    """Mock journal for test_invoke_function tests to avoid AWS dependencies."""
    with patch("src.agents.main.journal") as mock:
        yield mock


@pytest.fixture
def sample_payload():
    """Sample payload for testing invoke function."""
    return {"prompt": "hello"}


@pytest.fixture
def empty_payload():
    """Empty payload for testing default behavior."""
    return {}


@pytest.fixture
def throttling_error():
    """Create a ThrottlingException ClientError for testing."""
    error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
    return ClientError(error_response, "InvokeModel")


@pytest.fixture
def access_denied_error():
    """Create an AccessDeniedException ClientError for testing."""
    error_response = {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}
    return ClientError(error_response, "InvokeModel")


@pytest.fixture
def unknown_client_error():
    """Create an unknown ClientError for testing."""
    error_response = {"Error": {"Code": "UnknownException", "Message": "Unknown error"}}
    return ClientError(error_response, "InvokeModel")


@pytest.fixture
def no_credentials_error():
    """Create a NoCredentialsError for testing."""
    return NoCredentialsError()
