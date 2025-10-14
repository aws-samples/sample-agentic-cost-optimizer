"""
Unified DynamoDB Journaling Tool for Cost Optimization Agent

Provides stateful session and task tracking with automatic ID management through a single tool interface.

Environment Variables:
- JOURNAL_TABLE_NAME: DynamoDB table name for journaling Tasks and session.
"""

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from strands import tool, ToolContext


class TaskStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class SessionStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


dynamodb = boto3.client("dynamodb")

_session_cache: Dict[str, Any] = {
    "session_id": None,
    "start_time": None,
    "tasks": {},
}


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


def _start_session(tool_context: ToolContext) -> Dict[str, Any]:
    """Start a new journaling session using session_id from invocation state."""
    try:
        session_id = tool_context.invocation_state.get("session_id")
        if not session_id:
            return _create_error_response("session_id not found in invocation state")

        table_name = os.environ.get("JOURNAL_TABLE_NAME", "")
        if not table_name:
            return _create_error_response("JOURNAL_TABLE_NAME not set")

        current_time = datetime.now(timezone.utc)
        timestamp = current_time.isoformat()
        ttl = int(current_time.timestamp()) + (30 * 24 * 60 * 60)

        _session_cache["session_id"] = session_id
        _session_cache["start_time"] = timestamp
        _session_cache["tasks"] = {}

        try:
            item = {
                "session_id": {"S": session_id},
                "record_type": {"S": "SESSION"},
                "timestamp": {"S": timestamp},
                "status": {"S": "STARTED"},
                "start_time": {"S": timestamp},
                "ttl": {"N": str(ttl)},
            }
            dynamodb.put_item(TableName=table_name, Item=item)
        except ClientError as e:
            return _create_error_response(
                f"Failed to create session: {e.response['Error']['Code']}: {e.response['Error']['Message']}",
                {"session_id": session_id},
            )

        return {
            "success": True,
            "session_id": session_id,
            "start_time": timestamp,
            "status": "STARTED",
            "timestamp": timestamp,
        }
    except Exception as e:
        return _create_error_response(f"Unexpected error: {str(e)}")


