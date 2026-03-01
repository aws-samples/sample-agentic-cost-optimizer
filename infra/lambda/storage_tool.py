"""Storage Lambda handler for AgentCore Gateway.

Handles storage_read and storage_write tool calls routed via Gateway.
Event contains inputSchema properties directly. Tool name from context.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")

s3 = boto3.resource("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DELIMITER = "___"


def _create_error_response(error_message):
    return {
        "success": False,
        "error": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _validate_filename(filename: str) -> str | None:
    """Validate filename against path traversal. Returns error message or None."""
    if "\x00" in filename:
        return "Filename contains null bytes"
    if ".." in filename or "/" in filename or "\\" in filename:
        return "Filename contains path traversal characters"
    if not SAFE_FILENAME_RE.match(filename):
        return "Filename contains invalid characters. Allowed: a-z, A-Z, 0-9, '.', '_', '-'"
    return None


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")

    original_tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
    tool_name = original_tool_name[original_tool_name.index(DELIMITER) + len(DELIMITER) :]

    if tool_name == "storage_read":
        return storage_read(event)
    elif tool_name == "storage_write":
        return storage_write(event)
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def storage_read(event):
    session_id = event.get("session_id", "")
    filename = event.get("filename", "")
    timestamp = datetime.now(timezone.utc).isoformat()

    if not session_id or not filename:
        return _create_error_response("Missing required parameters: session_id, filename")

    filename_error = _validate_filename(filename)
    if filename_error:
        return _create_error_response(filename_error)

    key = f"{session_id}/{filename}"

    try:
        obj = s3.Bucket(BUCKET_NAME).Object(key)
        content = obj.get()["Body"].read().decode("utf-8")
        size_bytes = len(content.encode("utf-8"))
        s3_uri = f"s3://{BUCKET_NAME}/{key}"

        return {
            "success": True,
            "content": content,
            "s3_uri": s3_uri,
            "bucket": BUCKET_NAME,
            "key": key,
            "size_bytes": size_bytes,
            "timestamp": timestamp,
        }
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        return {
            "success": False,
            "error": f"S3 ClientError: {error_code} - {error_message}",
            "bucket": BUCKET_NAME,
            "key": key,
            "error_code": error_code,
            "timestamp": timestamp,
        }


def storage_write(event):
    session_id = event.get("session_id", "")
    filename = event.get("filename", "")
    content = event.get("content", "")
    timestamp = datetime.now(timezone.utc).isoformat()

    if not session_id or not filename or not content:
        return _create_error_response("Missing required parameters: session_id, filename, content")

    filename_error = _validate_filename(filename)
    if filename_error:
        return _create_error_response(filename_error)

    key = f"{session_id}/{filename}"
    content_bytes = content.encode("utf-8")
    size_bytes = len(content_bytes)

    try:
        s3.Bucket(BUCKET_NAME).put_object(Key=key, Body=content_bytes, ContentType="text/plain; charset=utf-8")
        s3_uri = f"s3://{BUCKET_NAME}/{key}"

        return {
            "success": True,
            "s3_uri": s3_uri,
            "bucket": BUCKET_NAME,
            "key": key,
            "size_bytes": size_bytes,
            "timestamp": timestamp,
        }
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        return {
            "success": False,
            "error": f"S3 ClientError: {error_code} - {error_message}",
            "bucket": BUCKET_NAME,
            "key": key,
            "error_code": error_code,
            "timestamp": timestamp,
        }
