# Design Document

## Overview

This design implements secure validation for dynamically generated event statuses in the `record_event` function. The solution uses regex-based pattern matching to validate both predefined statuses from the `EventStatus` class and dynamic statuses constructed with user-provided phase names. The validation prevents injection attacks while maintaining backward compatibility and supporting the journal tool's dynamic phase tracking capabilities.

The validation logic is extracted into a dedicated module (`src/shared/event_validation.py`) for reusability, testability, and maintainability.

## Architecture

### Validation Flow

```
Input: status string
    ↓
Check if status is predefined (EventStatus class)
    ↓ (if not predefined)
Check if status matches dynamic pattern (TASK_{phase}_{suffix})
    ↓
Extract phase component
    ↓
Validate phase against character whitelist and length limit
    ↓
Accept or reject with descriptive error
```

### Key Design Decisions

1. **Validation Module**: Extract validation logic to `src/shared/event_validation.py` for reusability and independent testing
2. **Validation Location**: Call validation in `record_event` function to ensure all callers benefit from security checks
3. **Regex Approach**: Use compiled regex patterns for performance and maintainability
4. **Two-Tier Validation**: First check predefined statuses (fast path), then validate dynamic patterns (secure path)
5. **Backward Compatibility**: All existing predefined statuses pass validation unchanged

## Components and Interfaces

### New Component: Event Validation Module

**Location**: `src/shared/event_validation.py`

**Purpose**: Centralized validation logic for event status strings, supporting both predefined and dynamic patterns.

**Public Interface**:

```python
import re
from typing import Set

# Validation constants
PHASE_NAME_PATTERN = re.compile(r'^[A-Za-z0-9_-]+$')
MAX_PHASE_NAME_LENGTH = 50
DYNAMIC_STATUS_PATTERN = re.compile(r'^TASK_([A-Za-z0-9_-]+)_(STARTED|COMPLETED|FAILED)$')

def validate_event_status(status: str, valid_predefined_statuses: Set[str]) -> None:
    """Validate event status against predefined and dynamic patterns.
    
    This function ensures event status strings are safe from injection attacks
    while supporting both predefined statuses and dynamically generated statuses
    with user-provided phase names.
    
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
    
    # Validate phase name characters (redundant with regex but explicit)
    if not PHASE_NAME_PATTERN.match(phase_name):
        raise ValueError(
            f"Invalid status '{status}'. Phase name '{phase_name}' contains "
            f"invalid characters. Only A-Z, a-z, 0-9, underscore, and dash are allowed"
        )
```

### Modified Component: `record_event` Function

**Location**: `src/shared/event_recorder.py`

**Changes**:
1. Import validation function from new module
2. Replace existing validation logic with call to `validate_event_status`

**Integration Point**:

```python
from .event_validation import validate_event_status

# Inside record_event function:
# Existing code builds valid_statuses set
valid_statuses = {
    getattr(EventStatus, attr)
    for attr in dir(EventStatus)
    if not attr.startswith("_") and isinstance(getattr(EventStatus, attr), str)
}

# New validation call (replaces existing simple check)
validate_event_status(status, valid_statuses)
```

### Modified Component: `__init__.py`

**Location**: `src/shared/__init__.py`

**Changes**: Export the new validation function for external use

```python
from .event_validation import validate_event_status

__all__ = [..., "validate_event_status"]
```

### Unchanged Components

- **Journal Tool** (`src/tools/journal.py`): No changes required; continues to generate dynamic statuses
- **EventStatus Class** (`src/shared/event_statuses.py`): No changes required; remains source of predefined statuses
- **DynamoDB Schema**: No changes required; validation occurs before database write

## Data Models

### Validation Patterns

**Predefined Status Pattern**:
- Any string constant defined in `EventStatus` class
- Examples: `SESSION_INITIATED`, `AGENT_INVOCATION_STARTED`, `TASK_COMPLETED`

**Dynamic Status Pattern**:
- Format: `TASK_{phase}_{suffix}`
- Phase component: 1-50 characters, `[A-Za-z0-9_-]+`
- Suffix component: `STARTED`, `COMPLETED`, or `FAILED`
- Examples: `TASK_DISCOVERY_STARTED`, `TASK_USAGE_AND_METRICS_COLLECTION_COMPLETED`

### Validation Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `PHASE_NAME_PATTERN` | `^[A-Za-z0-9_-]+$` | Validates allowed characters in phase names |
| `MAX_PHASE_NAME_LENGTH` | `50` | Maximum length for phase name component |
| `DYNAMIC_STATUS_PATTERN` | `^TASK_([A-Za-z0-9_-]+)_(STARTED\|COMPLETED\|FAILED)$` | Validates dynamic status format and extracts phase |

## Error Handling

### Validation Error Scenarios

