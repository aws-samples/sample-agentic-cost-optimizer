# Requirements Document

## Introduction

This feature implements a multi-agent architecture to isolate report generation from cost analysis operations. The current monolithic agent (src/agents/main.py) performs AWS resource discovery, metrics collection, cost analysis, report generation, and S3 file writing in a single execution context. This creates context window pressure, token inefficiency, and makes error recovery difficult. The proposed solution separates these concerns into specialized agents orchestrated through the Strands workflow tool, enabling better context management, failure isolation, and retry capabilities.

## Glossary

- **Main_Agent**: The current monolithic agent that will be refactored into specialized agents
- **Analysis_Agent**: A specialized agent responsible for AWS resource discovery, metrics collection, cost analysis, recommendation formatting, and cost estimation (phases 1-5 of current workflow)
- **Report_Agent**: A specialized agent responsible for report generation and S3 file writing (phases 6-7 of current workflow)
- **Workflow_Tool**: A Strands framework tool from strands_tools that executes tasks in a deterministic directed acyclic graph (DAG) pattern with automatic dependency resolution
- **Session_ID**: A unique identifier for a cost optimization execution session used to correlate events and data, passed via invocation_state
- **Journal_Table**: A DynamoDB table storing session-scoped events with format PK=SESSION#{session_id}, SK=EVENT#{timestamp}
- **Data_Store_Table**: A DynamoDB table for storing analysis results and other data with format PK=SESSION#{session_id}, SK=DATA#{data_key}
- **Analysis_Results_Record**: A DynamoDB record in the Data_Store_Table with SK=DATA#ANALYSIS_RESULTS containing structured output from the Analysis_Agent
- **Context_Passing**: The mechanism by which data flows from Analysis_Agent to Report_Agent through DynamoDB storage and workflow task outputs
- **Task_Dependency**: A workflow relationship where the report task depends on the analysis task completing successfully
- **Invocation_State**: A dictionary passed to agents containing session_id and other context, accessible in tools via ToolContext

## Requirements

### Requirement 1: Multi-Agent Architecture

**User Story:** As a system architect, I want to separate cost analysis from report generation into specialized agents, so that each agent can be optimized independently and context window pressure is reduced.

#### Acceptance Criteria

1. THE System SHALL define an Analysis_Agent with system prompt covering phases 1-5 (Discovery, Usage and Metrics Collection, Analysis and Decision Rules, Recommendation Format, Cost Estimation Method)
2. THE System SHALL define a Report_Agent with system prompt covering phases 6-7 (Output Contract, S3 Write Requirements)
3. THE Analysis_Agent SHALL have access to use_aws, journal, and calculator tools
4. THE Report_Agent SHALL have access to storage and journal tools
5. THE Main_Agent SHALL be refactored to use the workflow tool from strands_tools to coordinate the Analysis_Agent and Report_Agent

### Requirement 2: Workflow Orchestration

**User Story:** As a developer, I want a deterministic workflow pattern to coordinate agent execution, so that task dependencies are automatically managed and execution is repeatable.

#### Acceptance Criteria

1. THE Main_Agent SHALL use the workflow tool from strands_tools with action "create" to define two sequential tasks
2. THE workflow tool SHALL define task_id "analysis" with the Analysis_Agent system prompt and dependencies set to empty list
3. THE workflow tool SHALL define task_id "report" with the Report_Agent system prompt and dependencies set to ["analysis"]
4. THE Main_Agent SHALL use the workflow tool with action "start" to execute the workflow
5. IF the analysis task fails, THEN THE workflow tool SHALL halt execution without invoking the report task

### Requirement 3: Analysis Data Storage Tool

**User Story:** As a developer, I want a new tool to save and retrieve analysis results from DynamoDB, so that the report agent can access complete analysis data from the analysis agent.

#### Acceptance Criteria

1. THE System SHALL provide a new tool named "data_store" with actions "write" and "read"
2. THE write action SHALL accept parameters data_key and data_content, retrieve session_id from invocation_state, and write to Data_Store_Table with PK=SESSION#{session_id}, SK=DATA#{data_key}
3. THE read action SHALL accept parameter data_key, retrieve session_id from invocation_state, and query Data_Store_Table for the matching record
4. THE Data_Store_Table SHALL be a separate DynamoDB table from the Journal_Table with the same PK/SK structure
5. THE data_key parameter allows storing multiple types of data per session (e.g., "ANALYSIS_RESULTS", "WORKFLOW_METADATA")

