import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import boto3


def record_event(
    session_id: str,
    status: str,
    table_name: str,
    ttl_days: int = 90,
    error_message: Optional[str] = None,
    region_name: Optional[str] = None,
) -> None:
    """Record an event in DynamoDB for workflow tracking.

    Args:
        session_id: The session ID for the workflow
        status: The event status type (use EventStatus constants)
        table_name: DynamoDB table name for journaling
        ttl_days: Number of days before event expires (default: 90)
        error_message: Optional error message for failure events
        region_name: AWS region for DynamoDB (default: from AWS_REGION env var or us-east-1)

    Note:
        Errors during event recording are logged but do not raise exceptions
        to prevent event recording failures from crashing the caller.
        Events are automatically deleted via DynamoDB TTL.
    """
    try:
        region = region_name or os.environ.get("AWS_REGION", "us-east-1")

        dynamodb = boto3.resource("dynamodb", region_name=region)
        table = dynamodb.Table(table_name)

        now = datetime.now(timezone.utc)
        timestamp = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        event_id = str(uuid.uuid4())
        ttl_seconds = int(now.timestamp()) + (ttl_days * 24 * 60 * 60)

        item = {
            "PK": f"SESSION#{session_id}",
            "SK": f"EVENT#{timestamp}#{event_id}",
            "createdAt": timestamp,
            "status": status,
            "ttlSeconds": ttl_seconds,
        }

        if error_message:
            item["errorMessage"] = error_message

        # Prevent duplicate events from race conditions or retries
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
        )

    except Exception as e:
        # Log the error but don't crash the caller
        print(f"Failed to record event - Session: {session_id}, Status: {status}, Error: {str(e)}")
