"""
DynamoDB Data Store Tool for Multi-Agent Context Passing

Provides data storage and retrieval capabilities for passing analysis results
and other data between agents in a multi-agent workflow.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from strands import ToolContext, tool

from src.shared import read_data, write_data

aws_region = os.environ.get("AWS_REGION", "us-east-1")
ttl_days = int(os.environ.get("TTL_DAYS", "90"))


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
    return tool_context.invocation_state.get("session_id")


def _get_table_name() -> Optional[str]:
    return os.environ.get("DATA_STORE_TABLE_NAME", "")


def _write_data_action(
    data_key: str,
    data_content: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    try:
        if not data_key:
            return _create_error_response("data_key is required")

        if not data_content:
            return _create_error_response("data_content is required")

        session_id = _get_session_id(tool_context)
        if not session_id:
            return _create_error_response(
                "No active session found.",
                {"error_type": "NO_SESSION"},
            )

        table_name = _get_table_name()
        if not table_name:
            return _create_error_response("DATA_STORE_TABLE_NAME not set")

        write_data(
            session_id=session_id,
            data_key=data_key,
            data_content=data_content,
            table_name=table_name,
            ttl_days=ttl_days,
            region_name=aws_region,
        )

        return {
            "success": True,
            "session_id": session_id,
            "data_key": data_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return _create_error_response(f"Unexpected error: {str(e)}")


def _read_data_action(
    data_key: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    try:
        if not data_key:
            return _create_error_response("data_key is required")

        session_id = _get_session_id(tool_context)
        if not session_id:
            return _create_error_response(
                "No active session found.",
                {"error_type": "NO_SESSION"},
            )

        table_name = _get_table_name()
        if not table_name:
            return _create_error_response("DATA_STORE_TABLE_NAME not set")

        data_content = read_data(
            session_id=session_id,
            data_key=data_key,
            table_name=table_name,
            region_name=aws_region,
        )

        return {
            "success": True,
            "session_id": session_id,
            "data_key": data_key,
            "data_content": data_content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ValueError as e:
        return _create_error_response(str(e))
    except Exception as e:
        return _create_error_response(f"Unexpected error: {str(e)}")


@tool(context=True)
def data_store(
    action: str,
    tool_context: ToolContext,
    data_key: Optional[str] = None,
    data_content: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Save and retrieve data from DynamoDB Data Store Table.

    Args:
        action: Action to perform ("write" or "read")
        tool_context: Strands context providing invocation state with session_id
        data_key: Key identifier for the data
        data_content: The actual data content to store (required for write action)

    Returns:
        Dictionary with success status and operation results
    """
    valid_actions = ["write", "read"]
    if action not in valid_actions:
        return _create_error_response(f"Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}")

    if action == "write":
        if not data_key:
            return _create_error_response("data_key is required for write action")
        if not data_content:
            return _create_error_response("data_content is required for write action")
        return _write_data_action(data_key, data_content, tool_context)

    elif action == "read":
        if not data_key:
            return _create_error_response("data_key is required for read action")
        return _read_data_action(data_key, tool_context)

    else:
        return _create_error_response(f"Unknown action: {action}")
