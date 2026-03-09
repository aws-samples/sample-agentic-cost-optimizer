"""Unit tests for infra/lambda/cloudwatch_logs_tool.py."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).parent.parent / "infra" / "lambda"))
cloudwatch_logs_tool = importlib.import_module("cloudwatch_logs_tool")
sys.path.pop(0)


def _make_context(tool_name):
    return SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": f"CloudWatchLogsTarget___{tool_name}"})
    )


class TestRouting:
    def test_routes_to_start_query(self):
        with patch.object(
            cloudwatch_logs_tool,
            "cloudwatch_start_query",
            return_value={"success": True},
        ) as mock:
            result = cloudwatch_logs_tool.lambda_handler({}, _make_context("cloudwatch_start_query"))
            mock.assert_called_once_with({})
            assert result["success"] is True

    def test_routes_to_get_query_results(self):
        with patch.object(
            cloudwatch_logs_tool,
            "cloudwatch_get_query_results",
            return_value={"success": True},
        ) as mock:
            result = cloudwatch_logs_tool.lambda_handler({}, _make_context("cloudwatch_get_query_results"))
            mock.assert_called_once_with({})
            assert result["success"] is True

    def test_routes_to_stop_query(self):
        with patch.object(
            cloudwatch_logs_tool,
            "cloudwatch_stop_query",
            return_value={"success": True},
        ) as mock:
            result = cloudwatch_logs_tool.lambda_handler({}, _make_context("cloudwatch_stop_query"))
            mock.assert_called_once_with({})
            assert result["success"] is True

    def test_unknown_tool_returns_error(self):
        result = cloudwatch_logs_tool.lambda_handler({}, _make_context("unknown"))
        assert result["success"] is False
        assert "Unknown tool" in result["error"]


class TestStartQuery:
    _valid_event = {
        "log_group_name": "/aws/lambda/my-fn",
        "query_string": "fields @timestamp, @message | limit 20",
        "start_time": 1700000000,
        "end_time": 1700086400,
    }

    @patch.object(cloudwatch_logs_tool, "logs_client")
    def test_success(self, mock_client):
        mock_client.start_query.return_value = {"queryId": "query-abc-123"}

        result = cloudwatch_logs_tool.cloudwatch_start_query(self._valid_event)

        assert result["success"] is True
        assert result["query_id"] == "query-abc-123"
        mock_client.start_query.assert_called_once_with(
            logGroupName="/aws/lambda/my-fn",
            startTime=1700000000,
            endTime=1700086400,
            queryString="fields @timestamp, @message | limit 20",
        )

    def test_missing_required_params(self):
        result = cloudwatch_logs_tool.cloudwatch_start_query({"log_group_name": "/aws/lambda/my-fn"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    @patch.object(cloudwatch_logs_tool, "logs_client")
    def test_client_error(self, mock_client):
        mock_client.start_query.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Log group not found",
                }
            },
            "StartQuery",
        )

        result = cloudwatch_logs_tool.cloudwatch_start_query(self._valid_event)

        assert result["success"] is False
        assert "ResourceNotFoundException" in result["error"]


class TestGetQueryResults:
    @patch.object(cloudwatch_logs_tool, "logs_client")
    def test_success(self, mock_client):
        mock_client.get_query_results.return_value = {
            "status": "Complete",
            "results": [
                [
                    {"field": "@timestamp", "value": "2026-01-01 00:00:00"},
                    {"field": "@message", "value": "Hello world"},
                ]
            ],
            "statistics": {
                "recordsMatched": 1.0,
                "recordsScanned": 100.0,
                "bytesScanned": 5000.0,
            },
        }

        result = cloudwatch_logs_tool.cloudwatch_get_query_results({"query_id": "query-abc"})

        assert result["success"] is True
        assert result["status"] == "Complete"
        assert len(result["results"]) == 1
        assert result["results"][0]["@timestamp"] == "2026-01-01 00:00:00"
        assert result["results"][0]["@message"] == "Hello world"
        assert result["statistics"]["recordsMatched"] == 1.0

    def test_missing_query_id(self):
        result = cloudwatch_logs_tool.cloudwatch_get_query_results({})
        assert result["success"] is False
        assert "query_id" in result["error"]

    @patch.object(cloudwatch_logs_tool, "logs_client")
    def test_client_error(self, mock_client):
        mock_client.get_query_results.side_effect = ClientError(
            {
                "Error": {
                    "Code": "InvalidParameterException",
                    "Message": "Invalid query ID",
                }
            },
            "GetQueryResults",
        )

        result = cloudwatch_logs_tool.cloudwatch_get_query_results({"query_id": "bad-id"})

        assert result["success"] is False
        assert "InvalidParameterException" in result["error"]


class TestStopQuery:
    @patch.object(cloudwatch_logs_tool, "logs_client")
    def test_success(self, mock_client):
        result = cloudwatch_logs_tool.cloudwatch_stop_query({"query_id": "query-abc"})

        assert result["success"] is True
        assert result["query_id"] == "query-abc"
        mock_client.stop_query.assert_called_once_with(queryId="query-abc")

    def test_missing_query_id(self):
        result = cloudwatch_logs_tool.cloudwatch_stop_query({})
        assert result["success"] is False
        assert "query_id" in result["error"]

    @patch.object(cloudwatch_logs_tool, "logs_client")
    def test_client_error(self, mock_client):
        mock_client.stop_query.side_effect = ClientError(
            {
                "Error": {
                    "Code": "InvalidParameterException",
                    "Message": "Invalid query ID",
                }
            },
            "StopQuery",
        )

        result = cloudwatch_logs_tool.cloudwatch_stop_query({"query_id": "bad-id"})

        assert result["success"] is False
        assert "InvalidParameterException" in result["error"]
