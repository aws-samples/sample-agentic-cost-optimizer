# Requirements Document

## Introduction

This feature adds event journaling to the Step Function workflow and agent invocation process. Instead of updating a single SESSION record, the system will create immutable event records in DynamoDB for each significant state transition (similar to CloudFormation event journaling). This provides a complete audit trail of workflow execution from initialization through completion or failure.

## Requirements

### Requirement 1 (Core - Event Journaling Data Model)

**User Story:** As a developer, I want immutable event records in DynamoDB, so that I have a complete audit trail of workflow execution.

#### Acceptance Criteria

1. WHEN an event is recorded THEN it SHALL use PK format "SESSION#{session_id}"
2. WHEN an event is recorded THEN it SHALL use SK format "EVENT#{ISO_timestamp}"
3. WHEN an event is recorded THEN it SHALL include a Status field with the event type
4. WHEN an event is recorded THEN it SHALL include a Timestamp field in ISO format
5. WHEN an event represents a failure THEN it SHALL include an ErrorMessage field
6. WHEN an event is recorded THEN it SHALL NOT update existing records (immutable events only)

### Requirement 2 (Core - Step Function Event Recording)

**User Story:** As a system operator, I want the Step Function to record workflow initialization events, so that I can track when workflows start.

#### Acceptance Criteria

1. WHEN the Step Function starts THEN it SHALL create an event record with Status="SESSION_INITIATED"
2. WHEN creating the event THEN it SHALL use PK="SESSION#{session_id}" and SK="EVENT#{timestamp}"
3. WHEN the event creation fails THEN the Step Function SHALL transition to failure path
4. WHEN the event is created successfully THEN the Step Function SHALL proceed to invoke the Lambda function

### Requirement 3 (Core - Lambda Invoker Event Recording)

**User Story:** As a system operator, I want the Lambda invoker to record agent invocation events, so that I can track when AgentCore is called and its outcome.

#### Acceptance Criteria

1. WHEN the Lambda invoker starts THEN it SHALL create an event record with Status="AGENT_INVOCATION_STARTED"
2. WHEN AgentCore responds successfully THEN it SHALL create an event record with Status="AGENT_INVOCATION_SUCCEEDED"
3. WHEN AgentCore fails THEN it SHALL create an event record with Status="AGENT_INVOCATION_FAILED" and include ErrorMessage
4. WHEN creating events THEN it SHALL use PK="SESSION#{session_id}" and SK="EVENT#{timestamp}"
5. WHEN the Lambda function receives session_id THEN it SHALL pass it to the agent via environment variables

### Requirement 4 (Core - Agent Entrypoint Event Recording)

**User Story:** As a developer, I want the agent entrypoint to record lifecycle events, so that I can track when requests are received and background tasks are created.

#### Acceptance Criteria

1. WHEN the agent entrypoint receives a request THEN it SHALL create an event record with Status="AGENT_ENTRYPOINT_STARTED"
2. WHEN the background task is created successfully THEN it SHALL create an event record with Status="AGENT_BACKGROUND_TASK_STARTED"
3. WHEN the entrypoint encounters an error THEN it SHALL create an event record with Status="AGENT_ENTRYPOINT_FAILED" and include ErrorMessage
4. WHEN creating events THEN it SHALL use PK="SESSION#{session_id}" and SK="EVENT#{timestamp}"
5. WHEN creating events THEN it SHALL use the DynamoDB table name from environment variables

### Requirement 5 (Core - Agent Background Task Event Recording)

**User Story:** As a developer, I want the agent background task to record completion and failure events, so that I can track the final outcome of agent processing.

#### Acceptance Criteria

1. WHEN the background task completes successfully THEN it SHALL create an event record with Status="AGENT_BACKGROUND_TASK_COMPLETED"
2. WHEN the background task fails with NoCredentialsError THEN it SHALL create an event record with Status="AGENT_BACKGROUND_TASK_FAILED" and include ErrorMessage
3. WHEN the background task fails with ClientError THEN it SHALL create an event record with Status="AGENT_BACKGROUND_TASK_FAILED" and include ErrorMessage
4. WHEN the background task fails with any Exception THEN it SHALL create an event record with Status="AGENT_BACKGROUND_TASK_FAILED" and include ErrorMessage
5. WHEN creating events THEN it SHALL use PK="SESSION#{session_id}" and SK="EVENT#{timestamp}"

### Requirement 6 (Core - Step Function Status Monitoring)

**User Story:** As a system operator, I want the Step Function to monitor for completion events, so that I can know when the agent workflow has finished.

#### Acceptance Criteria

1. WHEN monitoring begins THEN the Step Function SHALL query DynamoDB for events using PK="SESSION#{session_id}" and SK begins_with "EVENT#"
2. WHEN an event with Status="AGENT_BACKGROUND_TASK_COMPLETED" is found THEN the Step Function SHALL complete successfully
3. WHEN an event with Status="AGENT_BACKGROUND_TASK_FAILED" is found THEN the Step Function SHALL transition to failure path
4. WHEN no completion events are found THEN the Step Function SHALL wait and retry the query
5. WHEN the maximum retry attempts are reached THEN the Step Function SHALL transition to failure path

### Requirement 7 (Infrastructure - IAM Permissions)

**User Story:** As a developer, I want proper IAM permissions configured, so that all components can write event records to DynamoDB.

#### Acceptance Criteria

1. WHEN deploying THEN the Step Function SHALL have dynamodb:PutItem permission on the journal table
2. WHEN deploying THEN the Step Function SHALL have dynamodb:Query permission on the journal table
3. WHEN deploying THEN the Lambda invoker SHALL have dynamodb:PutItem permission on the journal table
4. WHEN deploying THEN the Agent runtime SHALL have dynamodb:PutItem permission on the journal table (via existing AgentCore permissions)
5. WHEN deploying THEN all permissions SHALL be scoped to the specific journal table ARN

### Requirement 8 (Developer Experience - Event Querying)

**User Story:** As a developer, I want to easily query event records, so that I can debug and monitor workflow execution.

#### Acceptance Criteria

1. WHEN querying events THEN I SHALL be able to retrieve all events for a session using PK="SESSION#{session_id}"
2. WHEN querying events THEN the events SHALL be returned in chronological order (sorted by SK)
3. WHEN documenting THEN the LOCAL_DEVELOPMENT.md SHALL include example DynamoDB query commands
4. WHEN documenting THEN example event records SHALL be provided for each Status type
5. WHEN documenting THEN the event journaling approach SHALL be clearly explained

## Non-Functional Requirements

### Maintainability
- Code should be minimal and focused on core functionality only
- No over-engineering - this is a POC in active development
- Integration with existing project structure and patterns

