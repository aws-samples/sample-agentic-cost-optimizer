"""
S3 Storage Tool for Cost Optimization Agent

Provides S3 file writing capabilities with automatic session-based path management.
Simplifies S3 operations by handling boto3 complexity internally.

Environment Variables:
- S3_BUCKET_NAME: Target S3 bucket for file storage
- AWS_REGION: AWS region (defaults to "us-east-1")
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError
from strands import ToolContext, tool

from src.shared.config import config

s3 = boto3.resource("s3", region_name=config.aws_region)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _read_from_s3(filename: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Internal function to read text content from S3 with session-based path management.

    Args:
        filename: Name of the file to read (e.g., "analysis.txt")
        tool_context: Strands context providing invocation state

    Returns:
        Dictionary with operation results including success status, content, or error details
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    if not filename:
        error_msg = "Missing required parameter: filename"
        logger.error(f"--> Storage validation failed - {error_msg}")
        return {"success": False, "error": error_msg, "timestamp": timestamp}

    session_id = tool_context.invocation_state.get("session_id")
    if not session_id:
        error_msg = "Session ID not found in invocation state"
        logger.error(f"--> Storage configuration error - {error_msg}")
        return {"success": False, "error": error_msg, "timestamp": timestamp}

    bucket_name = config.s3_bucket_name
    key = f"{session_id}/{filename}"
    logger.debug(f"--> Reading from S3 key: {key}")

    try:
        bucket = s3.Bucket(bucket_name)
        obj = bucket.Object(key)
        content = obj.get()["Body"].read().decode("utf-8")
        size_bytes = len(content.encode("utf-8"))
        s3_uri = f"s3://{bucket_name}/{key}"

        logger.debug(f"--> Successfully read {size_bytes} bytes from {s3_uri}")

        return {
            "success": True,
            "content": content,
            "s3_uri": s3_uri,
            "bucket": bucket_name,
            "key": key,
            "size_bytes": size_bytes,
            "timestamp": timestamp,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        error_msg = f"S3 ClientError: {error_code} - {error_message}"
        logger.error(
            f"--> S3 read failed - Bucket: {bucket_name}, Key: {key}, " f"Error: {error_code} - {error_message}"
        )
        return {
            "success": False,
            "error": error_msg,
            "bucket": bucket_name,
            "key": key,
            "error_code": error_code,
            "timestamp": timestamp,
        }

    except Exception as e:
        error_msg = f"Unexpected error reading from S3: {str(e)}"
        logger.error(f"--> S3 read failed - Bucket: {bucket_name}, Key: {key}, " f"Error: {str(e)}")
        return {
            "success": False,
            "error": error_msg,
            "bucket": bucket_name,
            "key": key,
            "timestamp": timestamp,
        }


def _write_to_s3(filename: str, content: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Internal function to write text content to S3 with session-based path management.

    Args:
        filename: Name of the file to write (e.g., "cost_report.txt")
        content: Text content to write to the file
        tool_context: Strands context providing invocation state

    Returns:
        Dictionary with operation results including success status, S3 URI, or error details
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    if not filename:
        error_msg = "Missing required parameter: filename"
        logger.error(f"--> Storage validation failed - {error_msg}")
        return {"success": False, "error": error_msg, "timestamp": timestamp}

    if not content:
        error_msg = "Missing required parameter: content"
        logger.error(f"--> Storage validation failed - {error_msg}")
        return {"success": False, "error": error_msg, "timestamp": timestamp}

    session_id = tool_context.invocation_state.get("session_id")
    if not session_id:
        error_msg = "Session ID not found in invocation state"
        logger.error(f"--> Storage configuration error - {error_msg}")
        return {"success": False, "error": error_msg, "timestamp": timestamp}

    bucket_name = config.s3_bucket_name

    logger.info(f"--> Storage tool invoked - Session: {session_id}, File: {filename}")

    key = f"{session_id}/{filename}"
    logger.debug(f"--> Constructed S3 key: {key}")

    content_bytes = content.encode("utf-8")
    size_bytes = len(content_bytes)

    try:
        bucket = s3.Bucket(bucket_name)
        bucket.put_object(Key=key, Body=content_bytes, ContentType="text/plain")
        s3_uri = f"s3://{bucket_name}/{key}"

        logger.info(f"--> Successfully wrote {size_bytes} bytes to {s3_uri}")

        return {
            "success": True,
            "s3_uri": s3_uri,
            "bucket": bucket_name,
            "key": key,
            "size_bytes": size_bytes,
            "timestamp": timestamp,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        error_msg = f"S3 ClientError: {error_code} - {error_message}"
        logger.error(
            f"--> S3 write failed - Bucket: {bucket_name}, Key: {key}, " f"Error: {error_code} - {error_message}"
        )
        return {
            "success": False,
            "error": error_msg,
            "bucket": bucket_name,
            "key": key,
            "error_code": error_code,
            "timestamp": timestamp,
        }

    except Exception as e:
        error_msg = f"Unexpected error writing to S3: {str(e)}"
        logger.error(f"--> S3 write failed - Bucket: {bucket_name}, Key: {key}, " f"Error: {str(e)}")
        return {
            "success": False,
            "error": error_msg,
            "bucket": bucket_name,
            "key": key,
            "timestamp": timestamp,
        }


@tool(context=True)
def storage(action: str, filename: str, tool_context: ToolContext, content: str = "") -> Dict[str, Any]:
    """
    Read or write text content to S3 with automatic session-based path management.

    This tool provides a simple interface for reading and writing text files to S3,
    automatically managing file paths using the session ID from the invocation context.

    Args:
        action: Action to perform ("read" or "write")
        filename: Name of the file (e.g., "analysis.txt", "report.txt")
        tool_context: Strands context providing invocation state with session_id
        content: Text content to write (required for write action)

    Returns:
        Dictionary with operation results:
        - On read success: {"success": True, "content": "...", "s3_uri": "...", ...}
        - On write success: {"success": True, "s3_uri": "...", "size_bytes": 123, ...}
        - On error: {"success": False, "error": "...", "timestamp": "..."}
    """
    if action == "read":
        return _read_from_s3(filename, tool_context)
    elif action == "write":
        return _write_to_s3(filename, content, tool_context)
    else:
        timestamp = datetime.now(timezone.utc).isoformat()
        return {
            "success": False,
            "error": f"Invalid action '{action}'. Must be 'read' or 'write'",
            "timestamp": timestamp,
        }
