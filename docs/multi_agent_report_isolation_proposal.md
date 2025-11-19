# Multi-Agent Architecture: Report Generation Isolation

## Problem Statement

Current architecture has a single monolithic agent performing:
1. AWS resource discovery and metrics collection
2. Cost analysis and decision-making
3. Report generation and formatting
4. S3 file writing and evidence storage

This creates several issues:
- Context window pressure from large AWS API responses
- Token inefficiency (analysis context mixed with formatting)
- Potential timeout risks on long-running operations
- Difficult to optimize individual phases independently

## Implemented Solution: Specialized Report Agent

Isolated report generation and S3 operations into a dedicated agent with clear handoff from the analysis agent using S3 for data passing.

## Design Decisions

### 1. Context Management Between Agents

**Question**: How do we pass analysis results to the report agent without losing information?

**Implemented Solution: S3 Intermediate Storage**

After evaluating multiple options, we implemented S3-based data passing:

**Why S3 Instead of DynamoDB**:
- **Simpler Implementation**: Repurposed existing storage tool instead of creating new data_store tool
- **No Schema Management**: S3 handles arbitrary text content without schema constraints
- **Cost Effective**: S3 storage is cheaper than DynamoDB for large analysis results
- **Natural Fit**: Already using S3 for final outputs (cost_report.txt, evidence.txt)
- **Tool Reuse**: Single storage tool handles both intermediate data and final reports

**How It Works**:
- Analysis agent writes complete analysis results to S3 as `analysis.txt`
- Report agent reads `analysis.txt` from S3 using the same storage tool
- Both operations use session-scoped paths: `s3://{bucket}/{session_id}/analysis.txt`
- Storage tool enhanced with read/write actions for bidirectional operations

**Benefits**:
- Durable (survives crashes and enables retry)
- Decouples agents completely
- Can handle large datasets without token pressure
- No additional infrastructure (reuses existing S3 bucket)
- Consistent tool interface for all file operations

### 2. Orchestration Pattern Selection

**Question**: Which Strands orchestration pattern best fits this scenario?

**Implemented Solution: Sequential Agent Invocation**

After evaluating workflow patterns, we implemented a simpler sequential approach:

**Why Sequential Invocation Instead of Workflow Tool**:
- **Simplicity**: Direct agent invocation is easier to understand and debug
- **Sufficient for Linear Flow**: Analysis → Report is a simple two-step sequence
- **No Complex Dependencies**: No need for DAG management or parallel execution
- **Easier Error Handling**: Standard try-catch patterns instead of workflow error edges
- **Less Overhead**: No workflow orchestration layer or task management

**How It Works**:

- First, invoke analysis agent asynchronously with session context
- Then, invoke report agent asynchronously with same session context
- Sequential execution ensures analysis completes before report generation

**Benefits**:
- Clear execution order (analysis always runs before report)
- Natural error isolation (if analysis fails, report never runs)
- Simple to test and debug
- No additional dependencies (no strands_tools workflow)
- Maintains session context through session_id parameter

### 3. Consistent Journaling Across Agents

**Question**: How do we maintain consistent event journaling when work spans multiple agents?

**Implemented Solution: Shared Journal Table with Agent-Level Events**

Both agents write to the same DynamoDB journal table using session_id for correlation:

**Journaling Model**:
- Single DynamoDB table with session-scoped events
- Event format: `PK=SESSION#{session_id}`, `SK=EVENT#{timestamp}`
- Each agent records its own phase events using the journal tool
- No orchestration-level events needed (sequential invocation is simple enough)

**Event Flow**:
1. `AGENT_RUNTIME_INVOKE_STARTED` (main.py entrypoint)
2. `AGENT_BACKGROUND_TASK_STARTED` (main.py background_task)
3. `TASK_DISCOVERY_STARTED` (analysis agent)
4. `TASK_DISCOVERY_COMPLETED` (analysis agent)
5. `TASK_USAGE_AND_METRICS_COLLECTION_STARTED` (analysis agent)
6. `TASK_USAGE_AND_METRICS_COLLECTION_COMPLETED` (analysis agent)
7. `TASK_ANALYSIS_AND_DECISION_RULES_STARTED` (analysis agent)
8. `TASK_ANALYSIS_AND_DECISION_RULES_COMPLETED` (analysis agent)
9. `TASK_REPORT_GENERATION_STARTED` (report agent)
10. `TASK_REPORT_GENERATION_COMPLETED` (report agent)
11. `TASK_S3_WRITE_REQUIREMENTS_STARTED` (report agent)
12. `TASK_S3_WRITE_REQUIREMENTS_COMPLETED` (report agent)
13. `AGENT_BACKGROUND_TASK_COMPLETED` (main.py background_task)

