# AgentCore Logging Investigation

## Overview

This document records our investigation into AgentCore logging behavior, multiple log streams, and the challenges we encountered while trying to implement agent status monitoring and observability.

## Initial Problem

When we invoked the agent, we observed too many log streams being created in CloudWatch. This unexpected behavior led us to investigate what was causing multiple streams and whether our logging implementation was correct.

## Investigation Findings

### AgentCore Log Stream Behavior

**Discovery**: The number of log streams depends on the deployment method:

**Agent-as-Container Deployment** - Docker image:
- Creates ~11 log streams at deployment: 10 runtime + 1 OTEL
- AgentCore pre-warms 10 containers for performance and scalability
- Runtime log format: `YYYY/MM/DD/[runtime-logs-{SESSION_ID}]{EXECUTION_ENVIRONMENT_UUID}`
- OTEL log format: `otel-rt-logs`

**Agent-as-Code Deployment** - Python code via S3:
- Creates 1 OTEL stream at deployment: `otel-rt-logs`
- Runtime streams created on-demand after first invocation
- Runtime log format: `YYYY/MM/DD/[runtime-logs-{SESSION_ID}]{EXECUTION_ENVIRONMENT_UUID}`
  - Example: `2025/12/02/[runtime-logs-f07e0b11-3090-d01d-78b7-ad8eaf4a93fd]d46c08d5-f8a1-4bb0-9b8f-c2d9519a7a95`
  - Created per execution environment, not per session
  - Same session ID can appear in multiple log streams with different execution environment UUIDs

**Current Implementation**:
Agent-as-code deployment using `AgentRuntimeArtifact.fromS3()` in `infra/lib/agent.ts`.

**Why This Matters**:
- Agent-as-code: 1 OTEL stream at deployment + runtime streams created on-demand per execution environment
- Agent-as-container: 1 OTEL stream + 10 pre-warmed runtime streams - better cold start performance
- Execution environment behavior similar to AWS Lambda:
  - Runtime log streams created per execution environment, not per session
  - Same session ID can be routed to different execution environments
  - Concurrent requests for same session can use different environments
  - Global state is not reliable - use external storage like DynamoDB for journaling and S3 for data passing

**Log Stream Types**:
- Runtime logs: Standard logs with stdout/stderr from agent execution
- OTEL logs: Structured logs with telemetry data
- Traces and spans: Stored in `/aws/spans/default` log group

### False Assumptions We Made

1. Multiple streams = Multiple executions
   - Reality: Agent-as-container creates 11 streams at deployment; agent-as-code creates 1 OTEL stream at deployment + runtime streams on-demand
   - Impact: Led to confusion about logging volume and behavior

2. Manual status tracking required
   - Reality: `@app.async_task` decorator handles status automatically
   - Impact: Unnecessary complexity with manual ping handlers

## What We Tried

### 1. Complex Multi-Logger Setup
- Tried mixing multiple loggers (Strands, AgentCore, custom handlers)

### 2. Manual Status Tracking
- Custom `@app.ping` handler
- Unnecessary complexity

### 3. Manual Async Task Management
- Manual `add_async_task()` and `complete_async_task()` calls
- Manual threading with `threading.Thread()`
- Worked but verbose and error-prone

## What Actually Works

### 1. Simple AgentCore Logger
- Use built-in logger: `logger = app.logger`
- Integrates automatically with AgentCore log streams

### 2. Automatic Status Management with @app.async_task
- Decorator handles status transitions: HEALTHY ↔ HEALTHY_BUSY
- No manual `add_async_task()` or `complete_async_task()` calls needed
- Works with native Strands `invoke_async()` methods

### 3. Fire-and-Forget Pattern with asyncio.create_task
- Entrypoint uses `asyncio.create_task()` to start background work
- Returns immediately while agent continues processing
- Session ID available via `context.session_id` from RequestContext

## Key Learnings

