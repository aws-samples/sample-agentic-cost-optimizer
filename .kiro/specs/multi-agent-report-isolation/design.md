# Design Document

## Overview

This design implements a multi-agent architecture for the cost optimization system by separating the analysis and report generation concerns into specialized agents. The current monolithic agent in `src/agents/main.py` will be refactored to use the Strands workflow tool to orchestrate two specialized agents: an Analysis Agent (phases 1-5) and a Report Agent (phases 6-7). This separation reduces context window pressure, improves token efficiency, enables failure isolation, and allows selective retry of the report generation phase without re-running expensive AWS discovery and analysis operations.

## Architecture

### High-Level Component Diagram

```
EventBridge → Step Function → Lambda Invoker → AgentCore Runtime
                                                      ↓
                                                 Main Agent
                                                 (workflow tool)
                                                      ↓
                                    ┌─────────────────┴─────────────────┐
                                    ↓                                   ↓
                            Analysis Agent                        Report Agent
                         (phases 1-5)                          (phases 6-7)
                                    ↓                                   ↓
                            Data_Store_Table ←──────────────────────────┘
                            (analysis results)
```

### Agent Responsibilities

**Main Agent**
- Entry point for the cost optimization workflow
- Uses the workflow tool from strands_tools to orchestrate Analysis and Report agents
- Maintains the existing AgentCore entrypoint pattern with background_task decorator
- Passes invocation_state (containing session_id) to the workflow

**Analysis Agent**
- Executes phases 1-5 of the current workflow:
  1. Discovery (Inventory)
  2. Usage and Metrics Collection
  3. Analysis and Decision Rules
  4. Recommendation Format
  5. Cost Estimation Method
- Has access to: use_aws, journal, calculator, data_store tools
- Writes complete analysis results to Data_Store_Table
- Records phase events to Journal_Table

**Report Agent**
- Executes phases 6-7 of the current workflow:
  6. Output Contract (plain text)
  7. S3 Write Requirements
- Has access to: storage, journal, data_store tools
- Reads complete analysis results from Data_Store_Table
- Generates cost_report.txt and evidence.txt files
- Writes files to S3 using storage tool
- Records phase events to Journal_Table

## Components and Interfaces

### 1. Data Store Tool

**Purpose**: Enable saving and retrieving analysis results between agent executions

**Location**: `src/tools/data_store.py`

**Interface**:
```python
@tool(context=True)
def data_store(
    action: str,  # "write" or "read"
    tool_context: ToolContext,
    data_key: Optional[str] = None,  # e.g., "ANALYSIS_RESULTS"
    data_content: Optional[str] = None  # For write action
) -> Dict[str, Any]:
    """
    Save and retrieve data from DynamoDB Data_Store_Table.
    
    Write action:
        - Retrieves session_id from tool_context.invocation_state
        - Writes to Data_Store_Table with PK=SESSION#{session_id}, SK=DATA#{data_key}
        - Returns: {"success": True, "data_key": "...", "timestamp": "..."}
    
    Read action:
        - Retrieves session_id from tool_context.invocation_state
        - Queries Data_Store_Table for PK=SESSION#{session_id}, SK=DATA#{data_key}
        - Returns: {"success": True, "data_content": "...", "timestamp": "..."}
        - Or: {"success": False, "error": "Data not found"}
    """
```

**Implementation Details**:
- Similar structure to existing `storage.py` and `journal.py` tools
- Uses boto3 DynamoDB resource
- Retrieves session_id from `tool_context.invocation_state.get("session_id")`
- Handles ClientError exceptions and returns structured error responses
- Includes logging for debugging

**DynamoDB Schema**:
```
Table: Data_Store_Table
PK: SESSION#{session_id}  (Partition Key)
SK: DATA#{data_key}        (Sort Key)
Attributes:
  - data_content: String (the actual data)
  - timestamp: String (ISO 8601 format)
  - ttl: Number (Unix timestamp for TTL)
```

