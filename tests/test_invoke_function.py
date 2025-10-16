"""Unit tests for the invoke function with mocked agent."""

from unittest.mock import patch

from botocore.exceptions import ClientError

from src.agents.main import invoke


class TestInvokeFunction:
    """Test cases for the invoke function with various error scenarios."""

    @patch("src.agents.main.agent")
    def test_successful_agent_response(self, mock_agent):
        """Test successful agent response: agent returns response, invoke returns string."""
        mock_agent.return_value = "Hello, how can I help?"
        payload = {"prompt": "hello"}

        result = invoke(payload)

        assert result == "Hello, how can I help?"
        mock_agent.assert_called_once_with("hello")

    @patch("src.agents.main.agent")
    def test_no_credentials_error(self, mock_agent, no_credentials_error, sample_payload):
        """Test NoCredentialsError: agent raises exception, invoke returns credentials error message."""
        mock_agent.side_effect = no_credentials_error

        result = invoke(sample_payload)

        assert result == "AWS credentials are not configured. Please set up your AWS credentials."
        mock_agent.assert_called_once_with("hello")

    @patch("src.agents.main.agent")
    def test_throttling_exception(self, mock_agent, throttling_error, sample_payload):
        """Test ClientError with ThrottlingException: invoke returns throttling message."""
        mock_agent.side_effect = throttling_error

        result = invoke(sample_payload)

        assert result == "I'm currently experiencing high demand. Please try again in a moment."
        mock_agent.assert_called_once_with("hello")

    @patch("src.agents.main.agent")
    def test_access_denied_exception(self, mock_agent, access_denied_error, sample_payload):
        """Test ClientError with AccessDeniedException: invoke returns permissions message."""
        mock_agent.side_effect = access_denied_error

        result = invoke(sample_payload)

        assert result == "I don't have the necessary permissions to access the model."
        mock_agent.assert_called_once_with("hello")

    @patch("src.agents.main.agent")
    def test_unknown_client_error(self, mock_agent):
        """Test ClientError with unknown error code: invoke returns generic technical difficulties message."""
        error_response = {"Error": {"Code": "UnknownException", "Message": "Unknown error"}}
        mock_agent.side_effect = ClientError(error_response, "InvokeModel")
        payload = {"prompt": "test"}

        result = invoke(payload)

        assert result == "I'm experiencing some technical difficulties. Please try again later."
        mock_agent.assert_called_once_with("test")

    @patch("src.agents.main.agent")
    def test_generic_exception(self, mock_agent):
        """Test generic Exception: invoke returns unexpected error message."""
        mock_agent.side_effect = Exception("Unexpected error")
        payload = {"prompt": "test"}

        result = invoke(payload)

        assert result == "I encountered an unexpected error. Please try again."
        mock_agent.assert_called_once_with("test")

    @patch("src.agents.main.agent")
    def test_default_prompt_when_missing(self, mock_agent, empty_payload):
        """Test that default prompt 'Hello' is used when prompt is missing from payload."""
        mock_agent.return_value = "Default response"

        result = invoke(empty_payload)

        assert result == "Default response"
        mock_agent.assert_called_once_with("Hello")

    @patch("src.agents.main.agent")
    def test_client_error_without_error_code(self, mock_agent):
        """Test ClientError without Error.Code in response: should use generic message."""
        error_response = {"Error": {"Message": "Some error without code"}}
        mock_agent.side_effect = ClientError(error_response, "InvokeModel")
        payload = {"prompt": "test"}

        result = invoke(payload)

        assert result == "I'm experiencing some technical difficulties. Please try again later."
        mock_agent.assert_called_once_with("test")

    @patch("src.agents.main.agent")
    def test_client_error_without_error_dict(self, mock_agent):
        """Test ClientError without Error dict in response: should use generic message."""
        error_response = {}  # No Error key
        mock_agent.side_effect = ClientError(error_response, "InvokeModel")
        payload = {"prompt": "test"}

        result = invoke(payload)

        assert result == "I'm experiencing some technical difficulties. Please try again later."
        mock_agent.assert_called_once_with("test")
