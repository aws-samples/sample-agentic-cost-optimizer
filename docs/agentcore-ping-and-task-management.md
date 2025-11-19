# AgentCore Ping Status & Background Task Management

## Overview

This guide covers two interconnected AgentCore features:
1. **Ping Status** - How AgentCore Runtime monitors agent health
2. **Background Task Management** - How to properly manage async tasks and their impact on ping status

Understanding both is critical for building reliable agents that properly signal their availability to AgentCore Runtime.

---

## Part 1: Ping Status

### What is Ping Status?

AgentCore Runtime monitors every agent session through a ping mechanism that reports the agent's current state:
- **`Healthy`** - Agent is idle and ready to accept new work
- **`HealthyBusy`** - Agent is processing and may not accept new work

### How AgentCore Runtime Monitors Agents

**Key Finding from Testing:**
- AgentCore Runtime pings agents **every 2 seconds** via internal `_handle_ping()` method
- Pinging is **periodic and continuous**, not on-demand
- Ping frequency is **constant** regardless of Healthy or HealthyBusy status
- Pings are **internal Python calls**, not HTTP requests

```
Example from production logs:
12:33:40.172 - HealthyBusy
12:33:42.172 - HealthyBusy  (2.000s interval)
12:33:44.173 - HealthyBusy  (2.001s interval)
12:33:46.175 - HealthyBusy  (2.002s interval)
...continues every 2 seconds...
```

### The Three Priority Levels

When AgentCore Runtime (or your code) checks ping status, it follows this priority hierarchy (verified from source code):

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

**⚠️ Warning:** Never use in production - this overrides all other status logic.

---

### Level 2: Custom Handler (@app.ping)

**Purpose:** Define custom business logic for determining agent availability

**When to use:**
- Checking external dependencies (database, S3, message queues)
- Implementing resource-based throttling (memory, CPU)
- Custom availability logic beyond task tracking

**When NOT to use:**
- Your status is based purely on whether the agent is processing
- You don't have external dependencies to check
- Automatic mode (Level 3) is sufficient

#### Example: External Dependency Checks

```python
@app.ping
def custom_ping_status():
    """Check external dependencies before accepting work"""
    from bedrock_agentcore.runtime.models import PingStatus
    
    # Check if database is overloaded
    if db_connection_pool.active_connections > 90:
        return PingStatus.HEALTHY_BUSY
    
    # Check if message queue is backed up
    if message_queue.depth() > 1000:
        return PingStatus.HEALTHY_BUSY
    
    # Check if tasks are running (automatic mode logic)
    if app._active_tasks:
        return PingStatus.HEALTHY_BUSY
    
    return PingStatus.HEALTHY
```

#### Example: Resource-Based Throttling

```python
@app.ping
def check_resources():
    """Prevent new work when resources are constrained"""
    import psutil
    from bedrock_agentcore.runtime.models import PingStatus
    
    # Check memory usage
    memory_percent = psutil.virtual_memory().percent
    if memory_percent > 85:
        return PingStatus.HEALTHY_BUSY
    
    # Check CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.1)
    if cpu_percent > 90:
        return PingStatus.HEALTHY_BUSY
    
    # Fall back to automatic mode logic
    return PingStatus.HEALTHY_BUSY if app._active_tasks else PingStatus.HEALTHY
```

#### Custom Handler Requirements

- **Must return valid PingStatus enum** (`PingStatus.HEALTHY` or `PingStatus.HEALTHY_BUSY`)
- **Keep logic fast** - Called every 2 seconds by AgentCore Runtime
- **Handle exceptions gracefully** - Falls back to automatic mode on error
- **Avoid recursion** - Don't call `app.get_current_ping_status()` inside handler

---

### Level 3: Automatic Mode (Default & Recommended)

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
# Get current status as PingStatus enum
current_status = app.get_current_ping_status()
print(current_status)  # PingStatus.HEALTHY or PingStatus.HEALTHY_BUSY

