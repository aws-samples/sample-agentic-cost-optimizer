"""Tests for shared record_metadata function."""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.shared import record_metadata


class TestRecordMetadata:
    """Test cases for record_metadata function."""

    @patch("src.shared.record_metadata.boto3")
    def test_successful_metadata_recording(self, mock_boto3):
        """Test successful metadata recording with all parameters."""
        mock_table = MagicMock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        record_metadata(
            session_id="session-123",
            table_name="test-table",
            ttl_days=90,
            region_name="us-west-2",
        )

        # Verify boto3 resource was created with correct region
        mock_boto3.resource.assert_called_once_with("dynamodb", region_name="us-west-2")

        # Verify table was accessed
        mock_boto3.resource.return_value.Table.assert_called_once_with("test-table")

        # Verify put_item was called
        assert mock_table.put_item.called
        call_args = mock_table.put_item.call_args[1]
        assert call_args["Item"]["PK"] == "SESSION#session-123"
        assert call_args["Item"]["SK"].startswith("METADATA#")
        assert "createdAt" in call_args["Item"]
        assert "ttlSeconds" in call_args["Item"]

    @patch.dict(os.environ, {"AWS_REGION": "eu-west-1"})
    @patch("src.shared.record_metadata.boto3")
    def test_metadata_recording_uses_env_region(self, mock_boto3):
        """Test that metadata recording uses AWS_REGION from environment when region_name not provided."""
        mock_table = MagicMock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        record_metadata(
            session_id="session-123",
            table_name="test-table",
        )

        mock_boto3.resource.assert_called_once_with("dynamodb", region_name="eu-west-1")

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.shared.record_metadata.boto3")
    def test_metadata_recording_uses_default_region(self, mock_boto3):
        """Test that metadata recording uses default region when no region specified."""
        mock_table = MagicMock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        record_metadata(
            session_id="session-123",
            table_name="test-table",
        )

        mock_boto3.resource.assert_called_once_with("dynamodb", region_name="us-east-1")

    @patch("src.shared.record_metadata.boto3")
    @patch("builtins.print")
    def test_metadata_recording_handles_dynamodb_error(self, mock_print, mock_boto3):
        """Test that DynamoDB errors are caught and logged."""
        mock_table = MagicMock()
        mock_table.put_item.side_effect = Exception("DynamoDB error")
        mock_boto3.resource.return_value.Table.return_value = mock_table

        # Should not raise exception
        record_metadata(
            session_id="session-123",
            table_name="test-table",
        )

        # Verify error was logged
        mock_print.assert_called_once()
        assert "Failed to record metadata" in mock_print.call_args[0][0]
        assert "session-123" in mock_print.call_args[0][0]

    @patch("src.shared.record_metadata.boto3")
    def test_custom_ttl_days(self, mock_boto3):
        """Test that custom TTL days are correctly calculated."""
        mock_table = MagicMock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        record_metadata(
            session_id="session-123",
            table_name="test-table",
            ttl_days=30,
        )

        call_args = mock_table.put_item.call_args[1]
        ttl_seconds = call_args["Item"]["ttlSeconds"]

        # Verify TTL is approximately 30 days from now (within 1 minute tolerance)
        now_seconds = int(datetime.now(timezone.utc).timestamp())
        expected_ttl = now_seconds + (30 * 24 * 60 * 60)
        assert abs(ttl_seconds - expected_ttl) < 60

    @patch("src.shared.record_metadata.boto3")
    def test_metadata_sk_format(self, mock_boto3):
        """Test that metadata SK includes timestamp."""
        mock_table = MagicMock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        record_metadata(
            session_id="session-456",
            table_name="test-table",
        )

        call_args = mock_table.put_item.call_args[1]
        assert call_args["Item"]["SK"].startswith("METADATA#")
        assert call_args["Item"]["PK"] == "SESSION#session-456"
        # Verify timestamp format in SK (should be ISO format)
        assert "T" in call_args["Item"]["SK"]
        assert "Z" in call_args["Item"]["SK"]


class TestRecordMetadataValidation:
    """Test cases for input validation in record_metadata function."""

    def test_empty_session_id_raises_error(self):
        """Test that empty session_id raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="session_id must be a non-empty string"):
            record_metadata(
                session_id="",
                table_name="test-table",
            )

    def test_none_session_id_raises_error(self):
        """Test that None session_id raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="session_id must be a non-empty string"):
            record_metadata(
                session_id=None,
                table_name="test-table",
            )

    def test_empty_table_name_raises_error(self):
        """Test that empty table_name raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="table_name must be a non-empty string"):
            record_metadata(
                session_id="session-123",
                table_name="",
            )

    def test_none_table_name_raises_error(self):
        """Test that None table_name raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="table_name must be a non-empty string"):
            record_metadata(
                session_id="session-123",
                table_name=None,
            )
