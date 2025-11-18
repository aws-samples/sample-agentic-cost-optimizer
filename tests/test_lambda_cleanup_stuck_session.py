"""Unit tests for cleanup_stuck_session Lambda function."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Set environment variables BEFORE any imports
os.environ["AGENT_RUNTIME_ARN"] = "mock-agent-runtime-arn"
os.environ["JOURNAL_TABLE_NAME"] = "test-table"
os.environ["TTL_DAYS"] = "90"
os.environ["AWS_REGION"] = "us-east-1"

# Mock aws_lambda_powertools before importing cleanup_stuck_session
mock_tracer = MagicMock()
mock_tracer.capture_lambda_handler = lambda func: func  # Decorator passthrough

mock_powertools = MagicMock()
mock_powertools.Logger.return_value = MagicMock()
mock_powertools.Tracer.return_value = mock_tracer

sys.modules["aws_lambda_powertools"] = mock_powertools

# Mock boto3 before importing cleanup_stuck_session
mock_bedrock_client = MagicMock()
with patch("boto3.client", return_value=mock_bedrock_client):
    # Add infra/lambda to path
    sys.path.insert(0, str(Path(__file__).parent.parent / "infra" / "lambda"))
    import cleanup_stuck_session


@pytest.fixture(autouse=True)
def mock_boto3_client():
    """Reset the bedrock_agentcore client mock for each test."""
    cleanup_stuck_session.bedrock_agentcore.reset_mock()
    yield cleanup_stuck_session.bedrock_agentcore


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.function_name = "cleanup_stuck_session"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:cleanup_stuck_session"
    return context


class TestCleanupStuckSessionHandler:
    """Test cases for the cleanup stuck session Lambda handler."""

    def test_force_stop_stuck_session(self, lambda_context, mock_boto3_client):
        """Should force stop a session stuck in HealthyBusy state."""
        from cleanup_stuck_session import lambda_handler

        mock_bedrock_client.stop_runtime_session.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

        event = {"session_id": "test-session-123", "ping_status": "HealthyBusy"}

        with patch("cleanup_stuck_session.record_event") as mock_record_event:
            result = lambda_handler(event, lambda_context)

            assert result["status"] == "force_stopped"
            assert result["sessionId"] == "test-session-123"

            # Verify stop_runtime_session was called
            mock_bedrock_client.stop_runtime_session.assert_called_once_with(
                agentRuntimeId="mock-agent-runtime-arn", runtimeSessionId="test-session-123"
            )

            # Verify event was recorded
            mock_record_event.assert_called_once()
            call_args = mock_record_event.call_args[1]
            assert call_args["session_id"] == "test-session-123"
            assert call_args["status"] == "AGENT_RUNTIME_SESSION_FORCE_STOPPED"

    def test_skip_cleanup_for_healthy_session(self, lambda_context, mock_boto3_client):
        """Should skip cleanup for a Healthy session."""
        from cleanup_stuck_session import lambda_handler

        event = {"session_id": "test-session-456", "ping_status": "Healthy"}

        with patch("cleanup_stuck_session.record_event") as mock_record_event:
            result = lambda_handler(event, lambda_context)

            assert result["status"] == "stop_not_required"
            assert result["sessionId"] == "test-session-456"

            # Verify stop_runtime_session was NOT called
            mock_boto3_client.stop_runtime_session.assert_not_called()

            # Verify event was recorded
            mock_record_event.assert_called_once()
            call_args = mock_record_event.call_args[1]
            assert call_args["session_id"] == "test-session-456"
            assert call_args["status"] == "AGENT_RUNTIME_SESSION_STOP_NOT_REQUIRED"

    def test_handle_unexpected_ping_status(self, lambda_context, mock_boto3_client):
        """Should handle unexpected ping status gracefully."""
        from cleanup_stuck_session import lambda_handler

        event = {"session_id": "test-session-789", "ping_status": "UnknownStatus"}

        with patch("cleanup_stuck_session.record_event") as mock_record_event:
            result = lambda_handler(event, lambda_context)

            assert result["status"] == "stop_not_required"
            assert result["sessionId"] == "test-session-789"
            assert "warning" in result
            assert "UnknownStatus" in result["warning"]

            # Verify stop_runtime_session was NOT called
            mock_boto3_client.stop_runtime_session.assert_not_called()

            # Verify event was NOT recorded (unexpected status)
            mock_record_event.assert_not_called()

    def test_handle_stop_runtime_session_failure(self, lambda_context, mock_boto3_client):
        """Should handle stop_runtime_session failures gracefully."""
        from cleanup_stuck_session import lambda_handler

        error_response = {"Error": {"Code": "ValidationException", "Message": "Session not found"}}
        mock_boto3_client.stop_runtime_session.side_effect = ClientError(error_response, "StopRuntimeSession")

        event = {"session_id": "test-session-error", "ping_status": "HealthyBusy"}

        with patch("cleanup_stuck_session.record_event") as mock_record_event:
            with pytest.raises(ClientError):
                lambda_handler(event, lambda_context)

            # Verify stop_runtime_session was called
            mock_boto3_client.stop_runtime_session.assert_called_once()

            # Verify failure event was recorded
            mock_record_event.assert_called_once()
            call_args = mock_record_event.call_args[1]
            assert call_args["session_id"] == "test-session-error"
            assert call_args["status"] == "AGENT_RUNTIME_SESSION_FORCE_STOP_FAILED"
            assert "ValidationException" in call_args["error_message"]

    def test_missing_session_id(self, lambda_context, mock_boto3_client):
        """Should return error when session_id is missing."""
        from cleanup_stuck_session import lambda_handler

        event = {"ping_status": "HealthyBusy"}

        with patch("cleanup_stuck_session.record_event"):
            result = lambda_handler(event, lambda_context)

            assert result["statusCode"] == 400
            assert "Missing required field: session_id" in result["error"]

            # Verify stop_runtime_session was NOT called
            mock_boto3_client.stop_runtime_session.assert_not_called()

    def test_handle_different_client_errors(self, lambda_context, mock_boto3_client):
        """Should handle different ClientError types."""
        from cleanup_stuck_session import lambda_handler

        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        mock_boto3_client.stop_runtime_session.side_effect = ClientError(error_response, "StopRuntimeSession")

        event = {"session_id": "test-session-throttle", "ping_status": "HealthyBusy"}

        with patch("cleanup_stuck_session.record_event") as mock_record_event:
            with pytest.raises(ClientError):
                lambda_handler(event, lambda_context)

            # Verify failure event was recorded with correct error
            call_args = mock_record_event.call_args[1]
            assert "ThrottlingException" in call_args["error_message"]
            assert "Rate exceeded" in call_args["error_message"]