### Requirement 4: Context Passing via DynamoDB

**User Story:** As a developer, I want complete analysis results stored in DynamoDB between agent executions, so that the report agent can access all detailed analysis data to generate high-quality reports and evidence files.

#### Acceptance Criteria

1. WHEN the Analysis_Agent completes all analysis phases (1-5), THE Analysis_Agent SHALL use the data_store tool to write complete analysis results with data_key "ANALYSIS_RESULTS"
2. THE analysis results data SHALL include all discovery data, all metrics data, all formatted recommendations with full details, and all cost estimates without summarization
3. THE analysis results SHALL preserve all evidence details needed for the Evidence Appendix section of the report
4. WHEN the Report_Agent starts execution, THE Report_Agent SHALL use the data_store tool to read data with data_key "ANALYSIS_RESULTS"
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
2. IF the Analysis_Agent fails, THEN THE Workflow_Tool SHALL halt execution and return an error without invoking the Report_Agent
3. WHEN the Report_Agent encounters an error, THE Report_Agent SHALL record a FAILED event with error details to the Journal_Table
4. IF the Report_Agent fails, THEN THE Workflow_Tool SHALL return an error while preserving Analysis_Results in the Data_Store_Table
5. THE Report_Agent SHALL validate received Analysis_Results before generating reports and record validation failures as FAILED events

### Requirement 7: Tool Distribution

**User Story:** As a developer, I want each agent to have only the tools necessary for its responsibilities, so that agent contexts remain focused and token usage is optimized.

#### Acceptance Criteria

1. THE Main_Agent SHALL have access to the workflow tool from strands_tools
2. THE workflow tool SHALL create the Analysis_Agent with access to use_aws, journal, calculator, and data storage tools through task definition
3. THE workflow tool SHALL create the Report_Agent with access to storage, journal, and data storage tools through task definition
4. THE Analysis_Agent system prompt SHALL NOT include instructions for output contract generation or S3 writes
5. THE Report_Agent system prompt SHALL NOT include instructions for AWS discovery, metrics collection, or cost analysis

### Requirement 8: Integration with Existing Infrastructure

**User Story:** As a DevOps engineer, I want the multi-agent architecture to integrate with existing EventBridge, Step Functions, and Lambda infrastructure, so that deployment requires minimal changes to the orchestration layer.

#### Acceptance Criteria

1. THE System SHALL maintain the existing EventBridge trigger mechanism in infra/lib/infra-stack.ts
2. THE System SHALL maintain the existing Step Function workflow defined in infra/lib/workflow.ts
3. THE System SHALL maintain the existing Lambda invoker function in infra/lambda/agent_invoker.py
4. THE System SHALL maintain the existing AgentCore entrypoint pattern in src/agents/main.py with background_task decorator
5. THE System SHALL use the existing Journal_Table and S3 bucket configured through environment variables

### Requirement 9: Workflow Tool Integration Pattern

**User Story:** As a developer, I want to use the Strands workflow tool correctly, so that task execution is reliable and follows framework best practices.

#### Acceptance Criteria

1. THE Main_Agent SHALL pass invocation_state containing session_id to the workflow tool
2. THE workflow tool SHALL propagate invocation_state to both Analysis_Agent and Report_Agent
3. THE Analysis_Agent and Report_Agent SHALL access session_id from tool_context.invocation_state in their tools
4. THE workflow tool SHALL automatically handle task output passing from analysis task to report task
5. THE Main_Agent SHALL use workflow tool action "status" to check workflow completion and retrieve results

### Requirement 10: Backward Compatibility

**User Story:** As a product owner, I want the multi-agent implementation to produce the same outputs as the monolithic agent, so that downstream consumers are not impacted.

#### Acceptance Criteria

1. THE Report_Agent SHALL generate a cost_report.txt file with the same format as the current Main_Agent
2. THE Report_Agent SHALL generate an evidence.txt file with the same format as the current Main_Agent
3. THE System SHALL record the same event types to the Journal_Table as the current Main_Agent (TASK_*_STARTED, TASK_*_COMPLETED, TASK_*_FAILED)
4. THE Report_Agent SHALL use the storage tool to write files to S3, which returns s3_uri in the response
5. THE System SHALL maintain the same session lifecycle events (SESSION_INITIATED, AGENT_INVOCATION_STARTED, AGENT_BACKGROUND_TASK_STARTED, AGENT_BACKGROUND_TASK_COMPLETED)
