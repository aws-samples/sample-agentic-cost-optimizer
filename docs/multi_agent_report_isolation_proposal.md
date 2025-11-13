# Multi-Agent Architecture Proposal: Report Generation Isolation

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

## Proposed Solution: Specialized Report Agent

Isolate report generation and S3 operations into a dedicated agent with clear handoff from the analysis agent.

## Critical Design Questions

### 1. Context Management Between Agents

**Question**: How do we pass analysis results to the report agent without losing information?

**Options Analysis**:

**Option A: Explicit Message Passing**
- Mechanism: Analysis agent returns structured text/JSON, passed as prompt to report agent
- Context passing: Full analysis results serialized in handoff message
- Pros:
  - LLM can reason about the data
  - Clear audit trail in conversation history
  - Works with all orchestration patterns
- Cons:
  - Token-heavy (analysis results in prompt)
  - Serialization/deserialization overhead
  - Context window pressure (defeats isolation purpose)

**Option B: DynamoDB Intermediate Storage**
- Mechanism: Analysis agent writes results to DynamoDB, report agent reads via session_id
- Context passing: Session-scoped data store
- Pros:
  - Durable (survives crashes)
  - Decouples agents completely
  - Can handle large datasets
  - Provides audit trail
- Cons:
  - Additional DynamoDB read/write costs
  - Latency overhead
  - Schema management complexity
  - Requires error handling for missing data

**Recommendation**: Evaluate both options based on requirements. **Option B** provides durability and retry capability but adds complexity. **Option A** is simpler but requires full workflow retry on any failure.

### 2. Orchestration Pattern Selection

**Question**: Which Strands orchestration pattern best fits this scenario?

**Pattern Comparison**:

| Criteria | Graph | Swarm | Workflow |
|----------|-------|-------|----------|
| **Execution Flow** | Controlled but dynamic (LLM decides path) | Sequential autonomous handoffs | Deterministic DAG |
| **Context Passing** | Shared dict (full transcript) | Shared context (handoff history) | Task outputs to dependencies |
| **Error Handling** | Explicit error edges | Agent-driven handoff to error handler | Systemic (halts downstream) |
| **Cycles Allowed** | Yes | Yes | No |
| **Best For** | Conditional branching | Collaborative exploration | Repeatable processes |
| **Our Use Case Fit** | Medium | Medium | High |

**Selected Pattern: Workflow**

**Why Workflow**:
- Cost optimization is deterministic, repeatable (analysis → report)
- No conditional branching needed
- Clear task dependencies (report depends on analysis)
- Automatic dependency management
- Error isolation (analysis failure prevents report)

**Why Not Graph**: Over-engineered for linear flow; LLM-driven path adds unnecessary non-determinism

**Why Not Swarm**: Non-deterministic handoff timing; agent must explicitly decide when to hand off

**Recommendation**: Use **Workflow Pattern** for deterministic, repeatable execution.

### 3. Consistent Journaling Across Agents

**Question**: How do we maintain consistent event journaling when work spans multiple agents?

**Current Journaling Model**:
- Single DynamoDB table with session-scoped events
- Event format: `PK=SESSION#{session_id}`, `SK=EVENT#{timestamp}`
- Events track: Discovery, Metrics Collection, Analysis, Report Generation, S3 Writes

**Phased Approach**:

**Approach 1 (Initial): Same Journal Table with Workflow Events**
- Workflow records task boundaries to same journal table
- Proves centralized event ordering
- Tests complexity of workflow having journal tool access
- Validates if task boundary tracking adds value
- Expected outcome: Likely too complex; duplicates agent-level journaling

**Approach 2 (Fallback): Each Agent Journals Independently**
- Simplest approach after proving Approach 1 complexity
- Each agent owns its phase tracking
- Natural fit with current journal tool design
- No workflow coordination needed

**Evaluation Criteria**:
- Does workflow journaling provide value beyond agent journaling?
- Is the added complexity justified?
- Does it improve debugging or observability?
- Is event ordering clearer with workflow events?

**Recommendation**: Start with **Approach 1 (Same Journal Table)** as experiment to validate complexity, then migrate to **Approach 2 (Agent-Only Journaling)** if needed.

### 4. Error Handling and Recovery

**Question**: How do we handle errors when they occur in either agent?

**Error Scenarios**:

**Scenario 1: Analysis Task Fails**
- Failure point: AWS API errors, permission issues, timeout
- Workflow behavior:
  - Analysis task records FAILED event in journal
  - Workflow halts immediately (report task never runs)
  - Workflow returns error
  - Analysis results may be partially available (depending on context passing mechanism)
- Recovery: Step Function detects FAILED event, can retry entire workflow

**Scenario 2: Report Task Fails**
- Failure point: S3 write errors, formatting issues
- Workflow behavior:
  - Analysis task completed successfully
  - Report task records FAILED event in journal
  - Workflow returns error
  - Analysis results preserved (depending on context passing mechanism)
- Recovery: 
  - Option 1: Retry entire workflow (re-runs analysis + report)
  - Option 2: Report-only retry (if context passing mechanism supports it)
  - Option 3: Step Function conditional retry (check if analysis results exist)

**Scenario 3: Task Dependency Failure**
- Failure point: Analysis task output missing or corrupted
- Potential causes: Context passing mechanism failure, serialization errors
- Workflow behavior:
  - Analysis task completes but output is invalid
  - Report task receives invalid/missing input
  - Report task validates input, records FAILED if invalid
  - Workflow halts with validation error
