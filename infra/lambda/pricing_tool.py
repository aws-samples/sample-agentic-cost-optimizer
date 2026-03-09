"""Pricing tool for AgentCore Gateway.

Handles pricing_get_products tool call routed via Gateway.
Pricing API is only available in us-east-1.
"""

import json
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

pricing_client = boto3.client("pricing", region_name="us-east-1")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DELIMITER = "___"


def _create_error_response(error_message):
    return {
        "success": False,
        "error": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")

    original_tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
    tool_name = original_tool_name[original_tool_name.index(DELIMITER) + len(DELIMITER) :]

    if tool_name == "pricing_get_products":
        return pricing_get_products(event)
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def pricing_get_products(event):
    service_code = event.get("service_code", "")
    filters = event.get("filters", [])

    if not service_code:
        return _create_error_response("Missing required parameter: service_code")

    try:
        params = {
            "ServiceCode": service_code,
            "FormatVersion": "aws_v1",
        }
        if filters:
            params["Filters"] = [
                {
                    "Type": "TERM_MATCH",
                    "Field": f["field"],
                    "Value": f["value"],
                }
                for f in filters
            ]

        response = pricing_client.get_products(**params)
        price_list = [json.loads(item) for item in response.get("PriceList", [])]

        return {
            "success": True,
            "service_code": service_code,
            "price_list": price_list,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"Pricing GetProducts error: {error_code} - {error_message}")
        return _create_error_response(f"{error_code}: {error_message}")
