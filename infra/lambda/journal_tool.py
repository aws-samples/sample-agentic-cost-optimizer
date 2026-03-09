"""Journal Lambda handler for AgentCore Gateway.

Handles journal_start_task and journal_complete_task tool calls routed via Gateway.
Event contains inputSchema properties directly. Tool name from context.
"""

import json
import logging
import os
from datetime import datetime, timezone

from shared import EventStatus, record_event

JOURNAL_TABLE_NAME = os.environ.get("JOURNAL_TABLE_NAME", "")
TTL_DAYS = int(os.environ.get("TTL_DAYS", "90"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DELIMITER = "___"


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")

    original_tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
    tool_name = original_tool_name[original_tool_name.index(DELIMITER) + len(DELIMITER) :]

    if tool_name == "journal_start_task":
        return journal_start_task(event)
    elif tool_name == "journal_complete_task":
        return journal_complete_task(event)
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def _create_error_response(error_message):
    return {
        "success": False,
        "error": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def journal_start_task(event):
    session_id = event.get("session_id", "")
    phase_name = event.get("phase_name", "")
    timestamp = datetime.now(timezone.utc).isoformat()

    if not session_id or not phase_name:
        return _create_error_response("Missing required parameters: session_id, phase_name")

    if not JOURNAL_TABLE_NAME:
        return _create_error_response("JOURNAL_TABLE_NAME not set")

    try:
        phase_normalized = phase_name.upper().replace(" ", "_")
        event_status = f"TASK_{phase_normalized}_{EventStatus.TASK_STARTED}"

        record_event(
            session_id=session_id,
            status=event_status,
            table_name=JOURNAL_TABLE_NAME,
            ttl_days=TTL_DAYS,
            region_name=AWS_REGION,
        )

        return {
            "success": True,
            "session_id": session_id,
            "phase_name": phase_name,
            "status": "IN_PROGRESS",
            "timestamp": timestamp,
        }
    except Exception as e:
        return _create_error_response(f"Unexpected error: {str(e)}")


def journal_complete_task(event):
    session_id = event.get("session_id", "")
    phase_name = event.get("phase_name", "")
    status = event.get("status", EventStatus.TASK_COMPLETED)
    error_message = event.get("error_message")
    timestamp = datetime.now(timezone.utc).isoformat()

    if not session_id or not phase_name:
        return _create_error_response("Missing required parameters: session_id, phase_name")

    if not JOURNAL_TABLE_NAME:
        return _create_error_response("JOURNAL_TABLE_NAME not set")

    valid_statuses = [EventStatus.TASK_COMPLETED, EventStatus.TASK_FAILED]
    if status not in valid_statuses:
        return _create_error_response(f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}")

    try:
        phase_normalized = phase_name.upper().replace(" ", "_")
        event_status = f"TASK_{phase_normalized}_{status}"

        record_event(
            session_id=session_id,
            status=event_status,
            table_name=JOURNAL_TABLE_NAME,
            ttl_days=TTL_DAYS,
            error_message=error_message,
            region_name=AWS_REGION,
        )

        return {
            "success": True,
            "session_id": session_id,
            "phase_name": phase_name,
            "status": status,
            "timestamp": timestamp,
        }
    except Exception as e:
        return _create_error_response(f"Unexpected error: {str(e)}")
