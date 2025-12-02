# Fire-and-Forget Lambda Implementation for AgentCore

## Overview

This document details the challenges, attempts, and final solution for implementing a fire-and-forget pattern with AWS Lambda invoking Amazon Bedrock AgentCore, allowing the Lambda to return immediately while the agent processes asynchronously in the background.

## Problem Statement

**Goal**: Implement a Lambda function that triggers an AgentCore agent but returns immediately without waiting for the agent to complete processing.

**Challenge**: Standard Lambda → AgentCore invocation maintains an open connection until the agent completes, causing:
- Long Lambda execution times (2-4 minutes)
- Potential timeouts
- Resource waste
- Poor user experience

## Architecture Overview

```
EventBridge → Step Function → Lambda → AgentCore → Agent (Background Processing)
     ↓              ↓           ↓         ↓              ↓
  Unique ID    Orchestration  Fire &   Immediate    Async Processing
                             Forget    Return       + DynamoDB Tracking
```

## Issues Encountered and Solutions

### Issue 1: Understanding Agent Log Streams

**Observation**: The agent creates multiple log streams during execution.

**Initial Concern**: We initially thought this indicated multiple parallel executions when we saw many log streams during early testing.

**Root Cause Analysis**: 
- Runtime log streams are created **per execution environment**, not per session
- Log stream format: `YYYY/MM/DD/[runtime-logs-{SESSION_ID}]{EXECUTION_ENVIRONMENT_UUID}`
  - `SESSION_ID`: The session identifier
  - `EXECUTION_ENVIRONMENT_UUID`: The execution environment instance
- **Key Behaviors**:
  - Multiple requests for the same session can use different execution environments
  - Multiple requests for the same session can be handled concurrently by the same environment
  - Same session ID can appear in multiple log streams (different execution environment UUIDs)
- **Implication**: Similar to AWS Lambda, "global state" is not reliable across invocations
  - Same session can be routed to different execution environments
  - Concurrent requests for same session can use different environments
  - **External storage required** for state persistence (e.g., DynamoDB for journaling, S3 for data passing between agents)

**Resolution**: 
- EventBridge configuration was correct from the start using `EventField.fromPath('$.id')`
- Multiple log streams did not prevent the fire-and-forget pattern from working
- The real issue was the connection management pattern, not session ID generation
- Understanding execution environment behavior explains why we use DynamoDB and S3 for state management

### Issue 2: AgentCore Connection Management

**Problem**: Fire-and-forget approach in Lambda wasn't properly releasing AgentCore connections.

**Initial Approach** (Failed):
```typescript
// This didn't work - still maintained connection
agentCoreClient
  .send(new InvokeAgentRuntimeCommand({...}))
  .catch((error) => {
    logger.error('AgentCore invocation failed', { error: error.message });
  });
```

**Root Cause**: AgentCore's synchronous processing model expected the client to wait for completion.

**Final Solution**: Implement proper async task management within AgentCore itself.

### Issue 3: Agent Processing Pattern Evolution

**Problem**: Finding the right async pattern for agent processing in AgentCore.

**Evolution**:
1. Manual threading with synchronous `agent()` calls - Worked but verbose
2. Streaming with `agent.stream()` - Failed (incompatible with AgentCore runtime)
3. Native async with `@app.async_task` + `invoke_async()` - Final solution ✅

**Resolution**: Use `@app.async_task` decorator with Strands' native `invoke_async()` for clean async execution.

### Issue 4: AgentCore Async Task Management Evolution

**Problem**: Need proper status tracking for fire-and-forget operations.

**Evolution**:
- **Initial**: Manual `add_async_task()` / `complete_async_task()` with threading
- **Final**: `@app.async_task` decorator with `asyncio.create_task()` ✅

**Key Improvement**: Decorator handles status transitions (HEALTHY ↔ HEALTHY_BUSY) automatically, eliminating manual task lifecycle management.

### Issue 5: Step Function DynamoDB Integration Evolution

**Problem**: Step Function needed to poll DynamoDB for agent completion status.

**Evolution**:
- **Initial**: GetItem on single SESSION record - Failed (event journaling uses multiple EVENT records)
- **Final**: Query with filter for completion/failure events ✅

