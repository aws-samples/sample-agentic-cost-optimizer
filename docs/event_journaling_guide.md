# Event Journaling Guide

## Overview

The Step Function workflow uses an event journaling approach to track the complete lifecycle of agent invocations. Instead of updating a single SESSION record, the system creates immutable event records in DynamoDB for each significant state transition. This provides a complete audit trail similar to CloudFormation's event journaling, enabling better observability and debugging capabilities.

## Data Model

Each event is stored as a separate DynamoDB record with the following structure:

```json
{
  "PK": "SESSION#{session_id}",
  "SK": "EVENT#{ISO_timestamp}#{event_id}",
  "sessionId": "session_id",
  "eventId": "uuid",
  "status": "event_type",
  "createdAt": "2024-11-04T10:30:00.123Z",
  "ttlSeconds": 1730000000,
  "errorMessage": "optional error details (only for failure events)"
}
```

**Key Attributes:**
- **PK (Partition Key)**: `SESSION#{session_id}` - Groups all events for a single workflow execution
- **SK (Sort Key)**: `EVENT#{ISO_timestamp}#{event_id}` - Ensures chronological ordering and uniqueness
- **sessionId**: The session identifier (extracted from PK for easier querying)
- **eventId**: Unique UUID for each event (prevents duplicate events from race conditions)
- **status**: The event type (see Event Types section below)
- **createdAt**: ISO 8601 formatted timestamp
- **ttlSeconds**: Unix timestamp for DynamoDB TTL (automatic cleanup after configured days)
- **errorMessage**: Optional field included only for failure events

## Event Types

The workflow generates the following event types across different components:

### Step Function Events
- `SESSION_INITIATED` - Step Function starts workflow execution

### Lambda Invoker Events
- `AGENT_INVOCATION_STARTED` - Lambda invoker calls AgentCore (recorded in `infra/lambda/agent_invoker.py`)
- `AGENT_INVOCATION_SUCCEEDED` - AgentCore responds successfully (recorded in `infra/lambda/agent_invoker.py`)
- `AGENT_INVOCATION_FAILED` - AgentCore invocation fails (recorded in `infra/lambda/agent_invoker.py`)

### Agent Runtime Events
- `AGENT_RUNTIME_INVOKE_STARTED` - Agent entrypoint receives request (recorded in `src/agents/main.py`)
- `AGENT_BACKGROUND_TASK_STARTED` - Background task created successfully (recorded in `src/agents/main.py`)
- `AGENT_RUNTIME_INVOKE_FAILED` - Entrypoint encounters error (recorded in `src/agents/main.py`)

### Agent Background Task Events
- `AGENT_BACKGROUND_TASK_COMPLETED` - Agent processing completes successfully (recorded in `src/agents/main.py`)
- `AGENT_BACKGROUND_TASK_FAILED` - Agent processing fails (recorded in `src/agents/main.py`)

## Example Event Records

### Session Initiated
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:00.000Z#uuid-1",
  "sessionId": "abc-123-def",
  "eventId": "uuid-1",
  "status": "SESSION_INITIATED",
  "createdAt": "2024-11-04T10:30:00.000Z",
  "ttlSeconds": 1730000000
}
```

### Agent Invocation Started
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:01.234Z#uuid-2",
  "sessionId": "abc-123-def",
  "eventId": "uuid-2",
  "status": "AGENT_INVOCATION_STARTED",
  "createdAt": "2024-11-04T10:30:01.234Z",
  "ttlSeconds": 1730000000
}
```

### Agent Invocation Succeeded
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:02.456Z#uuid-3",
  "sessionId": "abc-123-def",
  "eventId": "uuid-3",
  "status": "AGENT_INVOCATION_SUCCEEDED",
  "createdAt": "2024-11-04T10:30:02.456Z",
  "ttlSeconds": 1730000000
}
```

### Agent Runtime Invoke Started
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:03.789Z#uuid",
  "Status": "AGENT_RUNTIME_INVOKE_STARTED",
  "Timestamp": "2024-11-04T10:30:03.789Z",
  "sessionId": "abc-123-def",
  "eventId": "uuid"
}
```

### Agent Background Task Started
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:04.012Z#uuid-5",
  "sessionId": "abc-123-def",
  "eventId": "uuid-5",
  "status": "AGENT_BACKGROUND_TASK_STARTED",
  "createdAt": "2024-11-04T10:30:04.012Z",
  "ttlSeconds": 1730000000
}
```

### Agent Background Task Completed
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:35:45.678Z#uuid-6",
  "sessionId": "abc-123-def",
  "eventId": "uuid-6",
  "status": "AGENT_BACKGROUND_TASK_COMPLETED",
  "createdAt": "2024-11-04T10:35:45.678Z",
  "ttlSeconds": 1730000000
}
```

