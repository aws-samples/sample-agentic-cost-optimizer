"""Unit tests for the storage tool."""

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Import the internal storage functions directly - don't have the @tool decorator
from src.tools.storage import _read_from_s3, _write_to_s3


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


class TestStorageSuccess:
    """Tests for successful storage operations."""

    @patch("src.tools.storage.s3")
    def test_successful_file_write(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Test successful file write with valid parameters."""
        mock_s3.Bucket.return_value = mock_s3_bucket

        result = _write_to_s3(
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

        # Verify S3 operations
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

        result = _write_to_s3(
            filename="test.txt",
            content="content",
            tool_context=context,
        )

        assert result["success"] is False
        assert "Session ID not found" in result["error"]
        assert "timestamp" in result

    def test_missing_bucket_name(self, mock_tool_context):
        """Test with missing S3_BUCKET_NAME environment variable."""
        del os.environ["S3_BUCKET_NAME"]

        result = _write_to_s3(
            filename="test.txt",
            content="content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "S3_BUCKET_NAME environment variable not set" in result["error"]
        assert "timestamp" in result


class TestStorageValidation:
    """Tests for parameter validation."""

    def test_missing_filename(self, mock_tool_context):
        """Test with missing filename parameter."""
        result = _write_to_s3(
            filename="",
            content="content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Missing required parameter: filename" in result["error"]

    def test_missing_content(self, mock_tool_context):
        """Test with missing content parameter."""
        result = _write_to_s3(
            filename="test.txt",
            content="",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Missing required parameter: content" in result["error"]


class TestStorageS3Errors:
    """Tests for S3 error handling."""

    @patch("src.tools.storage.s3")
    def test_no_such_bucket_error(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Test S3 NoSuchBucket error scenario."""
        error_response = {
            "Error": {
                "Code": "NoSuchBucket",
                "Message": "The specified bucket does not exist",
            }
        }
        mock_s3_bucket.put_object.side_effect = ClientError(error_response, "PutObject")
        mock_s3.Bucket.return_value = mock_s3_bucket

        result = _write_to_s3(
            filename="test.txt",
            content="content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "NoSuchBucket" in result["error"]
        assert result["error_code"] == "NoSuchBucket"
        assert result["bucket"] == "test-bucket"
        assert result["key"] == "test-session-123/test.txt"

    @patch("src.tools.storage.s3")
    def test_access_denied_error(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Test S3 AccessDenied error scenario."""
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        mock_s3_bucket.put_object.side_effect = ClientError(error_response, "PutObject")
        mock_s3.Bucket.return_value = mock_s3_bucket

        result = _write_to_s3(
            filename="test.txt",
            content="content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "AccessDenied" in result["error"]
        assert result["error_code"] == "AccessDenied"

    @patch("src.tools.storage.s3")
    def test_generic_exception(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Test generic exception handling."""
        mock_s3_bucket.put_object.side_effect = Exception("Unexpected error")
        mock_s3.Bucket.return_value = mock_s3_bucket

        result = _write_to_s3(
            filename="test.txt",
            content="content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Unexpected error" in result["error"]
        assert result["bucket"] == "test-bucket"
        assert result["key"] == "test-session-123/test.txt"


class TestStorageKeyConstruction:
    """Tests for S3 key construction."""

    @patch("src.tools.storage.s3")
    def test_key_format(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Verify correct key format: {session_id}/{filename}."""
        mock_s3.Bucket.return_value = mock_s3_bucket

        result = _write_to_s3(
            filename="report.txt",
            content="content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["key"] == "test-session-123/report.txt"

    @patch("src.tools.storage.s3")
    def test_various_filename_formats(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Test with various filename formats."""
        mock_s3.Bucket.return_value = mock_s3_bucket

        filenames = [
            "simple.txt",
            "with-dashes.txt",
            "with_underscores.txt",
            "with.multiple.dots.txt",
        ]

        for filename in filenames:
            result = _write_to_s3(
                filename=filename,
                content="content",
                tool_context=mock_tool_context,
            )

            assert result["success"] is True
            assert result["key"] == f"test-session-123/{filename}"


class TestStorageContentEncoding:
    """Tests for content encoding."""

    @patch("src.tools.storage.s3")
    def test_utf8_encoding(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Verify UTF-8 encoding applied to content."""
        mock_s3.Bucket.return_value = mock_s3_bucket

        content = "Test content with special chars: é, ñ, 中文"
        result = _write_to_s3(
            filename="test.txt",
            content=content,
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["size_bytes"] == len(content.encode("utf-8"))

        # Verify put_object called with UTF-8 encoded bytes
        call_args = mock_s3_bucket.put_object.call_args
        assert call_args.kwargs["Body"] == content.encode("utf-8")

    @patch("src.tools.storage.s3")
    def test_content_type_text_plain(self, mock_s3, mock_tool_context, mock_s3_bucket):
        """Verify ContentType set to 'text/plain'."""
        mock_s3.Bucket.return_value = mock_s3_bucket

        result = _write_to_s3(
            filename="test.txt",
            content="content",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True

        # Verify ContentType
        call_args = mock_s3_bucket.put_object.call_args
        assert call_args.kwargs["ContentType"] == "text/plain"


class TestStorageReadSuccess:
    """Tests for successful storage read operations."""

    @patch("src.tools.storage.s3")
    def test_successful_file_read(self, mock_s3, mock_tool_context):
        """Test successful file read with valid parameters."""
        mock_bucket = MagicMock()
        mock_object = MagicMock()
        mock_body = MagicMock()

        # Mock the S3 response
        test_content = "Test analysis content"
        mock_body.read.return_value = test_content.encode("utf-8")
        mock_object.get.return_value = {"Body": mock_body}
        mock_bucket.Object.return_value = mock_object
        mock_s3.Bucket.return_value = mock_bucket

        result = _read_from_s3(
            filename="analysis.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["content"] == test_content
        assert result["s3_uri"] == "s3://test-bucket/test-session-123/analysis.txt"
        assert result["bucket"] == "test-bucket"
        assert result["key"] == "test-session-123/analysis.txt"
        assert result["size_bytes"] == len(test_content.encode("utf-8"))
        assert "timestamp" in result

        # Verify S3 operations
        mock_s3.Bucket.assert_called_once_with("test-bucket")
        mock_bucket.Object.assert_called_once_with("test-session-123/analysis.txt")
        mock_object.get.assert_called_once()

    @patch("src.tools.storage.s3")
    def test_read_large_content(self, mock_s3, mock_tool_context):
        """Test reading large content from S3."""
        mock_bucket = MagicMock()
        mock_object = MagicMock()
        mock_body = MagicMock()

        # Create large content
        large_content = "x" * 10000
        mock_body.read.return_value = large_content.encode("utf-8")
        mock_object.get.return_value = {"Body": mock_body}
        mock_bucket.Object.return_value = mock_object
        mock_s3.Bucket.return_value = mock_bucket

        result = _read_from_s3(
            filename="large_file.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["content"] == large_content
        assert result["size_bytes"] == 10000

    @patch("src.tools.storage.s3")
    def test_read_utf8_content(self, mock_s3, mock_tool_context):
        """Test reading UTF-8 encoded content with special characters."""
        mock_bucket = MagicMock()
        mock_object = MagicMock()
        mock_body = MagicMock()

        content = "Content with special chars: é, ñ, 中文, emoji 🎉"
        mock_body.read.return_value = content.encode("utf-8")
        mock_object.get.return_value = {"Body": mock_body}
        mock_bucket.Object.return_value = mock_object
        mock_s3.Bucket.return_value = mock_bucket

        result = _read_from_s3(
            filename="utf8_test.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is True
        assert result["content"] == content


class TestStorageReadMissingFile:
    """Tests for reading missing files."""

    @patch("src.tools.storage.s3")
    def test_read_nonexistent_file(self, mock_s3, mock_tool_context):
        """Test reading a file that doesn't exist (NoSuchKey error)."""
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

        result = _read_from_s3(
            filename="missing.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "NoSuchKey" in result["error"]
        assert result["error_code"] == "NoSuchKey"
        assert result["bucket"] == "test-bucket"
        assert result["key"] == "test-session-123/missing.txt"
        assert "timestamp" in result

    @patch("src.tools.storage.s3")
    def test_read_from_nonexistent_bucket(self, mock_s3, mock_tool_context):
        """Test reading from a bucket that doesn't exist."""
        mock_bucket = MagicMock()
        mock_object = MagicMock()

        error_response = {
            "Error": {
                "Code": "NoSuchBucket",
                "Message": "The specified bucket does not exist",
            }
        }
        mock_object.get.side_effect = ClientError(error_response, "GetObject")
        mock_bucket.Object.return_value = mock_object
        mock_s3.Bucket.return_value = mock_bucket

        result = _read_from_s3(
            filename="test.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "NoSuchBucket" in result["error"]
        assert result["error_code"] == "NoSuchBucket"


class TestStorageReadErrorHandling:
    """Tests for S3 read error handling."""

    @patch("src.tools.storage.s3")
    def test_read_access_denied(self, mock_s3, mock_tool_context):
        """Test S3 AccessDenied error during read."""
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

        result = _read_from_s3(
            filename="test.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "AccessDenied" in result["error"]
        assert result["error_code"] == "AccessDenied"

    @patch("src.tools.storage.s3")
    def test_read_generic_client_error(self, mock_s3, mock_tool_context):
        """Test generic ClientError during read."""
        mock_bucket = MagicMock()
        mock_object = MagicMock()

        error_response = {
            "Error": {
                "Code": "InternalError",
                "Message": "We encountered an internal error. Please try again.",
            }
        }
        mock_object.get.side_effect = ClientError(error_response, "GetObject")
        mock_bucket.Object.return_value = mock_object
        mock_s3.Bucket.return_value = mock_bucket

        result = _read_from_s3(
            filename="test.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "InternalError" in result["error"]
        assert result["error_code"] == "InternalError"

    @patch("src.tools.storage.s3")
    def test_read_generic_exception(self, mock_s3, mock_tool_context):
        """Test generic exception handling during read."""
        mock_bucket = MagicMock()
        mock_object = MagicMock()

        mock_object.get.side_effect = Exception("Network timeout")
        mock_bucket.Object.return_value = mock_object
        mock_s3.Bucket.return_value = mock_bucket

        result = _read_from_s3(
            filename="test.txt",
            tool_context=mock_tool_context,
        )

        assert result["success"] is False
        assert "Unexpected error" in result["error"]
        assert "Network timeout" in result["error"]
        assert result["bucket"] == "test-bucket"
        assert result["key"] == "test-session-123/test.txt"