**Benefits**:
- Complete audit trail across both agents
- Session-scoped correlation via session_id
- Natural fit with existing journal tool
- No additional complexity from orchestration events

### 4. Error Handling and Recovery

**Question**: How do we handle errors when they occur in either agent?

**Implemented Solution: Sequential Error Handling with S3 Persistence**

**Error Scenarios**:

**Scenario 1: Analysis Agent Fails**
- Failure point: AWS API errors, permission issues, timeout
- Behavior:
  - Analysis agent records FAILED event in journal
  - Exception propagates to background_task()
  - Report agent never executes
  - `AGENT_BACKGROUND_TASK_FAILED` event recorded
- Recovery: Step Function detects FAILED event, retries entire workflow

**Scenario 2: Report Agent Fails**
- Failure point: S3 write errors, formatting issues
- Behavior:
  - Analysis completed successfully, `analysis.txt` exists in S3
  - Report agent records FAILED event in journal
  - Exception propagates to background_task()
  - `AGENT_BACKGROUND_TASK_FAILED` event recorded
- Recovery Options:
  - **Full Retry**: Step Function retries entire workflow (re-runs analysis + report)
  - **Selective Retry** (future): Check if `analysis.txt` exists in S3, skip analysis if present

**Scenario 3: Missing Analysis Results**
- Failure point: Report agent can't read `analysis.txt` from S3
- Behavior:
  - Report agent attempts to read using `storage(action="read", filename="analysis.txt")`
  - Storage tool returns `{"success": False, "error": "..."}`
  - Report agent records FAILED event with error details
  - Exception propagates to background_task()
- Recovery: Full workflow retry (analysis must complete successfully)

**Error Handling Implementation**:

- Try block: Invoke both agents sequentially, record completion event on success
- Catch AWS ClientError: Record failed event with error code and message, return error dict
- Catch generic Exception: Record failed event with exception type and message, return error dict
- All error paths ensure proper event journaling for observability

**Benefits of S3 Persistence**:
- Analysis results preserved on failure (enables selective retry)
- Durable storage survives crashes
- Step Function can check S3 for existing analysis before retry
- Natural recovery path for report-only failures

### 5. Context Window and Token Optimization

**Question**: Will this solve context window and token usage problems?

**How Multi-Agent Architecture Optimizes Context**:

**Separation of Concerns**:
- Analysis agent: Focused prompt for discovery, metrics, and analysis only
- Report agent: Focused prompt for formatting and S3 writes only
- Each agent optimized for its specific task

**Context Window Benefits**:

1. **Analysis Agent**:
   - Smaller system prompt (no report generation instructions)
   - More room for AWS API responses
   - May better handle larger accounts with reduced context pressure

2. **Report Agent**:
   - Receives complete analysis results (essential for report quality)
   - Only formatting logic in system prompt
   - No AWS API responses or discovery details in context

3. **Flexibility**:
   - Can generate multiple report formats from same analysis
   - Report agent can be invoked multiple times without re-running analysis

**Recommendation**: Multi-agent architecture provides context optimization through separation of concerns. Actual token impact depends on context passing mechanism choice.

## Implemented Architecture

### Agent Definitions

**Analysis Agent**:
- **Responsibility**: AWS discovery, metrics collection, cost analysis (phases 1-5)
- **Tools**: use_aws, journal, calculator, storage
- **Output**: Writes complete analysis results to S3 as `analysis.txt`
- **Journaling**: Discovery, Metrics Collection, Analysis phases
- **Prompt**: `src/agents/analysis_prompt.md`

**Report Agent**:
- **Responsibility**: Report formatting, evidence compilation, S3 writes (phases 6-7)
- **Tools**: storage, journal
- **Input**: Reads analysis results from S3 (`analysis.txt`)
- **Journaling**: Report Generation, S3 Write phases
- **Output**: S3 URIs for `cost_report.txt` and `evidence.txt`
- **Prompt**: `src/agents/report_prompt.md`

