"""Unit tests for infra/lambda/storage_tool.py."""

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

# Import the module from infra/lambda path
sys.path.insert(0, "infra/lambda")
storage_tool = importlib.import_module("storage_tool")
sys.path.pop(0)


def _make_context(tool_name):
    return SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": f"StorageTarget___{tool_name}"})
    )


class TestStorageToolRouting:
    def test_routes_to_storage_read(self):
        event = {"session_id": "s1", "filename": "f.txt"}
        with patch.object(storage_tool, "storage_read", return_value={"success": True}) as mock_read:
            result = storage_tool.lambda_handler(event, _make_context("storage_read"))
            mock_read.assert_called_once_with(event)
            assert result["success"] is True

    def test_routes_to_storage_write(self):
        event = {"session_id": "s1", "filename": "f.txt", "content": "data"}
        with patch.object(storage_tool, "storage_write", return_value={"success": True}) as mock_write:
            result = storage_tool.lambda_handler(event, _make_context("storage_write"))
            mock_write.assert_called_once_with(event)
            assert result["success"] is True

    def test_unknown_tool_returns_error(self):
        result = storage_tool.lambda_handler({}, _make_context("unknown_tool"))
        assert result["success"] is False
        assert "Unknown tool" in result["error"]


class TestStorageRead:
    @patch.object(storage_tool, "s3")
    def test_success(self, mock_s3):
        mock_obj = MagicMock()
        mock_obj.get.return_value = {"Body": MagicMock(read=MagicMock(return_value=b"file content"))}
        mock_s3.Bucket.return_value.Object.return_value = mock_obj

        result = storage_tool.storage_read({"session_id": "sess-1", "filename": "report.txt"})

        assert result["success"] is True
        assert result["content"] == "file content"
        assert result["key"] == "sess-1/report.txt"
        assert result["size_bytes"] == len(b"file content")

    def test_missing_session_id(self):
        result = storage_tool.storage_read({"filename": "report.txt"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    def test_missing_filename(self):
        result = storage_tool.storage_read({"session_id": "sess-1"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    @patch.object(storage_tool, "s3")
    def test_s3_client_error(self, mock_s3):
        mock_obj = MagicMock()
        mock_obj.get.side_effect = ClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")
        mock_s3.Bucket.return_value.Object.return_value = mock_obj

        result = storage_tool.storage_read({"session_id": "sess-1", "filename": "missing.txt"})

        assert result["success"] is False
        assert result["error_code"] == "NoSuchKey"


class TestStorageWrite:
    @patch.object(storage_tool, "s3")
    def test_success(self, mock_s3):
        mock_bucket = MagicMock()
        mock_s3.Bucket.return_value = mock_bucket

        result = storage_tool.storage_write({"session_id": "sess-1", "filename": "out.txt", "content": "hello"})

        assert result["success"] is True
        assert result["key"] == "sess-1/out.txt"
        assert result["size_bytes"] == len(b"hello")
        mock_bucket.put_object.assert_called_once()

    def test_missing_params(self):
        result = storage_tool.storage_write({"session_id": "sess-1", "filename": "out.txt"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    @patch.object(storage_tool, "s3")
    def test_s3_client_error(self, mock_s3):
        mock_s3.Bucket.return_value.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}, "PutObject"
        )

        result = storage_tool.storage_write({"session_id": "sess-1", "filename": "out.txt", "content": "data"})

        assert result["success"] is False
        assert result["error_code"] == "AccessDenied"


class TestFilenameValidation:
    """Tests that invalid filenames are rejected by storage_read/storage_write."""

    def test_read_rejects_path_traversal(self):
        result = storage_tool.storage_read({"session_id": "s1", "filename": "../../etc/passwd"})
        assert result["success"] is False
        assert "path traversal" in result["error"].lower()

    def test_write_rejects_path_traversal(self):
        result = storage_tool.storage_write({"session_id": "s1", "filename": "../secret.txt", "content": "data"})
        assert result["success"] is False
        assert "path traversal" in result["error"].lower()

    def test_read_rejects_forward_slash(self):
        result = storage_tool.storage_read({"session_id": "s1", "filename": "foo/bar.txt"})
        assert result["success"] is False
        assert "path traversal" in result["error"].lower()

    def test_write_rejects_backslash(self):
        result = storage_tool.storage_write({"session_id": "s1", "filename": "foo\\bar.txt", "content": "data"})
        assert result["success"] is False
        assert "path traversal" in result["error"].lower()

    def test_read_rejects_null_bytes(self):
        result = storage_tool.storage_read({"session_id": "s1", "filename": "file\x00.txt"})
        assert result["success"] is False
        assert "null bytes" in result["error"].lower()

    def test_write_rejects_special_characters(self):
        result = storage_tool.storage_write({"session_id": "s1", "filename": "file@name.txt", "content": "data"})
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()
