# AgentCore Logging Investigation

## Overview

This document records our investigation into AgentCore logging behavior, multiple log streams, and the challenges we encountered while trying to implement agent status monitoring and observability.

## Initial Problem

When we invoked the agent, we observed too many log streams being created in CloudWatch. This unexpected behavior led us to investigate what was causing multiple streams and whether our logging implementation was correct.

## Investigation Findings

### AgentCore Log Stream Behavior

**Discovery**: AgentCore creates **11 log streams per deployment**, not per execution as initially assumed.

**Log Stream Types** (from AgentCore Observability documentation):
- **Standard logs (stdout/stderr)**: `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/[runtime-logs] <UUID>`
- **OTEL structured logs**: `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/runtime-logs`
- **Traces and spans**: `/aws/spans/default`

**Documentation Findings**:
The AgentCore Observability documentation confirms multiple log locations but doesn't explain why 11+ streams are created per deployment. It mentions:
- Standard logs with UUID-based stream names
- OTEL structured logs in separate streams
- Trace data in dedicated spans location

**UUID Investigation**:
Research confirms that the UUID in log stream names (`[runtime-logs] <UUID>`) is **NOT** the session ID or runtime session ID:
- **Session IDs** are user-controlled identifiers for conversation state (as shown in session management examples)
- **Runtime sessions** have 15-minute timeouts and are separate from log stream UUIDs
- **Log stream UUIDs** appear to be internal AgentCore identifiers, possibly related to:
  - Container instances
  - Runtime endpoint instances
  - Internal service components
  - Agent version snapshots

**Example Log Streams**:
```
/aws/bedrock-agentcore/runtimes/agentRuntimedev-1bWpw8Hlj9-DEFAULT/
├── runtime-logs-<UUID-1>
├── runtime-logs-<UUID-2>
├── runtime-logs-<UUID-N>
├── otel-rt-logs
└── [additional streams...]
```

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

### 3. ThreadPoolExecutor for Async
```python
# What we tried (workaround)
with concurrent.futures.ThreadPoolExecutor() as executor:
    response = await loop.run_in_executor(executor, lambda: agent(user_message))
```

**Result**: Worked but was unnecessary - Strands has native `invoke_async()`.

## What Actually Works

### 1. Simple AgentCore Logger
```python
app = BedrockAgentCoreApp()
logger = app.logger  # Use built-in logger only
```

### 2. Automatic Status Management
```python
@app.async_task
async def background_agent_task(user_message: str, session_id: str):
    # Status automatically becomes HEALTHY_BUSY
    response = await agent.invoke_async(user_message, session_id=session_id)
    # Status automatically returns to HEALTHY
    return response
```

### 3. Fire-and-Forget Pattern
```python
@app.entrypoint
async def invoke(payload):
    # Lambda returns immediately, AgentCore continues processing
    asyncio.create_task(background_agent_task(user_message, session_id))
    return {"status": "started"}
```

## Key Learnings

### AgentCore Logging Behavior
- **Runtime logs**: Basic lifecycle events (agent startup, invocation)
- **otel-rt-logs**: Continuous telemetry stream with structured JSON
- **Automatic status logging**: AgentCore logs status changes internally
- **11 streams per deployment**: Not per execution, this is normal behavior

### What We Learned (Not Necessarily Best Practices)
1. **AgentCore's built-in logger works** - Simple and integrates with AgentCore streams
2. **@app.async_task decorator works** - Handles status automatically without manual tracking
3. **External loggers didn't create extra streams** - Powertools and other logging mechanisms didn't contribute to the 11+ stream issue
4. **Native async is cleaner** - Strands has `invoke_async()`, no ThreadPoolExecutor needed

**Note**: We haven't confirmed with the AgentCore service team whether using external loggers (like Powertools) is discouraged or problematic. The multiple streams appear to be related to AgentCore's internal architecture, not our logging choices.

### What to Monitor
- **otel-rt-logs stream** - Contains detailed execution telemetry
- **Agent status transitions** - HEALTHY ↔ HEALTHY_BUSY (automatic)
- **Error logs** - Appear in both streams for different purposes

## Unanswered Questions

### Why Does Agent Deployment Create So Many Log Streams?

**Observation**: When deploying and creating new agent versions, we see 11+ log streams created in the agent log group, which creates significant noise in CloudWatch.

**Agent Version Context**: Each deployment creates "a snapshot of the agent created automatically with each update, allowing you to track changes, manage rollbacks, and reference specific states."

**Questions**:
- Why does a single agent version deployment require multiple log streams?
- Is this related to AgentCore's internal architecture (containers, services, health checks, versioning)?
- Are the multiple streams related to the agent versioning system?
- Could this be optimized to reduce CloudWatch noise?
- Is this behavior documented anywhere in AgentCore documentation?

**Impact**: 
- Creates cluttered CloudWatch log groups
- Makes it harder to find relevant application logs
- Potentially increases CloudWatch costs due to multiple streams

**Status**: **Partially Documented** - The AgentCore Observability documentation acknowledges multiple log streams with UUID-based naming but doesn't explain the architectural reason for 11+ streams per deployment. The documentation confirms:
- Standard logs use UUID-based stream names: `[runtime-logs] <UUID>`
- OTEL structured logs use separate streams
- This appears to be intentional architecture, not a bug

**Remaining Questions**:
- What do the log stream UUIDs actually represent? (Container instances? Service components? Version snapshots?)
- Why does AgentCore's internal architecture require so many UUID-based streams?
- Is this related to container orchestration, scaling, health checks, or internal service architecture?
- Are the UUIDs related to agent versioning system since each deployment creates "snapshots"?
- Could this be optimized for reduced CloudWatch noise?

## Conclusion

The "multiple log streams issue" was not an issue but normal AgentCore behavior. Our various logging attempts were based on false assumptions about how AgentCore works. The simplest approach - using AgentCore's built-in logging and decorators - provides the best observability with minimal complexity.

**Current Working Architecture**:
- Using AgentCore's built-in logger (works, but not necessarily required)
- `@app.async_task` manages status transitions automatically
- Fire-and-forget pattern for Lambda timeout avoidance
- Native Strands async methods for clean execution

**Important Notes**:
- The 11+ streams appear regardless of our logging approach
- External loggers (Powertools, etc.) didn't contribute to the stream multiplication
- We need service team confirmation on logging best practices
- The multiple streams seem to be AgentCore's internal architecture, not a result of our implementation choices