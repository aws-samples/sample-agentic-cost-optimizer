import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import boto3

from .event_statuses import EventStatus

logger = logging.getLogger(__name__)


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

    Raises:
        ValueError: If required fields are empty or status is invalid
        Exception: If DynamoDB operation fails (table not found, permission denied, etc.)

    Note:
        Events are automatically deleted via DynamoDB TTL.
        Journaling is required infrastructure - errors will propagate to caller.
    """
    # Validate required fields
    if not session_id or not isinstance(session_id, str):
        raise ValueError("session_id must be a non-empty string")

    if not table_name or not isinstance(table_name, str):
        raise ValueError("table_name must be a non-empty string")

    # Validate status against allowed values
    valid_statuses = {
        EventStatus.SESSION_INITIATED,
        EventStatus.AGENT_INVOCATION_STARTED,
        EventStatus.AGENT_INVOCATION_SUCCEEDED,
        EventStatus.AGENT_INVOCATION_FAILED,
        EventStatus.AGENT_RUNTIME_INVOKE_STARTED,
        EventStatus.AGENT_RUNTIME_INVOKE_FAILED,
        EventStatus.AGENT_BACKGROUND_TASK_STARTED,
        EventStatus.AGENT_BACKGROUND_TASK_COMPLETED,
        EventStatus.AGENT_BACKGROUND_TASK_FAILED,
    }

    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(valid_statuses))}")

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
            "sessionId": session_id,
            "eventId": event_id,
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
        logger.error(f"Failed to record event - Session: {session_id}, Status: {status}, Error: {str(e)}")
        raise
