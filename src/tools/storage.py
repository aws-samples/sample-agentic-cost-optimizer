"""
S3 Storage Tool for Cost Optimization Agent

Provides S3 file writing capabilities with automatic session-based path management.
Simplifies S3 operations by handling boto3 complexity internally.

Environment Variables:
- S3_BUCKET_NAME: Target S3 bucket for file storage
- AWS_REGION: AWS region (defaults to "us-east-1")
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError
from strands import ToolContext, tool

# Initialize S3 resource at module level
s3 = boto3.resource("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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

    # Validate required parameters
    if not filename:
        error_msg = "Missing required parameter: filename"
        logger.error(f"--> Storage validation failed - {error_msg}")
        return {"success": False, "error": error_msg, "timestamp": timestamp}

    if not content:
        error_msg = "Missing required parameter: content"
        logger.error(f"--> Storage validation failed - {error_msg}")
        return {"success": False, "error": error_msg, "timestamp": timestamp}

    # Retrieve session_id from invocation state
    session_id = tool_context.invocation_state.get("session_id")
    if not session_id:
        error_msg = "Session ID not found in invocation state"
        logger.error(f"--> Storage configuration error - {error_msg}")
        return {"success": False, "error": error_msg, "timestamp": timestamp}

    # Retrieve bucket name from environment variable
    bucket_name = os.environ.get("S3_BUCKET_NAME")
    if not bucket_name:
        error_msg = "S3_BUCKET_NAME environment variable not set"
        logger.error(f"--> Storage configuration error - {error_msg}")
        return {"success": False, "error": error_msg, "timestamp": timestamp}

    logger.info(f"--> Storage tool invoked - Session: {session_id}, File: {filename}")

    # Construct S3 key using pattern: {session_id}/{filename}
    key = f"{session_id}/{filename}"
    logger.debug(f"--> Constructed S3 key: {key}")

    # Encode content as UTF-8 bytes
    content_bytes = content.encode("utf-8")
    size_bytes = len(content_bytes)

    try:
        # Get S3 bucket object
        bucket = s3.Bucket(bucket_name)

        # Write to S3 with put_object
        bucket.put_object(Key=key, Body=content_bytes, ContentType="text/plain")

        # Construct S3 URI
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
def storage(filename: str, content: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Write text content to S3 with automatic session-based path management.

    This tool provides a simple interface for saving text files to S3, automatically
    managing file paths using the session ID from the invocation context. The tool
    handles all boto3 S3 operations internally and provides structured responses
    with success/error status.

    Args:
        filename: Name of the file to write (e.g., "cost_report.txt", "evidence.txt")
        content: Text content to write to the file
        tool_context: Strands context providing invocation state with session_id

    Returns:
        Dictionary with operation results:
        - On success: {"success": True, "s3_uri": "s3://...", "bucket": "...",
                      "key": "...", "size_bytes": 123, "timestamp": "..."}
        - On error: {"success": False, "error": "...", "timestamp": "..."}
    """
    return _write_to_s3(filename, content, tool_context)
