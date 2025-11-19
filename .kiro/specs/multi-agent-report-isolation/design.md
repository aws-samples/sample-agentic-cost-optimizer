# Design Document

## Overview

This design implements a multi-agent architecture for the cost optimization system by separating the analysis and report generation concerns into specialized agents. The current monolithic agent in `src/agents/main.py` has been refactored to sequentially invoke two specialized agents: an Analysis Agent (phases 1-5) and a Report Agent (phases 6-7). Data passing between agents is handled through S3 using an enhanced storage tool. This separation reduces context window pressure, improves token efficiency, enables failure isolation, and allows selective retry of the report generation phase without re-running expensive AWS discovery and analysis operations.

## Architecture

### High-Level Component Diagram

```
EventBridge → Step Function → Lambda Invoker → AgentCore Runtime
                                                      ↓
                                              background_task()
                                                      ↓
                                          analysis_agent.invoke_async()
                                                      ↓
                                              Writes analysis.txt
                                                      ↓
                                                  S3 Bucket
                                                      ↓
                                          report_agent.invoke_async()
                                                      ↓
                                              Reads analysis.txt
                                                      ↓
                                    Writes cost_report.txt & evidence.txt
```

### Component Responsibilities

**background_task Function**
- Orchestration function in src/agents/main.py
- Sequentially invokes Analysis Agent and Report Agent using invoke_async()
- Decorated with @app.async_task for AgentCore integration
- Passes session_id parameter to both agents
- Handles exceptions and records AGENT_BACKGROUND_TASK_FAILED on errors

**Analysis Agent**
- Executes phases 1-5 of the current workflow:
  1. Discovery (Inventory)
  2. Usage and Metrics Collection
  3. Analysis and Decision Rules
  4. Recommendation Format
  5. Cost Estimation Method
- Has access to: use_aws, journal, calculator, storage tools
- Writes complete analysis results to S3 as analysis.txt
- Records phase events to Journal_Table

**Report Agent**
- Executes phases 6-7 of the current workflow:
  6. Output Contract (plain text)
  7. S3 Write Requirements
- Has access to: storage, journal tools
- Reads complete analysis results from S3 (analysis.txt)
- Generates cost_report.txt and evidence.txt files
- Writes files to S3 using storage tool
- Records phase events to Journal_Table

## Components and Interfaces

### 1. Enhanced Storage Tool

**Purpose**: Enable both reading and writing files to S3 for data passing between agents and final outputs

**Location**: `src/tools/storage.py`

**Interface**:
```python
@tool(context=True)
def storage(
    action: str,  # "write" or "read"
    filename: str,  # e.g., "analysis.txt", "cost_report.txt"
    tool_context: ToolContext,
    content: str = ""  # For write action
) -> Dict[str, Any]:
    """
    Read or write text content to S3 with automatic session-based path management.
    
    Write action:
        - Retrieves session_id from tool_context.invocation_state
        - Writes to S3 at path {session_id}/{filename}
        - Returns: {"success": True, "s3_uri": "...", "size_bytes": ..., "timestamp": "..."}
    
    Read action:
        - Retrieves session_id from tool_context.invocation_state
        - Reads from S3 at path {session_id}/{filename}
        - Returns: {"success": True, "content": "...", "s3_uri": "...", "timestamp": "..."}
        - Or: {"success": False, "error": "...", "timestamp": "..."}
    """
```

**Implementation Details**:
- Enhanced existing `storage.py` tool with read capability
- Uses boto3 S3 resource
- Retrieves session_id from `tool_context.invocation_state.get("session_id")`
- Handles ClientError exceptions and returns structured error responses
- Includes logging for debugging
- Reuses existing S3_BUCKET_NAME environment variable

**S3 Path Structure**:
```
Bucket: {S3_BUCKET_NAME}
Path: {session_id}/{filename}
Examples:
  - {session_id}/analysis.txt (intermediate data from Analysis Agent)
  - {session_id}/cost_report.txt (final output from Report Agent)
  - {session_id}/evidence.txt (final output from Report Agent)
```

**Benefits of S3 for Data Passing**:
- No new infrastructure required (reuses existing S3 bucket)
- No schema constraints (handles arbitrary text content)
- Cost-effective for large analysis results
- Durable storage enables selective retry
- Consistent tool interface for all file operations

### 2. Agent Creation and Orchestration

