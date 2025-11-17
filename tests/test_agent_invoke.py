"""Unit tests for the agent invoke function with fire-and-forget async behavior."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.main import invoke


class TestInvokeFunction:
    """Test cases for the invoke function with fire-and-forget async behavior."""

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_successful_task_creation(self, mock_create_task, mock_record_event):
        """Test successful task creation: invoke returns immediate success message."""
        mock_create_task.return_value = AsyncMock()
        payload = {"prompt": "hello", "session_id": "session-456"}

        result = await invoke(payload)

        assert "Started processing request for session session-456" in result["message"]
        assert result["session_id"] == "session-456"
        assert result["status"] == "started"

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_task_creation_failure(self, mock_create_task, mock_record_event):
        """Test task creation failure: invoke returns error message."""
        mock_create_task.side_effect = Exception("Task creation failed")
        payload = {"prompt": "hello", "session_id": "session-456"}

        result = await invoke(payload)

        assert "Error starting background processing: Task creation failed" in result["error"]

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_default_prompt_when_missing(self, mock_create_task, mock_record_event):
        """Test that default prompt 'Hello' is used when prompt is missing from payload."""
        mock_create_task.return_value = AsyncMock()
        payload = {"session_id": "session-456"}

        result = await invoke(payload)

        assert "Started processing request for session session-456" in result["message"]

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_default_session_id_when_missing(self, mock_create_task, mock_record_event):
        """Test that default session_id from environment is used when missing from payload."""
        mock_create_task.return_value = AsyncMock()
        payload = {"prompt": "test"}

        result = await invoke(payload)

        assert "Started processing request for session local-dev-session" in result["message"]


class TestBackgroundTaskIntegration:
    """Test cases for background task integration (testing the fire-and-forget pattern)."""

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_background_task_is_started(self, mock_create_task, mock_record_event):
        """Test that background task is started when invoke is called."""
        mock_create_task.return_value = AsyncMock()
        payload = {"prompt": "hello", "session_id": "session-456"}

        result = await invoke(payload)

        assert (
            result["message"]
            == "Started processing request for session session-456. Processing will continue in background."
        )
        assert result["session_id"] == "session-456"
        assert result["status"] == "started"
        mock_create_task.assert_called_once()


class TestBackgroundTaskErrorHandling:
    """Test error handling scenarios through the invoke function integration."""

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    @patch("src.agents.main.logger")
    @patch("src.agents.main.analysis_agent")
    async def test_credentials_error_through_invoke(self, mock_agent, mock_logger, mock_create_task, mock_record_event):
        """Test NoCredentialsError handling through invoke integration."""
        from botocore.exceptions import NoCredentialsError

        mock_create_task.return_value = AsyncMock()
        mock_agent.invoke_async.side_effect = NoCredentialsError()
        payload = {"prompt": "hello", "session_id": "session-456"}

        result = await invoke(payload)

        assert "Started processing request for session session-456" in result["message"]
        assert result["status"] == "started"
        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    @patch("src.agents.main.logger")
    @patch("src.agents.main.analysis_agent")
    async def test_throttling_error_through_invoke(self, mock_agent, mock_logger, mock_create_task, mock_record_event):
        """Test ThrottlingException handling through invoke integration."""
        from botocore.exceptions import ClientError

        throttling_error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}, "InvokeModel"
        )
        mock_create_task.return_value = AsyncMock()
        mock_agent.invoke_async.side_effect = throttling_error
        payload = {"prompt": "hello", "session_id": "session-456"}

        result = await invoke(payload)

        assert "Started processing request for session session-456" in result["message"]
        assert result["status"] == "started"
        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    @patch("src.agents.main.logger")
    @patch("src.agents.main.analysis_agent")
    async def test_access_denied_error_through_invoke(
        self, mock_agent, mock_logger, mock_create_task, mock_record_event
    ):
        """Test AccessDeniedException handling through invoke integration."""
        from botocore.exceptions import ClientError

        access_denied_error = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}, "InvokeModel"
        )
        mock_create_task.return_value = AsyncMock()
        mock_agent.invoke_async.side_effect = access_denied_error
        payload = {"prompt": "hello", "session_id": "session-456"}

        result = await invoke(payload)

        assert "Started processing request for session session-456" in result["message"]
        assert result["status"] == "started"
        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    @patch("src.agents.main.logger")
    @patch("src.agents.main.analysis_agent")
    async def test_generic_exception_through_invoke(self, mock_agent, mock_logger, mock_create_task, mock_record_event):
        """Test generic Exception handling through invoke integration."""
        mock_create_task.return_value = AsyncMock()
        mock_agent.invoke_async.side_effect = Exception("Unexpected error")
        payload = {"prompt": "hello", "session_id": "session-456"}

        result = await invoke(payload)

        assert "Started processing request for session session-456" in result["message"]
        assert result["status"] == "started"
        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    @patch("src.agents.main.logger")
    @patch("src.agents.main.analysis_agent")
    async def test_successful_agent_response_through_invoke(
        self, mock_agent, mock_logger, mock_create_task, mock_record_event
    ):
        """Test successful agent response through invoke integration."""
        mock_create_task.return_value = AsyncMock()
        mock_response = type("MockResponse", (), {"message": "Hello, how can I help?"})()
        mock_agent.invoke_async.return_value = mock_response
        payload = {"prompt": "hello", "session_id": "session-456"}

        result = await invoke(payload)

        assert "Started processing request for session session-456" in result["message"]
        assert result["status"] == "started"
        mock_create_task.assert_called_once()