# Get current status as string
current_status_str = app.get_current_ping_status().value
print(current_status_str)  # "Healthy" or "HealthyBusy"
```

**Note:** Calling `get_current_ping_status()` in your code:
- Does NOT trigger the `/ping` HTTP endpoint
- Does NOT count as an AgentCore Runtime health check
- Simply executes the priority hierarchy logic (Forced → Custom → Automatic)

---

## Part 2: Background Task Management

### Why Task Management Matters

AgentCore Runtime uses ping status to determine if an agent can accept new work. Proper task management ensures:
- Accurate status reporting (Healthy vs HealthyBusy)
- Cost optimization (no stuck sessions)
- Reliable session lifecycle

### The Two Approaches

#### Approach 1: Automatic with @app.async_task Decorator (Recommended for Simple Tasks)

**Best for:** Simple background tasks where decorator can wrap the entire function

**Pros:**
- Automatic task registration and cleanup
- Less boilerplate code
- Harder to forget cleanup
- Handles exceptions automatically

**Cons:**
- Less control over when task starts/stops
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

**How it works (verified from source code):**
- Decorator calls `add_async_task(func.__name__)` before function executes
- Decorator calls `complete_async_task(task_id)` in finally block after function completes
- Task completion happens regardless of success or failure
- You don't manage task IDs manually
- Logs task duration automatically

**Reference:** [AgentCore Runtime API - async_task](https://aws.github.io/bedrock-agentcore-starter-toolkit/api-reference/runtime.md#async_taskfunc)

---

#### Approach 2: Manual with add_async_task() and complete_async_task()

**Best for:** 
- Need to record ping status at specific lifecycle points (for observability/monitoring)
- Complex error handling with different cleanup paths
- Need fine-grained control over task lifecycle
- Want to include custom metadata with tasks

**Pros:**
- Full control over task lifecycle
- Can record ping status at specific points (limited use, due to ping endpoint be only avalible to AgentCore or localhost)
- Can handle complex error scenarios differently
- Can add custom metadata to tasks
- Works with both sync and async functions

**Cons:**
- More boilerplate code
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
        
        # 3. Complete task BEFORE recording completion
        app.complete_async_task(task_id)
        current_ping = app.get_current_ping_status().value
        logger.info(f"Ping status after completion: {current_ping}")  # "Healthy"
        
        # 4. Record completion with accurate ping status
        record_event(
            session_id=session_id,
            status="COMPLETED",
            ping_status=current_ping,  # Now shows "Healthy"
        )
        return response
        
    except Exception as e:
        logger.error(f"Task failed: {str(e)}")
        app.complete_async_task(task_id)
        current_ping = app.get_current_ping_status().value
        
        record_event(
            session_id=session_id,
            status="FAILED",
            ping_status=current_ping,
        )
        return {"error": str(e), "status": "failed"}
        
    finally:
        # 5. Safety net: Always ensure task is completed
        app.complete_async_task(task_id)
```

**Key Points:**
1. Register task with `add_async_task()` - status becomes HealthyBusy
2. Do your work
3. Complete task with `complete_async_task()` - status returns to Healthy
4. Record ping status for observability if needed
5. Use finally block as safety net (multiple calls are safe)

---

### Critical: Always Complete Tasks

**Problem:** If you forget to call `complete_async_task()`, the session stays in `HealthyBusy` state until timeout:
- **Idle timeout:** 15 minutes
- **Maximum session duration:** 8 hours

**Solution:** Use `finally` block as safety net:

```python
task_id = app.add_async_task("my_task")
try:
    # ... do work ...
    app.complete_async_task(task_id)  # Explicit cleanup
except Exception as e:
    app.complete_async_task(task_id)  # Cleanup on error
    raise
finally:
    # Safety net: Ensures cleanup even if we forgot above
    app.complete_async_task(task_id)
```

**Note:** Calling `complete_async_task()` multiple times with the same ID is safe - it logs a warning but doesn't cause errors.

