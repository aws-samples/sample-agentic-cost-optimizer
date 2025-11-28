# AgentCore Logging Investigation

## Overview

This document records our investigation into AgentCore logging behavior, multiple log streams, and the challenges we encountered while trying to implement agent status monitoring and observability.

## Initial Problem

When we invoked the agent, we observed too many log streams being created in CloudWatch. This unexpected behavior led us to investigate what was causing multiple streams and whether our logging implementation was correct.

## Investigation Findings

### AgentCore Log Stream Behavior

**Discovery**: The number of log streams depends on the deployment method:

**Agent-as-Container Deployment** (Docker image):
- Creates **~11 log streams** (10 runtime + 1 OTEL)
- AgentCore pre-warms **10 containers** for performance and scalability
- Each container gets its own log stream: `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/runtime-logs-<UUID>`
- Plus 1 OTEL stream: `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/otel-rt-logs`

**Agent-as-Code Deployment** (Python code via S3):
- Creates **only 2 log streams** (1 runtime + 1 OTEL)
- Single runtime stream: `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/runtime-logs-<UUID>`
- Single OTEL stream: `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/otel-rt-logs`

**Current Implementation**:
```typescript
// infra/lib/agent.ts - Using agent-as-code deployment
const agentRuntimeArtifact = AgentRuntimeArtifact.fromS3(
  {
    bucketName: deploymentPackage.s3BucketName,
    objectKey: deploymentPackage.s3ObjectKey,
  },
  AgentCoreRuntime.PYTHON_3_12,
  ['opentelemetry-instrument', 'src/agents/main.py'],
);
```

**Why This Matters**:
- **Agent-as-code** = cleaner CloudWatch logs (only 2 streams)
- **Agent-as-container** = more log streams but better cold start performance (pre-warmed containers)
- The UUID in log stream names represents container instances, not session IDs
- Session IDs are tracked separately via `context.session_id` in the agent code

**Log Stream Types**:
- **runtime-logs-<UUID>**: Standard logs (stdout/stderr) from agent execution
- **otel-rt-logs**: OTEL structured logs with telemetry data
- **Traces and spans**: `/aws/spans/default` (separate log group)

### False Assumptions We Made

1. **Multiple streams = Multiple executions** ❌
   - **Reality**: Deployment creates 11 streams regardless of execution count
   - **Impact**: Led to confusion about logging volume and behavior

2. **Complex logging setup needed** ❌
   - **Reality**: AgentCore handles logging automatically
   - **Impact**: Over-engineered logging solutions

3. **Manual status tracking required** ❌
   - **Reality**: `@app.async_task` decorator handles status automatically
   - **Impact**: Unnecessary complexity with manual ping handlers

## What We Tried

### 1. Complex Multi-Logger Setup
```python
# What we tried (unnecessary)
strands_logger = logging.getLogger("strands")
agentcore_logger = app.logger
custom_handler = logging.StreamHandler()
```

**Result**: Over-complicated, mixed logging sources, confusion about where logs appear.

### 2. Manual Status Tracking
```python
# What we tried (caused recursion)
@app.ping
def custom_ping_handler():
    current_status = app.get_current_ping_status()  # Recursion!
    logger.info(f"Status: {current_status.value}")
    return current_status
```

**Result**: Recursion errors, unnecessary complexity.

### 3. Manual Async Task Management
```python
# What we tried (manual task tracking)
@app.entrypoint
def invoke(payload):
    task_id = app.add_async_task("cost_analysis", {...})
    thread = threading.Thread(target=background_agent_processing, args=(...), daemon=True)
    thread.start()
    return f"Started analysis for session {session_id}"

def background_agent_processing(user_message: str, session_id: str, task_id: str):
    response = agent(user_message, session_id=session_id)
    app.complete_async_task(task_id)
```

**Result**: Worked but required manual task lifecycle management and threading.

## What Actually Works

### 1. Simple AgentCore Logger
```python
app = BedrockAgentCoreApp()
logger = app.logger  # Use built-in logger only

logger.info(f"Request received - Session: {session_id}")
logger.error(f"Background task failed - Session: {session_id}: {error_code} - {error_message}")
```

### 2. Automatic Status Management with @app.async_task
```python
# Decorator automatically manages AgentCore status: HEALTHY_BUSY while running, HEALTHY when complete
@app.async_task
async def background_task(user_message: str, session_id: str):
    # Status automatically becomes HEALTHY_BUSY
    await analysis_agent.invoke_async(
        "Analyze AWS costs and identify optimization opportunities",
        session_id=session_id,
    )
    response = await report_agent.invoke_async(
        "Generate cost optimization report based on analysis results",
        session_id=session_id,
    )
    # Status automatically returns to HEALTHY
    return response
```

