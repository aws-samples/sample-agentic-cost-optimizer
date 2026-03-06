"""Unit tests for infra/lambda/cloudwatch_metrics_tool.py."""

import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).parent.parent / "infra" / "lambda"))
cloudwatch_metrics_tool = importlib.import_module("cloudwatch_metrics_tool")
sys.path.pop(0)


def _make_context(tool_name):
    return SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": f"CloudWatchMetricsTarget___{tool_name}"})
    )


class TestRouting:
    def test_routes_to_get_metric_statistics(self):
        with patch.object(
            cloudwatch_metrics_tool,
            "cloudwatch_get_metric_statistics",
            return_value={"success": True},
        ) as mock:
            result = cloudwatch_metrics_tool.lambda_handler({}, _make_context("cloudwatch_get_metric_statistics"))
            mock.assert_called_once_with({})
            assert result["success"] is True

    def test_routes_to_list_metrics(self):
        with patch.object(
            cloudwatch_metrics_tool,
            "cloudwatch_list_metrics",
            return_value={"success": True},
        ) as mock:
            result = cloudwatch_metrics_tool.lambda_handler({}, _make_context("cloudwatch_list_metrics"))
            mock.assert_called_once_with({})
            assert result["success"] is True

    def test_unknown_tool_returns_error(self):
        result = cloudwatch_metrics_tool.lambda_handler({}, _make_context("unknown"))
        assert result["success"] is False
        assert "Unknown tool" in result["error"]


class TestGetMetricStatistics:
    _valid_event = {
        "namespace": "AWS/Lambda",
        "metric_name": "Duration",
        "start_time": "2026-01-01T00:00:00Z",
        "end_time": "2026-01-02T00:00:00Z",
        "period": 300,
        "statistics": ["Average", "Maximum"],
    }

    @patch.object(cloudwatch_metrics_tool, "cloudwatch_client")
    def test_success(self, mock_client):
        mock_client.get_metric_statistics.return_value = {
            "Datapoints": [
                {
                    "Timestamp": datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc),
                    "Average": 150.5,
                    "Maximum": 300.0,
                },
                {
                    "Timestamp": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                    "Average": 100.0,
                    "Maximum": 200.0,
                },
            ]
        }

        result = cloudwatch_metrics_tool.cloudwatch_get_metric_statistics(self._valid_event)

        assert result["success"] is True
        assert result["namespace"] == "AWS/Lambda"
        assert len(result["datapoints"]) == 2
        assert result["datapoints"][0]["average"] == 100.0
        assert result["datapoints"][1]["average"] == 150.5

    @patch.object(cloudwatch_metrics_tool, "cloudwatch_client")
    def test_with_dimensions(self, mock_client):
        mock_client.get_metric_statistics.return_value = {"Datapoints": []}
        event = {
            **self._valid_event,
            "dimensions": [{"name": "FunctionName", "value": "my-fn"}],
        }

        cloudwatch_metrics_tool.cloudwatch_get_metric_statistics(event)

        call_kwargs = mock_client.get_metric_statistics.call_args[1]
        assert call_kwargs["Dimensions"] == [{"Name": "FunctionName", "Value": "my-fn"}]

    def test_missing_required_params(self):
        result = cloudwatch_metrics_tool.cloudwatch_get_metric_statistics({"namespace": "AWS/Lambda"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]

    @patch.object(cloudwatch_metrics_tool, "cloudwatch_client")
    def test_client_error(self, mock_client):
        mock_client.get_metric_statistics.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameterValue", "Message": "Bad period"}},
            "GetMetricStatistics",
        )

        result = cloudwatch_metrics_tool.cloudwatch_get_metric_statistics(self._valid_event)

        assert result["success"] is False
        assert "InvalidParameterValue" in result["error"]


class TestListMetrics:
    @patch.object(cloudwatch_metrics_tool, "cloudwatch_client")
    def test_success(self, mock_client):
        mock_client.list_metrics.return_value = {
            "Metrics": [
                {
                    "Namespace": "AWS/Lambda",
                    "MetricName": "Duration",
                    "Dimensions": [{"Name": "FunctionName", "Value": "my-fn"}],
                }
            ]
        }

        result = cloudwatch_metrics_tool.cloudwatch_list_metrics({})

        assert result["success"] is True
        assert len(result["metrics"]) == 1
        assert result["metrics"][0]["namespace"] == "AWS/Lambda"
        assert result["metrics"][0]["dimensions"][0]["name"] == "FunctionName"

    @patch.object(cloudwatch_metrics_tool, "cloudwatch_client")
    def test_with_filters(self, mock_client):
        mock_client.list_metrics.return_value = {"Metrics": []}

        cloudwatch_metrics_tool.cloudwatch_list_metrics({"namespace": "AWS/Lambda", "metric_name": "Duration"})

        call_kwargs = mock_client.list_metrics.call_args[1]
        assert call_kwargs["Namespace"] == "AWS/Lambda"
        assert call_kwargs["MetricName"] == "Duration"

    @patch.object(cloudwatch_metrics_tool, "cloudwatch_client")
    def test_client_error(self, mock_client):
        mock_client.list_metrics.side_effect = ClientError(
            {"Error": {"Code": "InternalServiceFault", "Message": "Service error"}},
            "ListMetrics",
        )

        result = cloudwatch_metrics_tool.cloudwatch_list_metrics({})

        assert result["success"] is False
        assert "InternalServiceFault" in result["error"]
