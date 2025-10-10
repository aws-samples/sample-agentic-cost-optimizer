"""
DynamoDB Journaling Tools for Cost Optimization Agent

Provides stateful session and task tracking with automatic ID management.

Environment Variables:
- JOURNAL_TABLE_NAME: DynamoDB table name for journaling
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from strands import tool

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


def _retry_with_backoff(
    operation_func: Callable[[], Dict[str, Any]],
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> Dict[str, Any]:
    for attempt in range(max_attempts):
        try:
            result = operation_func()

            if isinstance(result, dict) and "error" in result:
                error_msg = result["error"].lower()
                retryable_errors = [
                    "throttling",
                    "provisioned throughput exceeded",
                    "service unavailable",
                    "internal server error",
                    "timeout",
                    "connection",
                    "network",
                ]
                is_retryable = any(err in error_msg for err in retryable_errors)

                if not is_retryable or attempt == max_attempts - 1:
                    return result

                time.sleep(base_delay * (2**attempt))
                continue

            return result

        except Exception as e:
            if attempt == max_attempts - 1:
                raise e
            time.sleep(base_delay * (2**attempt))

    return {"error": "Maximum retry attempts exceeded"}


@tool
def check_journal_table_exists() -> Dict[str, Any]:
    """Check if the DynamoDB journal table exists and is accessible."""
    try:
        table_name = os.environ.get("JOURNAL_TABLE_NAME", "")

        if not table_name:
            return _create_error_response(
                "JOURNAL_TABLE_NAME environment variable not set",
                {"error_type": "CONFIGURATION_ERROR"},
            )

        def _describe_table():
            try:
                response = dynamodb.describe_table(TableName=table_name)
                return response
            except ClientError as e:
                return {
                    "error": f"{e.response['Error']['Code']}: {e.response['Error']['Message']}"
                }
            except Exception as e:
                return {"error": str(e)}

        result = _retry_with_backoff(_describe_table)

        if "error" in result:
            error_msg = result["error"]
            if "ResourceNotFoundException" in error_msg:
                error_type = "TABLE_NOT_FOUND"
            elif "AccessDenied" in error_msg:
                error_type = "ACCESS_DENIED"
            else:
                error_type = "DYNAMODB_ERROR"

            return _create_error_response(
                f"Table check failed: {error_msg}",
                {"table_name": table_name, "error_type": error_type},
            )

        table_status = result.get("Table", {}).get("TableStatus", "UNKNOWN")

        return {
            "success": True,
            "table_name": table_name,
            "table_status": table_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return _create_error_response(f"Unexpected error: {str(e)}")


@tool
def start_session(session_id: str) -> Dict[str, Any]:
    """
    Start a new journaling session.

    Args:
        session_id: Unique identifier for this session
    """
    try:
        if not session_id:
            return _create_error_response("session_id is required")

        table_name = os.environ.get("JOURNAL_TABLE_NAME", "")
        if not table_name:
            return _create_error_response("JOURNAL_TABLE_NAME not set")

        current_time = datetime.now(timezone.utc)
        timestamp = current_time.isoformat()
        ttl = int(current_time.timestamp()) + (30 * 24 * 60 * 60)

        _session_cache["session_id"] = session_id
        _session_cache["start_time"] = timestamp
        _session_cache["tasks"] = {}

        def _put_session():
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
                return {"success": True}
            except ClientError as e:
                return {
                    "error": f"{e.response['Error']['Code']}: {e.response['Error']['Message']}"
                }
            except Exception as e:
                return {"error": str(e)}

        result = _retry_with_backoff(_put_session)

        if "error" in result:
            return _create_error_response(
                f"Failed to create session: {result['error']}",
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


@tool
def start_task(phase_name: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Start tracking a new task/phase.

    Args:
        phase_name: Name of the workflow phase
        session_id: Optional session ID (uses cached if not provided)
    """
    try:
        if not phase_name:
            return _create_error_response("phase_name is required")

        if not session_id:
            session_id = _session_cache.get("session_id")

        if not session_id:
            return _create_error_response(
                "No active session found. Call start_session() first or provide session_id.",
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

        def _put_task():
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
                return {"success": True}
            except ClientError as e:
                return {
                    "error": f"{e.response['Error']['Code']}: {e.response['Error']['Message']}"
                }
            except Exception as e:
                return {"error": str(e)}

        result = _retry_with_backoff(_put_task)

        if "error" in result:
            return _create_error_response(
                f"Failed to create task: {result['error']}",
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


@tool
def complete_task(
    phase_name: str,
    status: str = "COMPLETED",
    error_message: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Complete a task/phase and update its status.

    Args:
        phase_name: Name of the phase to complete (must match start_task call)
        status: Final status (COMPLETED, FAILED, CANCELLED, or SKIPPED)
        error_message: Optional error message if status is FAILED
        session_id: Optional session ID (uses cached if not provided)
    """
    try:
        if not phase_name:
            return _create_error_response("phase_name is required")

        if not session_id:
            session_id = _session_cache.get("session_id")

        if not session_id:
            return _create_error_response(
                "No active session found. Provide session_id parameter.",
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

        def _update_task():
            try:
                update_expr = "SET #status = :status, end_time = :end_time, duration_seconds = :duration"
                expr_values = {
                    ":status": {"S": status},
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
                return {"success": True}
            except ClientError as e:
                return {
                    "error": f"{e.response['Error']['Code']}: {e.response['Error']['Message']}"
                }
            except Exception as e:
                return {"error": str(e)}

        result = _retry_with_backoff(_update_task)

        if "error" in result:
            return _create_error_response(
                f"Failed to update task: {result['error']}",
                {"session_id": session_id, "phase_name": phase_name},
            )

        return {
            "success": True,
            "session_id": session_id,
            "phase_name": phase_name,
            "status": status,
            "duration_seconds": duration_seconds,
            "timestamp": end_time,
        }

    except Exception as e:
        return _create_error_response(f"Unexpected error: {str(e)}")


@tool
def complete_session(
    status: str = "COMPLETED",
    error_message: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Complete a session and finalize tracking.

    Args:
        status: Final status (COMPLETED or FAILED)
        error_message: Optional error message if status is FAILED
        session_id: Optional session ID (uses cached if not provided)
    """
    try:
        if not session_id:
            session_id = _session_cache.get("session_id")

        if not session_id:
            return _create_error_response(
                "No active session found. Provide session_id parameter.",
                {"error_type": "NO_SESSION"},
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

        def _update_session():
            try:
                update_expr = "SET #status = :status, end_time = :end_time, duration_seconds = :duration"
                expr_values = {
                    ":status": {"S": status},
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
                        "record_type": {"S": "SESSION"},
                    },
                    UpdateExpression=update_expr,
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues=expr_values,
                )
                return {"success": True}
            except ClientError as e:
                return {
                    "error": f"{e.response['Error']['Code']}: {e.response['Error']['Message']}"
                }
            except Exception as e:
                return {"error": str(e)}

        result = _retry_with_backoff(_update_session)

        if "error" in result:
            return _create_error_response(
                f"Failed to update session: {result['error']}",
                {"session_id": session_id},
            )

        _session_cache["session_id"] = None
        _session_cache["start_time"] = None
        _session_cache["tasks"] = {}

        return {
            "success": True,
            "session_id": session_id,
            "status": status,
            "duration_seconds": duration_seconds,
            "timestamp": end_time,
        }

    except Exception as e:
        return _create_error_response(f"Unexpected error: {str(e)}")
