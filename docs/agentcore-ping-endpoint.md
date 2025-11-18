# AgentCore Ping Endpoint - Technical Guide

## Overview

The `/ping` endpoint is an HTTP GET endpoint exposed by every AgentCore agent to report its current health status. This document explains how it works based on code investigation and practical usage.

## Endpoint Details

**URL:** `GET /ping`

**Response Format:**
```json
{
  "status": "Healthy" | "HealthyBusy",
  "time_of_last_update": 1234567890
}
```

## Who Can Call It?

### 1. AgentCore Runtime Service (Primary Caller)
- The AgentCore Runtime service monitors your agent's health
- **Frequency:** Not documented (appears to be periodic health checks)
- **Purpose:** Determine if agent can accept new work

### 2. Your Application Code
```python
# Get current status programmatically
current_status = app.get_current_ping_status()
print(current_status.value)  # "Healthy" or "HealthyBusy"
```

### 3. External Monitoring (Limited)
**Important:** There is no direct boto3 method to call the `/ping` endpoint. The AgentCore Runtime service manages this internally.

```bash
# Only works for local development
curl http://localhost:8080/ping

# For deployed agents: No public HTTP endpoint available
# The ping endpoint is internal to AgentCore Runtime
```

**Alternative:** Read ping status from DynamoDB journal events (see "Recording Ping Status" section)

---

## How get_current_ping_status() Works - Complete Logic

### Priority Hierarchy (Forced > Custom > Automatic)

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
            pass
    
    # Priority 3: AUTOMATIC (based on active tasks)
    return PingStatus.HEALTHY_BUSY if self._active_tasks else PingStatus.HEALTHY
```

---

## The Three Modes

### Mode 1: Forced Status (Debug/Testing)
- Set via `app.force_ping_status(PingStatus.HEALTHY_BUSY)`
- Used for testing or manual override
- **Highest priority** - overrides everything
- Clear with `app.clear_forced_ping_status()`

```python
# Force status for testing
app.force_ping_status(PingStatus.HEALTHY_BUSY)

# Clear override
app.clear_forced_ping_status()
```

### Mode 2: Custom Handler (@app.ping)
- You define custom logic for determining status
- Example: Check database connections, queue lengths, etc.
- Falls back to automatic if handler throws exception
- **Must return valid PingStatus enum values**

```python
@app.ping
def custom_ping_status():
    """Define custom logic for status determination"""
    if app._active_tasks:
        return PingStatus.HEALTHY_BUSY
    return PingStatus.HEALTHY
```

### Mode 3: Automatic (Default)
- Based on `self._active_tasks` dictionary
- `HEALTHY_BUSY` if any tasks in `_active_tasks`
- `HEALTHY` if `_active_tasks` is empty
- Managed by `add_async_task()` / `complete_async_task()`

```python
# Automatic tracking with decorator
@app.async_task
async def background_task():
    # Status automatically becomes HealthyBusy
    await do_work()
    # Status automatically returns to Healthy
```

---

## Sequence Diagram

```
Your Code                    AgentCore App                    _active_tasks
    |                              |                                |
    |-- add_async_task() --------->|                                |
    |                              |-- Add task to dict ----------->|
    |                              |                                | (count: 1)
    |                              |                                |
    |-- get_ping_status() -------->|                                |
    |                              |-- Check _active_tasks -------->|
    |                              |<-- Has tasks (1) --------------|
    |<-- HEALTHY_BUSY -------------|                                |
    |                              |                                |
    |-- complete_async_task() ---->|                                |
    |                              |-- Remove task from dict ------>|
    |                              |                                | (count: 0)
    |                              |                                |
    |-- get_ping_status() -------->|                                |
    |                              |-- Check _active_tasks -------->|
    |                              |<-- Empty (0) ------------------|
    |<-- HEALTHY ------------------|                                |
