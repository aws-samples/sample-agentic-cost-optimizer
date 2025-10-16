"""Unit tests for the journal tool."""

import os
from unittest.mock import MagicMock, patch

import pytest
from strands import ToolContext

from src.tools.journal import journal


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext with session_id."""
    context = MagicMock(spec=ToolContext)
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

        result = journal(action="start_session", tool_context=mock_tool_context)

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["status"] == "STARTED"
        assert "timestamp" in result
        mock_dynamodb_table.put_item.assert_called_once()

    def test_start_session_missing_session_id(self):
        """Test start_session with missing session_id."""
        context = MagicMock(spec=ToolContext)
        context.invocation_state = {}

        result = journal(action="start_session", tool_context=context)

        assert result["success"] is False
        assert "session_id not found" in result["error"]

    def test_start_session_missing_table_name(self, mock_tool_context):
        """Test start_session with missing JOURNAL_TABLE_NAME."""
        del os.environ["JOURNAL_TABLE_NAME"]

        result = journal(action="start_session", tool_context=mock_tool_context)

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

        result = journal(action="start_task", tool_context=mock_tool_context, phase_name="Discovery")

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["phase_name"] == "Discovery"
        assert result["status"] == "IN_PROGRESS"
        mock_dynamodb_table.put_item.assert_called_once()

    def test_start_task_missing_phase_name(self, mock_tool_context):
        """Test start_task without phase_name."""
        result = journal(action="start_task", tool_context=mock_tool_context)

        assert result["success"] is False
        assert "phase_name is required" in result["error"]

    @patch(
        "src.tools.journal._session_cache",
        {"session_id": None, "start_time": None, "tasks": {}},
    )
    def test_start_task_no_session(self):
        """Test start_task without active session."""
        context = MagicMock(spec=ToolContext)
        context.invocation_state = {}

        result = journal(action="start_task", tool_context=context, phase_name="Discovery")

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

        result = journal(
            action="complete_task",
            tool_context=mock_tool_context,
            phase_name="Discovery",
            status="COMPLETED",
        )

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["phase_name"] == "Discovery"
        assert result["status"] == "COMPLETED"
        assert "duration_seconds" in result
        mock_dynamodb_table.update_item.assert_called_once()

    def test_complete_task_missing_phase_name(self, mock_tool_context):
        """Test complete_task without phase_name."""
        result = journal(action="complete_task", tool_context=mock_tool_context)

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

        result = journal(
            action="complete_session",
            tool_context=mock_tool_context,
            status="COMPLETED",
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
        context = MagicMock(spec=ToolContext)
        context.invocation_state = {}

        result = journal(action="complete_session", tool_context=context)

        assert result["success"] is False
        assert "No active session" in result["error"]


class TestJournalInvalidAction:
    """Tests for invalid actions."""

    def test_unknown_action(self, mock_tool_context):
        """Test journal with unknown action."""
        result = journal(action="invalid_action", tool_context=mock_tool_context)

        assert result["success"] is False
        assert "Unknown action" in result["error"]
