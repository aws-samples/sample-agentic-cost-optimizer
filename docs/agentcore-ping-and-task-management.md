# AgentCore Runtine Background Task and Ping Management

## Overview

This guide covers two interconnected AgentCore features:
1. **Background Task Management** - How to properly manage async tasks and their lifecycle
2. **Ping Status** - How agents communicate their health status and how tasks affect it


Understanding both is critical for building reliable agents that properly signal their availability to AgentCore Runtime.

---

## Part 1: Background Task Management

### Why Task Management Matters

AgentCore Runtime uses ping status to determine if an agent can accept new work. Proper task management ensures:
- Accurate status reporting (Healthy vs HealthyBusy)
- Cost optimization (no stuck sessions)
- Reliable session lifecycle

### The Two Approaches

#### Approach 1: Automatic with @app.async_task Decorator

**Best for:** The simplest way to track asynchronous functions. The SDK automatically manages the ping status.

**Pros:**
- Automatic task registration and cleanup
- Handles task lifecycle automatically
- Handles exceptions automatically

**Cons:**
- Can't record ping status at specific points for observability
- Decorator must wrap entire async function
- Only works with async functions (raises ValueError for sync functions)

**Example:**
```python
@app.async_task
async def background_task(user_message: str, session_id: str):
    """Decorator automatically manages status"""
    logger.info(f"Task started - Session: {session_id}")
    # Status automatically becomes HealthyBusy here
    
    try:
        response = await agent.invoke_async(user_message, session_id=session_id)
        logger.info(f"Task completed - Session: {session_id}")
        return response
        # Status automatically returns to Healthy here
        
    except Exception as e:
        logger.error(f"Task failed - Session: {session_id}: {str(e)}")
        return {"error": str(e), "status": "failed"}
        # Status automatically returns to Healthy even on error
```

**How it works:**
- When the function runs, ping status changes to "HealthyBusy" 
- When the function completes, status returns to "Healthy"
- Decorator calls `add_async_task(func.__name__)` before function executes
- Decorator calls `complete_async_task(task_id)` in finally block after function completes
- Task completion happens regardless of success or failure
- You don't manage task IDs manually
- Logs task duration automatically