### Agent Background Task Failed (with error)
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:35:45.678Z#uuid-7",
  "sessionId": "abc-123-def",
  "eventId": "uuid-7",
  "status": "AGENT_BACKGROUND_TASK_FAILED",
  "createdAt": "2024-11-04T10:35:45.678Z",
  "ttlSeconds": 1730000000,
  "errorMessage": "ClientError: ThrottlingException - Rate exceeded"
}
```

### Agent Invocation Failed (with error)
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:02.456Z#uuid-8",
  "sessionId": "abc-123-def",
  "eventId": "uuid-8",
  "status": "AGENT_INVOCATION_FAILED",
  "createdAt": "2024-11-04T10:30:02.456Z",
  "ttlSeconds": 1730000000,
  "errorMessage": "Failed to invoke AgentCore: Timeout"
}
```

### Agent Runtime Invoke Failed (with error)
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:03.789Z#uuid",
  "Status": "AGENT_RUNTIME_INVOKE_FAILED",
  "Timestamp": "2024-11-04T10:30:03.789Z",
  "ErrorMessage": "ValueError: Invalid request format",
  "sessionId": "abc-123-def",
  "eventId": "uuid"
}
```

## Querying Events

### Retrieve All Events for a Session

Query all events for a specific session in chronological order:

```bash
aws dynamodb query \
  --table-name agents-table-dev \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"SESSION#abc-123-def"}}' \
  --scan-index-forward
```

### Retrieve Events in Reverse Chronological Order

Get the most recent events first:

```bash
aws dynamodb query \
  --table-name agents-table-dev \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"SESSION#abc-123-def"}}' \
  --scan-index-forward false
```

### Filter for Specific Event Types

Query for completion events only:

```bash
aws dynamodb query \
  --table-name agents-table-dev \
  --key-condition-expression "PK = :pk" \
  --filter-expression "#status = :status" \
  --expression-attribute-names '{
    "#status": "status"
  }' \
  --expression-attribute-values '{
    ":pk":{"S":"SESSION#abc-123-def"},
    ":status":{"S":"AGENT_BACKGROUND_TASK_COMPLETED"}
  }'
```

### Filter for Failure Events

Query for any failure events:

```bash
aws dynamodb query \
  --table-name agents-table-dev \
  --key-condition-expression "PK = :pk" \
  --filter-expression "contains(#status, :failed)" \
  --expression-attribute-names '{
    "#status": "status"
  }' \
  --expression-attribute-values '{
    ":pk":{"S":"SESSION#abc-123-def"},
    ":failed":{"S":"FAILED"}
  }'
```

### Get Latest N Events

Retrieve the 10 most recent events:

```bash
aws dynamodb query \
  --table-name agents-table-dev \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"SESSION#abc-123-def"}}' \
  --scan-index-forward false \
  --limit 10
