"""Lambda function to initialize session by recording metadata and SESSION_INITIATED event."""

import os

from aws_lambda_powertools import Logger

from src.shared import EventStatus, record_event, record_metadata

logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "session-initializer"))


def handler(event, context):
    """
    Lambda handler to record SESSION_INITIATED event.

    Expected input:
    {
        "session_id": "unique-session-id"
    }

    Returns:
    {
        "statusCode": 200,
        "session_id": "unique-session-id"
    }
    """
    try:
        session_id = event.get("session_id")
        if not session_id:
            raise ValueError("session_id is required in event payload")

        table_name = os.environ.get("JOURNAL_TABLE_NAME")
        if not table_name:
            raise ValueError("JOURNAL_TABLE_NAME environment variable is required")
        ttl_days = int(os.environ.get("TTL_DAYS", "90"))

        logger.info(f"Recording SESSION_INITIATED event for session: {session_id}")

        record_metadata(session_id=session_id, table_name=table_name, ttl_days=ttl_days)

        # Record the SESSION_INITIATED event
        record_event(
            session_id=session_id,
            status=EventStatus.SESSION_INITIATED,
            table_name=table_name,
            ttl_days=ttl_days,
        )

        logger.info(f"Successfully recorded SESSION_INITIATED event for session: {session_id}")

        return {
            "statusCode": 200,
            "session_id": session_id,
        }

    except Exception as e:
        logger.error(f"Failed to initialize session: {str(e)}", exc_info=True)
        raise
