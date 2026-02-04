"""Shared fixtures for test suite."""

import os
import sys
from functools import wraps
from unittest.mock import MagicMock


def mock_tool_decorator(*args, **kwargs):
    """Mock @tool decorator that handles both @tool and @tool(context=True).

    This decorator supports two usage patterns:
    1. @tool - Direct decoration without arguments (e.g., time tools)
    2. @tool(context=True) - Decoration with arguments (e.g., journal, storage)
    """
    # Case 1: @tool (direct decoration, first arg is the function)
    if len(args) == 1 and callable(args[0]) and not kwargs:
        f = args[0]

        @wraps(f)
        def decorated_function(*func_args, **func_kwargs):
            return f(*func_args, **func_kwargs)

        return decorated_function

    # Case 2: @tool(context=True) (decorator with arguments)
    def decorator(f):
        @wraps(f)
        def decorated_function(*func_args, **func_kwargs):
            return f(*func_args, **func_kwargs)

        return decorated_function

    return decorator


# Set required environment variables before any imports
os.environ["S3_BUCKET_NAME"] = "test-bucket"
os.environ["JOURNAL_TABLE_NAME"] = "test-journal-table"
os.environ["AWS_REGION"] = "us-east-1"

# Mock all dependencies before any imports of src.agents.main
mock_app = MagicMock()
mock_app.entrypoint = lambda func: func  # Make decorator a no-op
mock_app.async_task = lambda func: func  # Make async_task decorator a no-op

# Create strands mock with tool decorator
mock_strands = MagicMock()
mock_strands.tool = mock_tool_decorator

mocks_to_apply = {
    "strands": mock_strands,
    "strands.models": MagicMock(),
    "strands.multiagent": MagicMock(),
    "strands_tools": MagicMock(),
    "bedrock_agentcore.runtime": MagicMock(BedrockAgentCoreApp=lambda: mock_app),
}

sys.modules.update(mocks_to_apply)
