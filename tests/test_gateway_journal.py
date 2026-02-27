"""Unit tests for infra/lambda/journal_tool.py."""

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Mock the 'shared' module before importing journal_tool
mock_shared = MagicMock()
mock_shared.EventStatus = type(
    "EventStatus",
    (),
    {"TASK_STARTED": "STARTED", "TASK_COMPLETED": "COMPLETED", "TASK_FAILED": "FAILED"},
)
mock_shared.record_event = MagicMock()
sys.modules["shared"] = mock_shared

sys.path.insert(0, "infra/lambda")
journal_tool = importlib.import_module("journal_tool")
sys.path.pop(0)


def _make_context(tool_name):
    return SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": f"JournalTarget___{tool_name}"})
    )


class TestJournalToolRouting:
    def test_routes_to_start_task(self):
        event = {"session_id": "s1", "phase_name": "analysis"}
        with patch.object(journal_tool, "journal_start_task", return_value={"success": True}) as mock_fn:
            result = journal_tool.lambda_handler(event, _make_context("journal_start_task"))
            mock_fn.assert_called_once_with(event)
            assert result["success"] is True

    def test_routes_to_complete_task(self):
        event = {"session_id": "s1", "phase_name": "analysis"}
        with patch.object(journal_tool, "journal_complete_task", return_value={"success": True}) as mock_fn:
            result = journal_tool.lambda_handler(event, _make_context("journal_complete_task"))
            mock_fn.assert_called_once_with(event)
            assert result["success"] is True

    def test_unknown_tool_returns_error(self):
        result = journal_tool.lambda_handler({}, _make_context("unknown_tool"))
        assert result["success"] is False
        assert "Unknown tool" in result["error"]


class TestJournalStartTask:
    def setup_method(self):
        mock_shared.record_event.reset_mock()

    @patch.object(journal_tool, "JOURNAL_TABLE_NAME", "test-table")
    def test_success(self):
        result = journal_tool.journal_start_task({"session_id": "sess-1", "phase_name": "analysis"})

        assert result["success"] is True
        assert result["session_id"] == "sess-1"
        assert result["status"] == "IN_PROGRESS"
        mock_shared.record_event.assert_called_once()
        call_kwargs = mock_shared.record_event.call_args[1]
        assert call_kwargs["session_id"] == "sess-1"
        assert "TASK_ANALYSIS_STARTED" in call_kwargs["status"]

    def test_missing_params(self):
        result = journal_tool.journal_start_task({"session_id": "sess-1"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    @patch.object(journal_tool, "JOURNAL_TABLE_NAME", "")
    def test_missing_table_name(self):
        result = journal_tool.journal_start_task({"session_id": "sess-1", "phase_name": "analysis"})
        assert result["success"] is False
        assert "JOURNAL_TABLE_NAME" in result["error"]


class TestJournalCompleteTask:
    def setup_method(self):
        mock_shared.record_event.reset_mock()

    @patch.object(journal_tool, "JOURNAL_TABLE_NAME", "test-table")
    def test_success_completed(self):
        result = journal_tool.journal_complete_task(
            {"session_id": "sess-1", "phase_name": "analysis", "status": "COMPLETED"}
        )

        assert result["success"] is True
        assert result["status"] == "COMPLETED"
        mock_shared.record_event.assert_called_once()

    @patch.object(journal_tool, "JOURNAL_TABLE_NAME", "test-table")
    def test_success_failed_with_error(self):
        result = journal_tool.journal_complete_task(
            {
                "session_id": "sess-1",
                "phase_name": "analysis",
                "status": "FAILED",
                "error_message": "timeout",
            }
        )

        assert result["success"] is True
        assert result["status"] == "FAILED"
        call_kwargs = mock_shared.record_event.call_args[1]
        assert call_kwargs["error_message"] == "timeout"

    @patch.object(journal_tool, "JOURNAL_TABLE_NAME", "test-table")
    def test_invalid_status(self):
        result = journal_tool.journal_complete_task(
            {"session_id": "sess-1", "phase_name": "analysis", "status": "INVALID"}
        )
        assert result["success"] is False
        assert "Invalid status" in result["error"]

    def test_missing_params(self):
        result = journal_tool.journal_complete_task({"session_id": "sess-1"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    @patch.object(journal_tool, "JOURNAL_TABLE_NAME", "")
    def test_missing_table_name(self):
        result = journal_tool.journal_complete_task({"session_id": "sess-1", "phase_name": "analysis"})
        assert result["success"] is False
        assert "JOURNAL_TABLE_NAME" in result["error"]
