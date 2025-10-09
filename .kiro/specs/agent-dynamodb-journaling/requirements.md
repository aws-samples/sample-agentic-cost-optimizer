# Requirements Document

## Introduction

This feature enhances the existing cost optimization agent to track its workflow phases and execution steps in DynamoDB. The agent will maintain a journal of each session showing the phases it goes through (discovery, metrics collection, analysis, etc.) and their completion status, providing visibility into the agent's progress and final execution summary. This builds upon the existing AWS Agent Core integration and leverages the use_aws tool for DynamoDB operations.

## Requirements

### Requirement 1

**User Story:** As a developer, I want the agent to create a session journal in DynamoDB when it starts, so that I can track each cost optimization session and its overall status.

#### Acceptance Criteria

1. WHEN the agent starts a cost optimization analysis THEN it SHALL create a new session record in DynamoDB with a unique session ID
2. WHEN creating a session record THEN the system SHALL include session ID, start timestamp, and status "STARTED"
3. WHEN the session completes THEN it SHALL update the session status to "COMPLETED" with end timestamp
4. IF the DynamoDB table doesn't exist THEN the agent SHALL create it using the use_aws tool

### Requirement 2

**User Story:** As a developer, I want the agent to track each workflow phase as a separate task in DynamoDB, so that I can see which phases have been completed and their status.

#### Acceptance Criteria

1. WHEN the agent starts a workflow phase THEN it SHALL create a task record with phase name and status "IN_PROGRESS"
2. WHEN a phase completes successfully THEN it SHALL update the task status to "COMPLETED" with completion timestamp
3. WHEN a phase fails THEN it SHALL update the task status to "FAILED" with error message
4. WHEN all phases are tracked THEN the system SHALL support the standard workflow phases: Discovery, Metrics Collection, Analysis, Recommendations, Report Generation

### Requirement 3

**User Story:** As a developer, I want to query the journal to get a complete summary of a session's phases and their statuses, so that I can understand what the agent accomplished.

#### Acceptance Criteria

1. WHEN querying by session ID THEN the system SHALL return all phases/tasks for that session with their statuses
2. WHEN a session is in progress THEN I SHALL be able to see which phases are completed and which are still running
3. WHEN a session has errors THEN I SHALL be able to see which specific phases failed and why
4. WHEN viewing the journal THEN I SHALL see phases in chronological order with timestamps

### Requirement 4

**User Story:** As a developer, I want the agent to update task status in real-time as it progresses through phases, so that I can monitor live progress during execution.

#### Acceptance Criteria

1. WHEN the agent starts a phase THEN it SHALL immediately update DynamoDB with "IN_PROGRESS" status
2. WHEN the agent completes a phase THEN it SHALL immediately update DynamoDB with "COMPLETED" status
3. WHEN the agent encounters an error THEN it SHALL immediately update DynamoDB with "FAILED" status and error message
4. WHEN updating status THEN the system SHALL include timestamp for each status change

### Requirement 5

**User Story:** As a developer, I want the DynamoDB journal structure to support querying and analysis, so that I can retrieve session data efficiently and analyze agent performance over time.

#### Acceptance Criteria

1. WHEN designing the table schema THEN it SHALL use session ID as partition key and timestamp as sort key
2. WHEN storing data THEN it SHALL include GSI for querying by status and date ranges
3. WHEN writing journal entries THEN it SHALL use consistent attribute naming and data types
4. WHEN the table is created THEN it SHALL have appropriate TTL settings for data retention


### Requirement 6

**User Story:** As a developer, I want the journal to include basic execution metrics for each phase, so that I can understand timing and performance.

#### Acceptance Criteria

1. WHEN starting each phase THEN the agent SHALL record start timestamp
2. WHEN completing each phase THEN the agent SHALL record end timestamp and calculate duration
3. WHEN the session completes THEN the agent SHALL record total session duration