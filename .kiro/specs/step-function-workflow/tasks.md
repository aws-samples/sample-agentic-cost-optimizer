# Implementation Plan

- [x] 1. Update Step Function to record SESSION_INITIATED event
- [x] 1.1 Modify InitializeSession state to use event journaling format
  - Update `infra/lib/workflow.ts` to create event with PK="SESSION#{session_id}" and SK="EVENT#{timestamp}"
  - Set Status="SESSION_INITIATED" and Timestamp fields
  - Remove old SESSION record creation logic
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4_

- [x] 1.2 Update Step Function polling logic to query for completion events
  - Modify CheckStatus state to query for events with PK="SESSION#{session_id}"
  - Add logic to scan query results for AGENT_BACKGROUND_TASK_COMPLETED or AGENT_BACKGROUND_TASK_FAILED status
  - Update success/failure transitions based on event status
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 2. Add event recording to Lambda invoker
- [x] 2.1 Create DynamoDB helper function in agent-invoker.ts
  - Add `recordEvent()` function to create event records in DynamoDB
  - Use PK="SESSION#{session_id}" and SK="EVENT#{timestamp}" format
  - Include Status and Timestamp fields, optional ErrorMessage
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2.2 Record AGENT_INVOCATION_STARTED event
  - Call `recordEvent()` before invoking AgentCore
  - Use Status="AGENT_INVOCATION_STARTED"
  - _Requirements: 3.1, 3.4_

- [x] 2.3 Record AGENT_INVOCATION_SUCCEEDED event
  - Call `recordEvent()` after successful AgentCore response
  - Use Status="AGENT_INVOCATION_SUCCEEDED"
  - _Requirements: 3.2, 3.4_

- [x] 2.4 Record AGENT_INVOCATION_FAILED event
  - Call `recordEvent()` in catch block with error message
  - Use Status="AGENT_INVOCATION_FAILED"
  - Include ErrorMessage field with error details
  - _Requirements: 3.3, 3.4, 1.5_

- [x] 3. Add event recording to agent main.py
- [x] 3.1 Create DynamoDB helper function in main.py
  - Add `record_event()` function to create event records in DynamoDB
  - Use PK="SESSION#{session_id}" and SK="EVENT#{timestamp}" format
  - Include Status and Timestamp fields, optional ErrorMessage
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 3.2 Record AGENT_ENTRYPOINT_STARTED event in invoke()
  - Call `record_event()` when request is received (at existing logger.info point)
  - Use Status="AGENT_ENTRYPOINT_STARTED"
  - _Requirements: 4.1, 4.4, 4.5_

- [x] 3.3 Record AGENT_BACKGROUND_TASK_STARTED event in invoke()
  - Call `record_event()` after creating background task (at existing logger.info point)
  - Use Status="AGENT_BACKGROUND_TASK_STARTED"
  - _Requirements: 4.2, 4.4, 4.5_

- [x] 3.4 Record AGENT_ENTRYPOINT_FAILED event in invoke()
  - Call `record_event()` in except block with error message
  - Use Status="AGENT_ENTRYPOINT_FAILED"
  - Include ErrorMessage field
  - _Requirements: 4.3, 4.4, 4.5, 1.5_

- [x] 3.5 Record AGENT_BACKGROUND_TASK_COMPLETED event in background_agent_task()
  - Call `record_event()` after successful agent.invoke_async (at existing logger.info point)
  - Use Status="AGENT_BACKGROUND_TASK_COMPLETED"
  - _Requirements: 5.1, 5.5_

- [x] 3.6 Record AGENT_BACKGROUND_TASK_FAILED event for NoCredentialsError
  - Call `record_event()` in NoCredentialsError except block (at existing logger.error point)
  - Use Status="AGENT_BACKGROUND_TASK_FAILED"
  - Include ErrorMessage with error details
  - _Requirements: 5.2, 5.5, 1.5_

- [x] 3.7 Record AGENT_BACKGROUND_TASK_FAILED event for ClientError
  - Call `record_event()` in ClientError except block (at existing logger.error point)
  - Use Status="AGENT_BACKGROUND_TASK_FAILED"
  - Include ErrorMessage with error code and message
  - _Requirements: 5.3, 5.5, 1.5_

- [x] 3.8 Record AGENT_BACKGROUND_TASK_FAILED event for Exception
  - Call `record_event()` in Exception except block (at existing logger.error point)
  - Use Status="AGENT_BACKGROUND_TASK_FAILED"
  - Include ErrorMessage with error type and message
  - _Requirements: 5.4, 5.5, 1.5_

- [x] 4. Update IAM permissions
- [x] 4.1 Grant Step Function DynamoDB permissions
  - Add dynamodb:PutItem permission for journal table to Step Function role
  - Add dynamodb:Query permission for journal table to Step Function role
  - _Requirements: 7.1, 7.2, 7.5_

- [x] 4.2 Grant Lambda invoker DynamoDB permissions
  - Add dynamodb:PutItem permission for journal table to Lambda role
  - _Requirements: 7.3, 7.5_

- [x] 4.3 Verify Agent runtime DynamoDB permissions
  - Confirm AgentCore execution role has dynamodb:PutItem permission for journal table
  - Add permission if missing
  - _Requirements: 7.4, 7.5_

- [x] 5. Update documentation
- [x] 5.1 Document event journaling approach in LOCAL_DEVELOPMENT.md
  - Explain event journaling concept and data model
  - Provide example event records for each Status type
  - Include DynamoDB query examples for retrieving events
  - Document how to debug workflows using event records
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
