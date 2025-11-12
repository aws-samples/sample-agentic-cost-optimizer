# Implementation Plan

- [ ] 1. Create event validation module with regex-based validation
  - Create `src/shared/event_validation.py` file with validation constants and function
  - Define `PHASE_NAME_PATTERN` regex constant for character validation (`^[A-Za-z0-9_-]+$`)
  - Define `MAX_PHASE_NAME_LENGTH` constant set to 50
  - Define `DYNAMIC_STATUS_PATTERN` regex constant for status format validation (`^TASK_([A-Za-z0-9_-]+)_(STARTED|COMPLETED|FAILED)$`)
  - Implement `validate_event_status` function with predefined status fast-path check
  - Implement dynamic pattern matching and phase name extraction
  - Implement phase name length validation with descriptive error messages
  - Implement phase name character validation with descriptive error messages
  - Add comprehensive docstring with examples and parameter descriptions
  - _Requirements: 1.1, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.5_

- [ ] 2. Update shared module exports
  - Modify `src/shared/__init__.py` to import `validate_event_status` from event_validation module
  - Add `validate_event_status` to `__all__` list for public API exposure
  - _Requirements: 4.3_

- [ ] 3. Integrate validation into event recorder
  - Add import statement in `src/shared/event_recorder.py` for `validate_event_status`
  - Locate the existing validation logic in `record_event` function (after building `valid_statuses` set)
  - Replace existing simple status validation check with call to `validate_event_status(status, valid_statuses)`
  - Update `record_event` docstring to document the new validation behavior and supported dynamic patterns
  - Ensure error logging captures validation failures before re-raising
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 3.5, 4.4_

- [ ] 4. Verify integration and backward compatibility
  - Run existing tests to ensure no regressions with predefined statuses
  - Manually test with a valid dynamic status (e.g., `TASK_DISCOVERY_STARTED`)
  - Manually test with an invalid status to verify error messages
  - Check that journal tool continues to work with dynamic phase names
  - _Requirements: 2.1, 4.4_