**Before (Monolithic Agent)**:
```python
# Single agent with all phases
agent = Agent(
    model=bedrock_model,
    system_prompt=SYSTEM_PROMPT,  # All 7 phases
    tools=[use_aws, journal, storage, calculator],
)
```

**After (Multi-Agent with Sequential Invocation)**:
```python
# Two specialized agents
analysis_agent = create_agent(
    system_prompt=ANALYSIS_PROMPT,  # Phases 1-5
    tools=[use_aws, journal, calculator, storage]
)

report_agent = create_agent(
    system_prompt=REPORT_PROMPT,  # Phases 6-7
    tools=[storage, journal]
)

# Sequential invocation in background_task
@app.async_task
async def background_task(user_message: str, session_id: str):
    try:
        await analysis_agent.invoke_async(
            "Analyze AWS costs and identify optimization opportunities",
            session_id=session_id,
        )
        
        response = await report_agent.invoke_async(
            "Generate cost optimization report based on analysis results",
            session_id=session_id,
        )
        
        record_event(status=EventStatus.AGENT_BACKGROUND_TASK_COMPLETED)
        return response
    except Exception as e:
        record_event(status=EventStatus.AGENT_BACKGROUND_TASK_FAILED)
        return error_dict
```

**Key Changes**:
- No workflow tool needed - simple sequential invocation
- Each agent has focused prompt and minimal tools
- Session context maintained through session_id parameter
- Natural error handling with try-catch
- Analysis must complete before report starts

### 3. Analysis Agent Prompt

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

1. Use the storage tool with action="write"
2. Set filename="analysis.txt"
3. Set content to include:
   - All discovery data (function names, ARNs, configurations)
   - All metrics data (invocations, errors, duration, memory usage)
   - All formatted recommendations with full details
   - All cost estimates with calculation inputs
   - All evidence for the Evidence Appendix

Format the content as structured text that preserves all details.

Example:
```
storage(
    action="write",
    filename="analysis.txt",
    content="""
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

### 4. Report Agent Prompt

**Location**: `src/agents/report_prompt.md`

**Content**: Extract phases 6-7 from current `prompt.md`:
- Output Contract (plain text)
- S3 Write Requirements

**Key Additions**:
```markdown
## Loading Analysis Results

Before generating the report, you MUST load the analysis results:

1. Use the storage tool with action="read"
2. Set filename="analysis.txt"
3. Check the response:
   - If success is true, extract content
   - If success is false, record TASK_REPORT_GENERATION_FAILED and halt

Example:
```
result = storage(action="read", filename="analysis.txt")

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
    analysis_data = result.get("content")
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

Use the storage tool to write final reports:
- storage(action="write", filename="cost_report.txt", content=report_content)
- storage(action="write", filename="evidence.txt", content=evidence_content)
```

## Data Models

### Analysis Results Data Structure

The analysis results stored in S3 as analysis.txt will be structured text containing:

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
1. Analysis results preserved in S3 (analysis.txt)
2. Report Agent records TASK_S3_WRITE_REQUIREMENTS_FAILED event to Journal_Table
3. Exception propagates to background_task
4. AGENT_BACKGROUND_TASK_FAILED event recorded

**Recovery Options**:
1. Retry entire workflow (re-runs analysis + report)
2. Manual intervention: Check S3 for analysis.txt, fix S3 issue, retry workflow
3. Future enhancement: Step Function logic to detect existing analysis.txt and retry only report agent

### Storage Tool Failures

**Scenario**: Analysis Agent fails to write results to S3

**Handling**:
1. Analysis Agent logs error in "Gaps & Limitations"
2. Analysis Agent may continue or fail depending on error severity
3. Report Agent attempts to read results
4. Report Agent receives error from storage tool
5. Report Agent records TASK_REPORT_GENERATION_FAILED and halts

**Recovery**: Full workflow retry

**Scenario**: Report Agent fails to read results from S3

**Handling**:
1. Report Agent receives error from storage tool
2. Report Agent records TASK_REPORT_GENERATION_FAILED with error message
3. Exception propagates to background_task

**Recovery**: Check S3 for analysis.txt, investigate read failure, retry workflow

## Testing Strategy

### Unit Tests

