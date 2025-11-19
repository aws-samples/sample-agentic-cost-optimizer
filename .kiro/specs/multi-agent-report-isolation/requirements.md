# Requirements Document

## Introduction

This feature implements a multi-agent architecture to isolate report generation from cost analysis operations. The current monolithic agent (src/agents/main.py) performs AWS resource discovery, metrics collection, cost analysis, report generation, and S3 file writing in a single execution context. This creates context window pressure, token inefficiency, and makes error recovery difficult. The implemented solution separates these concerns into specialized agents with sequential invocation, using S3 for data passing between agents, enabling better context management, failure isolation, and retry capabilities.

## Glossary

- **Background_Task**: The async function in src/agents/main.py that orchestrates sequential agent invocation
- **Analysis_Agent**: A specialized agent responsible for AWS resource discovery, metrics collection, cost analysis, recommendation formatting, and cost estimation (phases 1-5 of current workflow)
- **Report_Agent**: A specialized agent responsible for report generation and S3 file writing (phases 6-7 of current workflow)
- **Sequential_Invocation**: The orchestration pattern where Analysis_Agent is invoked first, followed by Report_Agent after successful completion
- **Session_ID**: A unique identifier for a cost optimization execution session used to correlate events and data, passed to agents via session_id parameter
- **Journal_Table**: A DynamoDB table storing session-scoped events with format PK=SESSION#{session_id}, SK=EVENT#{timestamp}
- **S3_Bucket**: The existing S3 bucket used for storing both intermediate data (analysis.txt) and final outputs (cost_report.txt, evidence.txt)
- **Analysis_Results_File**: An S3 object at path {session_id}/analysis.txt containing structured output from the Analysis_Agent
- **Context_Passing**: The mechanism by which data flows from Analysis_Agent to Report_Agent through S3 storage using the storage tool
- **Storage_Tool**: An enhanced tool that supports both read and write actions for S3 operations with session-scoped path management

## Requirements

### Requirement 1: Multi-Agent Architecture

**User Story:** As a system architect, I want to separate cost analysis from report generation into specialized agents, so that each agent can be optimized independently and context window pressure is reduced.

#### Acceptance Criteria

1. THE System SHALL define an Analysis_Agent with system prompt covering phases 1-5 (Discovery, Usage and Metrics Collection, Analysis and Decision Rules, Recommendation Format, Cost Estimation Method)
2. THE System SHALL define a Report_Agent with system prompt covering phases 6-7 (Output Contract, S3 Write Requirements)
3. THE Analysis_Agent SHALL have access to use_aws, journal, calculator, and storage tools
4. THE Report_Agent SHALL have access to storage and journal tools
5. THE background_task function SHALL sequentially invoke Analysis_Agent followed by Report_Agent

### Requirement 2: Sequential Orchestration

**User Story:** As a developer, I want a simple sequential orchestration pattern to coordinate agent execution, so that execution order is clear and error handling is straightforward.

#### Acceptance Criteria

1. THE background_task function SHALL invoke analysis_agent.invoke_async() first with the session_id parameter
2. THE background_task function SHALL await completion of the analysis agent before proceeding
3. THE background_task function SHALL invoke report_agent.invoke_async() second with the session_id parameter
4. THE background_task function SHALL await completion of the report agent before recording completion event
5. IF the analysis agent fails, THEN THE background_task function SHALL propagate the exception without invoking the report agent

### Requirement 3: Enhanced Storage Tool

**User Story:** As a developer, I want the storage tool to support both reading and writing to S3, so that agents can pass data through S3 without needing a separate tool.

#### Acceptance Criteria

1. THE storage tool SHALL support an action parameter with values "read" or "write"
2. THE write action SHALL accept parameters filename and content, retrieve session_id from tool_context.invocation_state, and write to S3 at path {session_id}/{filename}
3. THE read action SHALL accept parameter filename, retrieve session_id from tool_context.invocation_state, and read from S3 at path {session_id}/{filename}
4. THE read action SHALL return a dictionary with success status and content on success, or error message on failure
5. THE storage tool SHALL use the existing S3_BUCKET_NAME environment variable for all operations

### Requirement 4: Context Passing via S3

**User Story:** As a developer, I want complete analysis results stored in S3 between agent executions, so that the report agent can access all detailed analysis data to generate high-quality reports and evidence files.

#### Acceptance Criteria

1. WHEN the Analysis_Agent completes all analysis phases (1-5), THE Analysis_Agent SHALL use the storage tool to write complete analysis results with filename "analysis.txt"
2. THE analysis results data SHALL include all discovery data, all metrics data, all formatted recommendations with full details, and all cost estimates without summarization
3. THE analysis results SHALL preserve all evidence details needed for the Evidence Appendix section of the report
4. WHEN the Report_Agent starts execution, THE Report_Agent SHALL use the storage tool to read data with filename "analysis.txt"
5. IF the analysis results are missing, THEN THE Report_Agent SHALL record a TASK_REPORT_GENERATION_FAILED event with error message and halt execution

### Requirement 5: Consistent Event Journaling