---

### Comparison: Decorator vs Manual

| Approach | How it works |
|----------|--------------|
| **@app.async_task** | Automatically manages task lifecycle - registers task before function executes, completes task aftefinishes (success or failure) |
| **Manual add/complete** | Provides granular control over task lifecycle - you decide exactly when to register and complete tasks |

**Recommendation:**
- Use `@app.async_task` when automatic management is sufficient
- Use manual approach when you need fine-grained control over task lifecycle

---

## Part 3: Practical Use Cases

### Use Case 1: Stuck Session Detection (This Project)

**Problem:** Sessions can get stuck in `HealthyBusy` if task cleanup fails

**Solution:**
1. Agent records `pingStatus` to DynamoDB when task completes/fails
2. Step Functions workflow reads `pingStatus` from completion event
3. Cleanup Lambda checks: if `pingStatus == "HealthyBusy"`, calls `stop_runtime_session()`

**Benefits:**
- Automatic cost optimization
- No manual intervention
- Full observability

**Implementation:**
```python
# Agent records ping status
record_event(
    session_id=session_id,
    status=EventStatus.AGENT_BACKGROUND_TASK_COMPLETED,
    ping_status=app.get_current_ping_status().value,  # "Healthy" or "HealthyBusy"
)

# Step Functions reads from DynamoDB and passes to cleanup Lambda
# Cleanup Lambda checks:
if ping_status == "HealthyBusy":
    # Session is stuck - force stop
    bedrock_agentcore.stop_runtime_session(
        agentRuntimeId=agent_runtime_arn,
        runtimeSessionId=session_id
    )
```

---

### Use Case 2: Load Balancing

Distribute work based on agent availability:

```python
# Query agents and check their status
available_agents = [
    agent for agent in agents 
    if get_agent_ping_status(agent) == "Healthy"
]

# Route work to available agent
if available_agents:
    route_work_to(available_agents[0])
else:
    # All agents busy - queue work or create new session
    queue_work()
```

---

### Use Case 3: External Dependency Throttling

Prevent new work when external systems are overloaded:

```python
@app.ping
def check_dependencies():
    """Custom ping handler for dependency checks"""
    from bedrock_agentcore.runtime.models import PingStatus
    
    # Check DynamoDB throttling
    if dynamodb_throttle_count > 10:
        return PingStatus.HEALTHY_BUSY
    
    # Check S3 availability
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError:
        return PingStatus.HEALTHY_BUSY
    
    # Fall back to automatic mode
    return PingStatus.HEALTHY_BUSY if app._active_tasks else PingStatus.HEALTHY
```

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

**❌ WRONG:**
```python
@app.ping
def bad_example():
    return "some_status"  # ValueError: 'some_status' is not a valid PingStatus
```

**✅ CORRECT:**
```python
@app.ping
def good_example():
    from bedrock_agentcore.runtime.models import PingStatus
    return PingStatus.HEALTHY  # Must be PingStatus enum
```

---

### 2. Forgetting to Complete Tasks

**❌ WRONG:**
```python
task_id = app.add_async_task("work")
# ... do work ...
# Forgot to call complete_async_task(task_id)
# Status stays HealthyBusy until session timeout!
```

**✅ CORRECT:**
```python
task_id = app.add_async_task("work")
try:
    # ... do work ...
finally:
    app.complete_async_task(task_id)  # Always completes
```

---

### 3. Calling get_current_ping_status() in Custom Handler

**❌ WRONG - Causes recursion:**
```python
@app.ping
def bad_example():
    # This calls the ping handler again!
    return app.get_current_ping_status()
```

**✅ CORRECT:**
```python
@app.ping
def good_example():
    from bedrock_agentcore.runtime.models import PingStatus
    # Check _active_tasks directly
    return PingStatus.HEALTHY_BUSY if app._active_tasks else PingStatus.HEALTHY
```

---

## Summary & Best Practices