### 2. Data Store Table (Infrastructure)

**Purpose**: Store analysis results and other data separate from event journal

**Location**: `infra/lib/infra-stack.ts`

**Configuration**:
```typescript
const dataStoreTable = new Table(this, 'DataStoreTable', {
  partitionKey: { name: 'PK', type: AttributeType.STRING },
  sortKey: { name: 'SK', type: AttributeType.STRING },
  billingMode: BillingMode.PAY_PER_REQUEST,
  timeToLiveAttribute: 'ttl',
  removalPolicy: RemovalPolicy.DESTROY,
  pointInTimeRecovery: true,
});
```

**IAM Permissions**:
- AgentCore Runtime role needs read/write access to Data_Store_Table
- Similar to existing Journal_Table permissions

**Environment Variable**:
- `DATA_STORE_TABLE_NAME`: Passed to AgentCore runtime

### 3. Main Agent Refactoring

**Current Structure** (`src/agents/main.py`):
```python
agent = Agent(
    model=bedrock_model,
    system_prompt=SYSTEM_PROMPT,
    tools=[use_aws, journal, storage, calculator],
)
```

**New Structure**:
```python
from strands_tools import workflow

agent = Agent(
    model=bedrock_model,
    system_prompt=MAIN_AGENT_PROMPT,  # New simplified prompt
    tools=[workflow],
)
```

**Main Agent Prompt** (`src/agents/main_prompt.md`):
```markdown
# Cost Optimization Orchestrator

You are responsible for orchestrating a multi-agent cost optimization workflow.

## Your Task

Use the workflow tool to coordinate two specialized agents:
1. Analysis Agent: Performs AWS discovery, metrics collection, and cost analysis
2. Report Agent: Generates reports and writes to S3

## Workflow Definition

Create a workflow with two tasks:

**Task 1: Analysis**
- task_id: "analysis"
- description: "Perform AWS Lambda discovery, metrics collection, cost analysis, recommendation formatting, and cost estimation"
- system_prompt: [Analysis Agent prompt - phases 1-5]
- dependencies: []
- priority: 5

**Task 2: Report**
- task_id: "report"
- description: "Generate cost optimization report and evidence files, write to S3"
- system_prompt: [Report Agent prompt - phases 6-7]
- dependencies: ["analysis"]
- priority: 3

## Execution Steps

1. Create the workflow using workflow tool with action="create"
2. Start the workflow using workflow tool with action="start"
3. Monitor completion using workflow tool with action="status"
4. Return the final results

## Important

- The workflow tool will automatically pass invocation_state (including session_id) to both agents
- The Analysis Agent will save results to DynamoDB for the Report Agent to use
- If the Analysis task fails, the Report task will not execute
```

### 4. Analysis Agent Prompt

**Location**: `src/agents/analysis_prompt.md`

**Content**: Extract phases 1-5 from current `prompt.md`:
- Discovery (Inventory)
- Usage and Metrics Collection
- Analysis and Decision Rules
- Recommendation Format
- Cost Estimation Method

**Key Additions**:
```markdown
## Saving Analysis Results

After completing all analysis phases (1-5), you MUST save your complete analysis results:

1. Use the data_store tool with action="write"
2. Set data_key="ANALYSIS_RESULTS"
3. Set data_content to include:
   - All discovery data (function names, ARNs, configurations)
   - All metrics data (invocations, errors, duration, memory usage)
   - All formatted recommendations with full details
   - All cost estimates with calculation inputs
   - All evidence for the Evidence Appendix

Format the data_content as structured text that preserves all details.

Example:
```
data_store(
    action="write",
    data_key="ANALYSIS_RESULTS",
    data_content="""
    === DISCOVERY DATA ===
    [All Lambda functions with full configurations]
    
    === METRICS DATA ===
    [All CloudWatch metrics and Log Insights results]
    
    === RECOMMENDATIONS ===
    [All formatted recommendations with evidence, actions, impacts, risks, steps]
    
    === COST ESTIMATES ===
    [All cost calculations with inputs and assumptions]
    
    === EVIDENCE ===
    [All evidence for appendix: queries used, raw data, timestamps]
    """
)
```

Check the response:
- If success is true, your analysis phase is complete
- If success is false, log the error in "Gaps & Limitations" and note that report generation may fail
```

