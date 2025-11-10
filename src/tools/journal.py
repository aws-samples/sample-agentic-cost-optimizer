"""
DynamoDB Journaling Tool for Cost Optimization Agent

Provides stateful session and task tracking with automatic ID management
through a single tool interface.

Environment Variables:
- JOURNAL_TABLE_NAME: DynamoDB table name for journaling Tasks and session.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from strands import ToolContext, tool

from src.shared import EventStatus, record_event


def _create_error_response(
    error_message: str,
    additional_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response = {
        "success": False,
        "error": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if additional_context:
        response.update(additional_context)
    return response


def _get_session_id(tool_context: ToolContext) -> Optional[str]:
    """Get session ID from context."""
    return tool_context.invocation_state.get("session_id")


def _get_table_name() -> Optional[str]:
    """Get table name from environment."""
    return os.environ.get("JOURNAL_TABLE_NAME", "")


def _create_timestamp_and_ttl() -> tuple[str, int]:
    """Create timestamp and TTL for DynamoDB items."""
    current_time = datetime.now(timezone.utc)
    timestamp = current_time.isoformat()
    ttl = int(current_time.timestamp()) + (30 * 24 * 60 * 60)
    return timestamp, ttl


def _start_task(phase_name: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Start tracking a new task/phase."""
    try:
        if not phase_name:
            return _create_error_response("phase_name is required")

        session_id = _get_session_id(tool_context)
        if not session_id:
            return _create_error_response(
                "No active session found. Call start_session() first.",
                {"error_type": "NO_SESSION"},
            )

        table_name = _get_table_name()
        if not table_name:
            return _create_error_response("JOURNAL_TABLE_NAME not set")

        timestamp, ttl = _create_timestamp_and_ttl()

        # Create immutable event with phase name appended to status
        event_status = f"{EventStatus.TASK_STARTED}_{phase_name.upper().replace(' ', '_')}"

        record_event(
            session_id=session_id,
            status=event_status,
            table_name=table_name,
            ttl_days=ttl // (24 * 60 * 60),
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
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


def _complete_task(
    phase_name: str,
    tool_context: ToolContext,
    status: str = EventStatus.TASK_COMPLETED,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Complete a task/phase and update its status."""
    try:
        if not phase_name:
            return _create_error_response("phase_name is required")

        session_id = _get_session_id(tool_context)
        if not session_id:
            return _create_error_response(
                "No active session found.",
                {"error_type": "NO_SESSION"},
            )

        table_name = _get_table_name()
        if not table_name:
            return _create_error_response("JOURNAL_TABLE_NAME not set")

        timestamp, ttl = _create_timestamp_and_ttl()

        # Map string status to EventStatus constants
        status_map = {
            "COMPLETED": EventStatus.TASK_COMPLETED,
            "FAILED": EventStatus.TASK_FAILED,
            "CANCELLED": EventStatus.TASK_CANCELLED,
            "SKIPPED": EventStatus.TASK_SKIPPED,
        }

        event_status_base = status_map.get(status, EventStatus.TASK_COMPLETED)

        # Append phase name to create final event status
        final_event_status = f"{event_status_base}_{phase_name.upper().replace(' ', '_')}"

        record_event(
            session_id=session_id,
            status=final_event_status,
            table_name=table_name,
            ttl_days=ttl // (24 * 60 * 60),
            error_message=error_message,
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
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


@tool(context=True)
def journal(
    action: str,
    tool_context: ToolContext,
    phase_name: Optional[str] = None,
    status: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    DynamoDB journaling tool for session and task tracking.

       Args:
           action: Action to perform ( start_task,
               complete_task)
           phase_name: Name of the task/phase (required for start_task and
               complete_task)
           status: Status for completion (BUSY, COMPLETED, FAILED)
           error_message: Optional error message for failed completions

       Returns:
           Dictionary with success status and operation results
    """

    # Validate action parameter
    valid_actions = ["start_task", "complete_task"]
    if action not in valid_actions:
        return _create_error_response(f"Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}")

    if action == "start_task":
        if not phase_name:
            return _create_error_response("phase_name is required for start_task action")
        return _start_task(phase_name, tool_context)
    elif action == "complete_task":
        if not phase_name:
            return _create_error_response("phase_name is required for complete_task action")

        # Validate status parameter
        valid_statuses = ["COMPLETED", "FAILED", "CANCELLED", "SKIPPED"]
        if status and status not in valid_statuses:
            return _create_error_response(f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}")

        return _complete_task(phase_name, tool_context, status or "COMPLETED", error_message)
    else:
        return _create_error_response(f"Unknown action: {action}")