### Ping Status
1. ✅ AgentCore Runtime pings every 2 seconds via internal Python calls
2. ✅ Use automatic mode (Level 3) unless you have external dependencies
3. ✅ Custom handlers must return valid `PingStatus` enum values
4. ✅ Keep custom handlers fast and stateless
5. ✅ Avoid recursion in custom handlers

### Background Task Management
1. ✅ Use `@app.async_task` decorator for simple tasks
2. ✅ Use manual `add_async_task()` / `complete_async_task()` when you need observability
3. ✅ Always use `finally` block to ensure task cleanup
4. ✅ Record ping status to DynamoDB for stuck session detection
5. ✅ Multiple calls to `complete_async_task()` with same ID are safe

### Observability
1. ✅ Record `pingStatus` at task start and completion for monitoring
2. ✅ Use ping status to detect stuck sessions
3. ✅ Log ping status changes for debugging
4. ✅ Monitor AgentCore Runtime's 2-second ping heartbeat in CloudWatch

---

---

## Documentation Gaps

The following information was **not documented** in official AWS or AgentCore documentation and required investigation through code analysis and production testing:

### 1. Ping Mechanism Not Clearly Explained ❌

**What's Missing:**
- How AgentCore Runtime actually monitors agent health
- Frequency of health checks
- Whether checks are automatic or on-demand
- Implementation details (HTTP vs internal calls)

**What We Discovered:**
- AgentCore Runtime pings **every 2 seconds automatically** via internal `_handle_ping()` method
- Pings are **internal Python calls**, not HTTP requests
- Ping frequency is **constant** regardless of Healthy or HealthyBusy status
- **Cannot be called from external services** (e.g., Lambda functions cannot call `/ping` endpoint directly)

**Evidence:** Production CloudWatch logs showing consistent 2-second intervals with call stack `_handle_ping -> run -> _bootstrap_inner`

**Impact:** Developers cannot:
- Monitor agent health from external services
- Understand monitoring overhead
- Debug session behavior without this knowledge

---

### 2. No External Access to Ping Endpoint ❌

**What's Missing:**
- Clear statement that `/ping` endpoint is internal-only
- No boto3 method to check agent health from external code
- Alternative approaches for external monitoring

**What We Discovered:**
- The `/ping` endpoint exists but is **not accessible from external services**
- No AWS SDK method to query agent health status
- Must use alternative approaches (e.g., DynamoDB journal events) for external monitoring

**Impact:** Developers expecting to check agent status from Lambda/Step Functions must implement workarounds

---

### 3. Decorator vs Manual Task Management Not Compared ⚠️

**What's Missing:**
- When to use `@app.async_task` decorator vs manual `add_async_task()`/`complete_async_task()`
- Trade-offs between approaches
- Use case guidance

**What's Documented:**
- Both approaches exist and their basic usage
- API signatures and parameters

**Impact:** Developers may choose wrong approach for their use case

---

### 4. Safety of Multiple complete_async_task() Calls ❌

**What's Missing:**
- Whether calling `complete_async_task()` multiple times with same ID is safe
- Recommended pattern for ensuring cleanup (try + finally)

**What We Discovered:**
- Multiple calls with same ID are **safe** - logs warning but doesn't error
- Enables safety net pattern: explicit cleanup in try/except + finally block

**Evidence:** Logs showing "Attempted to complete unknown task ID" warnings without failures

**Impact:** Developers may avoid safety net pattern thinking it will cause errors

---

## References

### Official Documentation
- [AgentCore Runtime API Reference](https://aws.github.io/bedrock-agentcore-starter-toolkit/api-reference/runtime.md)
- [AWS AgentCore Runtime Lifecycle Settings](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-lifecycle-settings.html)
- [AWS AgentCore Service Quotas](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)

### Investigation Sources
- Source code: `bedrock_agentcore/runtime/app.py`
- CloudWatch logs analysis
- Code testing and experimentation
- Call stack inspection