### 5. Report Agent Prompt

**Location**: `src/agents/report_prompt.md`

**Content**: Extract phases 6-7 from current `prompt.md`:
- Output Contract (plain text)
- S3 Write Requirements

**Key Additions**:
```markdown
## Loading Analysis Results

Before generating the report, you MUST load the analysis results:

1. Use the data_store tool with action="read"
2. Set data_key="ANALYSIS_RESULTS"
3. Check the response:
   - If success is true, extract data_content
   - If success is false, record TASK_REPORT_GENERATION_FAILED and halt

Example:
```
result = data_store(action="read", data_key="ANALYSIS_RESULTS")

if not result.get("success"):
    # Record failure and halt
    journal(
        action="complete_task",
        phase_name="Report Generation",
        status="FAILED",
        error_message=f"Failed to load analysis results: {result.get('error')}"
    )
    # Stop execution
else:
    analysis_data = result.get("data_content")
    # Use analysis_data to generate report
```

## Generating the Report

Use the analysis_data to create the cost optimization report following the Output Contract structure:

1. Executive Summary (from recommendations and cost estimates)
2. Findings & Recommendations by Service (from formatted recommendations)
3. Gaps & Limitations (from analysis notes)
4. Evidence Appendix (from evidence data)
5. Next Review Window and Monitoring Suggestions

## Writing to S3

Use the storage tool exactly as before:
- storage(filename="cost_report.txt", content=report_content)
- storage(filename="evidence.txt", content=evidence_content)
```

## Data Models

### Analysis Results Data Structure

The analysis results stored in Data_Store_Table will be structured text containing:

```
=== DISCOVERY DATA ===
Total Lambda Functions: 15

Function: my-api-function
ARN: arn:aws:lambda:us-east-1:123456789012:function:my-api-function
Memory: 1024 MB
Timeout: 30 seconds
Runtime: python3.12
Architecture: x86_64
...

=== METRICS DATA ===
Function: my-api-function
Time Window: 2024-01-01 to 2024-01-30 (30 days)
Invocations: 1,234,567
Errors: 123 (0.01%)
Throttles: 0
Avg Duration: 245 ms
P95 Duration: 450 ms
P99 Duration: 680 ms
Avg Memory Used: 512 MB
P90 Memory Used: 580 MB
P99 Memory Used: 650 MB
...

=== RECOMMENDATIONS ===
Recommendation 1: Reduce Memory for my-api-function

Resource: my-api-function (arn:aws:lambda:us-east-1:123456789012:function:my-api-function)

Evidence:
- Allocated Memory: 1024 MB
- P95 Memory Used: 580 MB
- Memory Headroom: 43.4%
- P95 Duration: 450 ms (within SLO)
- No throttles observed

Action: Reduce Lambda memory from 1024 MB to 640 MB

Impact:
- Estimated Monthly Savings: $45.67 USD
- Calculation: (1024 MB - 640 MB) × 1,234,567 invocations × $0.0000166667 per GB-second × 0.450 seconds

Risk/Trade-offs:
- Minimal risk: 640 MB provides 10% headroom above P95 usage
- No expected latency impact
- Monitor for memory pressure

Steps to Implement:
1. Update function configuration: aws lambda update-function-configuration --function-name my-api-function --memory-size 640
2. Monitor CloudWatch metrics for 7 days
3. Verify no increase in errors or duration

Validation:
- Watch @maxMemoryUsed in CloudWatch Logs
- Monitor Duration metrics
- Check for OutOfMemory errors
...

=== COST ESTIMATES ===
Total Estimated Monthly Savings: $234.56 USD

Breakdown:
- Memory right-sizing: $189.23
- Timeout optimization: $23.45
- Idle function cleanup: $21.88

Calculation Method:
- Used 30-day usage data
- AWS Lambda pricing for us-east-1: $0.0000166667 per GB-second
- Request pricing: $0.20 per 1M requests
...

=== EVIDENCE ===
CloudWatch Insights Queries Used:

Query 1: Memory Usage Analysis
```
fields @timestamp, @requestId, @maxMemoryUsed, @memorySize
| filter @type = "REPORT"
| stats avg(@maxMemoryUsed) as avgMemoryKB,
  pct(@maxMemoryUsed, 90) as p90MemoryKB,
  avg(@memorySize) as avgAllocatedKB
