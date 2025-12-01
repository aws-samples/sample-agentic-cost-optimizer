"""Unit tests for the agent invoke function with fire-and-forget async behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.main import background_task, invoke


@pytest.fixture
def mock_context():
    """Create a mock RequestContext with session_id."""
    context = MagicMock()
    context.session_id = "session-456"
    return context


@pytest.fixture
def mock_create_task():
    """Create a mock for asyncio.create_task that properly handles coroutines."""

    def consume_coroutine(coro):
        coro.close()
        return AsyncMock()

    return consume_coroutine


class TestInvokeFunction:
    """Test cases for the invoke function with fire-and-forget async behavior."""

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_successful_task_creation(
        self, mock_create_task_patch, mock_record_event, mock_context, mock_create_task
    ):
        """Test successful task creation: invoke returns immediate success message."""
        mock_create_task_patch.side_effect = mock_create_task
        payload = {"prompt": "hello"}

        result = await invoke(payload, mock_context)

        assert "Started processing request for session session-456" in result["message"]
        assert result["session_id"] == "session-456"
        assert result["status"] == "started"

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_task_creation_failure(self, mock_create_task_patch, mock_record_event, mock_context):
        """Test task creation failure: invoke returns error message."""

        def consume_and_raise(coro):
            coro.close()
            raise Exception("Task creation failed")

        mock_create_task_patch.side_effect = consume_and_raise
        payload = {"prompt": "hello"}

        result = await invoke(payload, mock_context)

        assert "Error starting background processing: Task creation failed" in result["error"]

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_default_prompt_when_missing(
        self, mock_create_task_patch, mock_record_event, mock_context, mock_create_task
    ):
        """Test that default prompt 'Hello' is used when prompt is missing from payload."""
        mock_create_task_patch.side_effect = mock_create_task
        payload = {}

        result = await invoke(payload, mock_context)

        assert "Started processing request for session session-456" in result["message"]

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_session_id_from_context(
        self, mock_create_task_patch, mock_record_event, mock_context, mock_create_task
    ):
        """Test that session_id is retrieved from context."""
        mock_create_task_patch.side_effect = mock_create_task
        payload = {"prompt": "test"}

        result = await invoke(payload, mock_context)

        assert "Started processing request for session session-456" in result["message"]
        assert result["session_id"] == "session-456"


class TestBackgroundTask:
    """Test cases for background_task function."""

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_background_task_is_started(
        self, mock_create_task_patch, mock_record_event, mock_context, mock_create_task
    ):
        """Test that background task is started when invoke is called."""
        mock_create_task_patch.side_effect = mock_create_task
        payload = {"prompt": "hello"}

        result = await invoke(payload, mock_context)

        assert (
            result["message"]
            == "Started processing request for session session-456. Processing will continue in background."
        )
        assert result["session_id"] == "session-456"
        assert result["status"] == "started"
        mock_create_task_patch.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("src.agents.main.create_agent")
    async def test_background_task_success(self, mock_create_agent, mock_record_event):
        """Test successful background task execution."""
        mock_analysis_agent = MagicMock()
        mock_analysis_response = MagicMock()
        mock_analysis_agent.invoke_async = AsyncMock(return_value=mock_analysis_response)

        mock_report_agent = MagicMock()
        mock_report_response = MagicMock()
        mock_report_response.message = "Report generated successfully"
        mock_report_agent.invoke_async = AsyncMock(return_value=mock_report_response)

        # create_agent is called twice: first for analysis_agent, then for report_agent
        mock_create_agent.side_effect = [mock_analysis_agent, mock_report_agent]

        session_id = "test-session-123"
        user_message = "Analyze costs"

        result = await background_task(user_message, session_id)

        assert result == mock_report_response
        mock_analysis_agent.invoke_async.assert_called_once_with(
            "Analyze AWS costs and identify optimization opportunities",
            session_id=session_id,
        )
        mock_report_agent.invoke_async.assert_called_once_with(
            "Generate cost optimization report based on analysis results",
            session_id=session_id,
        )
        assert mock_record_event.call_count == 1

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("src.agents.main.create_agent")
    async def test_background_task_no_credentials_error(self, mock_create_agent, mock_record_event):
        """Test background task handles NoCredentialsError."""
        from botocore.exceptions import NoCredentialsError

        mock_analysis_agent = MagicMock()
        mock_analysis_agent.invoke_async = AsyncMock(side_effect=NoCredentialsError())
        mock_create_agent.return_value = mock_analysis_agent

        session_id = "test-session-123"
        user_message = "Analyze costs"

        result = await background_task(user_message, session_id)

        assert result["error"] == "NoCredentialsError"
        assert result["error_code"] == "NoCredentialsError"
        assert result["session_id"] == session_id
        assert result["status"] == "failed"

        assert mock_record_event.call_count == 1
        call_args = mock_record_event.call_args[1]
        assert "FAILED" in call_args["status"]

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("src.agents.main.create_agent")
    async def test_background_task_client_error(self, mock_create_agent, mock_record_event):
        """Test background task handles ClientError (e.g., ThrottlingException)."""
        from botocore.exceptions import ClientError

        throttling_error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )
        mock_analysis_agent = MagicMock()
        mock_analysis_agent.invoke_async = AsyncMock(side_effect=throttling_error)
        mock_create_agent.return_value = mock_analysis_agent

        session_id = "test-session-123"
        user_message = "Analyze costs"

        result = await background_task(user_message, session_id)

        assert result["error"] == "ClientError"
        assert result["error_code"] == "ThrottlingException"
        assert result["error_message"] == "Rate exceeded"
        assert result["session_id"] == session_id
        assert result["status"] == "failed"

        assert mock_record_event.call_count == 1
        call_args = mock_record_event.call_args[1]
        assert "FAILED" in call_args["status"]

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("src.agents.main.create_agent")
    async def test_background_task_generic_exception(self, mock_create_agent, mock_record_event):
        """Test background task handles generic Exception."""
        mock_analysis_agent = MagicMock()
        mock_analysis_agent.invoke_async = AsyncMock(side_effect=ValueError("Invalid input"))
        mock_create_agent.return_value = mock_analysis_agent

        session_id = "test-session-123"
        user_message = "Analyze costs"

        result = await background_task(user_message, session_id)

        assert result["error"] == "Exception"
        assert result["error_type"] == "ValueError"
        assert result["error_message"] == "Invalid input"
        assert result["session_id"] == session_id
        assert result["status"] == "failed"

        assert mock_record_event.call_count == 1
        call_args = mock_record_event.call_args[1]
        assert "FAILED" in call_args["status"]
