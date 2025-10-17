"""Unit tests for the invoke function with fire-and-forget async behavior."""

from unittest.mock import patch

from botocore.exceptions import ClientError

from src.agents.main import background_agent_processing, invoke


class TestInvokeFunction:
    """Test cases for the invoke function with fire-and-forget async behavior."""

    def test_successful_task_creation(self):
        """Test successful task creation: invoke returns immediate success message."""
        payload = {"prompt": "hello", "session_id": "session-456"}

        result = invoke(payload)

        assert "Started cost optimization analysis for session session-456" in result

    @patch("src.agents.main.app.add_async_task")
    def test_task_creation_failure(self, mock_add_task):
        """Test task creation failure: invoke returns error message."""
        mock_add_task.side_effect = Exception("Task creation failed")
        payload = {"prompt": "hello", "session_id": "session-456"}

        result = invoke(payload)

        assert "Error starting background processing: Task creation failed" in result
        mock_add_task.assert_called_once_with("cost_analysis", {"session_id": "session-456", "message": "hello"})

    def test_default_prompt_when_missing(self):
        """Test that default prompt 'Hello' is used when prompt is missing from payload."""
        payload = {"session_id": "session-456"}

        result = invoke(payload)

        assert "Started cost optimization analysis for session session-456" in result

    def test_default_session_id_when_missing(self):
        """Test that default session_id is used when missing from payload."""
        payload = {"prompt": "test"}

        result = invoke(payload)

        # Should use the global session_id (None in test environment)
        assert "Started cost optimization analysis for session None" in result


class TestBackgroundAgentProcessing:
    """Test cases for the background_agent_processing function error handling."""

    @patch("src.agents.main.agent")
    def test_successful_agent_response(self, mock_agent):
        """Test successful agent response: background processing returns agent response."""
        mock_agent.return_value = "Hello, how can I help?"

        result = background_agent_processing("hello", "session-123", "task-456")

        assert result == "Hello, how can I help?"
        mock_agent.assert_called_once_with("hello", session_id="session-123")

    @patch("src.agents.main.agent")
    def test_no_credentials_error(self, mock_agent, no_credentials_error):
        """Test NoCredentialsError: background processing returns credentials error message."""
        mock_agent.side_effect = no_credentials_error

        result = background_agent_processing("hello", "session-123", "task-456")

        assert result == "AWS credentials are not configured. Please set up your AWS credentials."
        mock_agent.assert_called_once_with("hello", session_id="session-123")

    @patch("src.agents.main.agent")
    def test_throttling_exception(self, mock_agent, throttling_error):
        """Test ClientError with ThrottlingException: background processing returns throttling message."""
        mock_agent.side_effect = throttling_error

        result = background_agent_processing("hello", "session-123", "task-456")

        assert result == "I'm currently experiencing high demand. Please try again in a moment."
        mock_agent.assert_called_once_with("hello", session_id="session-123")

    @patch("src.agents.main.agent")
    def test_access_denied_exception(self, mock_agent, access_denied_error):
        """Test ClientError with AccessDeniedException: background processing returns permissions message."""
        mock_agent.side_effect = access_denied_error

        result = background_agent_processing("hello", "session-123", "task-456")

        assert result == "I don't have the necessary permissions to access the model."
        mock_agent.assert_called_once_with("hello", session_id="session-123")

    @patch("src.agents.main.agent")
    def test_unknown_client_error(self, mock_agent, unknown_client_error):
        """Test ClientError with unknown error code: background processing returns generic technical difficulties message."""
        mock_agent.side_effect = unknown_client_error

        result = background_agent_processing("test", "session-123", "task-456")

        assert result == "I'm experiencing some technical difficulties. Please try again later."
        mock_agent.assert_called_once_with("test", session_id="session-123")

    @patch("src.agents.main.agent")
    def test_generic_exception(self, mock_agent):
        """Test generic Exception: background processing returns unexpected error message."""
        mock_agent.side_effect = Exception("Unexpected error")

        result = background_agent_processing("test", "session-123", "task-456")

        assert result == "I encountered an unexpected error. Please try again."
        mock_agent.assert_called_once_with("test", session_id="session-123")

    @patch("src.agents.main.agent")
    def test_client_error_without_error_code(self, mock_agent):
        """Test ClientError without Error.Code in response: should use generic message."""
        error_response = {"Error": {"Message": "Some error without code"}}
        mock_agent.side_effect = ClientError(error_response, "InvokeModel")

        result = background_agent_processing("test", "session-123", "task-456")

        assert result == "I'm experiencing some technical difficulties. Please try again later."
        mock_agent.assert_called_once_with("test", session_id="session-123")

    @patch("src.agents.main.agent")
    def test_client_error_without_error_dict(self, mock_agent):
        """Test ClientError without Error dict in response: should use generic message."""
        error_response = {}  # No Error key
        mock_agent.side_effect = ClientError(error_response, "InvokeModel")

        result = background_agent_processing("test", "session-123", "task-456")

        assert result == "I'm experiencing some technical difficulties. Please try again later."
        mock_agent.assert_called_once_with("test", session_id="session-123")