**Reference:** [AgentCore Runtime API - async_task](https://aws.github.io/bedrock-agentcore-starter-toolkit/api-reference/runtime.md#async_taskfunc)

---

#### Approach 2: Manual with add_async_task() and complete_async_task()

**Best for:** More control over task tracking, using the API methods directly

**Pros:**
- Full control over task lifecycle
- Can record ping status at specific points (limited use, due to ping endpoint be only available to AgentCore or localhost)
- Can handle complex error scenarios differently
- Can add custom metadata to tasks
- Works with both sync and async functions

**Cons:**
- Must remember to call `complete_async_task()` in all paths

**Reference:** [AgentCore Runtime API - add_async_task](https://aws.github.io/bedrock-agentcore-starter-toolkit/api-reference/runtime.md#add_async_taskname-metadatanone)

**Example:**
```python
async def background_task(user_message: str, session_id: str):
    """Manual task management for fine-grained control"""
    
    # 1. Manually register task
    task_id = app.add_async_task(f"agent_processing_{session_id}")
    current_ping = app.get_current_ping_status().value
    logger.info(f"Ping status after task start: {current_ping}")  # "HealthyBusy"
    
    try:
        # 2. Do your work
        response = await agent.invoke_async(user_message, session_id=session_id)
        
        # 3. Record completion event (task still active)
        record_event(
            session_id=session_id,
            status="COMPLETED",
            ping_status=current_ping,  # Still "HealthyBusy"
        )
        return response
        
    except Exception as e:
        logger.error(f"Task failed: {str(e)}")
        
        record_event(
            session_id=session_id,
            status="FAILED",
            ping_status=current_ping,  # Still "HealthyBusy"
        )
        return {"error": str(e), "status": "failed"}
        
    finally:
        # 4. Always cleanup - status returns to Healthy
        app.complete_async_task(task_id)
```

**Key Points:**
1. Register task with `add_async_task()` - status becomes HealthyBusy
2. Do your work
3. Record events while task is still active (optional for observability)
4. Use `finally` block to complete task lifecycle - ensures cleanup regardless of success or failure

**Important:** If you forget to call `complete_async_task()`, the session stays in `HealthyBusy` state until default timeout (15 minutes idle or 8 hours maximum).

---

### Comparison: Decorator vs Manual

| Approach | How it works |
|----------|--------------|
| **@app.async_task** | Automatically manages task lifecycle - registers task before function executes, completes task after function finishes (success or failure) |
| **Manual add/complete** | Provides granular control over task lifecycle - you decide exactly when to register and complete tasks |

**Recommendation:**
- Use `@app.async_task` when automatic management is sufficient
- Use manual approach when you need fine-grained control over task lifecycle

## Part 2: Ping Status

### What is Ping Status?

Agent code communicates its processing status using the `/ping` health endpoint:
- **`Healthy`** - Agent is idle and ready to accept new work
- **`HealthyBusy`** - Agent is currently processing background tasks

### How Ping Status Works

**Agent Side:**
- `BedrockAgentCoreApp` exposes a `/ping` HTTP endpoint (GET method)
- The endpoint calls `_handle_ping()` which returns current ping status
- Response format: `{"status": "Healthy" | "HealthyBusy", "time_of_last_update": <timestamp>}`
- You can call `get_current_ping_status()` anytime in your code to get the current status

**AgentCore Runtime Side:**
- AgentCore Runtime polls the `/ping` endpoint periodically (~2 seconds observed)
- Requests come from `127.0.0.1` (localhost) 
- Polling frequency appears **constant** regardless of Healthy or HealthyBusy status
- Runtime uses this status to determine if the agent can accept new work


### The Three Priority Levels

When AgentCore Runtime (or your code) checks ping status, it follows this priority hierarchy:

```python
def get_current_ping_status(self) -> PingStatus:
    # Priority 1: FORCED status (highest priority)
    if self._forced_ping_status is not None:
        return self._forced_ping_status
    
    # Priority 2: CUSTOM handler (via @app.ping decorator)
    elif self._ping_handler:
        try:
            result = self._ping_handler()
            return PingStatus(result) if isinstance(result, str) else result
        except Exception:
            # Falls through to automatic if custom handler fails
            # Logs warning but doesn't raise exception
            pass
    
    # Priority 3: AUTOMATIC (based on active tasks)
    return PingStatus.HEALTHY_BUSY if self._active_tasks else PingStatus.HEALTHY
```

**Reference:** [AgentCore Runtime API - get_current_ping_status](https://aws.github.io/bedrock-agentcore-starter-toolkit/api-reference/runtime.md#get_current_ping_status)

---

### Level 1: Forced Status (Debug/Testing Only)

**Purpose:** Manual override for testing and debugging

**When to use:**
- Testing stuck session detection
- Debugging ping-related issues
- Simulating specific scenarios

**How to use:**
```python
from bedrock_agentcore.runtime.models import PingStatus

# Force status
app.force_ping_status(PingStatus.HEALTHY_BUSY)

# Clear override
app.clear_forced_ping_status()
```

**Warning:** Shouldn't be used in production as it overrides all other status logic.

---

### Level 2: Custom Handler (@app.ping)

**Purpose:** Define custom business logic for determining agent availability

**When to use:**
- You need custom logic beyond checking if tasks are active

#### Example from Documentation

```python
@app.ping
def custom_status():
    """Basic custom ping handler example"""
    from bedrock_agentcore.runtime.models import PingStatus
    
    if system_busy():
        return PingStatus.HEALTHY_BUSY
    return PingStatus.HEALTHY
```

#### Custom Handler Requirements

- **Must return valid PingStatus enum** (`PingStatus.HEALTHY` or `PingStatus.HEALTHY_BUSY`)
- **Keep logic fast** - Called every 2 seconds by AgentCore Runtime
- **Handle exceptions gracefully** - Falls back to automatic mode on error
- **Avoid recursion** - Don't call `app.get_current_ping_status()` inside handler

---

### Level 3: Automatic Mode (Default)

**Purpose:** Automatic status based on active background tasks

**When to use:**
- Default mode for most agents
- Status based purely on whether agent is processing
- No external dependencies to check

**How it works:**
- `HEALTHY_BUSY` if any tasks in `app._active_tasks` dictionary
- `HEALTHY` if `app._active_tasks` is empty
- Managed automatically by `add_async_task()` / `complete_async_task()`

**No code needed** - This is the default behavior when you don't define a custom handler.

---

### Reading Ping Status in Your Code

```python
# Get current status as string
current_status_str = app.get_current_ping_status().value
print(current_status_str)  # "Healthy" or "HealthyBusy"
```

---



---

## Session Lifecycle & Timeouts

AgentCore Runtime sessions have built-in lifecycle limits:

| Limit | Default Value | Adjustable | Notes |
|-------|---------------|------------|-------|
| **Idle session timeout** | 15 minutes (900s) | Yes (via `idleRuntimeSessionTimeout` in `LifecycleConfiguration`) | Range: 60-28800 seconds. Session terminates after inactivity period. |
| **Maximum session duration** | 8 hours (28800s) | Yes (via `maxLifetime` in `LifecycleConfiguration`) | Range: 60-28800 seconds. Absolute maximum session lifetime. |
| **Request timeout** | 15 minutes | No | Maximum time for synchronous requests |
| **Async job max duration** | 8 hours | No | Maximum execution time for async jobs |
| **Streaming maximum duration** | 60 minutes | No | Maximum time for streaming connections |

**Configuration Constraints:**
- `idleRuntimeSessionTimeout` must be ≤ `maxLifetime`
- Both values must be between 60 and 28800 seconds

**Key Insight:** If you forget to call `complete_async_task()`, the session won't stay `HEALTHY_BUSY` forever - it will eventually timeout and terminate based on these limits.

**Reference:** [AWS AgentCore Runtime Lifecycle Settings](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-lifecycle-settings.html)

---

## Common Pitfalls

### 1. Returning Invalid Status from Custom Handler

**WRONG:**
```python
@app.ping
def bad_example():
    return "some_status"  # ValueError: 'some_status' is not a valid PingStatus
```

**CORRECT:**
```python
@app.ping
def good_example():
    from bedrock_agentcore.runtime.models import PingStatus
    return PingStatus.HEALTHY  # Must be PingStatus enum
```

---

### 2. Forgetting to Complete Tasks

**WRONG:**
```python
task_id = app.add_async_task("work")
# ... do work ...
# Forgot to call complete_async_task(task_id)
# Status stays HealthyBusy until session timeout!
```

**CORRECT:**
```python
task_id = app.add_async_task("work")
try:
    # ... do work ...
finally:
    app.complete_async_task(task_id)  # Always completes
```

---

### 3. Calling get_current_ping_status() in Custom Handler

**WRONG - Causes recursion:**
```python
@app.ping
def bad_example():
    # This calls the ping handler again!
    return app.get_current_ping_status()
```

**CORRECT:**
```python
@app.ping
def good_example():
    from bedrock_agentcore.runtime.models import PingStatus
    # Check _active_tasks directly
    return PingStatus.HEALTHY_BUSY if app._active_tasks else PingStatus.HEALTHY
```

---

## Summary

### Ping Status
1. `/ping` endpoint is exposed by `BedrockAgentCoreApp` for health monitoring
2. AgentCore Runtime makes periodic HTTP GET requests to this endpoint (observed: ~2 seconds)
3. Use automatic mode (Level 3) unless you have external dependencies
4. Custom handlers must return valid `PingStatus` enum values
5. Keep custom handlers fast and stateless (called on every ping request)
6. Avoid recursion in custom handlers

### Background Task Management
1. Use `@app.async_task` decorator for autmomatic task lifecycle
2. Use manual `add_async_task()` / `complete_async_task()` when you need observability
3. Use `finally` block to ensure task cleanup
5. Multiple calls to `complete_async_task()` with same ID are safe

### Observability
1. Record `pingStatus` at task start and completion for monitoring
2. Use ping status to detect stuck sessions
3. Log ping status changes for debugging
4. Monitor AgentCore Runtime's 2-second ping heartbeat in CloudWatch

---

## References

### Official Documentation
- [AgentCore Runtime API Reference](https://aws.github.io/bedrock-agentcore-starter-toolkit/api-reference/runtime.md)
- [AWS AgentCore Runtime Lifecycle Settings](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-lifecycle-settings.html)
- [AWS AgentCore Service Quotas](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)

### Investigation Sources
- **Verified**: Source code from `bedrock_agentcore/runtime/app.py` (official AgentCore SDK)
- **Verified**: Official API documentation at https://aws.github.io/bedrock-agentcore-starter-toolkit/
- **Observed**: CloudWatch logs analysis with HTTP request logging middleware in deployed AgentCore
- **Observed**: HTTP traffic patterns showing periodic GET requests to `/ping` endpoint