### Orchestration Flow (Sequential Invocation)

```
EventBridge → Step Function → Lambda → AgentCore Runtime
                                            ↓
                                    background_task()
                                            ↓
                                analysis_agent.invoke_async()
                                            ↓
                                Writes analysis.txt to S3
                                            ↓
                                    Records phase events
                                            ↓
                                report_agent.invoke_async()
                                            ↓
                                Reads analysis.txt from S3
                                            ↓
                        Writes cost_report.txt & evidence.txt to S3
                                            ↓
                                    Records phase events
```

### Context Passing Mechanism (S3 Storage)

**Analysis Agent**:
- Performs analysis (discovery, metrics, cost analysis)
- Writes complete results to S3: `s3://{bucket}/{session_id}/analysis.txt`
- Uses storage tool: `storage(action="write", filename="analysis.txt", content=analysis_data)`

**Report Agent**:
- Reads analysis results from S3: `s3://{bucket}/{session_id}/analysis.txt`
- Uses storage tool: `storage(action="read", filename="analysis.txt")`
- Validates received data before generating report
- Writes final reports to S3

### Journaling Flow

1. `SESSION_INITIATED` (Step Function)
2. `AGENT_INVOCATION_STARTED` (Lambda)
3. `AGENT_INVOCATION_SUCCEEDED` (Lambda)
4. `AGENT_RUNTIME_INVOKE_STARTED` (main.py entrypoint)
5. `AGENT_BACKGROUND_TASK_STARTED` (main.py background_task)
6. `TASK_DISCOVERY_STARTED` (Analysis Agent)
7. `TASK_DISCOVERY_COMPLETED` (Analysis Agent)
8. `TASK_USAGE_AND_METRICS_COLLECTION_STARTED` (Analysis Agent)
9. `TASK_USAGE_AND_METRICS_COLLECTION_COMPLETED` (Analysis Agent)
10. `TASK_ANALYSIS_AND_DECISION_RULES_STARTED` (Analysis Agent)
11. `TASK_ANALYSIS_AND_DECISION_RULES_COMPLETED` (Analysis Agent)
12. `TASK_REPORT_GENERATION_STARTED` (Report Agent)
13. `TASK_REPORT_GENERATION_COMPLETED` (Report Agent)
14. `TASK_S3_WRITE_REQUIREMENTS_STARTED` (Report Agent)
15. `TASK_S3_WRITE_REQUIREMENTS_COMPLETED` (Report Agent)
16. `AGENT_BACKGROUND_TASK_COMPLETED` (main.py background_task)

## Implementation Summary

### What Changed

**Before (Monolithic Agent)**:
- Single agent with 7-phase prompt
- Tools: use_aws, journal, storage, calculator
- All phases executed in one context
- Large context window with mixed concerns

**After (Multi-Agent Architecture)**:
- Two specialized agents with focused prompts
- Analysis Agent: phases 1-5, tools: use_aws, journal, calculator, storage
- Report Agent: phases 6-7, tools: storage, journal
- Sequential invocation with S3-based data passing
- Reduced context window per agent

### Key Implementation Decisions

| Decision | Chosen Approach | Rationale |
|----------|----------------|-----------|
| **Data Passing** | S3 intermediate storage | Simpler than DynamoDB, reuses existing infrastructure, cost-effective |
| **Orchestration** | Sequential agent invocation | Simpler than workflow tool, sufficient for linear flow |
| **Storage Tool** | Enhanced with read/write actions | Avoided creating new tool, consistent interface |
| **Journaling** | Shared table, agent-level events | Complete audit trail, no orchestration complexity |
| **Error Handling** | Try-catch with S3 persistence | Natural Python patterns, enables selective retry |

### Benefits Achieved

| Criterion | Monolithic Agent | Multi-Agent (Sequential) | Improvement |
|-----------|------------------|--------------------------|-------------|
| **Context Window Pressure** | High (all phases in one context) | Medium (split across agents) | ✓ Reduced |
| **Token Efficiency** | Low (mixed concerns) | Medium (specialized prompts) | ✓ Improved |
| **Failure Isolation** | None (all-or-nothing) | High (analysis preserved in S3) | ✓ Achieved |
| **Retry Capability** | Full re-run only | Report-only retry possible | ✓ Enabled |
| **Code Complexity** | Low (single agent) | Low (sequential invocation) | ✓ Maintained |
| **Maintainability** | Medium (large prompt) | High (separated concerns) | ✓ Improved |
| **Testing** | Simple (one agent) | Medium (two agents, shared S3) | ~ Acceptable |

