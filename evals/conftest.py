"""Eval fixtures and tool factories."""

import json
import os

import pytest
from deepeval.models import AmazonBedrockModel
from deepeval.test_case import ToolCall
from strands import tool

from evals.mock_data import (
    MOCK_CLOUDWATCH_GET_METRIC_DATA,
    MOCK_CLOUDWATCH_METRIC_STATISTICS,
    MOCK_LAMBDA_FUNCTIONS,
    MOCK_LOGS_QUERY_RESULTS,
    MOCK_LOGS_START_QUERY,
    MOCK_PRICING_LAMBDA_COMPUTE,
    MOCK_PRICING_LAMBDA_REQUESTS,
)
from src.shared.constants import DEFAULT_AWS_REGION, DEFAULT_MODEL_ID

# Agent model - runs the actual workflow
AGENT_MODEL_ID = os.getenv("MODEL_ID", DEFAULT_MODEL_ID)
AWS_REGION = os.getenv("AWS_REGION", DEFAULT_AWS_REGION)

# Judge model - different family to avoid bias (Llama instead of Claude)
JUDGE_MODEL_ID = os.getenv("JUDGE_MODEL_ID", "us.meta.llama3-3-70b-instruct-v1:0")

FIXED_CURRENT_TIME = 1733011200  # 2024-12-01 00:00:00 UTC


class ToolCapture:
    """Captures tool calls for DeepEval evaluation."""

    def __init__(self):
        self.calls: list[ToolCall] = []
        self.written_files: dict[str, str] = {}  # For report agent to capture file contents

    def record(self, name: str, **kwargs):
        self.calls.append(ToolCall(name=name, input_parameters=kwargs))

    @property
    def names(self) -> list[str]:
        return [c.name for c in self.calls]

    def clear(self):
        self.calls = []
        self.written_files = {}


def create_journal_tool(capture: ToolCapture):
    """Create journal tool that captures invocations."""

    @tool
    def journal(action: str, phase_name: str = None, status: str = None, error_message: str = None) -> dict:
        """Track workflow phases."""
        capture.record("journal", action=action, phase_name=phase_name, status=status)
        return {"success": True, "session_id": "eval-session"}

    return journal


def create_time_tool(capture: ToolCapture):
    """Create current_time_unix_utc tool with fixed timestamp."""

    @tool
    def current_time_unix_utc() -> int:
        """Get current Unix timestamp in UTC."""
        capture.record("current_time_unix_utc")
        return FIXED_CURRENT_TIME

    return current_time_unix_utc


def create_calculator_tool(capture: ToolCapture):
    """Create calculator tool for arithmetic expressions."""

    @tool
    def calculator(expression: str) -> float:
        """Evaluate arithmetic expressions."""
        capture.record("calculator", expression=expression)
        result = eval(expression, {"__builtins__": {}}, {})
        return float(result)

    return calculator


def create_storage_tool(capture: ToolCapture, mock_read_content: str = None):
    """Create storage tool that captures read/write operations.

    Args:
        capture: ToolCapture instance to record calls
        mock_read_content: If provided, returns this content for read operations (for report agent)
    """

    @tool
    def storage(action: str, filename: str = None, content: str = None) -> dict:
        """Read/write files to S3 storage."""
        capture.record("storage", action=action, filename=filename)

        if action == "read":
            if mock_read_content and filename == "analysis.txt":
                return {"success": True, "content": mock_read_content}
            return {"success": False, "error": f"File not found: {filename}"}
        elif action == "write":
            capture.written_files[filename] = content
            return {"success": True, "s3_uri": f"s3://bucket/eval-session/{filename}"}
        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    return storage


def create_use_aws_tool(capture: ToolCapture):
    """Create use_aws tool with mock responses."""

    @tool
    def use_aws(service: str, action: str, **kwargs) -> dict:
        """Call AWS APIs."""
        params = kwargs
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], str):
            params = json.loads(kwargs["kwargs"])

        capture.record("use_aws", service=service, action=action, **params)

        # Lambda API
        if service == "lambda" and action == "list_functions":
            return MOCK_LAMBDA_FUNCTIONS

        # CloudWatch Metrics API
        if service == "cloudwatch":
            if action == "get_metric_data":
                return MOCK_CLOUDWATCH_GET_METRIC_DATA
            elif action == "get_metric_statistics":
                metric_name = params.get("MetricName", "")
                return MOCK_CLOUDWATCH_METRIC_STATISTICS.get(
                    metric_name, MOCK_CLOUDWATCH_METRIC_STATISTICS["Invocations"]
                )

        # CloudWatch Logs API
        if service == "logs":
            if action == "start_query":
                return MOCK_LOGS_START_QUERY
            elif action == "get_query_results":
                return MOCK_LOGS_QUERY_RESULTS

        # Pricing API
        if service == "pricing":
            if action == "get_products":
                filters = params.get("Filters", [])
                for f in filters:
                    if f.get("Field") == "group" and "Requests" in f.get("Value", ""):
                        return MOCK_PRICING_LAMBDA_REQUESTS
                return MOCK_PRICING_LAMBDA_COMPUTE

        return {"error": f"Not implemented: {service}.{action}"}

    return use_aws


@pytest.fixture
def capture():
    """Fresh tool capture for each test."""
    return ToolCapture()


@pytest.fixture
def judge_model():
    """Judge model for metrics evaluation (different family from agent)."""
    return AmazonBedrockModel(model_id=JUDGE_MODEL_ID, region_name=AWS_REGION)