def _start_task(phase_name: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Start tracking a new task/phase."""
    try:
        if not phase_name:
            return _create_error_response("phase_name is required")

        session_id = tool_context.invocation_state.get(
            "session_id"
        ) or _session_cache.get("session_id")
        if not session_id:
            return _create_error_response(
                "No active session found. Call start_session() first.",
                {"error_type": "NO_SESSION"},
            )

        table_name = os.environ.get("JOURNAL_TABLE_NAME", "")
        if not table_name:
            return _create_error_response("JOURNAL_TABLE_NAME not set")

        current_time = datetime.now(timezone.utc)
        timestamp = current_time.isoformat()
        ttl = int(current_time.timestamp()) + (30 * 24 * 60 * 60)
        record_type = f"TASK#{timestamp}"

        _session_cache["tasks"][phase_name] = {
            "record_type": record_type,
            "start_time": timestamp,
            "session_id": session_id,
        }

        try:
            item = {
                "session_id": {"S": session_id},
                "record_type": {"S": record_type},
                "timestamp": {"S": timestamp},
                "status": {"S": "IN_PROGRESS"},
                "phase_name": {"S": phase_name},
                "start_time": {"S": timestamp},
                "ttl": {"N": str(ttl)},
            }
            dynamodb.put_item(TableName=table_name, Item=item)
        except ClientError as e:
            return _create_error_response(
                f"Failed to create task: {e.response['Error']['Code']}: {e.response['Error']['Message']}",
                {"session_id": session_id, "phase_name": phase_name},
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


def _find_task_by_phase(session_id: str, phase_name: str) -> Optional[Dict[str, str]]:
    try:
        table_name = os.environ.get("JOURNAL_TABLE_NAME", "")
        if not table_name:
            return None

        response = dynamodb.query(
            TableName=table_name,
            KeyConditionExpression="session_id = :sid AND begins_with(record_type, :task)",
            ExpressionAttributeValues={
                ":sid": {"S": session_id},
                ":task": {"S": "TASK#"},
            },
        )

        for item in response.get("Items", []):
            if item.get("phase_name", {}).get("S") == phase_name:
                return {
                    "record_type": item.get("record_type", {}).get("S", ""),
                    "start_time": item.get("start_time", {}).get("S", ""),
                }
        return None
    except Exception:
        return None


def _complete_task(
    phase_name: str,
    tool_context: ToolContext,
    status: TaskStatus = TaskStatus.COMPLETED,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Complete a task/phase and update its status."""
    try:
        if not phase_name:
            return _create_error_response("phase_name is required")

        session_id = tool_context.invocation_state.get(
            "session_id"
        ) or _session_cache.get("session_id")
        if not session_id:
            return _create_error_response(
                "No active session found.",
                {"error_type": "NO_SESSION"},
            )

        task_info = _session_cache["tasks"].get(phase_name)
        if not task_info or task_info.get("session_id") != session_id:
            task_info = _find_task_by_phase(session_id, phase_name)

        if not task_info:
            return _create_error_response(
                f"Task '{phase_name}' not found for session '{session_id}'. Call start_task() first.",
                {
                    "error_type": "TASK_NOT_FOUND",
                    "phase_name": phase_name,
                    "session_id": session_id,
                },
            )

        table_name = os.environ.get("JOURNAL_TABLE_NAME", "")
        if not table_name:
            return _create_error_response("JOURNAL_TABLE_NAME not set")

        record_type = task_info["record_type"]
        start_time = task_info["start_time"]
        current_time = datetime.now(timezone.utc)
        end_time = current_time.isoformat()

        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            duration_seconds = int((current_time - start_dt).total_seconds())
        except Exception:
            duration_seconds = 0

        try:
            update_expr = "SET #status = :status, end_time = :end_time, duration_seconds = :duration"
            expr_values = {
                ":status": {"S": status.value},
                ":end_time": {"S": end_time},
                ":duration": {"N": str(duration_seconds)},
            }

            if error_message:
                update_expr += ", error_message = :error_message"
                expr_values[":error_message"] = {"S": error_message}

            dynamodb.update_item(
                TableName=table_name,
                Key={
                    "session_id": {"S": session_id},
                    "record_type": {"S": record_type},
                },
                UpdateExpression=update_expr,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=expr_values,
            )
        except ClientError as e:
            return _create_error_response(
                f"Failed to update task: {e.response['Error']['Code']}: {e.response['Error']['Message']}",
                {"session_id": session_id, "phase_name": phase_name},
            )

        return {
            "success": True,
            "session_id": session_id,
            "phase_name": phase_name,
            "status": status.value,
            "duration_seconds": duration_seconds,
            "timestamp": end_time,
        }
    except Exception as e:
        return _create_error_response(f"Unexpected error: {str(e)}")


def _complete_session(
    tool_context: ToolContext,
    status: SessionStatus = SessionStatus.COMPLETED,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Complete a session and finalize tracking."""
    try:
        session_id = tool_context.invocation_state.get(
            "session_id"
        ) or _session_cache.get("session_id")
        if not session_id:
            return _create_error_response(
                "No active session found.", {"error_type": "NO_SESSION"}
            )

        start_time = _session_cache.get("start_time")
        if not start_time:
            try:
                table_name = os.environ.get("JOURNAL_TABLE_NAME", "")
                response = dynamodb.get_item(
                    TableName=table_name,
                    Key={
                        "session_id": {"S": session_id},
                        "record_type": {"S": "SESSION"},
                    },
                )
                item = response.get("Item", {})
                start_time = item.get("start_time", {}).get("S")
            except Exception:
                pass

        if not start_time:
            return _create_error_response(
                f"Session start_time not found for session '{session_id}'",
                {"session_id": session_id},
            )

        table_name = os.environ.get("JOURNAL_TABLE_NAME", "")
        if not table_name:
            return _create_error_response("JOURNAL_TABLE_NAME not set")

        current_time = datetime.now(timezone.utc)
        end_time = current_time.isoformat()

        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            duration_seconds = int((current_time - start_dt).total_seconds())
        except Exception:
            duration_seconds = 0

        try:
            update_expr = "SET #status = :status, end_time = :end_time, duration_seconds = :duration"
            expr_values = {
                ":status": {"S": status.value},
                ":end_time": {"S": end_time},
                ":duration": {"N": str(duration_seconds)},
            }

            if error_message:
                update_expr += ", error_message = :error_message"
                expr_values[":error_message"] = {"S": error_message}

            dynamodb.update_item(
                TableName=table_name,
                Key={"session_id": {"S": session_id}, "record_type": {"S": "SESSION"}},
                UpdateExpression=update_expr,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=expr_values,
            )
        except ClientError as e:
            return _create_error_response(
                f"Failed to update session: {e.response['Error']['Code']}: {e.response['Error']['Message']}",
                {"session_id": session_id},
            )

        _session_cache["session_id"] = None
        _session_cache["start_time"] = None
        _session_cache["tasks"] = {}

        return {
            "success": True,
            "session_id": session_id,
            "status": status.value,
            "duration_seconds": duration_seconds,
            "timestamp": end_time,
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
    Unified DynamoDB journaling tool for session and task tracking.

    Args:
        action: Action to perform (check_table, start_session, start_task, complete_task, complete_session)
        phase_name: Name of the task/phase (required for start_task and complete_task)
        status: Status for completion (COMPLETED, FAILED, CANCELLED, SKIPPED for tasks; COMPLETED, FAILED for sessions)
        error_message: Optional error message for failed completions

    Returns:
        Dictionary with success status and operation results
    """
    if action == "start_session":
        return _start_session(tool_context)
    elif action == "start_task":
        if not phase_name:
            return _create_error_response(
                "phase_name is required for start_task action"
            )
        return _start_task(phase_name, tool_context)
    elif action == "complete_task":
        if not phase_name:
            return _create_error_response(
                "phase_name is required for complete_task action"
            )
        task_status = TaskStatus(status) if status else TaskStatus.COMPLETED
        return _complete_task(phase_name, tool_context, task_status, error_message)
    elif action == "complete_session":
        session_status = SessionStatus(status) if status else SessionStatus.COMPLETED
        return _complete_session(tool_context, session_status, error_message)
    else:
        return _create_error_response(f"Unknown action: {action}")