```

---

## Session Lifecycle & Timeouts

AgentCore Runtime sessions have built-in lifecycle limits:

| Limit | Value | Adjustable | Notes |
|-------|-------|------------|-------|
| **Idle session timeout** | 15 minutes | Yes (via `idleRuntimeSessionTimeout` API) | Session terminates after 15 min of inactivity |
| **Maximum session duration** | 8 hours | Yes (via `maxLifetime` API) | Absolute maximum session lifetime |
| **Request timeout** | 15 minutes | No | Maximum time for synchronous requests |
| **Async job max duration** | 8 hours | No | Maximum execution time for async jobs |

**Key Insight:** If you forget to call `complete_async_task()`, the session won't stay `HEALTHY_BUSY` forever - it will eventually timeout and terminate based on these limits.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| **Multiple tasks** | Status is `HEALTHY_BUSY` if ANY task is active |
| **Task completion failure** | If `complete_async_task()` isn't called, status stays `HEALTHY_BUSY` until session timeout (15 min idle or 8 hour max - use `finally` block!) |
| **Custom handler exception** | Silently falls back to automatic mode |
| **Forced status** | Stays until explicitly cleared |
| **Thread safety** | Uses `_task_counter_lock` for concurrent access |

---

## Status Values

| Status | Meaning | When Used |
|--------|---------|-----------|
| `Healthy` | Agent is idle and ready for work | No active tasks running |
| `HealthyBusy` | Agent is processing and may not accept new work | One or more tasks are active |



## Custom Ping Handler (@app.ping) - Purpose & Use Cases

### What It Does
The `@app.ping` decorator lets you define custom business logic for determining if your agent is busy, beyond just tracking async tasks.

### Real-World Use Cases

#### Use Case 1: External Dependencies
```python
@app.ping
def check_dependencies():
    # Check if database is overloaded
    if db_connection_pool.active_connections > 90:
        return PingStatus.HEALTHY_BUSY
    
    # Check if message queue is backed up
    if message_queue.depth() > 1000:
        return PingStatus.HEALTHY_BUSY
    
    return PingStatus.HEALTHY
```

#### Use Case 2: Resource Limits
```python
@app.ping
def check_resources():
    # Check memory usage
    memory_percent = psutil.virtual_memory().percent
    if memory_percent > 85:
        return PingStatus.HEALTHY_BUSY
    
    # Check CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.1)
    if cpu_percent > 90:
        return PingStatus.HEALTHY_BUSY
    
    return PingStatus.HEALTHY
```

### When to Use Custom Handlers

**Use custom handlers when:**
- You want to prevent new sessions when DynamoDB is throttling
- You want to check if S3 bucket is accessible before accepting work
- You have rate limits or quotas to respect
- You need to check external dependencies

**Don't use custom handlers when:**
- Your status is based purely on whether the agent is processing
- You don't have external dependencies to check
- Automatic mode with `add_async_task` / `complete_async_task` is sufficient

## Recording Ping Status

You can capture and log the current status:

```python
from bedrock_agentcore.runtime.models import PingStatus

# Get current status
current_ping = app.get_current_ping_status().value

# Log it
logger.info(f"Current status: {current_ping}")

# Record to DynamoDB
record_event(
    session_id=session_id,
    status=EventStatus.TASK_STARTED,
    ping_status=current_ping,  # "Healthy" or "HealthyBusy"
)
```

## Common Pitfalls

### Returning Custom Strings (Incorrect)
```python
@app.ping
def bad_example():
    return "some_status"  # ValueError: 'some_status' is not a valid PingStatus
```

### Returning Valid PingStatus (Correct)
```python
@app.ping
def good_example():
    return PingStatus.HEALTHY  # Correct
```

### Forgetting to Complete Tasks (Incorrect)
```python
task_id = app.add_async_task("work")
# ... do work ...
# Forgot to call complete_async_task(task_id)
# Status stays HealthyBusy until session timeout!
# (15 minutes idle or 8 hours maximum session duration)
```

### Always Complete Tasks (Correct)
```python
task_id = app.add_async_task("work")
try:
    # ... do work ...
finally:
    app.complete_async_task(task_id)  # Always completes
