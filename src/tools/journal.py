"""
DynamoDB Journaling Tool for Cost Optimization Agent

Provides stateful session and task tracking with automatic ID management
through a single tool interface.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from strands import tool

from src.shared import EventStatus, record_event
from src.shared.config import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Journal:
    """Class-based journal tool that captures session_id at initialization."""

    def __init__(self, session_id: str):
        self.session_id = session_id

    @staticmethod
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

    @tool
    def journal(
        self,
        action: str,
        phase_name: Optional[str] = None,
        status: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        DynamoDB journaling tool for session and task tracking.

        Args:
            action: Action to perform (start_task, complete_task)
            phase_name: Name of the task/phase (required for start_task and complete_task)
            status: Status for completion ("TASK_COMPLETED" or "TASK_FAILED")
            error_message: Optional error message for failed completions

        Returns:
            Dictionary with success status and operation results
        """
        valid_actions = ["start_task", "complete_task"]
        if action not in valid_actions:
            return self._create_error_response(f"Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}")

        if action == "start_task":
            if not phase_name:
                return self._create_error_response("phase_name is required for start_task action")
            return self._start_task(phase_name)
        elif action == "complete_task":
            if not phase_name:
                return self._create_error_response("phase_name is required for complete_task action")

            valid_statuses = [EventStatus.TASK_COMPLETED, EventStatus.TASK_FAILED]
            if status and status not in valid_statuses:
                return self._create_error_response(
                    f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}"
                )

            return self._complete_task(
                phase_name,
                status or EventStatus.TASK_COMPLETED,
                error_message,
            )
        else:
            return self._create_error_response(f"Unknown action: {action}")

    def _start_task(self, phase_name: str) -> Dict[str, Any]:
        """Start tracking a new task/phase."""
        try:
            if not phase_name:
                error_msg = "phase_name is required"
                logger.error(f"--> Journal validation failed - {error_msg}")
                return self._create_error_response(error_msg)

            phase_normalized = phase_name.upper().replace(" ", "_")
            event_status = f"TASK_{phase_normalized}_{EventStatus.TASK_STARTED}"

            logger.info(
                f"--> Journal tool invoked - Session: {self.session_id}, " f"Action: start_task, Phase: {phase_name}"
            )
            logger.debug(f"--> Recording event status: {event_status}")

            record_event(
                session_id=self.session_id,
                status=event_status,
                table_name=config.journal_table_name,
                ttl_days=config.ttl_days,
                region_name=config.aws_region,
            )

            logger.info(f"--> Successfully started task '{phase_name}' for session {self.session_id}")

            return {
                "success": True,
                "session_id": self.session_id,
                "phase_name": phase_name,
                "status": "IN_PROGRESS",
                "timestamp": config.ttl_days,
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(
                f"--> Journal start_task failed - Session: {self.session_id}, " f"Phase: {phase_name}, Error: {str(e)}"
            )
            return self._create_error_response(error_msg)

    def _complete_task(
        self,
        phase_name: str,
        status: str = EventStatus.TASK_COMPLETED,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Complete a task/phase and update its status."""
        try:
            if not phase_name:
                error_msg = "phase_name is required"
                logger.error(f"--> Journal validation failed - {error_msg}")
                return self._create_error_response(error_msg)

            phase_normalized = phase_name.upper().replace(" ", "_")
            event_status = f"TASK_{phase_normalized}_{status}"

            logger.info(
                f"--> Journal tool invoked - Session: {self.session_id}, "
                f"Action: complete_task, Phase: {phase_name}, Status: {status}"
            )
            logger.debug(f"--> Recording event status: {event_status}")

            if error_message:
                logger.error(
                    f"--> Task '{phase_name}' completed with error - Session: {self.session_id}, "
                    f"Error: {error_message}"
                )

            record_event(
                session_id=self.session_id,
                status=event_status,
                table_name=config.journal_table_name,
                ttl_days=config.ttl_days,
                error_message=error_message,
                region_name=config.aws_region,
            )

            logger.info(
                f"--> Successfully completed task '{phase_name}' for session {self.session_id} " f"with status {status}"
            )

            return {
                "success": True,
                "session_id": self.session_id,
                "phase_name": phase_name,
                "status": status,
                "timestamp": config.ttl_days,
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(
                f"--> Journal complete_task failed - Session: {self.session_id}, "
                f"Phase: {phase_name}, Error: {str(e)}"
            )
            return self._create_error_response(error_msg)
