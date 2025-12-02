"""Unit tests for the journal tool."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Import the journal tool function - @tool decorator is mocked in conftest.py
from src.tools.journal import journal


class TestJournalValidation:
    """Tests for journal function validation."""

    def test_invalid_action(self):
        """Test journal with invalid action parameter."""
        mock_context = MagicMock()
        mock_context.invocation_state = {"session_id": "test-session-123"}

        result = journal(action="invalid_action", tool_context=mock_context, phase_name="Discovery")

        assert result["success"] is False
        assert "Invalid action 'invalid_action'" in result["error"]
        assert "start_task, complete_task" in result["error"]

    def test_invalid_status(self):
        """Test journal complete_task with invalid status parameter."""
        mock_context = MagicMock()
        mock_context.invocation_state = {"session_id": "test-session-123"}

        result = journal(
            action="complete_task",
            tool_context=mock_context,
            phase_name="Discovery",
            status="INVALID_STATUS",
        )

        assert result["success"] is False
        assert "Invalid status 'INVALID_STATUS'" in result["error"]
        assert "COMPLETED, FAILED" in result["error"]

    @patch("src.tools.journal.record_event")
    @patch("src.tools.journal.config")
    def test_phase_name_special_characters(self, mock_config, mock_record_event):
        """Test journal with phase names containing special characters."""
        mock_config.journal_table_name = "test-journal-table"
        mock_config.ttl_days = 90
        mock_config.aws_region = "us-east-1"

        mock_context = MagicMock()
        mock_context.invocation_state = {"session_id": "test-session-123"}

        result = journal(
            action="start_task",
            tool_context=mock_context,
            phase_name="Data Analysis & Cleanup",
        )

        assert result["success"] is True
        mock_record_event.assert_called_once()

        call_args = mock_record_event.call_args
        event_status = call_args[1]["status"]
        assert "TASK_DATA_ANALYSIS_&_CLEANUP_STARTED" in event_status


@pytest.fixture
def mock_record_event():
    """Create a mock record_event function."""
    mock = MagicMock()
    mock.return_value = None
    return mock


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext with session_id."""
    context = MagicMock()
    context.invocation_state = {"session_id": "test-session-123"}
    return context


@pytest.fixture(autouse=True)
def setup_env():
    """Set up environment variables for tests."""
    os.environ["JOURNAL_TABLE_NAME"] = "test-journal-table"
    yield
    if "JOURNAL_TABLE_NAME" in os.environ:
        del os.environ["JOURNAL_TABLE_NAME"]


class TestJournalStartTask:
    """Tests for start_task action."""

    @patch("src.tools.journal.record_event")
    @patch("src.tools.journal.config")
    def test_start_task_success(self, mock_config, mock_record_event, mock_tool_context):
        """Test journal starts task successfully."""
        mock_config.journal_table_name = "test-journal-table"
        mock_config.ttl_days = 90
        mock_config.aws_region = "us-east-1"

        result = journal(action="start_task", phase_name="Discovery", tool_context=mock_tool_context)

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["phase_name"] == "Discovery"
        assert result["status"] == "IN_PROGRESS"
        mock_record_event.assert_called_once()

    def test_start_task_missing_phase_name(self, mock_tool_context):
        """Test journal start_task fails without phase_name."""
        result = journal(action="start_task", tool_context=mock_tool_context)

        assert result["success"] is False
        assert "phase_name is required" in result["error"]

    def test_start_task_no_session(self):
        """Test journal start_task fails without active session."""
        context = MagicMock()
        context.invocation_state = {}

        result = journal(action="start_task", phase_name="Discovery", tool_context=context)

        assert result["success"] is False
        assert "No active session" in result["error"]


class TestJournalCompleteTask:
    """Tests for complete_task action."""

    @patch("src.tools.journal.record_event")
    @patch("src.tools.journal.config")
    def test_complete_task_success(self, mock_config, mock_record_event, mock_tool_context):
        """Test journal completes task successfully."""
        mock_config.journal_table_name = "test-journal-table"
        mock_config.ttl_days = 90
        mock_config.aws_region = "us-east-1"

        result = journal(
            action="complete_task",
            phase_name="Discovery",
            status="COMPLETED",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["phase_name"] == "Discovery"
        assert result["status"] == "COMPLETED"
        mock_record_event.assert_called_once()

    def test_complete_task_missing_phase_name(self, mock_tool_context):
        """Test journal complete_task fails without phase_name."""
        result = journal(action="complete_task", tool_context=mock_tool_context)

        assert result["success"] is False
        assert "phase_name is required" in result["error"]

    @patch("src.tools.journal.record_event")
    @patch("src.tools.journal.config")
    def test_complete_task_with_default_status(self, mock_config, mock_record_event, mock_tool_context):
        """Test journal complete_task uses default COMPLETED status."""
        mock_config.journal_table_name = "test-journal-table"
        mock_config.ttl_days = 90
        mock_config.aws_region = "us-east-1"

        result = journal(
            action="complete_task",
            phase_name="Analysis",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["status"] == "COMPLETED"
        mock_record_event.assert_called_once()

    @patch("src.tools.journal.record_event")
    @patch("src.tools.journal.config")
    def test_complete_task_with_failed_status(self, mock_config, mock_record_event, mock_tool_context):
        """Test journal complete_task with FAILED status."""
        mock_config.journal_table_name = "test-journal-table"
        mock_config.ttl_days = 90
        mock_config.aws_region = "us-east-1"

        result = journal(
            action="complete_task",
            phase_name="Processing",
            status="FAILED",
            error_message="Processing error",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["status"] == "FAILED"
        mock_record_event.assert_called_once()
        call_args = mock_record_event.call_args[1]
        assert call_args["error_message"] == "Processing error"

    def test_complete_task_no_session(self):
        """Test journal complete_task fails without active session."""
        context = MagicMock()
        context.invocation_state = {}

        result = journal(action="complete_task", phase_name="Discovery", tool_context=context)

        assert result["success"] is False
        assert "No active session" in result["error"]

    @patch("src.tools.journal.record_event")
    def test_start_task_exception_handling(self, mock_record_event, mock_tool_context):
        """Test journal start_task handles unexpected exceptions."""
        mock_record_event.side_effect = Exception("Database connection error")

        result = journal(action="start_task", phase_name="Discovery", tool_context=mock_tool_context)

        assert result["success"] is False
        assert "Unexpected error" in result["error"]
        assert "Database connection error" in result["error"]

    @patch("src.tools.journal.record_event")
    def test_complete_task_exception_handling(self, mock_record_event, mock_tool_context):
        """Test journal complete_task handles unexpected exceptions."""
        mock_record_event.side_effect = Exception("Network timeout")

        result = journal(
            action="complete_task",
            phase_name="Analysis",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Unexpected error" in result["error"]
        assert "Network timeout" in result["error"]
