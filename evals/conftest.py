"""Eval configuration and shared fixtures."""

import os

import pytest
from deepeval.models import AmazonBedrockModel
from deepeval.test_case import ToolCall

from src.shared.constants import DEFAULT_AWS_REGION, DEFAULT_MODEL_ID

MODEL_ID = os.getenv("MODEL_ID", DEFAULT_MODEL_ID)
AWS_REGION = os.getenv("AWS_REGION", DEFAULT_AWS_REGION)

MOCK_LAMBDA_FUNCTIONS = {
    "Functions": [
        {
            "FunctionName": "payment-processor",
            "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:payment-processor",
            "Runtime": "python3.12",
            "MemorySize": 1024,
            "Timeout": 30,
            "Architectures": ["x86_64"],
            "LastModified": "2024-01-15T10:30:00.000+0000",
        },
        {
            "FunctionName": "order-handler",
            "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:order-handler",
            "Runtime": "python3.11",
            "MemorySize": 512,
            "Timeout": 15,
            "Architectures": ["arm64"],
            "LastModified": "2024-02-20T14:45:00.000+0000",
        },
    ]
}


class ToolCapture:
    """Captures tool calls for DeepEval evaluation."""

    def __init__(self):
        self.calls: list[ToolCall] = []

    def record(self, name: str, **kwargs):
        self.calls.append(ToolCall(name=name, input_parameters=kwargs))

    @property
    def names(self) -> list[str]:
        return [c.name for c in self.calls]

    def clear(self):
        self.calls = []


@pytest.fixture
def capture():
    """Fresh tool capture for each test."""
    return ToolCapture()


@pytest.fixture
def deepeval_model():
    """DeepEval model for metrics evaluation."""
    return AmazonBedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)