1. **Invalid Pattern**:
   - Trigger: Status doesn't match predefined or dynamic pattern
   - Error: `ValueError: Invalid status 'XYZ'. Must be a predefined status or match pattern TASK_{phase}_{STARTED|COMPLETED|FAILED}`

2. **Invalid Characters**:
   - Trigger: Phase name contains characters outside `[A-Za-z0-9_-]`
   - Error: `ValueError: Invalid status 'TASK_PHASE@NAME_STARTED'. Phase name 'PHASE@NAME' contains invalid characters. Only A-Z, a-z, 0-9, underscore, and dash are allowed`

3. **Excessive Length**:
   - Trigger: Phase name exceeds 50 characters
   - Error: `ValueError: Invalid status 'TASK_VERY_LONG_PHASE_NAME..._STARTED'. Phase name 'VERY_LONG_PHASE_NAME...' exceeds maximum length of 50 characters`

### Error Propagation

- All validation errors raise `ValueError` (consistent with existing validation)
- Errors propagate to caller (journal tool or direct callers)
- Journal tool catches exceptions and returns error response to agent
- Logging occurs at `record_event` level before re-raising

### Backward Compatibility

- All existing predefined statuses pass validation unchanged
- Existing error handling behavior preserved
- No changes to function signature or return type

## Testing Strategy

### Unit Tests for `validate_event_status` Function

**Test File**: `tests/shared/test_event_validation.py`

**Test Cases**:

1. **Predefined Status Validation**:
   - Valid predefined statuses pass (e.g., `SESSION_INITIATED`)
   - All EventStatus constants pass validation

2. **Dynamic Status Validation**:
   - Valid dynamic statuses pass (e.g., `TASK_DISCOVERY_STARTED`)
   - Valid phase names with underscores pass (e.g., `TASK_USAGE_AND_METRICS_COLLECTION_COMPLETED`)
   - Valid phase names with dashes pass (e.g., `TASK_COST-ESTIMATION_FAILED`)
   - Mixed case phase names pass (e.g., `TASK_MyPhase_STARTED`)

3. **Invalid Character Rejection**:
   - Special characters rejected (e.g., `TASK_PHASE@NAME_STARTED`)
   - SQL injection attempts rejected (e.g., `TASK_'; DROP TABLE--_STARTED`)
   - Spaces rejected (e.g., `TASK_PHASE NAME_STARTED`)

4. **Length Limit Enforcement**:
   - Phase name with exactly 50 characters passes
   - Phase name with 51 characters fails
   - Very long phase names fail with descriptive error

5. **Pattern Mismatch**:
   - Invalid suffix rejected (e.g., `TASK_PHASE_RUNNING`)
   - Missing components rejected (e.g., `TASK_STARTED`)
   - Wrong prefix rejected (e.g., `EVENT_PHASE_STARTED`)

### Integration Tests

**Test File**: `tests/shared/test_event_recorder.py`

1. **Journal Tool Integration**:
   - Valid phase names successfully record events
   - Invalid phase names return error responses
   - Error messages propagate correctly to agent

2. **End-to-End Flow**:
   - Start task with valid phase name succeeds
   - Complete task with valid phase name succeeds
   - Invalid phase names fail gracefully with clear errors

### Performance Considerations

- Compiled regex patterns cached at module level (no per-call compilation)
- Predefined status check (fast path) avoids regex for common cases
- Validation adds minimal overhead (<1ms per call)

## Security Considerations

### Threat Model

**Prevented Attacks**:
1. **NoSQL Injection**: Character whitelist prevents injection of DynamoDB operators
2. **Log Injection**: Newline and control characters blocked by character whitelist
3. **Path Traversal**: Slash characters blocked by character whitelist
4. **Command Injection**: Shell metacharacters blocked by character whitelist

**Defense in Depth**:
- Input validation (this design)
- DynamoDB parameterized queries (existing)
- IAM permissions (existing)
- CloudWatch log sanitization (existing)

### Validation Strength

- Whitelist approach (allow known-good) vs blacklist (block known-bad)
- Regex anchored with `^` and `$` to prevent partial matches
- Length limit prevents resource exhaustion attacks
- Case-insensitive pattern allows natural phase names while maintaining security

## Implementation Notes

### Code Organization

1. Create new file `src/shared/event_validation.py` with validation constants and function
2. Update `src/shared/__init__.py` to export `validate_event_status`
3. Modify `src/shared/event_recorder.py` to import and use `validate_event_status`
4. Update docstrings to document validation behavior

### Migration Path

- No migration required (backward compatible)
- Existing code continues to work unchanged
- New dynamic statuses automatically validated

### Future Enhancements

- Consider adding validation for other dynamic patterns if needed
- Consider adding metrics for validation failures
- Consider early validation in journal tool for better error messages
