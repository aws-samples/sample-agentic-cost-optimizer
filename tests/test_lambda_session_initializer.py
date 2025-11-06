"""Unit tests for session_initializer Lambda function."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock aws_lambda_powertools before importing the handler
sys.modules["aws_lambda_powertools"] = MagicMock()

# Add infra/lambda to path
lambda_path = Path(__file__).parent.parent / "infra" / "lambda"
sys.path.insert(0, str(lambda_path))


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.function_name = "session_initializer"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:session_initializer"
    return context


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables."""
    monkeypatch.setenv("JOURNAL_TABLE_NAME", "test-table")
    monkeypatch.setenv("TTL_DAYS", "90")
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "session-initializer")


def test_handler_success(mock_env, lambda_context):
    """Test successful session initialization."""
    from session_initializer import handler

    event = {"session_id": "test-session-123"}

    with patch("session_initializer.record_event") as mock_record:
        result = handler(event, lambda_context)

        assert result["statusCode"] == 200
        assert result["session_id"] == "test-session-123"
        mock_record.assert_called_once()


def test_handler_missing_session_id(mock_env, lambda_context):
    """Test handler raises error when session_id is missing."""
    from session_initializer import handler

    event = {}

    with patch("session_initializer.record_event"):
        with pytest.raises(ValueError, match="session_id is required"):
            handler(event, lambda_context)


def test_handler_missing_table_name(lambda_context, monkeypatch):
    """Test handler raises error when JOURNAL_TABLE_NAME is missing."""
    monkeypatch.delenv("JOURNAL_TABLE_NAME", raising=False)
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "session-initializer")

    from session_initializer import handler

    event = {"session_id": "test-session-123"}

    with patch("session_initializer.record_event"):
        with pytest.raises(ValueError, match="JOURNAL_TABLE_NAME environment variable is required"):
            handler(event, lambda_context)


def test_handler_record_event_failure(mock_env, lambda_context):
    """Test handler propagates exceptions from record_event."""
    from session_initializer import handler

    event = {"session_id": "test-session-123"}

    with patch("session_initializer.record_event", side_effect=Exception("DynamoDB error")):
        with pytest.raises(Exception, match="DynamoDB error"):
            handler(event, lambda_context)