### AgentCore Logging Behavior
- Runtime logs: Basic lifecycle events like agent startup and invocation - created per execution environment after first invocation
- OTEL logs: Continuous telemetry stream with structured JSON - created at deployment
- Automatic status logging: AgentCore logs status changes internally
- Log stream count depends on deployment method:
  - Agent-as-container: ~11 streams at deployment - 10 pre-warmed runtime + 1 OTEL
  - Agent-as-code: 1 OTEL stream at deployment + runtime streams created on-demand per execution environment

### What We Learned
1. AgentCore's built-in logger works - Simple and integrates with AgentCore streams
2. @app.async_task decorator is the recommended approach - Handles status automatically without manual task management
3. Multiple log streams are normal - Agent-as-container pre-warms 10 execution environments; agent-as-code creates them on-demand
4. Native async is cleaner - Strands has invoke_async, no ThreadPoolExecutor or manual threading needed
5. RequestContext provides session_id - No need to manually pass it through payload
6. asyncio.create_task for fire-and-forget - Cleaner than manual threading for background task execution

### What to Monitor
- OTEL logs stream: Contains detailed execution telemetry
- Agent status transitions: HEALTHY ↔ HEALTHY_BUSY - automatic via @app.async_task
- Error logs: Appear in both runtime logs and OTEL logs streams
- DynamoDB event journal: Workflow-level tracking like SESSION_INITIATED, AGENT_INVOCATION_STARTED, AGENT_BACKGROUND_TASK_COMPLETED
- Step Function execution logs: Orchestration-level visibility

## Resolved Questions

### Why Does Agent Deployment Create Multiple Log Streams?

**Answer**: The number of log streams depends on the deployment method:

**Agent-as-Container Deployment** - Docker image:
- Creates ~11 log streams at deployment: 10 runtime + 1 OTEL
- AgentCore pre-warms 10 containers for performance and scalability
- Runtime log format: `YYYY/MM/DD/[runtime-logs-{SESSION_ID}]{EXECUTION_ENVIRONMENT_UUID}`
- OTEL log format: `otel-rt-logs`
- Trade-off: More log streams but better cold start performance

**Agent-as-Code Deployment** - Python code via S3:
- OTEL stream created at deployment: `otel-rt-logs`
- Runtime streams created on-demand per execution environment
- Runtime log format: `YYYY/MM/DD/[runtime-logs-{SESSION_ID}]{EXECUTION_ENVIRONMENT_UUID}`
- Trade-off: Fewer initial streams but potentially slower cold starts

**Our Implementation**:
We use agent-as-code deployment via `AgentRuntimeArtifact.fromS3()` in CDK.

**Impact**: 
- Fewer initial log streams: 1 OTEL at deployment
- Runtime streams created only when needed per execution environment
- Lower initial CloudWatch costs

**Key Learning**: 
- Runtime log stream format: `YYYY/MM/DD/[runtime-logs-{SESSION_ID}]{EXECUTION_ENVIRONMENT_UUID}`
  - Example: `2025/12/02/[runtime-logs-f07e0b11-3090-d01d-78b7-ad8eaf4a93fd]d46c08d5-f8a1-4bb0-9b8f-c2d9519a7a95`
- Execution environment behavior similar to AWS Lambda:
  - Runtime log streams created per execution environment, not per session
  - Created only after first invocation, not at deployment
  - Same session can use different execution environments
  - Concurrent requests for same session can use different environments
  - Global state is not reliable - use external storage like DynamoDB and S3 for state persistence

## Conclusion

The "multiple log streams issue" was not an issue but normal AgentCore behavior. Our various logging attempts were based on false assumptions about how AgentCore works. The simplest approach - using AgentCore's built-in logging (`app.logger`) and decorators (`@app.async_task`) - provides the best observability with minimal complexity.

**Current Working Architecture**:
- Using AgentCore's built-in logger: app.logger
- @app.async_task decorator manages status transitions automatically: HEALTHY ↔ HEALTHY_BUSY
- Fire-and-forget pattern using asyncio.create_task for Lambda timeout avoidance
- Native Strands invoke_async methods for clean async execution
- AgentCore RequestContext provides session_id automatically
- DynamoDB event journaling for workflow tracking - complements AgentCore logs