```
Results: [raw data]

Query 2: Duration Analysis
...
```

This structured text format:
- Preserves all details without summarization
- Is human-readable for debugging
- Can be parsed by the Report Agent
- Includes all evidence needed for the Evidence Appendix

## Error Handling

### Analysis Agent Failures

**Scenario**: AWS API error during discovery

**Handling**:
1. Analysis Agent records TASK_DISCOVERY_FAILED event to Journal_Table
2. Workflow tool halts execution
3. Report Agent never executes
4. Step Function detects FAILED event and can retry entire workflow

**Recovery**: Full workflow retry (both analysis and report)

### Report Agent Failures

**Scenario**: S3 write error

**Handling**:
1. Analysis results preserved in Data_Store_Table
2. Report Agent records TASK_S3_WRITE_REQUIREMENTS_FAILED event to Journal_Table
3. Workflow tool returns error
4. Step Function detects FAILED event

**Recovery Options**:
1. Retry entire workflow (re-runs analysis + report)
2. Manual intervention: Check Data_Store_Table for analysis results, fix S3 issue, retry workflow
3. Future enhancement: Step Function logic to detect existing analysis results and retry only report task

### Data Store Tool Failures

**Scenario**: Analysis Agent fails to write results to Data_Store_Table

**Handling**:
1. Analysis Agent logs error in "Gaps & Limitations"
2. Analysis Agent continues to complete its phases
3. Report Agent attempts to read results
4. Report Agent receives error from data_store tool
5. Report Agent records TASK_REPORT_GENERATION_FAILED and halts

**Recovery**: Full workflow retry

**Scenario**: Report Agent fails to read results from Data_Store_Table

**Handling**:
1. Report Agent receives error from data_store tool
2. Report Agent records TASK_REPORT_GENERATION_FAILED with error message
3. Workflow tool returns error

**Recovery**: Check Data_Store_Table for data, investigate read failure, retry workflow

## Testing Strategy

### Unit Tests

**Test**: `test_data_store_tool.py`
- Test write action with valid data
- Test read action with existing data
- Test read action with missing data
- Test error handling for DynamoDB ClientError
- Test session_id retrieval from invocation_state
- Mock boto3 DynamoDB operations

**Test**: `test_analysis_agent_prompt.py`
- Verify prompt includes phases 1-5
- Verify prompt includes data_store write instructions
- Verify prompt does NOT include phases 6-7

**Test**: `test_report_agent_prompt.py`
- Verify prompt includes phases 6-7
- Verify prompt includes data_store read instructions
- Verify prompt does NOT include phases 1-5

### Manual Testing

**Test**: Local development with real AWS account
- Run workflow against test AWS account
- Verify analysis results in Data_Store_Table
- Verify report quality matches current system
- Verify S3 files are identical in format
- Verify Journal_Table events are complete

**Test**: Failure scenarios
- Simulate AWS API throttling during analysis
- Simulate S3 write failure during report
- Verify error handling and event recording
- Verify Data_Store_Table preserves analysis results

## Deployment Strategy

### Phase 1: Infrastructure Setup