**Test**: `test_storage_tool.py`
- Test write action with valid data
- Test read action with existing data
- Test read action with missing data
- Test error handling for S3 ClientError
- Test session_id retrieval from invocation_state
- Mock boto3 S3 operations

**Test**: `test_analysis_agent_prompt.py`
- Verify prompt includes phases 1-5
- Verify prompt includes storage write instructions for analysis.txt
- Verify prompt does NOT include phases 6-7

**Test**: `test_report_agent_prompt.py`
- Verify prompt includes phases 6-7
- Verify prompt includes storage read instructions for analysis.txt
- Verify prompt does NOT include phases 1-5

### Manual Testing

**Test**: Local development with real AWS account
- Run sequential agent invocation against test AWS account
- Verify analysis results in S3 (analysis.txt)
- Verify report quality matches current system
- Verify S3 files are identical in format (cost_report.txt, evidence.txt)
- Verify Journal_Table events are complete

**Test**: Failure scenarios
- Simulate AWS API throttling during analysis
- Simulate S3 write failure during report
- Verify error handling and event recording
- Verify S3 preserves analysis.txt for selective retry

## Deployment Strategy

### Phase 1: Tool Enhancement

1. Enhance storage tool in `src/tools/storage.py` with read action
2. Add unit tests for storage tool read action
3. Deploy and test tool in isolation

### Phase 2: Agent Refactoring

1. Create analysis_prompt.md with phases 1-5 + storage write for analysis.txt
2. Create report_prompt.md with phases 6-7 + storage read for analysis.txt
3. Update main.py to create two agents and invoke sequentially
4. No new dependencies needed (no strands_tools workflow)

### Phase 3: Testing and Validation

1. Run unit tests
2. Run integration tests
3. Deploy to dev environment
4. Run manual tests with real AWS account
5. Compare outputs with current system
6. Validate event journaling

### Phase 4: Production Deployment

1. Deploy to production
2. Monitor CloudWatch logs for errors
3. Monitor Journal_Table for FAILED events
4. Monitor S3 for analysis.txt and final reports
5. Compare S3 outputs with baseline

### Rollback Plan

If issues are detected:
1. Revert main.py to use monolithic agent
2. Enhanced storage tool remains backward compatible (no harm)
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
  - Analysis results (from S3 analysis.txt)
  - Report generation reasoning
  - Tool call history for report phases

**Benefit**:
- Reduced context window pressure for each agent
- More room for AWS API responses in Analysis Agent

## Security Considerations

### IAM Permissions

**AgentCore Runtime Role**:
- Existing: Bedrock, Lambda (read), CloudWatch (read), S3 (read/write), Journal_Table (write)
- No new permissions needed (reuses existing S3 access)

**Principle of Least Privilege**:
- S3 permissions already scoped to specific bucket
- Session-scoped paths (enforced by {session_id}/ prefix)

### Data Sensitivity

**Analysis Results**:
- Contains AWS resource configurations
- Contains cost data
- Stored in S3 with session-scoped paths
- Encrypted at rest (S3 default encryption)
- Can be cleaned up via S3 lifecycle policies

**Access Control**:
- Only AgentCore Runtime can access S3 bucket
- Session-scoped data (path includes session_id)
- S3 lifecycle policies can enforce automatic cleanup

## Future Enhancements

### Selective Retry

**Goal**: Retry only report generation without re-running analysis

**Implementation**:
1. Step Function checks S3 for existing analysis.txt
2. If found and fresh (< 1 hour old), skip analysis agent
3. Invoke only report agent with existing session_id

**Benefits**:
- Faster retry (seconds vs minutes)
- Reduced AWS API calls
- Lower cost

### Multiple Report Formats

**Goal**: Generate multiple report formats from same analysis

**Implementation**:
1. Analysis Agent runs once, writes analysis.txt
2. Multiple Report Agents run in parallel:
   - Text report agent (current)
   - JSON report agent (for APIs)
   - HTML report agent (for dashboards)

**Benefits**:
- Reuse expensive analysis work
- Support multiple consumers
- Parallel report generation

### Analysis Caching

**Goal**: Cache analysis results for similar requests

**Implementation**:
1. Hash request parameters (region, filters, etc.)
2. Check S3 for cached analysis.txt with matching hash
3. If found and fresh, skip analysis
4. If not found or stale, run analysis and cache

**Benefits**:
- Instant response for repeated requests
- Reduced AWS API calls
- Lower cost



