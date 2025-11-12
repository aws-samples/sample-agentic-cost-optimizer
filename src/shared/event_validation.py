"""Event status validation module for secure handling of dynamic event statuses."""

import re
from typing import Set

PHASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_PHASE_NAME_LENGTH = 50
DYNAMIC_STATUS_PATTERN = re.compile(r"^TASK_([A-Za-z0-9_-]+)_(STARTED|COMPLETED|FAILED)$")


def validate_event_status(status: str, valid_predefined_statuses: Set[str]) -> None:
    """Validate event status against predefined and dynamic patterns.

    This function ensures event status strings are safe from injection attacks
    while supporting both predefined statuses and dynamically generated statuses
    with user-provided phase names.

    The validation follows a two-tier approach:
    1. Fast path: Check if status is in the predefined set (EventStatus class constants)
    2. Secure path: Validate dynamic pattern TASK_{phase}_{STARTED|COMPLETED|FAILED}

    Args:
        status: The event status string to validate
        valid_predefined_statuses: Set of predefined valid statuses from EventStatus class

    Raises:
        ValueError: If status is invalid, contains unsafe characters, or exceeds length limits
    """
    # Fast path: check predefined statuses
    if status in valid_predefined_statuses:
        return

    # Check dynamic pattern: TASK_{phase}_{STARTED|COMPLETED|FAILED}
    match = DYNAMIC_STATUS_PATTERN.match(status)
    if not match:
        raise ValueError(
            f"Invalid status '{status}'. Must be a predefined status or "
            f"match pattern TASK_{{phase}}_{{STARTED|COMPLETED|FAILED}}"
        )

    phase_name = match.group(1)

    # Validate phase name length
    if len(phase_name) > MAX_PHASE_NAME_LENGTH:
        raise ValueError(
            f"Invalid status '{status}'. Phase name '{phase_name}' exceeds "
            f"maximum length of {MAX_PHASE_NAME_LENGTH} characters"
        )

    # Validate phase name characters (redundant with regex but explicit for clarity)
    if not PHASE_NAME_PATTERN.match(phase_name):
        raise ValueError(
            f"Invalid status '{status}'. Phase name '{phase_name}' contains "
            f"invalid characters. Only A-Z, a-z, 0-9, underscore, and dash are allowed"
        )