1. Deploy Data_Store_Table via CDK
2. Update AgentCore Runtime IAM role with Data_Store_Table permissions
3. Add DATA_STORE_TABLE_NAME environment variable to AgentCore Runtime

### Phase 2: Tool Implementation

1. Implement data_store tool in `src/tools/data_store.py`
2. Add unit tests for data_store tool
3. Deploy and test tool in isolation

### Phase 3: Agent Refactoring

1. Create analysis_prompt.md with phases 1-5 + data_store write
2. Create report_prompt.md with phases 6-7 + data_store read
3. Create main_prompt.md with workflow orchestration
4. Update main.py to use workflow tool
5. Add strands_tools dependency

### Phase 4: Testing and Validation

1. Run unit tests
2. Run integration tests
3. Deploy to dev environment
4. Run manual tests with real AWS account
5. Compare outputs with current system
6. Validate event journaling

### Phase 5: Production Deployment

1. Deploy to production
2. Monitor CloudWatch logs for errors
3. Monitor Journal_Table for FAILED events
4. Monitor Data_Store_Table for data integrity
5. Compare S3 outputs with baseline

### Rollback Plan

If issues are detected:
1. Revert main.py to use monolithic agent
2. Keep Data_Store_Table and data_store tool (no harm)
3. Investigate issues in dev environment
4. Fix and redeploy

## Performance Considerations

### Context Window Optimization

**Before** (Monolithic Agent):
- Single agent context includes:
  - Full system prompt (all 7 phases)
  - AWS API responses (discovery + metrics)
  - Analysis reasoning
  - Report generation reasoning
  - Tool call history for all phases

**After** (Multi-Agent):
- Analysis Agent context includes:
  - Focused system prompt (phases 1-5 only)
  - AWS API responses (discovery + metrics)
  - Analysis reasoning
  - Tool call history for analysis phases
- Report Agent context includes:
  - Focused system prompt (phases 6-7 only)
  - Analysis results (from Data_Store_Table)
  - Report generation reasoning
  - Tool call history for report phases

**Benefit**:
- Reduced context window pressure for each agent
- More room for AWS API responses in Analysis Agent

## Security Considerations

### IAM Permissions

**AgentCore Runtime Role**:
- Existing: Bedrock, Lambda (read), CloudWatch (read), S3 (write), Journal_Table (write)
- New: Data_Store_Table (read/write)

**Principle of Least Privilege**:
- Data_Store_Table permissions scoped to specific table
- No cross-session access (enforced by PK=SESSION#{session_id})

### Data Sensitivity

**Analysis Results**:
- Contains AWS resource configurations
- Contains cost data
- Stored in Data_Store_Table with TTL (90 days)
- Encrypted at rest (DynamoDB default encryption)

**Access Control**:
- Only AgentCore Runtime can access Data_Store_Table
- Session-scoped data (PK includes session_id)
- TTL ensures automatic cleanup

## Future Enhancements

### Selective Retry

**Goal**: Retry only report generation without re-running analysis

**Implementation**:
1. Step Function checks Data_Store_Table for existing analysis results
2. If found, invoke workflow with "skip_analysis" flag
3. Workflow tool skips analysis task, executes only report task

**Benefits**:
- Faster retry (seconds vs minutes)
- Reduced AWS API calls
- Lower cost

### Multiple Report Formats

**Goal**: Generate multiple report formats from same analysis

**Implementation**:
1. Analysis Agent runs once
2. Multiple Report Agents run in parallel:
   - Text report (current)
   - JSON report (for APIs)
   - HTML report (for dashboards)

**Benefits**:
- Reuse expensive analysis work
- Support multiple consumers

### Analysis Caching

**Goal**: Cache analysis results for similar requests

**Implementation**:
1. Hash request parameters (region, filters, etc.)
2. Check Data_Store_Table for cached results
3. If found and fresh, skip analysis
4. If not found or stale, run analysis and cache

**Benefits**:
- Faster response for repeated requests
- Reduced AWS API calls
- Lower cost