```

## Value of Ping Checks - Why This Matters

### Business Value

#### 1. Cost Optimization
- Prevents starting new sessions when agent is busy
- Avoids wasting money on stuck sessions
- Enables smart session management

#### 2. Reliability
- Know if agent is actually processing or stuck
- Detect hung sessions (15-minute timeout)
- Enable automatic recovery

#### 3. Observability
- Real-time visibility into agent state
- Historical tracking in DynamoDB
- Debug issues faster

### Real-World Implementation: Automatic Stuck Session Cleanup

**This Project's Solution:**

We implemented automatic stuck session detection using ping status monitoring:

1. **Problem:** Sessions can get stuck in `HealthyBusy` if `complete_async_task()` isn't called, wasting resources until timeout (15 min idle or 8 hour max)

2. **Solution:** 
   - Agent records `pingStatus` to DynamoDB when task completes/fails
   - Step Function reads `pingStatus` from the completion event
   - Cleanup Lambda checks: if `pingStatus == "HealthyBusy"`, calls `stop_runtime_session()`

3. **Event Statuses:**
   - `AGENT_RUNTIME_SESSION_FORCE_STOPPED` - Session was stuck, force stopped (indicates bug)
   - `AGENT_RUNTIME_SESSION_STOP_NOT_REQUIRED` - Session healthy, no action needed (normal)
   - `AGENT_RUNTIME_SESSION_FORCE_STOP_FAILED` - Force stop failed (needs investigation)

4. **Benefits:** Automatic cost optimization, no manual intervention, full observability

This demonstrates practical ping status usage for reliability and cost savings.

---

### Practical Use Cases

#### Use Case 1: Session Management
Check if an existing session is busy before reusing it:

```
User Request → Check Ping Status → Decision
                      ↓
        ┌──────────────────┐
        │  HEALTHY         │ → Can reuse session or start new work
        ├──────────────────┤
        │  HEALTHY_BUSY    │ → Wait or create new session
        ├──────────────────┤
        │  Failed + Busy   │ → Kill session, start fresh (prevents waste!)
        └──────────────────┘
```

```python
status = get_session_status(session_id)
if status == "Healthy":
    # Reuse session
    invoke_agent(session_id, new_message)
else:
    # Create new session
    new_session_id = create_session()
```

#### Use Case 2: Stuck Session Detection
Detect sessions that are stuck in HealthyBusy:

**Without Ping Status:**
```
Session ABC starts → Agent crashes → Session stays "running" 
→ Wastes money for 15 minutes until timeout → User can't start new work
```

**With Ping Status:**
```
Session ABC starts → Agent crashes → Ping shows HEALTHY_BUSY but last event is FAILED 
→ Your cleanup Lambda detects this → Calls stop_runtime_session() 
→ Saves money → User can start new session immediately
```

```python
# Query DynamoDB for sessions
# If last_event = FAILED and ping_status = HealthyBusy
# Session is stuck - clean it up
if last_event.status == "FAILED" and last_event.ping_status == "HealthyBusy":
    stop_runtime_session(session_id)
```

#### Use Case 3: Load Balancing
Distribute work based on agent availability:
```python
available_agents = [
    agent for agent in agents 
    if get_ping_status(agent) == "Healthy"
]
```

---

## Summary & Key Insights

### Key Insights

1. **Ping is reactive, not proactive** - The endpoint responds when called; it doesn't push updates
2. **Status is computed on-demand** - Each call to `/ping` or `get_current_ping_status()` runs the logic fresh
3. **Custom handlers run frequently** - Keep logic fast and stateless
4. **Automatic mode is usually sufficient** - Only use custom handlers for external dependency checks
5. **Frequency is undocumented** - How often AgentCore Runtime calls `/ping` is not specified in docs
6. **No direct boto3 access** - Cannot call `/ping` endpoint directly from external code; use DynamoDB journal events instead

### Recommendations

**Current Best Practice:**
- Use automatic mode with manual task tracking (`add_async_task` / `complete_async_task`)
- Record real ping status to DynamoDB for observability
- Add logging for debugging
- Always use `finally` blocks to ensure tasks complete

**Avoid:**
- Return custom strings from ping handlers (must be valid `PingStatus` enum)
- Forget to call `complete_async_task()` (causes stuck sessions)
- Add custom handlers unless you have external dependencies to check
- Try to call `/ping` endpoint via boto3 (not supported)

**Next Steps:**
- Build cleanup Lambda to detect stuck sessions
- Read ping status from DynamoDB journal events
- Call `stop_runtime_session()` to clean up failed sessions

---

## References

- [AgentCore Runtime API Reference](https://aws.github.io/bedrock-agentcore-starter-toolkit/api-reference/runtime.md)
- Source: `bedrock_agentcore/runtime/app.py`
- Based on code investigation and practical usage
