"""
DynamoDB Data Store Recorder for Multi-Agent Context Passing

Provides low-level data storage and retrieval operations for passing analysis results
and other data between agents in a multi-agent workflow.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import boto3

logger = logging.getLogger(__name__)


def write_data(
    session_id: str,
    data_key: str,
    data_content: str,
    table_name: str,
    ttl_days: int = 90,
    region_name: Optional[str] = None,
) -> None:
    """Write data to DynamoDB Data Store Table.

    Args:
        session_id: The session ID for the workflow
        data_key: Key identifier for the data (e.g., "ANALYSIS_RESULTS")
        data_content: The actual data content to store
        table_name: DynamoDB table name for data storage
        ttl_days: Number of days before data expires (default: 90)
        region_name: AWS region for DynamoDB (default: from AWS_REGION env var or us-east-1)

    Raises:
        ValueError: If required fields are empty
        Exception: If DynamoDB operation fails (table not found, permission denied, etc.)
    """
    if not session_id or not isinstance(session_id, str):
        raise ValueError("session_id must be a non-empty string")

    if not data_key or not isinstance(data_key, str):
        raise ValueError("data_key must be a non-empty string")

    if not data_content or not isinstance(data_content, str):
        raise ValueError("data_content must be a non-empty string")

    if not table_name or not isinstance(table_name, str):
        raise ValueError("table_name must be a non-empty string")

    try:
        region = region_name or os.environ.get("AWS_REGION", "us-east-1")

        dynamodb = boto3.resource("dynamodb", region_name=region)
        table = dynamodb.Table(table_name)

        now = datetime.now(timezone.utc)
        timestamp = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        ttl_seconds = int(now.timestamp()) + (ttl_days * 24 * 60 * 60)

        item = {
            "PK": f"SESSION#{session_id}",
            "SK": f"DATA#{data_key}",
            "sessionId": session_id,
            "dataKey": data_key,
            "dataContent": data_content,
            "createdAt": timestamp,
            "ttlSeconds": ttl_seconds,
        }

        table.put_item(Item=item)

        logger.info(f"Successfully wrote data - Session: {session_id}, Key: {data_key}")

    except Exception as e:
        logger.error(f"Failed to write data - Session: {session_id}, Key: {data_key}, Error: {str(e)}")
        raise


def read_data(
    session_id: str,
    data_key: str,
    table_name: str,
    region_name: Optional[str] = None,
) -> str:
    """Read data from DynamoDB Data Store Table.

    Args:
        session_id: The session ID for the workflow
        data_key: Key identifier for the data (e.g., "ANALYSIS_RESULTS")
        table_name: DynamoDB table name for data storage
        region_name: AWS region for DynamoDB (default: from AWS_REGION env var or us-east-1)

    Returns:
        The data content as a string

    Raises:
        ValueError: If required fields are empty or data not found
        Exception: If DynamoDB operation fails (table not found, permission denied, etc.)
    """
    if not session_id or not isinstance(session_id, str):
        raise ValueError("session_id must be a non-empty string")

    if not data_key or not isinstance(data_key, str):
        raise ValueError("data_key must be a non-empty string")

    if not table_name or not isinstance(table_name, str):
        raise ValueError("table_name must be a non-empty string")

    try:
        region = region_name or os.environ.get("AWS_REGION", "us-east-1")

        dynamodb = boto3.resource("dynamodb", region_name=region)
        table = dynamodb.Table(table_name)

        response = table.get_item(
            Key={
                "PK": f"SESSION#{session_id}",
                "SK": f"DATA#{data_key}",
            }
        )

        if "Item" not in response:
            raise ValueError(f"Data not found for key: {data_key}")

        item = response["Item"]
        data_content = item.get("dataContent", "")

        logger.info(f"Successfully read data - Session: {session_id}, Key: {data_key}")

        return data_content

    except ValueError:
        # Re-raise ValueError for data not found
        raise
    except Exception as e:
        logger.error(f"Failed to read data - Session: {session_id}, Key: {data_key}, Error: {str(e)}")
        raise
