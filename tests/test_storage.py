"""Unit tests for the storage tool."""

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Import the storage tool function
from src.tools.storage import storage


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext with session_id."""
    context = MagicMock()
    context.invocation_state = {"session_id": "test-session-123"}
    return context


@pytest.fixture
def mock_s3_bucket():
    """Create a mock S3 bucket."""
    bucket = MagicMock()
    bucket.put_object = MagicMock()
    return bucket


@pytest.fixture(autouse=True)
def setup_env():
    """Set up environment variables for tests."""
    os.environ["S3_BUCKET_NAME"] = "test-bucket"
    yield
    if "S3_BUCKET_NAME" in os.environ:
        del os.environ["S3_BUCKET_NAME"]


class TestStorageTool:
    """Tests for the storage tool main function."""

    @patch("src.tools.storage.s3")
    def test_write_to_s3_success(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Test storage tool writes to S3 successfully."""
        mock_s3.Bucket.return_value = mock_s3_bucket

        result = storage(
            action="write",
            filename="report.txt",
            content="Analysis results",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["s3_uri"] == "s3://test-bucket/test-session-123/report.txt"
        assert result["size_bytes"] == len("Analysis results".encode("utf-8"))
        mock_s3_bucket.put_object.assert_called_once()

    @patch("src.tools.storage.s3")
    def test_read_from_s3_success(self, mock_s3, mock_tool_context):
        """Test storage tool reads from S3 successfully."""
        mock_bucket = MagicMock()
        mock_object = MagicMock()
        mock_body = MagicMock()

        test_content = "Stored analysis data"
        mock_body.read.return_value = test_content.encode("utf-8")
        mock_object.get.return_value = {"Body": mock_body}
        mock_bucket.Object.return_value = mock_object
        mock_s3.Bucket.return_value = mock_bucket

        result = storage(
            action="read",
            filename="analysis.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["content"] == test_content
        assert result["s3_uri"] == "s3://test-bucket/test-session-123/analysis.txt"

    def test_invalid_action(self, mock_tool_context):
        """Test storage tool with invalid action."""
        result = storage(
            action="delete",
            filename="test.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Invalid action 'delete'" in result["error"]
        assert "Must be 'read' or 'write'" in result["error"]

    def test_read_missing_filename(self, mock_tool_context):
        """Test storage tool read fails with missing filename."""
        result = storage(
            action="read",
            filename="",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Missing required parameter: filename" in result["error"]

    def test_read_missing_session_id(self):
        """Test storage tool read fails with missing session_id."""
        context = MagicMock()
        context.invocation_state = {}

        result = storage(
            action="read",
            filename="test.txt",
            tool_context=context,
        )

        assert result["success"] is False
        assert "Session ID not found" in result["error"]

    @patch("src.tools.storage.s3")
    def test_read_file_not_found(self, mock_s3, mock_tool_context):
        """Test storage tool read fails when file doesn't exist."""
        mock_bucket = MagicMock()
        mock_object = MagicMock()

        error_response = {
            "Error": {
                "Code": "NoSuchKey",
                "Message": "The specified key does not exist.",
            }
        }
        mock_object.get.side_effect = ClientError(error_response, "GetObject")
        mock_bucket.Object.return_value = mock_object
        mock_s3.Bucket.return_value = mock_bucket

        result = storage(
            action="read",
            filename="missing.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "NoSuchKey" in result["error"]
        assert result["error_code"] == "NoSuchKey"


class TestStorageSuccess:
    """Tests for successful storage operations."""

    @patch("src.tools.storage.s3")
    def test_successful_file_write(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Test successful file write with valid parameters."""
        mock_s3.Bucket.return_value = mock_s3_bucket

        result = storage(
            action="write",
            filename="cost_report.txt",
            content="Test report content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["s3_uri"] == "s3://test-bucket/test-session-123/cost_report.txt"
        assert result["bucket"] == "test-bucket"
        assert result["key"] == "test-session-123/cost_report.txt"
        assert result["size_bytes"] == len("Test report content".encode("utf-8"))
        assert "timestamp" in result

        mock_s3.Bucket.assert_called_once_with("test-bucket")
        mock_s3_bucket.put_object.assert_called_once()
        call_args = mock_s3_bucket.put_object.call_args
        assert call_args.kwargs["Key"] == "test-session-123/cost_report.txt"
        assert call_args.kwargs["Body"] == b"Test report content"
        assert call_args.kwargs["ContentType"] == "text/plain"


class TestStorageMissingConfiguration:
    """Tests for missing configuration scenarios."""

    def test_missing_session_id(self):
        """Test with missing session_id in invocation_state."""
        context = MagicMock()
        context.invocation_state = {}

        result = storage(
            action="write",
            filename="test.txt",
            content="content",
            tool_context=context,
        )

        assert result["success"] is False
        assert "Session ID not found" in result["error"]
        assert "timestamp" in result


class TestStorageValidation:
    """Tests for parameter validation."""

    def test_missing_filename(self, mock_tool_context):
        """Test with missing filename parameter."""
        result = storage(
            action="write",
            filename="",
            content="content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Missing required parameter: filename" in result["error"]

    def test_missing_content(self, mock_tool_context):
        """Test with missing content parameter."""
        result = storage(
            action="write",
            filename="test.txt",
            content="",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Missing required parameter: content" in result["error"]


class TestStorageWriteErrors:
    """Tests for S3 write error handling."""

    @patch("src.tools.storage.s3")
    def test_write_fails_with_s3_error(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Test storage tool write fails with S3 error."""
        error_response = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "Access Denied",
            }
        }
        mock_s3_bucket.put_object.side_effect = ClientError(error_response, "PutObject")
        mock_s3.Bucket.return_value = mock_s3_bucket

        result = storage(
            action="write",
            filename="test.txt",
            content="content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "AccessDenied" in result["error"]
        assert result["error_code"] == "AccessDenied"

    @patch("src.tools.storage.s3")
    def test_write_fails_with_generic_exception(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Test storage tool write fails with generic exception."""
        mock_s3_bucket.put_object.side_effect = Exception("Network error")
        mock_s3.Bucket.return_value = mock_s3_bucket

        result = storage(
            action="write",
            filename="test.txt",
            content="content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Unexpected error" in result["error"]
        assert "Network error" in result["error"]


class TestStorageReadErrors:
    """Tests for S3 read error handling."""

    @patch("src.tools.storage.s3")
    def test_read_fails_with_s3_error(self, mock_s3, mock_tool_context):
        """Test storage tool read fails with S3 error."""
        mock_bucket = MagicMock()
        mock_object = MagicMock()

        error_response = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "Access Denied",
            }
        }
        mock_object.get.side_effect = ClientError(error_response, "GetObject")
        mock_bucket.Object.return_value = mock_object
        mock_s3.Bucket.return_value = mock_bucket

        result = storage(
            action="read",
            filename="test.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "AccessDenied" in result["error"]
        assert result["error_code"] == "AccessDenied"

    @patch("src.tools.storage.s3")
    def test_read_fails_with_generic_exception(self, mock_s3, mock_tool_context):
        """Test storage tool read fails with generic exception."""
        mock_bucket = MagicMock()
        mock_object = MagicMock()

        mock_object.get.side_effect = Exception("Network timeout")
        mock_bucket.Object.return_value = mock_object
        mock_s3.Bucket.return_value = mock_bucket

        result = storage(
            action="read",
            filename="test.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Unexpected error" in result["error"]
        assert "Network timeout" in result["error"]
