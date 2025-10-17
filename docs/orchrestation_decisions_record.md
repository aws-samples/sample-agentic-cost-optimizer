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

**Observation**: The agent creates multiple log streams (typically 12) during execution.

**Initial Concern**: We initially thought this indicated multiple parallel executions when we saw 21 log streams during early testing.

**Root Cause Analysis**: 
- The multiple log streams (12) appear to be related to the agent's internal operations
- **Note**: This behavior needs verification with the AgentCore service team to understand if this is expected or indicates an issue
- Possible causes could include: Strands agent reasoning loops, tool calls, AWS service interactions, or AgentCore runtime behavior

**Resolution**: 
- EventBridge configuration was correct from the start using `EventField.fromPath('$.id')`
- Multiple log streams did not prevent the fire-and-forget pattern from working
- The real issue was the connection management pattern, not session ID generation
- **Action Item**: Verify with AgentCore service team whether 12 log streams per execution is expected behavior

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

### Issue 3: Agent Processing Pattern Incompatibility

**Problem**: Different agent processing approaches caused runtime failures.

**Attempts**:

1. **Synchronous Agent Call** ✅ (Working):
```python
def background_agent_processing(user_message: str, session_id: str, task_id: str):
    response = agent(user_message, session_id=session_id)
    return str(response)
```

2. **Streaming Agent Call** ❌ (Failed):
```python
def background_agent_processing(user_message: str, session_id: str, task_id: str):
    for event in agent.stream(user_message, session_id=session_id):
        # Process events...
```

**Root Cause**: `agent.stream()` was incompatible with AgentCore's runtime environment, likely due to event loop conflicts.

**Resolution**: Stick with simple `agent()` call for background processing.

### Issue 4: AgentCore Async Task Management

**Problem**: Need proper status tracking for fire-and-forget operations.

**Solution**: Implement AgentCore's Manual Task Management pattern:

```python
@app.entrypoint
def invoke(payload):
    # Start tracking async task (sets status to HealthyBusy)
    task_id = app.add_async_task("cost_analysis", {
        "session_id": payload_session_id, 
        "message": user_message
    })
    
    # Start background thread
    thread = threading.Thread(
        target=background_agent_processing,
        args=(user_message, payload_session_id, task_id),
        daemon=True
    )
    thread.start()
    
    # Return immediately (AgentCore connection closes here)
    return f"Started analysis for session {payload_session_id}"

def background_agent_processing(user_message: str, session_id: str, task_id: str):
    try:
        response = agent(user_message, session_id=session_id)
        app.complete_async_task(task_id)  # Mark as complete
        return str(response)
    except Exception as e:
        app.complete_async_task(task_id)  # Mark as complete even on error
        raise
```

### Issue 5: Step Function DynamoDB Integration

**Problem**: Step Function couldn't properly read DynamoDB session status.

**Errors Encountered**:
```json
{
  "cause": "Invalid path '$.statusResult.Item.STATUS.S': The choice state's condition path references an invalid value.",
  "error": "States.Runtime"
}
```

**Root Causes**:
1. Incorrect JSONPath evaluation for session_id
2. Wrong DynamoDB attribute format expectations
3. Missing item handling

**Solutions Applied**:

1. **Proper JSONPath Usage**:
```typescript
// Wrong
key: {
  PK: DynamoAttributeValue.fromString('$.session_id'), // Literal string
}

// Correct
key: {
  PK: DynamoAttributeValue.fromString(JsonPath.stringAt('$.session_id')), // Evaluated
}
```

2. **Handle Multiple DynamoDB Formats**:
```typescript
evaluateStatus
  .when(
    Condition.and(
      Condition.isPresent('$.statusResult.Item'),
      Condition.or(
        Condition.stringEquals('$.statusResult.Item.status.S', 'COMPLETED'), // Native format
        Condition.stringEquals('$.statusResult.Item.status', 'COMPLETED')    // Simplified format
      )
    ), 
    success
  )
```

3. **Graceful Missing Item Handling**:
```typescript
.when(
  Condition.or(
    Condition.isNotPresent('$.statusResult.Item'), // Item doesn't exist yet
    Condition.and(
      Condition.isPresent('$.statusResult.Item'),
      Condition.stringEquals('$.statusResult.Item.status', 'BUSY')
    )
  ),
  waitForCompletion.next(checkStatus) // Continue polling
)
```