- Recovery: Retry entire workflow (analysis must succeed for report to run)

**Error Handling Strategy**:

1. **Task-Level Validation**:
   - Analysis task validates results before passing to next task
   - Report task validates received context before generating report
   - Record validation failures in journal with specific error details

2. **Workflow-Level Error Handling**:
   - Workflow halts on first task failure (prevents cascading errors)
   - Failed workflow returns error
   - Step Function can decide: retry, alert, or terminate

3. **Context Persistence for Recovery** (if using durable storage):
   - Analysis task persists results on success
   - If report fails, analysis results are preserved
   - Enables report-only retry without re-running analysis
   - Step Function can check for persisted results before deciding to retry

4. **Error Event Journaling**:
   - Each task records its own failures in journal
   - Error messages include task name and context
   - Step Function polls for FAILED events
   - Journal provides complete audit trail

5. **Step Function Retry Logic** (if using durable context storage):
   - Check if analysis results exist in storage
   - If yes: retry report task only
   - If no: retry entire workflow

**Recommendation**: Use Workflow's built-in error handling (halt on failure). If using durable context storage, implement Step Function logic to enable report-only retry when analysis results exist.

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

## Proposed Architecture

### Agent Definitions

**Orchestrator Agent**:
- **Responsibility**: Manages workflow execution
- **Tools**: cost_optimization_workflow (Workflow tool)
- **Output**: Workflow execution results

**Analysis Agent** (Task 1):
- **Responsibility**: AWS discovery, metrics collection, cost analysis
- **Tools**: use_aws, journal, calculator
- **Output**: Analysis results (passed to Task 2 by workflow)
- **Journaling**: Discovery, Metrics Collection, Analysis phases

**Report Agent** (Task 2):
- **Responsibility**: Report formatting, evidence compilation, S3 writes
- **Tools**: storage, journal
- **Input**: Analysis results from Task 1 (provided by workflow)
- **Journaling**: Report Generation, S3 Write phases
- **Output**: S3 URIs for cost_report.txt and evidence.txt

### Orchestration Flow (Workflow Pattern)

- EventBridge triggers Step Function
- Step Function invokes Lambda
- Lambda invokes AgentCore with Orchestrator Agent
- Orchestrator Agent executes Cost Optimization Workflow tool
- Workflow executes Task 1 (Analysis Agent)
- Analysis Agent writes results to DynamoDB
- Workflow executes Task 2 (Report Agent)
- Report Agent reads from DynamoDB and writes to S3

### Context Passing Mechanism (Workflow + DynamoDB)

**Task 1: Analysis Agent**
- Performs analysis (discovery, metrics, cost analysis)
- Writes results to DynamoDB: `PK=SESSION#{session_id}`, `SK=ANALYSIS_RESULTS`

**Task 2: Report Agent**
- Receives Task 1 output automatically (workflow dependency)
- Reads full analysis results from DynamoDB using session_id
- Generates report from analysis results
- Writes report to S3

### Journaling Flow

1. SESSION_INITIATED (Step Function)
2. AGENT_INVOCATION_STARTED (Lambda)
3. AGENT_INVOCATION_SUCCEEDED (Lambda)
4. AGENT_RUNTIME_INVOKE_STARTED (AgentCore)
5. AGENT_BACKGROUND_TASK_STARTED (AgentCore)
6. TASK_DISCOVERY_STARTED (Analysis Agent)
7. TASK_DISCOVERY_COMPLETED (Analysis Agent)
8. TASK_USAGE_AND_METRICS_COLLECTION_STARTED (Analysis Agent)
9. TASK_USAGE_AND_METRICS_COLLECTION_COMPLETED (Analysis Agent)
10. TASK_ANALYSIS_AND_DECISION_RULES_STARTED (Analysis Agent)
11. TASK_ANALYSIS_AND_DECISION_RULES_COMPLETED (Analysis Agent)
12. TASK_REPORT_GENERATION_STARTED (Report Agent)
13. TASK_REPORT_GENERATION_COMPLETED (Report Agent)
14. TASK_S3_WRITE_REQUIREMENTS_STARTED (Report Agent)
15. TASK_S3_WRITE_REQUIREMENTS_COMPLETED (Report Agent)
16. AGENT_BACKGROUND_TASK_COMPLETED (AgentCore)

## Decision Matrix

| Criterion | Monolithic Agent | Multi-Agent (Workflow) | Winner |
|-----------|------------------|------------------------|--------|
| **Context Window Pressure** | High (all phases in one context) | Medium (split across agents) | Multi-Agent |
| **Token Efficiency** | Low (mixed concerns) | Medium (specialized prompts) | Multi-Agent |
| **Failure Isolation** | None (all-or-nothing) | High (analysis preserved) | Multi-Agent |
| **Retry Capability** | Full re-run only | Report-only retry possible | Multi-Agent |
| **Code Complexity** | Low (single agent) | Medium (orchestration) | Monolithic |
| **Maintainability** | Medium (large prompt) | High (separated concerns) | Multi-Agent |
| **Testing** | Simple (one agent) | Complex (integration tests) | Monolithic |

## Next Steps

1. **Implement** multi-agent architecture with Workflow pattern
2. **Iterate** based on findings and metrics
3. **Document** final architecture and deployment guide

## References

- Strands Multi-Agent Patterns: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/
- Strands Swarm Pattern: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/swarm/
- Strands A2A Protocol: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agent-to-agent/
- Current Orchestration Decisions: docs/orchrestation_decisions_record.md
- Current Journaling Guide: docs/event_journaling_guide.md