**Key Learnings**:
1. Event journaling = multiple immutable events, not single mutable record
2. Query needed to find completion events among all events
3. Expression attribute names required for reserved keyword `status`
4. `JsonPath.format()` cleaner for composite keys
5. Filter on query more efficient than scanning all events

### Issue 6: Logging and Debugging Interference

**Problem**: Changing logging levels from DEBUG to INFO broke the agent execution.

**Root Cause**: The issue wasn't the logging level itself, but a simultaneous change from synchronous `agent()` to `agent.stream()` that was incompatible with AgentCore runtime.

**Resolution**: 
- Use INFO level for production
- Use native async `agent.invoke_async()` instead of `agent.stream()`
- Use AgentCore's built-in logger (`app.logger`) for consistency

## Final Working Architecture

### 1. Lambda Invoker (Fire-and-Forget)
- Records `AGENT_INVOCATION_STARTED` event
- Invokes AgentCore with X-Ray trace ID for observability linking
- Records `AGENT_INVOCATION_SUCCEEDED` event
- Returns immediately (~560ms)

### 2. AgentCore Agent (Async Processing)
- Entrypoint gets `session_id` from `context.session_id`
- Uses `asyncio.create_task()` to start background work
- Returns immediately to Lambda
- Background task uses `@app.async_task` decorator for automatic status management
- Calls multiple agents with `invoke_async()` for multi-agent workflow
- Records completion/failure events

### 3. Step Function Workflow
- Queries DynamoDB for completion/failure events using `begins_with(SK, 'EVENT#')`
- Filters for `AGENT_BACKGROUND_TASK_COMPLETED` or `AGENT_BACKGROUND_TASK_FAILED`
- Uses expression attribute names for reserved keyword `status`
- Polls every 10 seconds until completion or failure detected

## Performance Results

### Before (Synchronous)
- Lambda Duration: 2-4 minutes
- Connection: Maintained throughout agent processing
- Scalability: Limited by Lambda timeout

### After (Fire-and-Forget)
- Lambda Duration: ~560ms (just to start background task)
- AgentCore Response: ~2-3ms (immediate return)
- Connection: Closed immediately
- Agent Processing: Continues asynchronously for full duration (~164 seconds)
- Scalability: No Lambda timeout constraints

## Key Learnings

1. **@app.async_task Decorator**: Simplifies async task management with automatic status transitions (HEALTHY ↔ HEALTHY_BUSY)
2. **Native Async with invoke_async()**: Cleaner than manual threading or synchronous calls
3. **RequestContext for session_id**: AgentCore provides session_id automatically via `context.session_id`
4. **Event Journaling Pattern**: Multiple immutable events better than single mutable record
5. **DynamoDB Query with Filter**: More efficient than GetItem for event-based tracking
6. **JSONPath.format()**: Cleaner composite key construction in Step Functions
7. **Expression Attribute Names**: Required for DynamoDB reserved keywords like `status`
8. **asyncio.create_task()**: Fire-and-forget pattern for Lambda timeout avoidance

## Best Practices

1. **Use `@app.async_task` decorator** for automatic status management instead of manual `add_async_task()`/`complete_async_task()`
2. **Use `agent.invoke_async()`** for native async execution instead of threading or synchronous calls
3. **Get session_id from RequestContext** via `context.session_id` instead of passing through payload
4. **Use `asyncio.create_task()`** for fire-and-forget pattern instead of manual threading
5. **Use DynamoDB Query with Filter** for event-based tracking instead of GetItem on single record
6. **Use `JsonPath.format()`** for composite keys in Step Functions for cleaner code
7. **Use Expression Attribute Names** for DynamoDB reserved keywords like `status`
8. **Record events at key lifecycle points** for comprehensive workflow observability

## Conclusion

The fire-and-forget pattern for Lambda → AgentCore integration requires careful attention to:
- AgentCore's `@app.async_task` decorator for automatic status management
- RequestContext for session_id retrieval
- Native async patterns with `invoke_async()` and `asyncio.create_task()`
- Event journaling pattern with DynamoDB Query for status tracking
- Step Function integration with proper JSONPath and expression attribute names

The final solution provides immediate Lambda returns (~560ms) while maintaining full agent functionality through background processing, enabling scalable and responsive serverless AI agent architectures. The agent continues processing asynchronously for the full duration (~164 seconds) without Lambda timeout constraints.