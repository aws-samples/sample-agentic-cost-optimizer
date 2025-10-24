# Requirements Document

## Introduction

This feature adds a Step Function workflow to orchestrate the agent invocation process and monitor its completion status through DynamoDB polling. The workflow will trigger the existing Lambda invoker function, then poll the DynamoDB table for session status updates created by the agent's journal tool, handling success and failure paths appropriately.

## Requirements

### Requirement 1 (Foundation - Existing Code Updates)

**User Story:** As a developer, I want the agent and journal tool updated to support the workflow, so that session status can be properly tracked.

#### Acceptance Criteria

1. WHEN the journal tool tracks session status THEN it SHALL support "BUSY" status in addition to "COMPLETED" and "FAILED"
2. WHEN the agent starts THEN it SHALL read session_id, s3_bucket_name, and ddb_table_name from environment variables
3. WHEN the agent uses the journal tool THEN it SHALL pass these variables to the tool
4. WHEN the agent starts processing THEN the journal tool SHALL set session status to "BUSY" once
5. WHEN the agent prompt is updated THEN it SHALL instruct the agent to set status to "BUSY" at the beginning of processing

### Requirement 2 (Foundation - Lambda Updates)

**User Story:** As a system operator, I want the Lambda invoker function updated to pass session context, so that the agent receives the necessary environment variables.

#### Acceptance Criteria

1. WHEN the Lambda invoker function is called THEN it SHALL accept session_id as input parameter
2. WHEN the Lambda invoker function runs THEN it SHALL pass session_id, s3_bucket_name, and ddb_table_name as environment variables to the agent

### Requirement 3 (Core - Session Initialization)

**User Story:** As a system operator, I want the Step Function to initialize session records in DynamoDB, so that I can track workflow execution from the very beginning.

#### Acceptance Criteria

1. WHEN the Step Function starts THEN it SHALL create a DynamoDB record with PK=session_id from event
2. WHEN creating the record THEN it SHALL use SK="SESSION" 
3. WHEN creating the record THEN it SHALL set status field to "INITIATED"
4. WHEN creating the record THEN it SHALL include start_time timestamp field
5. WHEN creating the record THEN it SHALL include created_at timestamp field
6. WHEN the DynamoDB PutItem operation fails THEN the Step Function SHALL catch the error and transition to failure path

### Requirement 4 (Core - Step Function Workflow)

**User Story:** As a system operator, I want to trigger agent workflows through Step Functions, so that I can have reliable orchestration and error handling for agent invocations.

#### Acceptance Criteria

1. WHEN the Step Function is triggered THEN it SHALL create a session record in DynamoDB with status "INITIATED"
2. WHEN the DynamoDB record creation fails THEN the Step Function SHALL transition to a failure path
3. WHEN the DynamoDB record is created successfully THEN the Step Function SHALL invoke the existing agent invoker Lambda function
4. WHEN the Lambda function fails THEN the Step Function SHALL transition to a failure path
5. WHEN the Lambda function succeeds THEN the Step Function SHALL proceed to status monitoring

### Requirement 5 (Core - Status Monitoring)

**User Story:** As a system operator, I want the Step Function to monitor agent session status, so that I can know when the agent has completed its work.

#### Acceptance Criteria

1. WHEN monitoring begins THEN the Step Function SHALL query DynamoDB for session status using PK=session_id and SK=SESSION
2. WHEN the STATUS field equals "BUSY" THEN the Step Function SHALL wait and retry the query
3. WHEN the STATUS field equals "COMPLETED" THEN the Step Function SHALL complete successfully
4. WHEN the STATUS field equals "FAILED" THEN the Step Function SHALL transition to failure path
5. WHEN the session record does not exist THEN the Step Function SHALL wait and retry the query

### Requirement 6 (Infrastructure - CDK Integration)

**User Story:** As a developer, I want the Step Function integrated into the existing CDK infrastructure, so that it follows the current deployment patterns.

#### Acceptance Criteria

1. WHEN deploying THEN the Step Function SHALL be defined in a separate workflow.ts file and imported into the existing CDK stack
2. WHEN deploying THEN the Step Function SHALL have appropriate IAM permissions for Lambda invocation and DynamoDB access
3. WHEN deploying THEN the Step Function SHALL reference existing resources (Lambda function, DynamoDB table) by their CDK constructs
4. WHEN deploying THEN the Step Function SHALL output its ARN for external triggering

### Requirement 7 (Trigger - EventBridge Integration)

**User Story:** As a system operator, I want EventBridge integration for triggering the workflow, so that I can manually trigger executions from console or CLI.

#### Acceptance Criteria

1. WHEN deploying THEN an EventBridge rule SHALL be created to trigger the Step Function
2. WHEN the rule is created THEN it SHALL use an event pattern to match manual trigger events
3. WHEN manually triggering THEN I SHALL be able to publish events via AWS CLI or console to start the workflow
4. WHEN EventBridge triggers the workflow THEN the EventBridge event ID SHALL be automatically passed as session_id to the Step Function
5. WHEN the event flows through THEN the session_id SHALL be passed from EventBridge → Step Function → Lambda invoker → Agent

### Requirement 8 (Developer Experience - CLI Integration)

**User Story:** As a developer, I want convenient CLI commands for triggering workflows, so that I can easily test the system during development.

#### Acceptance Criteria

1. WHEN developing THEN there SHALL be a Makefile target to trigger the workflow
2. WHEN running the make target THEN it SHALL publish the appropriate EventBridge event
3. WHEN documenting THEN the LOCAL_DEVELOPMENT.md SHALL include comprehensive CLI trigger examples
4. WHEN documenting THEN the project structure SHALL be accurately documented

## Non-Functional Requirements

### Maintainability
- Code should be minimal and focused on core functionality only
- No over-engineering - this is a POC in active development
- Integration with existing project structure and patterns

