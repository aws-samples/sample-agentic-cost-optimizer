# Requirements Document

## Introduction

This feature enhances the event recording system to securely handle dynamically generated event statuses while preventing injection attacks. Currently, the `journal` tool creates event statuses by concatenating user-provided phase names (e.g., `TASK_{phase_normalized}_STARTED`), but the `record_event` function only validates against a fixed set of predefined statuses from the `EventStatus` class. This creates both a security vulnerability (no input validation) and a functional issue (dynamic statuses are rejected). The solution implements regex-based validation to allow safe dynamic phase names while maintaining security.

## Glossary

- **Event Recorder**: The `record_event` function in `src/shared/event_recorder.py` that writes events to DynamoDB
- **Journal Tool**: The `journal` tool in `src/tools/journal.py` that provides session and task tracking
- **Phase Name**: User-provided string identifying a task or phase (e.g., "Discovery", "Usage and Metrics Collection")
- **Phase Normalized**: The uppercase, space-replaced version of phase name used in event statuses (e.g., "USAGE_AND_METRICS_COLLECTION")
- **Dynamic Event Status**: Event status string constructed at runtime by concatenating base status with phase name (e.g., "TASK_DISCOVERY_STARTED")
- **Base Event Status**: Predefined event status constants from the `EventStatus` class (e.g., "TASK_STARTED", "SESSION_INITIATED")

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want phase names to be validated against injection attacks, so that malicious input cannot compromise the DynamoDB records or system integrity

#### Acceptance Criteria

1. WHEN THE Event Recorder receives a status parameter, THE Event Recorder SHALL validate the status string format using regex pattern matching
2. WHERE the status contains a dynamic phase component, THE Event Recorder SHALL extract and validate the phase name against allowed characters
3. THE Event Recorder SHALL reject status strings containing characters outside the allowed set: A-Z, a-z, 0-9, underscore, and dash
4. IF a status string contains invalid characters, THEN THE Event Recorder SHALL raise a ValueError with a descriptive message indicating the validation failure
5. THE Event Recorder SHALL enforce a maximum length of 50 characters for the phase name component

### Requirement 2

**User Story:** As a developer, I want the event recorder to accept both predefined and dynamic event statuses, so that the journal tool can track arbitrary phase names without requiring code changes

#### Acceptance Criteria

1. THE Event Recorder SHALL accept all predefined status constants from the EventStatus class without modification
2. THE Event Recorder SHALL accept dynamic status strings matching the pattern `TASK_{phase}_STARTED`
3. THE Event Recorder SHALL accept dynamic status strings matching the pattern `TASK_{phase}_COMPLETED`
4. THE Event Recorder SHALL accept dynamic status strings matching the pattern `TASK_{phase}_FAILED`
5. WHERE a status matches the dynamic pattern, THE Event Recorder SHALL validate the phase component independently from the base status

### Requirement 3

**User Story:** As a developer, I want clear error messages when validation fails, so that I can quickly identify and fix invalid phase names

#### Acceptance Criteria

1. WHEN validation fails due to invalid characters, THE Event Recorder SHALL include the invalid status string in the error message
2. WHEN validation fails due to invalid characters, THE Event Recorder SHALL specify which characters are allowed in the error message
3. WHEN validation fails due to excessive length, THE Event Recorder SHALL include the maximum allowed length in the error message
4. THE Event Recorder SHALL raise ValueError exceptions for all validation failures to maintain consistency with existing error handling
5. THE Event Recorder SHALL log validation failures with sufficient context for debugging

### Requirement 4

**User Story:** As a system operator, I want the validation logic to be maintainable and testable, so that security requirements can be verified and updated as needed

#### Acceptance Criteria

1. THE Event Recorder SHALL implement validation logic using compiled regex patterns for performance
2. THE Event Recorder SHALL define validation rules as constants that can be easily modified
3. THE Event Recorder SHALL separate the validation logic into a distinct, testable function
4. THE Event Recorder SHALL maintain backward compatibility with existing predefined event statuses
5. THE Event Recorder SHALL document the validation rules in code comments and docstrings
