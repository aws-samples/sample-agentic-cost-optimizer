import os
from datetime import datetime, timezone
from typing import Optional

import boto3


def record_metadata(
    session_id: str,
    table_name: str,
    ttl_days: int = 90,
    region_name: Optional[str] = None,
) -> None:
    """Record session metadata in DynamoDB for workflow tracking.

    Args:
        session_id: The session ID for the workflow
        table_name: DynamoDB table name for journaling
        ttl_days: Number of days before metadata expires (default: 90)
        region_name: AWS region for DynamoDB (default: from AWS_REGION env var or us-east-1)

    Raises:
        ValueError: If required fields are empty

    Note:
        Errors during metadata recording are logged but do not raise exceptions
        to prevent metadata recording failures from crashing the caller.
        Metadata is automatically deleted via DynamoDB TTL.
    """
    # Validate required fields
    if not session_id or not isinstance(session_id, str):
        raise ValueError("session_id must be a non-empty string")

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
            "SK": f"METADATA#{timestamp}",
            "sessionId": session_id,
            "createdAt": timestamp,
            "ttlSeconds": ttl_seconds,
        }

        # Use put_item without condition since there should only be one metadata record per session
        table.put_item(Item=item)

    except Exception as e:
        # Log the error but don't crash the caller
        print(f"Failed to record metadata - Session: {session_id}, Error: {str(e)}")
