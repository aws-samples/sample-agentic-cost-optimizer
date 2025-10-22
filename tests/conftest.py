"""Shared fixtures for test suite."""

import sys
from unittest.mock import MagicMock

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
