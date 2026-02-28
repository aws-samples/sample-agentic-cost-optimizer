"""Unit tests for infra/lambda/pricing_tool.py."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).parent.parent / "infra" / "lambda"))
pricing_tool = importlib.import_module("pricing_tool")
sys.path.pop(0)


def _make_context(tool_name):
    return SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": f"PricingTarget___{tool_name}"})
    )


class TestRouting:
    def test_routes_to_get_products(self):
        with patch.object(pricing_tool, "pricing_get_products", return_value={"success": True}) as mock:
            result = pricing_tool.lambda_handler({}, _make_context("pricing_get_products"))
            mock.assert_called_once_with({})
            assert result["success"] is True

    def test_unknown_tool_returns_error(self):
        result = pricing_tool.lambda_handler({}, _make_context("unknown"))
        assert result["success"] is False
        assert "Unknown tool" in result["error"]


class TestGetProducts:
    @patch.object(pricing_tool, "pricing_client")
    def test_success(self, mock_client):
        price_item = {"product": {"sku": "ABC123"}, "terms": {}}
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_item)]}

        result = pricing_tool.pricing_get_products({"service_code": "AmazonEC2"})

        assert result["success"] is True
        assert result["service_code"] == "AmazonEC2"
        assert len(result["price_list"]) == 1
        assert result["price_list"][0]["product"]["sku"] == "ABC123"

    @patch.object(pricing_tool, "pricing_client")
    def test_with_filters(self, mock_client):
        mock_client.get_products.return_value = {"PriceList": []}

        pricing_tool.pricing_get_products(
            {
                "service_code": "AmazonEC2",
                "filters": [{"field": "instanceType", "value": "t3.micro"}],
            }
        )

        call_kwargs = mock_client.get_products.call_args[1]
        assert call_kwargs["Filters"] == [{"Type": "TERM_MATCH", "Field": "instanceType", "Value": "t3.micro"}]

    def test_missing_service_code(self):
        result = pricing_tool.pricing_get_products({})
        assert result["success"] is False
        assert "service_code" in result["error"]

    @patch.object(pricing_tool, "pricing_client")
    def test_client_error(self, mock_client):
        mock_client.get_products.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameterException", "Message": "Bad filter"}},
            "GetProducts",
        )

        result = pricing_tool.pricing_get_products({"service_code": "AmazonEC2"})

        assert result["success"] is False
        assert "InvalidParameterException" in result["error"]