### 3. Fire-and-Forget Pattern with asyncio.create_task
```python
@app.entrypoint
async def invoke(payload, context: RequestContext):
    user_message = payload.get("prompt", "Hello")
    session_id = context.session_id  # Get session_id from AgentCore context
    
    # Start background task (returns immediately)
    asyncio.create_task(background_task(user_message, session_id))
    
    return {
        "message": f"Started processing request for session {session_id}",
        "session_id": session_id,
        "status": "started",
    }
```

## Key Learnings

### AgentCore Logging Behavior
- **Runtime logs**: Basic lifecycle events (agent startup, invocation)
- **otel-rt-logs**: Continuous telemetry stream with structured JSON
- **Automatic status logging**: AgentCore logs status changes internally
- **Log stream count depends on deployment method**:
  - Agent-as-container: ~11 streams (10 pre-warmed containers + 1 OTEL)
  - Agent-as-code: 2 streams (1 runtime + 1 OTEL) ← **Our implementation**

### What We Learned
1. **AgentCore's built-in logger works** - Simple and integrates with AgentCore streams
2. **@app.async_task decorator is the recommended approach** - Handles status automatically without manual `add_async_task()` and `complete_async_task()` calls
3. **External loggers didn't create extra streams** - Powertools and other logging mechanisms didn't contribute to the 11+ stream issue
4. **Native async is cleaner** - Strands has `invoke_async()`, no ThreadPoolExecutor or manual threading needed
5. **RequestContext provides session_id** - No need to manually pass session_id through payload, AgentCore provides it via `context.session_id`
6. **asyncio.create_task() for fire-and-forget** - Cleaner than manual threading for background task execution

**Note**: We haven't confirmed with the AgentCore service team whether using external loggers (like Powertools) is discouraged or problematic. The multiple streams appear to be related to AgentCore's internal architecture, not our logging choices.

### What to Monitor
- **otel-rt-logs stream** - Contains detailed execution telemetry
- **Agent status transitions** - HEALTHY ↔ HEALTHY_BUSY (automatic via `@app.async_task`)
- **Error logs** - Appear in both runtime-logs and otel-rt-logs streams
- **DynamoDB event journal** - Workflow-level tracking (SESSION_INITIATED, AGENT_INVOCATION_STARTED, AGENT_BACKGROUND_TASK_COMPLETED, etc.)
- **Step Function execution logs** - Orchestration-level visibility

## Resolved Questions

### Why Does Agent Deployment Create Multiple Log Streams?

**Answer**: The number of log streams depends on the deployment method:

**Agent-as-Container Deployment** (Docker image):
- Creates **~11 log streams** (10 runtime + 1 OTEL)
- AgentCore pre-warms **10 containers** for performance and scalability
- Each container gets its own log stream with UUID: `runtime-logs-<UUID>`
- Plus 1 OTEL stream for telemetry: `otel-rt-logs`
- **Trade-off**: More log streams but better cold start performance

**Agent-as-Code Deployment** (Python code via S3):
- Creates **only 2 log streams** (1 runtime + 1 OTEL)
- Single runtime stream: `runtime-logs-<UUID>`
- Single OTEL stream: `otel-rt-logs`
- **Trade-off**: Cleaner logs but potentially slower cold starts

**Our Implementation**:
We use **agent-as-code deployment** via `AgentRuntimeArtifact.fromS3()`:
```typescript
// infra/lib/agent.ts
const agentRuntimeArtifact = AgentRuntimeArtifact.fromS3(
  {
    bucketName: deploymentPackage.s3BucketName,
    objectKey: deploymentPackage.s3ObjectKey,
  },
  AgentCoreRuntime.PYTHON_3_12,
  ['opentelemetry-instrument', 'src/agents/main.py'],
);
```

**Impact**: 
- Cleaner CloudWatch log groups (only 2 streams)
- Easier to find relevant application logs
- Lower CloudWatch costs
- Simpler log management

**Key Learning**: 
- The UUID in log stream names represents **container instances**, not session IDs or agent versions
- Session IDs are tracked separately via `context.session_id` in the agent code

## Conclusion

The "multiple log streams issue" was not an issue but normal AgentCore behavior. Our various logging attempts were based on false assumptions about how AgentCore works. The simplest approach - using AgentCore's built-in logging (`app.logger`) and decorators (`@app.async_task`) - provides the best observability with minimal complexity.

**Current Working Architecture**:
- Using AgentCore's built-in logger (`app.logger`)
- `@app.async_task` decorator manages status transitions automatically (HEALTHY ↔ HEALTHY_BUSY)
- Fire-and-forget pattern using `asyncio.create_task()` for Lambda timeout avoidance
- Native Strands `invoke_async()` methods for clean async execution
- AgentCore `RequestContext` provides session_id automatically
- DynamoDB event journaling for workflow tracking (complements AgentCore logs)