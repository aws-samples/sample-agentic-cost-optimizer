"""Unit tests for the journal tool."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Import the journal functions - @tool decorator is mocked in conftest.py
from src.tools.journal import (
    _complete_task,
    _start_task,
    journal,
)


class TestJournalValidation:
    """Tests for journal function validation."""

    def test_invalid_action(self):
        """Test journal with invalid action parameter."""
        # Create a simple mock context
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
            action="complete_task", tool_context=mock_context, phase_name="Discovery", status="INVALID_STATUS"
        )

        assert result["success"] is False
        assert "Invalid status 'INVALID_STATUS'" in result["error"]
        assert "COMPLETED, FAILED" in result["error"]

    def test_missing_table_name(self):
        """Test journal with missing JOURNAL_TABLE_NAME environment variable."""
        # Temporarily remove the env var
        original_table_name = os.environ.get("JOURNAL_TABLE_NAME")
        if "JOURNAL_TABLE_NAME" in os.environ:
            del os.environ["JOURNAL_TABLE_NAME"]

        try:
            mock_context = MagicMock()
            mock_context.invocation_state = {"session_id": "test-session-123"}

            result = journal(action="start_task", tool_context=mock_context, phase_name="Discovery")

            assert result["success"] is False
            assert "JOURNAL_TABLE_NAME not set" in result["error"]
        finally:
            # Restore the env var
            if original_table_name:
                os.environ["JOURNAL_TABLE_NAME"] = original_table_name

    @patch("src.tools.journal.record_event")
    def test_phase_name_special_characters(self, mock_record_event):
        """Test journal with phase names containing special characters."""
        mock_context = MagicMock()
        mock_context.invocation_state = {"session_id": "test-session-123"}

        result = journal(action="start_task", tool_context=mock_context, phase_name="Data Analysis & Cleanup")

        assert result["success"] is True
        mock_record_event.assert_called_once()

        # Check that the event status has the correct format: TASK_<PHASE>_STARTED
        call_args = mock_record_event.call_args
        event_status = call_args[1]["status"]
        assert event_status == "TASK_DATA_ANALYSIS_&_CLEANUP_STARTED"


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
    def test_start_task_success(self, mock_record_event, mock_tool_context):
        """Test successful task start."""
        result = _start_task(phase_name="Discovery", tool_context=mock_tool_context)

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["phase_name"] == "Discovery"
        assert result["status"] == "IN_PROGRESS"
        mock_record_event.assert_called_once()

    def test_start_task_missing_phase_name(self, mock_tool_context):
        """Test start_task without phase_name."""
        result = _start_task(phase_name="", tool_context=mock_tool_context)

        assert result["success"] is False
        assert "phase_name is required" in result["error"]

    def test_start_task_no_session(self):
        """Test start_task without active session."""
        context = MagicMock()
        context.invocation_state = {}

        result = _start_task(phase_name="Discovery", tool_context=context)

        assert result["success"] is False
        assert "No active session" in result["error"]


class TestJournalCompleteTask:
    """Tests for complete_task action."""

    @patch("src.tools.journal.record_event")
    def test_complete_task_success(self, mock_record_event, mock_tool_context):
        """Test successful task completion."""
        result = _complete_task(
            phase_name="Discovery",
            tool_context=mock_tool_context,
            status="COMPLETED",
        )

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["phase_name"] == "Discovery"
        assert result["status"] == "COMPLETED"
        mock_record_event.assert_called_once()

    def test_complete_task_missing_phase_name(self, mock_tool_context):
        """Test complete_task without phase_name."""
        result = _complete_task(phase_name="", tool_context=mock_tool_context)

        assert result["success"] is False
        assert "phase_name is required" in result["error"]