### Issue 6: Logging and Debugging Interference

**Problem**: Changing logging levels from DEBUG to INFO broke the agent execution.

**Root Cause**: The issue wasn't the logging level change itself, but a simultaneous change from `agent()` to `agent.stream()` that was incompatible with AgentCore runtime.

**Resolution**: 
- Keep logging at INFO level for production
- Use simple `agent()` call instead of `agent.stream()`
- Add meaningful progress logs without debug noise

## Final Working Architecture

### 1. Lambda Invoker (Fire-and-Forget)
```typescript
export const handler = async (event: { session_id: string; prompt?: string }) => {
  const response = await agentCoreClient.send(
    new InvokeAgentRuntimeCommand({
      agentRuntimeArn,
      runtimeSessionId: event.session_id,
      payload: JSON.stringify({
        prompt: event.prompt ?? 'Hello',
        session_id: event.session_id,
      }),
    }),
  );
  
  // Returns immediately after AgentCore starts background task
  return { status: response.statusCode, sessionId: response.runtimeSessionId };
};
```

### 2. AgentCore Agent (Async Processing)
```python
@app.entrypoint
def invoke(payload):
    user_message = payload.get("prompt", "Hello")
    payload_session_id = payload.get("session_id", session_id)
    
    # Start async task tracking
    task_id = app.add_async_task("cost_analysis", {
        "session_id": payload_session_id, 
        "message": user_message
    })
    
    # Start background processing
    thread = threading.Thread(
        target=background_agent_processing,
        args=(user_message, payload_session_id, task_id),
        daemon=True
    )
    thread.start()
    
    # Return immediately
    return f"Started cost optimization analysis for session {payload_session_id}"

def background_agent_processing(user_message: str, session_id: str, task_id: str):
    try:
        response = agent(user_message, session_id=session_id)  # Simple call, not streaming
        app.complete_async_task(task_id)
        return str(response)
    except Exception as e:
        app.complete_async_task(task_id)
        return f"Error: {str(e)}"
```

### 3. Step Function Workflow
```typescript
const checkStatus = new DynamoGetItem(this, 'CheckStatus', {
  table: props.journalTable,
  key: {
    PK: DynamoAttributeValue.fromString(JsonPath.stringAt('$.session_id')), // Proper JSONPath
    SK: DynamoAttributeValue.fromString('SESSION'),
  },
  resultPath: '$.statusResult',
});

// Robust status evaluation with multiple format support
evaluateStatus
  .when(
    Condition.and(
      Condition.isPresent('$.statusResult.Item'),
      Condition.or(
        Condition.stringEquals('$.statusResult.Item.status.S', 'COMPLETED'),
        Condition.stringEquals('$.statusResult.Item.status', 'COMPLETED')
      )
    ), 
    success
  )
```

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

1. **AgentCore Manual Task Management**: Essential for proper fire-and-forget behavior
2. **Threading vs Streaming**: Simple `agent()` calls work better than `agent.stream()` in AgentCore runtime
3. **JSONPath Evaluation**: Critical for Step Function DynamoDB integration
4. **Session ID Management**: Use EventBridge event IDs for uniqueness
5. **Error Handling**: Always complete async tasks, even on failure
6. **DynamoDB Format Handling**: Support both native and simplified attribute formats

## Best Practices

1. **Always use `JsonPath.stringAt()` for dynamic values in Step Functions**
2. **Implement proper async task lifecycle management in AgentCore**
3. **Use simple agent calls instead of streaming for background processing**
4. **Handle missing DynamoDB items gracefully in Step Functions**
5. **Maintain clean logging without interfering with runtime behavior**
6. **Use unique session IDs to prevent parallel execution issues**

## Conclusion

The fire-and-forget pattern for Lambda → AgentCore integration requires careful attention to:
- AgentCore's async task management patterns
- Proper session lifecycle handling
- Step Function DynamoDB integration nuances
- Agent processing compatibility

The final solution provides immediate Lambda returns while maintaining full agent functionality through background processing, enabling scalable and responsive serverless AI agent architectures.