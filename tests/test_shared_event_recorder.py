"""Unit tests for the shared event_recorder module."""

import time
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from src.shared import EventStatus, record_event


class TestRecordEvent:
    """Test cases for the record_event function."""

    @patch("src.shared.event_recorder.boto3")
    def test_successful_event_recording(self, mock_boto3):
        """Test successful event recording to DynamoDB."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table

        record_event(
            session_id="session-123",
            status=EventStatus.AGENT_INVOCATION_STARTED,
            table_name="test-table",
            ttl_days=90,
            region_name="us-east-1",
        )

        mock_boto3.resource.assert_called_once_with("dynamodb", region_name="us-east-1")
        mock_dynamodb.Table.assert_called_once_with("test-table")
        mock_table.put_item.assert_called_once()

        call_args = mock_table.put_item.call_args[1]
        assert call_args["Item"]["PK"] == "SESSION#session-123"
        assert call_args["Item"]["status"] == EventStatus.AGENT_INVOCATION_STARTED
        assert "SK" in call_args["Item"]
        assert "createdAt" in call_args["Item"]
        assert "ttlSeconds" in call_args["Item"]

        # Verify TTL is approximately 90 days from now (allow 1 second tolerance)
        expected_ttl = int(time.time()) + (90 * 24 * 60 * 60)
        assert abs(call_args["Item"]["ttlSeconds"] - expected_ttl) <= 1

    @patch("src.shared.event_recorder.boto3")
    def test_event_recording_with_error_message(self, mock_boto3):
        """Test event recording with an error message."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table

        record_event(
            session_id="session-123",
            status=EventStatus.AGENT_INVOCATION_FAILED,
            table_name="test-table",
            error_message="Connection timeout",
        )

        call_args = mock_table.put_item.call_args[1]
        assert call_args["Item"]["errorMessage"] == "Connection timeout"

    @patch("src.shared.event_recorder.boto3")
    def test_event_recording_uses_env_region(self, mock_boto3):
        """Test that region is read from environment when not provided."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table

        with patch.dict("os.environ", {"AWS_REGION": "eu-west-1"}):
            record_event(
                session_id="session-123",
                status=EventStatus.SESSION_INITIATED,
                table_name="test-table",
            )

        mock_boto3.resource.assert_called_once_with("dynamodb", region_name="eu-west-1")

    @patch("src.shared.event_recorder.boto3")
    def test_event_recording_uses_default_region(self, mock_boto3):
        """Test that default region is used when not provided and not in env."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table

        with patch.dict("os.environ", {}, clear=True):
            record_event(
                session_id="session-123",
                status=EventStatus.SESSION_INITIATED,
                table_name="test-table",
            )

        # Should use default us-east-1
        mock_boto3.resource.assert_called_once_with("dynamodb", region_name="us-east-1")

    @patch("src.shared.event_recorder.boto3")
    def test_event_recording_handles_dynamodb_error(self, mock_boto3):
        """Test that DynamoDB errors are caught and logged without crashing."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Rate exceeded"}},
            "PutItem",
        )

        # Should not raise exception
        record_event(
            session_id="session-123",
            status=EventStatus.AGENT_INVOCATION_STARTED,
            table_name="test-table",
        )

    @patch("src.shared.event_recorder.boto3")
    def test_event_recording_handles_generic_exception(self, mock_boto3):
        """Test that generic exceptions are caught and logged without crashing."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.put_item.side_effect = Exception("Unexpected error")

        # Should not raise exception
        record_event(
            session_id="session-123",
            status=EventStatus.AGENT_INVOCATION_STARTED,
            table_name="test-table",
        )

    @patch("src.shared.event_recorder.boto3")
    def test_event_recording_handles_table_not_found(self, mock_boto3):
        """Test that ResourceNotFoundException is caught and logged."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}}, "PutItem"
        )

        # Should not raise exception
        record_event(
            session_id="session-123",
            status=EventStatus.AGENT_INVOCATION_STARTED,
            table_name="test-table",
        )

    @patch("src.shared.event_recorder.boto3")
    def test_custom_ttl_days(self, mock_boto3):
        """Test that custom TTL days are respected."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table

        record_event(
            session_id="session-123",
            status=EventStatus.SESSION_INITIATED,
            table_name="test-table",
            ttl_days=30,
        )

        call_args = mock_table.put_item.call_args[1]
        expected_ttl = int(time.time()) + (30 * 24 * 60 * 60)
        assert abs(call_args["Item"]["ttlSeconds"] - expected_ttl) <= 1
