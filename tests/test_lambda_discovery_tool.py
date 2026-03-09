"""Unit tests for infra/lambda/lambda_discovery_tool.py."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).parent.parent / "infra" / "lambda"))
lambda_discovery_tool = importlib.import_module("lambda_discovery_tool")
sys.path.pop(0)


def _make_context(tool_name):
    return SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": f"LambdaDiscoveryTarget___{tool_name}"})
    )


class TestRouting:
    def test_routes_to_list_functions(self):
        with patch.object(
            lambda_discovery_tool,
            "lambda_list_functions",
            return_value={"success": True},
        ) as mock:
            result = lambda_discovery_tool.lambda_handler({}, _make_context("lambda_list_functions"))
            mock.assert_called_once_with({})
            assert result["success"] is True

    def test_routes_to_get_function(self):
        event = {"function_name": "my-fn"}
        with patch.object(lambda_discovery_tool, "lambda_get_function", return_value={"success": True}) as mock:
            result = lambda_discovery_tool.lambda_handler(event, _make_context("lambda_get_function"))
            mock.assert_called_once_with(event)
            assert result["success"] is True

    def test_routes_to_get_function_configuration(self):
        event = {"function_name": "my-fn"}
        with patch.object(
            lambda_discovery_tool,
            "lambda_get_function_configuration",
            return_value={"success": True},
        ) as mock:
            result = lambda_discovery_tool.lambda_handler(event, _make_context("lambda_get_function_configuration"))
            mock.assert_called_once_with(event)
            assert result["success"] is True

    def test_unknown_tool_returns_error(self):
        result = lambda_discovery_tool.lambda_handler({}, _make_context("unknown"))
        assert result["success"] is False
        assert "Unknown tool" in result["error"]


class TestListFunctions:
    @patch.object(lambda_discovery_tool, "lambda_client")
    def test_success(self, mock_client):
        mock_client.list_functions.return_value = {
            "Functions": [
                {
                    "FunctionName": "my-fn",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-fn",
                    "Runtime": "python3.12",
                    "MemorySize": 256,
                    "Timeout": 30,
                    "Architectures": ["arm64"],
                    "LastModified": "2026-01-01T00:00:00Z",
                    "CodeSize": 1024,
                    "EphemeralStorage": {"Size": 512},
                }
            ],
            "NextMarker": "token-abc",
        }

        result = lambda_discovery_tool.lambda_list_functions({})

        assert result["success"] is True
        assert len(result["functions"]) == 1
        assert result["functions"][0]["function_name"] == "my-fn"
        assert result["functions"][0]["runtime"] == "python3.12"
        assert result["functions"][0]["memory_size"] == 256
        assert result["functions"][0]["architecture"] == ["arm64"]
        assert result["next_marker"] == "token-abc"

    @patch.object(lambda_discovery_tool, "lambda_client")
    def test_pagination(self, mock_client):
        mock_client.list_functions.return_value = {"Functions": [], "NextMarker": ""}

        lambda_discovery_tool.lambda_list_functions({"marker": "prev-token"})

        mock_client.list_functions.assert_called_once_with(Marker="prev-token")

    @patch.object(lambda_discovery_tool, "lambda_client")
    def test_client_error(self, mock_client):
        mock_client.list_functions.side_effect = ClientError(
            {"Error": {"Code": "ServiceException", "Message": "Internal error"}},
            "ListFunctions",
        )

        result = lambda_discovery_tool.lambda_list_functions({})

        assert result["success"] is False
        assert "ServiceException" in result["error"]


class TestGetFunction:
    @patch.object(lambda_discovery_tool, "lambda_client")
    def test_success(self, mock_client):
        mock_client.get_function.return_value = {
            "Configuration": {
                "FunctionName": "my-fn",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-fn",
                "Runtime": "python3.12",
                "MemorySize": 256,
                "Timeout": 30,
                "Architectures": ["arm64"],
                "LastModified": "2026-01-01T00:00:00Z",
                "CodeSize": 1024,
                "Handler": "index.handler",
                "Environment": {"Variables": {"KEY": "val"}},
                "Layers": [{"Arn": "arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1"}],
                "EphemeralStorage": {"Size": 512},
            },
            "Concurrency": {"ReservedConcurrentExecutions": 10},
        }

        result = lambda_discovery_tool.lambda_get_function({"function_name": "my-fn"})

        assert result["success"] is True
        assert result["function_name"] == "my-fn"
        assert result["handler"] == "index.handler"
        assert result["environment"] == {"KEY": "val"}
        assert result["reserved_concurrent_executions"] == 10

    def test_missing_function_name(self):
        result = lambda_discovery_tool.lambda_get_function({})
        assert result["success"] is False
        assert "function_name" in result["error"]

    @patch.object(lambda_discovery_tool, "lambda_client")
    def test_client_error(self, mock_client):
        mock_client.get_function.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Function not found",
                }
            },
            "GetFunction",
        )

        result = lambda_discovery_tool.lambda_get_function({"function_name": "missing-fn"})

        assert result["success"] is False
        assert "ResourceNotFoundException" in result["error"]


class TestGetFunctionConfiguration:
    @patch.object(lambda_discovery_tool, "lambda_client")
    def test_success(self, mock_client):
        mock_client.get_function_configuration.return_value = {
            "FunctionName": "my-fn",
            "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-fn",
            "Runtime": "python3.12",
            "MemorySize": 256,
            "Timeout": 30,
            "Architectures": ["arm64"],
            "LastModified": "2026-01-01T00:00:00Z",
            "Handler": "index.handler",
            "Environment": {"Variables": {}},
            "Layers": [],
            "EphemeralStorage": {"Size": 512},
            "State": "Active",
            "LastUpdateStatus": "Successful",
        }

        result = lambda_discovery_tool.lambda_get_function_configuration({"function_name": "my-fn"})

        assert result["success"] is True
        assert result["function_name"] == "my-fn"
        assert result["state"] == "Active"
        assert result["last_update_status"] == "Successful"

    def test_missing_function_name(self):
        result = lambda_discovery_tool.lambda_get_function_configuration({})
        assert result["success"] is False
        assert "function_name" in result["error"]

    @patch.object(lambda_discovery_tool, "lambda_client")
    def test_client_error(self, mock_client):
        mock_client.get_function_configuration.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Function not found",
                }
            },
            "GetFunctionConfiguration",
        )

        result = lambda_discovery_tool.lambda_get_function_configuration({"function_name": "missing-fn"})

        assert result["success"] is False
        assert "ResourceNotFoundException" in result["error"]
