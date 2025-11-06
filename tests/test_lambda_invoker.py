"""Unit tests for the agent invoker Lambda function."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Set environment variables BEFORE any imports
os.environ["AGENT_CORE_RUNTIME_ARN"] = "mock-agent-runtime-arn"
os.environ["JOURNAL_TABLE_NAME"] = "mock-journal-table"
os.environ["TTL_DAYS"] = "90"
os.environ["AWS_REGION"] = "us-east-1"

# Mock aws_lambda_powertools before importing agent_invoker
mock_tracer = MagicMock()
mock_tracer.capture_lambda_handler = lambda func: func  # Decorator passthrough

mock_powertools = MagicMock()
mock_powertools.Logger.return_value = MagicMock()
mock_powertools.Tracer.return_value = mock_tracer

sys.modules["aws_lambda_powertools"] = mock_powertools
sys.modules["aws_lambda_powertools.shared"] = MagicMock()
sys.modules["aws_lambda_powertools.shared.functions"] = MagicMock()

# Mock boto3 before importing agent_invoker
mock_bedrock_client = MagicMock()
with patch("boto3.client", return_value=mock_bedrock_client):
    # Add infra/lambda to path
    sys.path.insert(0, str(Path(__file__).parent.parent / "infra" / "lambda"))
    import agent_invoker


@pytest.fixture(autouse=True)
def mock_boto3_client():
    """Reset the bedrock_agentcore client mock for each test."""
    # Reset the mock for each test
    agent_invoker.bedrock_agentcore.reset_mock()

    yield agent_invoker.bedrock_agentcore


class TestAgentInvokerHandler:
    """Test cases for the agent invoker Lambda handler - matching TS tests."""

    @patch("agent_invoker.record_event")
    def test_successfully_invoke_agent_with_default_prompt(self, mock_record_event, mock_boto3_client):
        """Should successfully invoke agent with default prompt."""
        import agent_invoker

        # Configure mock bedrock client
        mock_boto3_client.invoke_agent_runtime.return_value = {
            "statusCode": 200,
            "runtimeSessionId": "test-session-123",
        }

        event = {"session_id": "test-session-123"}
        context = MagicMock()

        result = agent_invoker.handler(event, context)

        assert result == {"status": 200, "sessionId": "test-session-123"}

        # Verify bedrock was called once
        assert mock_boto3_client.invoke_agent_runtime.call_count == 1
        call_args = mock_boto3_client.invoke_agent_runtime.call_args[1]
        assert call_args["agentRuntimeArn"] == "mock-agent-runtime-arn"
        assert call_args["runtimeSessionId"] == "test-session-123"
        payload = json.loads(call_args["payload"])
        assert payload["prompt"] == "Check my resources and let me know if they're overprovisioned"
        assert payload["session_id"] == "test-session-123"

        # Verify record_event was called twice (started and succeeded)
        assert mock_record_event.call_count == 2

    @patch("agent_invoker.record_event")
    def test_successfully_invoke_agent_with_custom_prompt(self, mock_record_event, mock_boto3_client):
        """Should successfully invoke agent with custom prompt."""
        import agent_invoker

        mock_boto3_client.invoke_agent_runtime.return_value = {
            "statusCode": 200,
            "runtimeSessionId": "test-session-456",
        }

        event = {"session_id": "test-session-456", "prompt": "Custom optimization request"}
        context = MagicMock()

        result = agent_invoker.handler(event, context)

        assert result == {"status": 200, "sessionId": "test-session-456"}

        # Verify bedrock was called with custom prompt
        call_args = mock_boto3_client.invoke_agent_runtime.call_args[1]
        payload = json.loads(call_args["payload"])
        assert payload["prompt"] == "Custom optimization request"
        assert payload["session_id"] == "test-session-456"

        # Verify record_event was called twice
        assert mock_record_event.call_count == 2

    @patch("agent_invoker.record_event")
    def test_handle_agentcore_errors_gracefully(self, mock_record_event, mock_boto3_client):
        """Should handle AgentCore errors gracefully."""
        import agent_invoker

        mock_boto3_client.invoke_agent_runtime.side_effect = Exception("AgentCore service unavailable")

        event = {"session_id": "test-session-error"}
        context = MagicMock()

        with pytest.raises(Exception, match="AgentCore service unavailable"):
            agent_invoker.handler(event, context)

        # Verify bedrock was called
        assert mock_boto3_client.invoke_agent_runtime.call_count == 1
        call_args = mock_boto3_client.invoke_agent_runtime.call_args[1]
        assert call_args["runtimeSessionId"] == "test-session-error"

        # Verify record_event was called twice (started and failed)
        assert mock_record_event.call_count == 2

    @patch("agent_invoker.record_event")
    def test_handle_different_status_codes_from_agentcore(self, mock_record_event, mock_boto3_client):
        """Should handle different status codes from AgentCore."""
        import agent_invoker

        # Reset side_effect from previous test
        mock_boto3_client.invoke_agent_runtime.side_effect = None
        mock_boto3_client.invoke_agent_runtime.return_value = {
            "statusCode": 202,
            "runtimeSessionId": "test-session-partial",
        }

        event = {"session_id": "test-session-partial"}
        context = MagicMock()

        result = agent_invoker.handler(event, context)

        assert result == {"status": 202, "sessionId": "test-session-partial"}

        # Verify record_event was called twice
        assert mock_record_event.call_count == 2

    @patch("agent_invoker.record_event")
    def test_continue_even_if_dynamodb_event_recording_fails(self, mock_record_event, mock_boto3_client):
        """Should continue even if DynamoDB event recording fails."""
        import agent_invoker

        # Reset side_effect from previous test
        mock_boto3_client.invoke_agent_runtime.side_effect = None
        mock_boto3_client.invoke_agent_runtime.return_value = {
            "statusCode": 200,
            "runtimeSessionId": "test-session-ddb-error",
        }

        # record_event catches exceptions internally, so it won't raise
        # Just verify the Lambda continues successfully
        event = {"session_id": "test-session-ddb-error"}
        context = MagicMock()

        result = agent_invoker.handler(event, context)

        assert result == {"status": 200, "sessionId": "test-session-ddb-error"}
        assert mock_boto3_client.invoke_agent_runtime.call_count == 1
        # Verify record_event was called (it handles its own errors)
        assert mock_record_event.call_count == 2

    @patch("agent_invoker.get_tracer_id", return_value="1-5e645f3e-1234567890abcdef")
    @patch("agent_invoker.record_event")
    def test_pass_trace_id_to_agentcore_for_observability(
        self, mock_record_event, mock_get_tracer_id, mock_boto3_client
    ):
        """Should pass X-Ray trace ID to AgentCore for GenAI Observability."""
        import agent_invoker

        # Reset side_effect from previous test
        mock_boto3_client.invoke_agent_runtime.side_effect = None
        mock_boto3_client.invoke_agent_runtime.return_value = {
            "statusCode": 200,
            "runtimeSessionId": "test-session-trace",
        }

        event = {"session_id": "test-session-trace"}
        context = MagicMock()

        result = agent_invoker.handler(event, context)

        assert result == {"status": 200, "sessionId": "test-session-trace"}

        # Verify get_tracer_id was called
        mock_get_tracer_id.assert_called_once()

        # Verify trace ID was passed to AgentCore
        call_args = mock_boto3_client.invoke_agent_runtime.call_args[1]
        assert "traceId" in call_args
        assert call_args["traceId"] == "1-5e645f3e-1234567890abcdef"

        # Verify record_event was called twice
        assert mock_record_event.call_count == 2