```

## Debugging Workflows

### Understanding Workflow Execution Flow

A typical successful workflow generates events in this order:

1. `SESSION_INITIATED` - Step Function starts (recorded by `infra/lambda/session_initializer.py`)
2. `AGENT_INVOCATION_STARTED` - Lambda begins AgentCore invocation (recorded by `infra/lambda/agent_invoker.py`)
3. `AGENT_INVOCATION_SUCCEEDED` - AgentCore accepts the request (recorded by `infra/lambda/agent_invoker.py`)
4. `AGENT_RUNTIME_INVOKE_STARTED` - Agent receives the request (recorded by `src/agents/main.py` entrypoint)
5. `AGENT_BACKGROUND_TASK_STARTED` - Agent creates background task (recorded by `src/agents/main.py` entrypoint)
6. `AGENT_BACKGROUND_TASK_COMPLETED` - Agent finishes processing (recorded by `src/agents/main.py` background task)

### Common Failure Scenarios

**Scenario 1: Lambda Invocation Failure**
```
SESSION_INITIATED → AGENT_INVOCATION_STARTED → AGENT_INVOCATION_FAILED
```
- Check the ErrorMessage field in AGENT_INVOCATION_FAILED event
- Review Lambda CloudWatch logs for detailed error traces
- Common causes: AgentCore timeout, permission issues, network errors

**Scenario 2: Agent Runtime Invoke Failure**
```
SESSION_INITIATED → AGENT_INVOCATION_STARTED → AGENT_INVOCATION_SUCCEEDED → 
AGENT_RUNTIME_INVOKE_STARTED → AGENT_RUNTIME_INVOKE_FAILED
```
- Check the errorMessage field in AGENT_RUNTIME_INVOKE_FAILED event
- Review agent CloudWatch logs for stack traces
- Common causes: Invalid request format, missing environment variables, asyncio.create_task() errors

**Scenario 3: Background Task Failure**
```
SESSION_INITIATED → AGENT_INVOCATION_STARTED → AGENT_INVOCATION_SUCCEEDED → 
AGENT_RUNTIME_INVOKE_STARTED → AGENT_BACKGROUND_TASK_STARTED → AGENT_BACKGROUND_TASK_FAILED
```
- Check the errorMessage field in AGENT_BACKGROUND_TASK_FAILED event
- Review agent CloudWatch logs for detailed error information
- Common causes: Bedrock throttling (ThrottlingException), AWS credential issues, tool execution errors, agent reasoning failures

**Scenario 4: Missing Completion Event**
```
SESSION_INITIATED → AGENT_INVOCATION_STARTED → AGENT_INVOCATION_SUCCEEDED → 
AGENT_RUNTIME_INVOKE_STARTED → AGENT_BACKGROUND_TASK_STARTED → (no completion event)
```
- Agent may have crashed without recording failure event
- Check agent CloudWatch logs (`/aws/bedrock-agentcore/runtimes/...`) for unexpected termination
- Check Step Function execution for timeout errors
- Common causes: Out of memory, unhandled exceptions in background task, Bedrock throttling

### Debugging Workflow

1. **Get the Session ID**
   - From Step Function execution input or EventBridge event ID
   - From CloudWatch logs (search for "session_id")

2. **Query All Events**
   ```bash
   aws dynamodb query \
     --table-name agents-table-dev \
     --key-condition-expression "PK = :pk" \
     --expression-attribute-values '{":pk":{"S":"SESSION#YOUR_SESSION_ID"}}' \
     --scan-index-forward
   ```

3. **Identify the Last Event**
   - The last event shows where the workflow stopped
   - Check if it's a failure event with ErrorMessage
   - If no completion event exists, the agent may have crashed

4. **Check for Error Messages**
   - Look for errorMessage fields in failure events
   - Cross-reference with CloudWatch logs for detailed traces

5. **Verify Event Sequence**
   - Ensure events follow the expected order
   - Missing events indicate component failures
   - Gaps in timestamps may indicate delays or retries

6. **Review Component Logs**
   - **Step Function**: AWS Console → Step Functions → Execution details
   - **Session Initializer Lambda**: CloudWatch Logs → `/aws/lambda/<stack-name>-SessionInitializer-*`
   - **Agent Invoker Lambda**: CloudWatch Logs → `/aws/lambda/<stack-name>-AgentInvoker-*`
   - **Agent Runtime**: CloudWatch Logs → `/aws/bedrock-agentcore/runtimes/<agent-runtime-name>/`
     - `runtime-logs-<UUID>`: Standard agent logs (stdout/stderr)
     - `otel-rt-logs`: OTEL telemetry data

### Monitoring Active Workflows

To monitor an active workflow, poll for new events:

```bash
# Get events from the last 5 minutes
aws dynamodb query \
  --table-name agents-table-dev \
  --key-condition-expression "PK = :pk AND SK > :sk" \
  --expression-attribute-values '{
    ":pk":{"S":"SESSION#abc-123-def"},
    ":sk":{"S":"EVENT#2024-11-04T10:30:00.000Z"}
  }' \
  --scan-index-forward false
```

### Performance Analysis

Calculate workflow duration by comparing timestamps:

```bash
# Query all events and calculate time between first and last
aws dynamodb query \
  --table-name agents-table-dev \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"SESSION#abc-123-def"}}' \
  --scan-index-forward \
  --output json | jq '[.Items[0].createdAt.S, .Items[-1].createdAt.S]'
```

## Best Practices

1. **Always Query by Session ID**: Use the PK to efficiently retrieve all events for a workflow
2. **Check Chronological Order**: Events should follow the expected sequence
3. **Look for Error Messages**: Failure events contain diagnostic information
4. **Cross-Reference Logs**: DynamoDB events provide high-level flow, CloudWatch logs provide details
5. **Monitor Completion Events**: Step Function polls for AGENT_BACKGROUND_TASK_COMPLETED or FAILED
6. **Use Timestamps**: Calculate durations and identify bottlenecks
7. **Filter Strategically**: Use filter expressions to find specific event types quickly

## Triggering Workflows

Trigger a workflow execution for testing:

```bash
# Using Makefile (recommended)
make trigger-workflow

# Or directly via AWS CLI
aws events put-events --entries '[
  {
    "Source": "manual-trigger",
    "DetailType": "execute-agent",
    "Detail": "{}"
  }
]'
```

The EventBridge event ID becomes the session_id for tracking.
