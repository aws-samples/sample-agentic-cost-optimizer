# Implementation Plan

- [x] 1. Create unified journal tool with action-based dispatch
  - Create single `journal()` function with `@tool` decorator
  - Implement action parameter to dispatch to different operations
  - Support actions: start_session, start_task, complete_task, complete_session
  - Use `tool_context` parameter to access invocation state
  - _Requirements: 1.1, 3.1, 4.1_

- [x] 2. Implement session management operations
  - Create `_start_session()` internal function to initialize sessions
  - Retrieve session_id from `tool_context.invocation_state`
  - Create `_complete_session()` to finalize sessions with status
  - Calculate session duration and update DynamoDB
  - _Requirements: 1.2, 1.3, 2.2_

- [x] 3. Implement task tracking operations
  - Create `_start_task()` to begin tracking tasks by phase_name
  - Create `_complete_task()` to finalize tasks with status
  - Support TaskStatus enum: COMPLETED, FAILED, CANCELLED, SKIPPED
  - Calculate task duration and update DynamoDB
  - _Requirements: 2.1, 2.2, 2.4_

- [x] 4. Integrate boto3 resource API for DynamoDB
  - Initialize DynamoDB resource using `boto3.resource("dynamodb")`
  - Use resource API methods for cleaner syntax
  - Handle `ClientError` exceptions from botocore
  - Implement consistent error response formatting
  - _Requirements: 1.2, 5.1, 5.2_

- [x] 5. Create helper functions for code reusability
  - Implement `_create_error_response()` for consistent error formatting
  - Create `_get_session_id()` to retrieve session ID from context
  - Implement `_create_timestamp_and_ttl()` for timestamp generation
  - Create `_calculate_duration()` for duration calculations
  - Implement `_create_dynamodb_item()` and `_update_dynamodb_item()` helpers
  - _Requirements: 3.1, 4.2, 5.3_

- [x] 6. Implement status enums for type safety
  - Create TaskStatus enum with COMPLETED, FAILED, CANCELLED, SKIPPED
  - Create SessionStatus enum with COMPLETED, FAILED
  - Use enums in function signatures for type safety
  - _Requirements: 3.4, 5.3_

- [x] 7. Update agent main.py for session ID management
  - Import journal tool from `..tools`
  - Add journal to agent tools list
  - Generate unique session_id with timestamp and UUID
  - Pass session_id to agent via invocation state
  - _Requirements: 6.3, 6.4, 7.1_

- [x] 8. Remove check_table_exists functionality
  - Simplify tool by removing table existence checking
  - Rely on DynamoDB errors for missing table scenarios
  - _Requirements: 4.1, 5.1_