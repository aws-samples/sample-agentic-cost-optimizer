"""CloudWatch Logs tool for AgentCore Gateway.

Handles cloudwatch_start_query, cloudwatch_get_query_results, and cloudwatch_stop_query
tool calls routed via Gateway.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logs_client = boto3.client("logs", region_name=os.environ.get("AWS_REGION", "us-east-1"))

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

    if tool_name == "cloudwatch_start_query":
        return cloudwatch_start_query(event)
    elif tool_name == "cloudwatch_get_query_results":
        return cloudwatch_get_query_results(event)
    elif tool_name == "cloudwatch_stop_query":
        return cloudwatch_stop_query(event)
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def cloudwatch_start_query(event):
    log_group_name = event.get("log_group_name", "")
    query_string = event.get("query_string", "")
    start_time = event.get("start_time", 0)
    end_time = event.get("end_time", 0)

    if not all([log_group_name, query_string, start_time, end_time]):
        return _create_error_response("Missing required parameters: log_group_name, query_string, start_time, end_time")

    try:
        response = logs_client.start_query(
            logGroupName=log_group_name,
            startTime=int(start_time),
            endTime=int(end_time),
            queryString=query_string,
        )
        return {
            "success": True,
            "query_id": response["queryId"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"CloudWatch StartQuery error: {error_code} - {error_message}")
        return _create_error_response(f"{error_code}: {error_message}")


def cloudwatch_get_query_results(event):
    query_id = event.get("query_id", "")

    if not query_id:
        return _create_error_response("Missing required parameter: query_id")

    try:
        response = logs_client.get_query_results(queryId=query_id)
        results = []
        for row in response.get("results", []):
            result_row = {}
            for field in row:
                result_row[field["field"]] = field["value"]
            results.append(result_row)

        return {
            "success": True,
            "status": response.get("status"),
            "results": results,
            "statistics": response.get("statistics", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"CloudWatch GetQueryResults error: {error_code} - {error_message}")
        return _create_error_response(f"{error_code}: {error_message}")


def cloudwatch_stop_query(event):
    query_id = event.get("query_id", "")

    if not query_id:
        return _create_error_response("Missing required parameter: query_id")

    try:
        logs_client.stop_query(queryId=query_id)
        return {
            "success": True,
            "query_id": query_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"CloudWatch StopQuery error: {error_code} - {error_message}")
        return _create_error_response(f"{error_code}: {error_message}")
