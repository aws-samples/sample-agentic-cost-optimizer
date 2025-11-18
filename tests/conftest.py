"""Shared fixtures for test suite."""

import os
import sys
from functools import wraps
from unittest.mock import MagicMock

import pytest


def mock_tool_decorator(*args, **kwargs):
    """Mock @tool decorator by doing nothing."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# Set required environment variables before any imports
os.environ["S3_BUCKET_NAME"] = "test-bucket"
os.environ["JOURNAL_TABLE_NAME"] = "test-journal-table"
os.environ["AWS_REGION"] = "us-east-1"

# Mock all dependencies before any imports of src.agents.main
mock_app = MagicMock()
mock_app.entrypoint = lambda func: func  # Make decorator a no-op
mock_app.add_async_task = MagicMock(return_value="task-123")
mock_app.complete_async_task = MagicMock()
mock_app.get_current_ping_status = MagicMock(return_value=MagicMock(value="Healthy"))

# Create strands mock with tool decorator
mock_strands = MagicMock()
mock_strands.tool = mock_tool_decorator

mocks_to_apply = {
    "strands": mock_strands,
    "strands.models": MagicMock(),
    "strands_tools": MagicMock(),
    "bedrock_agentcore.runtime": MagicMock(BedrockAgentCoreApp=lambda: mock_app),
}

sys.modules.update(mocks_to_apply)


@pytest.fixture(autouse=True)
def _mock_background_task(monkeypatch):
    """Mock background_task to prevent coroutine warnings."""
    mock_bg = MagicMock(return_value=MagicMock())
    monkeypatch.setattr("src.agents.main.background_task", mock_bg)
