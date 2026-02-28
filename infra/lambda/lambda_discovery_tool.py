"""Lambda Discovery tool for AgentCore Gateway.

Handles lambda_list_functions, lambda_get_function, and lambda_get_function_configuration
tool calls routed via Gateway.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

lambda_client = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "us-east-1"))

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

    if tool_name == "lambda_list_functions":
        return lambda_list_functions(event)
    elif tool_name == "lambda_get_function":
        return lambda_get_function(event)
    elif tool_name == "lambda_get_function_configuration":
        return lambda_get_function_configuration(event)
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def lambda_list_functions(event):
    marker = event.get("marker", "")
    try:
        params = {}
        if marker:
            params["Marker"] = marker
        response = lambda_client.list_functions(**params)
        functions = []
        for fn in response.get("Functions", []):
            functions.append(
                {
                    "function_name": fn.get("FunctionName"),
                    "function_arn": fn.get("FunctionArn"),
                    "runtime": fn.get("Runtime"),
                    "memory_size": fn.get("MemorySize"),
                    "timeout": fn.get("Timeout"),
                    "architecture": fn.get("Architectures", ["x86_64"]),
                    "last_modified": fn.get("LastModified"),
                    "code_size": fn.get("CodeSize"),
                    "ephemeral_storage": fn.get("EphemeralStorage", {}).get("Size"),
                }
            )
        return {
            "success": True,
            "functions": functions,
            "next_marker": response.get("NextMarker", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"Lambda ListFunctions error: {error_code} - {error_message}")
        return _create_error_response(f"{error_code}: {error_message}")


def lambda_get_function(event):
    function_name = event.get("function_name", "")
    if not function_name:
        return _create_error_response("Missing required parameter: function_name")
    try:
        response = lambda_client.get_function(FunctionName=function_name)
        config = response.get("Configuration", {})
        concurrency = response.get("Concurrency", {})
        return {
            "success": True,
            "function_name": config.get("FunctionName"),
            "function_arn": config.get("FunctionArn"),
            "runtime": config.get("Runtime"),
            "memory_size": config.get("MemorySize"),
            "timeout": config.get("Timeout"),
            "architecture": config.get("Architectures", ["x86_64"]),
            "last_modified": config.get("LastModified"),
            "code_size": config.get("CodeSize"),
            "handler": config.get("Handler"),
            "environment": config.get("Environment", {}).get("Variables", {}),
            "layers": [layer.get("Arn") for layer in config.get("Layers", [])],
            "ephemeral_storage": config.get("EphemeralStorage", {}).get("Size"),
            "reserved_concurrent_executions": concurrency.get("ReservedConcurrentExecutions"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"Lambda GetFunction error: {error_code} - {error_message}")
        return _create_error_response(f"{error_code}: {error_message}")


def lambda_get_function_configuration(event):
    function_name = event.get("function_name", "")
    if not function_name:
        return _create_error_response("Missing required parameter: function_name")
    try:
        config = lambda_client.get_function_configuration(FunctionName=function_name)
        return {
            "success": True,
            "function_name": config.get("FunctionName"),
            "function_arn": config.get("FunctionArn"),
            "runtime": config.get("Runtime"),
            "memory_size": config.get("MemorySize"),
            "timeout": config.get("Timeout"),
            "architecture": config.get("Architectures", ["x86_64"]),
            "last_modified": config.get("LastModified"),
            "handler": config.get("Handler"),
            "environment": config.get("Environment", {}).get("Variables", {}),
            "layers": [layer.get("Arn") for layer in config.get("Layers", [])],
            "ephemeral_storage": config.get("EphemeralStorage", {}).get("Size"),
            "state": config.get("State"),
            "last_update_status": config.get("LastUpdateStatus"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"Lambda GetFunctionConfiguration error: {error_code} - {error_message}")
        return _create_error_response(f"{error_code}: {error_message}")
