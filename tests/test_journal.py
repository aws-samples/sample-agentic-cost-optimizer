"""Unit tests for the journal tool."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Import the internal journal functions directly - these don't have the @tool decorator
from src.tools.journal import _complete_session, _complete_task, _start_session, _start_task


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext with session_id."""
    context = MagicMock()
    context.invocation_state = {"session_id": "test-session-123"}
    return context


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table."""
    table = MagicMock()
    table.put_item = MagicMock()
    table.update_item = MagicMock()
    table.query = MagicMock(return_value={"Items": []})
    table.get_item = MagicMock(return_value={"Item": {"start_time": "2025-01-01T00:00:00Z"}})
    return table


@pytest.fixture(autouse=True)
def setup_env():
    """Set up environment variables for tests."""
    os.environ["JOURNAL_TABLE_NAME"] = "test-journal-table"
    yield
    if "JOURNAL_TABLE_NAME" in os.environ:
        del os.environ["JOURNAL_TABLE_NAME"]


class TestJournalStartSession:
    """Tests for start_session action."""

    @patch("src.tools.journal.dynamodb")
    def test_start_session_success(self, mock_dynamodb, mock_tool_context, mock_dynamodb_table):
        """Test successful session start."""
        mock_dynamodb.Table.return_value = mock_dynamodb_table

        result = _start_session(tool_context=mock_tool_context)

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["status"] == "BUSY"
        assert "timestamp" in result
        mock_dynamodb_table.put_item.assert_called_once()

    def test_start_session_missing_session_id(self):
        """Test start_session with missing session_id."""
        context = MagicMock()
        context.invocation_state = {}

        result = _start_session(tool_context=context)

        assert result["success"] is False
        assert "session_id not found" in result["error"]

    def test_start_session_missing_table_name(self, mock_tool_context):
        """Test start_session with missing JOURNAL_TABLE_NAME."""
        del os.environ["JOURNAL_TABLE_NAME"]

        result = _start_session(tool_context=mock_tool_context)

        assert result["success"] is False
        assert "JOURNAL_TABLE_NAME not set" in result["error"]


class TestJournalStartTask:
    """Tests for start_task action."""

    @patch("src.tools.journal.dynamodb")
    @patch(
        "src.tools.journal._session_cache",
        {
            "session_id": "test-session-123",
            "start_time": "2025-01-01T00:00:00Z",
            "tasks": {},
        },
    )
    def test_start_task_success(self, mock_dynamodb, mock_tool_context, mock_dynamodb_table):
        """Test successful task start."""
        mock_dynamodb.Table.return_value = mock_dynamodb_table

        result = _start_task(phase_name="Discovery", tool_context=mock_tool_context)

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["phase_name"] == "Discovery"
        assert result["status"] == "IN_PROGRESS"
        mock_dynamodb_table.put_item.assert_called_once()

    def test_start_task_missing_phase_name(self, mock_tool_context):
        """Test start_task without phase_name."""
        result = _start_task(phase_name="", tool_context=mock_tool_context)

        assert result["success"] is False
        assert "phase_name is required" in result["error"]

    @patch(
        "src.tools.journal._session_cache",
        {"session_id": None, "start_time": None, "tasks": {}},
    )
    def test_start_task_no_session(self):
        """Test start_task without active session."""
        context = MagicMock()
        context.invocation_state = {}

        result = _start_task(phase_name="Discovery", tool_context=context)

        assert result["success"] is False
        assert "No active session" in result["error"]


class TestJournalCompleteTask:
    """Tests for complete_task action."""

    @patch("src.tools.journal.dynamodb")
    @patch(
        "src.tools.journal._session_cache",
        {
            "session_id": "test-session-123",
            "start_time": "2025-01-01T00:00:00Z",
            "tasks": {
                "Discovery": {
                    "record_type": "TASK#2025-01-01T00:00:00Z",
                    "start_time": "2025-01-01T00:00:00Z",
                    "session_id": "test-session-123",
                }
            },
        },
    )
    def test_complete_task_success(self, mock_dynamodb, mock_tool_context, mock_dynamodb_table):
        """Test successful task completion."""
        mock_dynamodb.Table.return_value = mock_dynamodb_table

        from src.tools.journal import TaskStatus

        result = _complete_task(
            phase_name="Discovery",
            tool_context=mock_tool_context,
            status=TaskStatus.COMPLETED,
        )

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["phase_name"] == "Discovery"
        assert result["status"] == "COMPLETED"
        assert "duration_seconds" in result
        mock_dynamodb_table.update_item.assert_called_once()

    def test_complete_task_missing_phase_name(self, mock_tool_context):
        """Test complete_task without phase_name."""
        result = _complete_task(phase_name="", tool_context=mock_tool_context)

        assert result["success"] is False
        assert "phase_name is required" in result["error"]


class TestJournalCompleteSession:
    """Tests for complete_session action."""

    @patch("src.tools.journal.dynamodb")
    @patch(
        "src.tools.journal._session_cache",
        {
            "session_id": "test-session-123",
            "start_time": "2025-01-01T00:00:00Z",
            "tasks": {},
        },
    )
    def test_complete_session_success(self, mock_dynamodb, mock_tool_context, mock_dynamodb_table):
        """Test successful session completion."""
        mock_dynamodb.Table.return_value = mock_dynamodb_table

        from src.tools.journal import SessionStatus

        result = _complete_session(
            tool_context=mock_tool_context,
            status=SessionStatus.COMPLETED,
        )

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["status"] == "COMPLETED"
        assert "duration_seconds" in result
        mock_dynamodb_table.update_item.assert_called_once()

    @patch(
        "src.tools.journal._session_cache",
        {"session_id": None, "start_time": None, "tasks": {}},
    )
    def test_complete_session_no_active_session(self):
        """Test complete_session without active session."""
        context = MagicMock()
        context.invocation_state = {}

        result = _complete_session(tool_context=context)

        assert result["success"] is False
        assert "No active session" in result["error"]
