"""Shared fixtures for test suite."""

import os
import sys
from unittest.mock import MagicMock

# Set required environment variables before any imports
os.environ["S3_BUCKET_NAME"] = "test-bucket"
os.environ["JOURNAL_TABLE_NAME"] = "test-journal-table"
# SESSION_ID is optional - only used as fallback for local dev
os.environ["AWS_REGION"] = "us-east-1"

# Mock all dependencies before any imports of src.agents.main
mock_app = MagicMock()
mock_app.entrypoint = lambda func: func  # Make decorator a no-op

mocks_to_apply = {
    "strands": MagicMock(),
    "strands.models": MagicMock(),
    "strands_tools": MagicMock(),
    "bedrock_agentcore.runtime": MagicMock(BedrockAgentCoreApp=lambda: mock_app),
}

sys.modules.update(mocks_to_apply)
