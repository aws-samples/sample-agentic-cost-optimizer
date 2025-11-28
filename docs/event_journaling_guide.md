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

### Example Event Records

**Session Initiated**:
- Status: `SESSION_INITIATED`
- Recorded by: `infra/lambda/session_initializer.py`

**Agent Invocation Started**:
- Status: `AGENT_INVOCATION_STARTED`
- Recorded by: `infra/lambda/agent_invoker.py`

**Agent Invocation Succeeded**:
- Status: `AGENT_INVOCATION_SUCCEEDED`
- Recorded by: `infra/lambda/agent_invoker.py`

**Agent Runtime Invoke Started**:
- Status: `AGENT_RUNTIME_INVOKE_STARTED`
- Recorded by: `src/agents/main.py` (entrypoint)

**Agent Background Task Started**:
- Status: `AGENT_BACKGROUND_TASK_STARTED`
- Recorded by: `src/agents/main.py` (entrypoint)

**Agent Background Task Completed**:
- Status: `AGENT_BACKGROUND_TASK_COMPLETED`
- Recorded by: `src/agents/main.py` (background task)

**Failure Events** (include `errorMessage` field):
- `AGENT_BACKGROUND_TASK_FAILED`: Agent processing error
- `AGENT_INVOCATION_FAILED`: Lambda → AgentCore invocation error
- `AGENT_RUNTIME_INVOKE_FAILED`: Agent entrypoint error

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

Use `--filter-expression` with expression attribute names (required for reserved keyword `status`):
- Completion events: `#status = :status` where `:status` = `AGENT_BACKGROUND_TASK_COMPLETED`
- Failure events: `contains(#status, :failed)` where `:failed` = `FAILED`

### Get Latest N Events

Use `--scan-index-forward false` with `--limit N` to retrieve most recent events first.

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

Poll for new events using `SK > :timestamp` in key condition expression.

### Performance Analysis

Compare `createdAt` timestamps between first and last events to calculate workflow duration.

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