### Infrastructure Changes

**No New Resources Required**:
- Reused existing S3 bucket for intermediate storage
- Reused existing DynamoDB journal table
- No additional IAM permissions needed
- No new environment variables

**Code Changes**:
- Split `prompt.md` into `analysis_prompt.md` and `report_prompt.md`
- Enhanced `storage.py` tool with read action
- Updated `main.py` to create two agents and invoke sequentially
- Maintained backward compatibility with existing infrastructure

## Lessons Learned

### Design Simplicity Wins

**Initial Plan**: Use Strands workflow tool with DynamoDB data store
- Workflow tool for DAG orchestration
- New data_store tool for DynamoDB operations
- Separate Data_Store_Table infrastructure

**Actual Implementation**: Sequential invocation with S3 storage
- Direct agent invocation (simpler than workflow)
- Enhanced existing storage tool (no new tool needed)
- Reused existing S3 bucket (no new infrastructure)

**Lesson**: For simple linear flows, sequential invocation is clearer and easier to maintain than workflow orchestration. Evaluate whether complexity is justified before adding orchestration layers.

### Tool Reuse Over Tool Proliferation

**Initial Plan**: Create separate data_store tool for intermediate data
**Actual Implementation**: Enhanced storage tool with read/write actions

**Lesson**: Before creating new tools, evaluate if existing tools can be extended. The storage tool naturally handles both intermediate data (analysis.txt) and final outputs (cost_report.txt, evidence.txt) with a consistent interface.

### S3 vs DynamoDB for Data Passing

**Why S3 Won**:
- No schema constraints (handles arbitrary text)
- Lower cost for large analysis results
- Natural fit with existing S3 usage
- Simpler implementation (no new table)

**When DynamoDB Would Be Better**:
- Structured data with frequent queries
- Need for atomic updates or transactions
- Small data sizes (< 4KB)
- Complex access patterns

**Lesson**: Choose storage based on data characteristics and access patterns, not just familiarity. S3 is excellent for large, unstructured, write-once-read-once data.

### Context Window Optimization

**Measured Impact**:
- Analysis Agent: Reduced prompt size by ~40% (removed phases 6-7)
- Report Agent: Reduced prompt size by ~60% (removed phases 1-5)
- More room for AWS API responses in analysis context
- More room for detailed report formatting in report context

**Lesson**: Multi-agent architecture provides real context window benefits when agents have truly distinct responsibilities. The separation must be meaningful, not arbitrary.

## Future Enhancements

### 1. Selective Retry (Report-Only)

**Current State**: Full workflow retry on any failure

**Enhancement**:
- Step Function checks S3 for existing `analysis.txt`
- If found and fresh (< 1 hour old), skip analysis agent
- Invoke only report agent for retry

**Benefits**:
- Faster retry (seconds vs minutes)
- Reduced AWS API calls
- Lower cost

**Implementation Approach**:

- Check if analysis.txt exists in S3 for the session
- If exists and fresh: Skip analysis agent, invoke only report agent
- If missing or stale: Run full workflow (both agents sequentially)

### 2. Multiple Report Formats

**Goal**: Generate multiple report formats from same analysis

**Implementation**:
- Analysis agent runs once, writes `analysis.txt`
- Multiple report agents run in parallel:
  - Text report agent (current)
  - JSON report agent (for APIs)
  - HTML report agent (for dashboards)

**Benefits**:
- Reuse expensive analysis work
- Support multiple consumers
- Parallel report generation

### 3. Analysis Caching

**Goal**: Cache analysis results for similar requests

**Implementation**:
- Hash request parameters (region, filters, time window)
- Check S3 for cached `analysis.txt` with matching hash
- If found and fresh, skip analysis
- If not found or stale, run analysis and cache

**Benefits**:
- Instant response for repeated requests
- Reduced AWS API calls
- Lower cost

## References

- Strands Multi-Agent Patterns: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/
- Strands Agent Invocation: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agent/
- Current Orchestration Decisions: docs/orchrestation_decisions_record.md
- Current Journaling Guide: docs/event_journaling_guide.md