**User Story:** As an operations engineer, I want all agents to record events to the same journal table, so that I have a complete audit trail of the entire workflow execution.

#### Acceptance Criteria

1. THE Analysis_Agent SHALL record TASK_DISCOVERY_STARTED and TASK_DISCOVERY_COMPLETED events to the Journal_Table
2. THE Analysis_Agent SHALL record TASK_USAGE_AND_METRICS_COLLECTION_STARTED and TASK_USAGE_AND_METRICS_COLLECTION_COMPLETED events to the Journal_Table
3. THE Analysis_Agent SHALL record TASK_ANALYSIS_AND_DECISION_RULES_STARTED and TASK_ANALYSIS_AND_DECISION_RULES_COMPLETED events to the Journal_Table
4. THE Report_Agent SHALL record TASK_REPORT_GENERATION_STARTED and TASK_REPORT_GENERATION_COMPLETED events to the Journal_Table
5. THE Report_Agent SHALL record TASK_S3_WRITE_REQUIREMENTS_STARTED and TASK_S3_WRITE_REQUIREMENTS_COMPLETED events to the Journal_Table
6. THE System SHALL ensure all events include the Session_ID for correlation

### Requirement 6: Error Handling and Failure Isolation

**User Story:** As a system operator, I want failures in one agent to be isolated and recoverable, so that partial work is preserved and selective retry is possible.

#### Acceptance Criteria

1. WHEN the Analysis_Agent encounters an error, THE Analysis_Agent SHALL record a FAILED event with error details to the Journal_Table
2. IF the Analysis_Agent fails, THEN THE background_task function SHALL catch the exception and record AGENT_BACKGROUND_TASK_FAILED without invoking the Report_Agent
3. WHEN the Report_Agent encounters an error, THE Report_Agent SHALL record a FAILED event with error details to the Journal_Table
4. IF the Report_Agent fails, THEN THE background_task function SHALL catch the exception and record AGENT_BACKGROUND_TASK_FAILED while preserving analysis.txt in S3
5. THE Report_Agent SHALL validate received analysis results before generating reports and record validation failures as FAILED events

### Requirement 7: Tool Distribution

**User Story:** As a developer, I want each agent to have only the tools necessary for its responsibilities, so that agent contexts remain focused and token usage is optimized.

#### Acceptance Criteria

1. THE Analysis_Agent SHALL be created with access to use_aws, journal, calculator, and storage tools
2. THE Report_Agent SHALL be created with access to storage and journal tools
3. THE Analysis_Agent SHALL use the storage tool to write analysis.txt to S3
4. THE Analysis_Agent system prompt SHALL NOT include instructions for output contract generation or final report S3 writes
5. THE Report_Agent system prompt SHALL NOT include instructions for AWS discovery, metrics collection, or cost analysis

### Requirement 8: Integration with Existing Infrastructure

**User Story:** As a DevOps engineer, I want the multi-agent architecture to integrate with existing EventBridge, Step Functions, and Lambda infrastructure, so that deployment requires minimal changes to the orchestration layer.

#### Acceptance Criteria

1. THE System SHALL maintain the existing EventBridge trigger mechanism in infra/lib/infra-stack.ts
2. THE System SHALL maintain the existing Step Function workflow defined in infra/lib/workflow.ts
3. THE System SHALL maintain the existing Lambda invoker function in infra/lambda/agent_invoker.py
4. THE System SHALL maintain the existing AgentCore entrypoint pattern in src/agents/main.py with background_task decorator
5. THE System SHALL use the existing Journal_Table and S3 bucket configured through environment variables

### Requirement 9: Agent Invocation Pattern

**User Story:** As a developer, I want to use the Strands agent invocation pattern correctly, so that session context is maintained across agent executions.

#### Acceptance Criteria

1. THE background_task function SHALL pass session_id parameter to analysis_agent.invoke_async()
2. THE background_task function SHALL pass session_id parameter to report_agent.invoke_async()
3. THE Analysis_Agent and Report_Agent SHALL access session_id from tool_context.invocation_state in their tools
4. THE storage tool SHALL use session_id to construct S3 paths for reading and writing files
5. THE journal tool SHALL use session_id to correlate events across both agent executions

### Requirement 10: Backward Compatibility

**User Story:** As a product owner, I want the multi-agent implementation to produce the same outputs as the monolithic agent, so that downstream consumers are not impacted.

#### Acceptance Criteria

1. THE Report_Agent SHALL generate a cost_report.txt file with the same format as the current Main_Agent
2. THE Report_Agent SHALL generate an evidence.txt file with the same format as the current Main_Agent
3. THE System SHALL record the same event types to the Journal_Table as the current Main_Agent (TASK_*_STARTED, TASK_*_COMPLETED, TASK_*_FAILED)
4. THE Report_Agent SHALL use the storage tool to write files to S3, which returns s3_uri in the response
5. THE System SHALL maintain the same session lifecycle events (SESSION_INITIATED, AGENT_INVOCATION_STARTED, AGENT_BACKGROUND_TASK_STARTED, AGENT_BACKGROUND_TASK_COMPLETED)
