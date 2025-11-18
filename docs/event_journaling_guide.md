# Event Journaling Guide

## Overview

The Step Function workflow uses an event journaling approach to track the complete lifecycle of agent invocations. Instead of updating a single SESSION record, the system creates immutable event records in DynamoDB for each significant state transition. This provides a complete audit trail similar to CloudFormation's event journaling, enabling better observability and debugging capabilities.

## Data Model

Each event is stored as a separate DynamoDB record with the following structure:

```json
{
  "PK": "SESSION#{session_id}",
  "SK": "EVENT#{ISO_timestamp}",
  "Status": "event_type",
  "Timestamp": "2024-11-04T10:30:00.123Z",
  "ErrorMessage": "optional error details (only for failure events)"
}
```

**Key Attributes:**
- **PK (Partition Key)**: `SESSION#{session_id}` - Groups all events for a single workflow execution
- **SK (Sort Key)**: `EVENT#{ISO_timestamp}` - Ensures chronological ordering of events
- **Status**: The event type (see Event Types section below)
- **Timestamp**: ISO 8601 formatted timestamp
- **ErrorMessage**: Optional field included only for failure events

## Event Types

The workflow generates the following event types across different components:

### Step Function Events
- `SESSION_INITIATED` - Step Function starts workflow execution

### Lambda Invoker Events (invoke_agent_runtime boto3 API)
- `AGENT_RUNTIME_INVOCATION_STARTED` - Lambda invoker calls AgentCore
- `AGENT_RUNTIME_INVOCATION_SUCCEEDED` - AgentCore responds successfully
- `AGENT_RUNTIME_INVOCATION_FAILED` - AgentCore invocation fails

### Agent Entrypoint Events
- `AGENT_ENTRYPOINT_STARTED` - Agent entrypoint receives request
- `AGENT_BACKGROUND_TASK_STARTED` - Background task created successfully
- `AGENT_ENTRYPOINT_FAILED` - Entrypoint encounters error

### Agent Background Task Events
- `AGENT_BACKGROUND_TASK_COMPLETED` - Agent processing completes successfully
- `AGENT_BACKGROUND_TASK_FAILED` - Agent processing fails

## Example Event Records

### Session Initiated
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:00.000Z",
  "Status": "SESSION_INITIATED",
  "Timestamp": "2024-11-04T10:30:00.000Z"
}
```

### Agent Runtime Invocation Started
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:01.234Z",
  "Status": "AGENT_RUNTIME_INVOCATION_STARTED",
  "Timestamp": "2024-11-04T10:30:01.234Z"
}
```

### Agent Runtime Invocation Succeeded
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:02.456Z",
  "Status": "AGENT_RUNTIME_INVOCATION_SUCCEEDED",
  "Timestamp": "2024-11-04T10:30:02.456Z"
}
```

### Agent Entrypoint Started
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:03.789Z",
  "Status": "AGENT_ENTRYPOINT_STARTED",
  "Timestamp": "2024-11-04T10:30:03.789Z"
}
```

### Agent Background Task Started
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:04.012Z",
  "Status": "AGENT_BACKGROUND_TASK_STARTED",
  "Timestamp": "2024-11-04T10:30:04.012Z"
}
```

### Agent Background Task Completed
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:35:45.678Z",
  "Status": "AGENT_BACKGROUND_TASK_COMPLETED",
  "Timestamp": "2024-11-04T10:35:45.678Z"
}
```

### Agent Background Task Failed (with error)
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:35:45.678Z",
  "Status": "AGENT_BACKGROUND_TASK_FAILED",
  "Timestamp": "2024-11-04T10:35:45.678Z",
  "ErrorMessage": "ClientError: ThrottlingException - Rate exceeded"
}
```

### Agent Runtime Invocation Failed (with error)
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:02.456Z",
  "Status": "AGENT_RUNTIME_INVOCATION_FAILED",
  "Timestamp": "2024-11-04T10:30:02.456Z",
  "ErrorMessage": "Failed to invoke AgentCore: Timeout"
}
```

### Agent Entrypoint Failed (with error)
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:03.789Z",
  "Status": "AGENT_ENTRYPOINT_FAILED",
  "Timestamp": "2024-11-04T10:30:03.789Z",
  "ErrorMessage": "ValueError: Invalid request format"
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
  --filter-expression "Status = :status" \
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
  --filter-expression "contains(Status, :failed)" \
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

1. `SESSION_INITIATED` - Step Function starts
2. `AGENT_RUNTIME_INVOCATION_STARTED` - Lambda begins AgentCore invocation
3. `AGENT_RUNTIME_INVOCATION_SUCCEEDED` - AgentCore accepts the request
4. `AGENT_ENTRYPOINT_STARTED` - Agent receives the request
5. `AGENT_BACKGROUND_TASK_STARTED` - Agent creates background task
6. `AGENT_BACKGROUND_TASK_COMPLETED` - Agent finishes processing

### Common Failure Scenarios

**Scenario 1: Lambda Invocation Failure**
```
SESSION_INITIATED → AGENT_RUNTIME_INVOCATION_STARTED → AGENT_RUNTIME_INVOCATION_FAILED
```
- Check the ErrorMessage field in AGENT_RUNTIME_INVOCATION_FAILED event
- Review Lambda CloudWatch logs for detailed error traces
- Common causes: AgentCore timeout, permission issues, network errors

**Scenario 2: Agent Entrypoint Failure**
```
SESSION_INITIATED → AGENT_RUNTIME_INVOCATION_STARTED → AGENT_RUNTIME_INVOCATION_SUCCEEDED → 
AGENT_ENTRYPOINT_STARTED → AGENT_ENTRYPOINT_FAILED
```
- Check the ErrorMessage field in AGENT_ENTRYPOINT_FAILED event
- Review agent CloudWatch logs for stack traces
- Common causes: Invalid request format, missing environment variables

**Scenario 3: Background Task Failure**
```
SESSION_INITIATED → AGENT_RUNTIME_INVOCATION_STARTED → AGENT_RUNTIME_INVOCATION_SUCCEEDED → 
AGENT_ENTRYPOINT_STARTED → AGENT_BACKGROUND_TASK_STARTED → AGENT_BACKGROUND_TASK_FAILED
```
- Check the ErrorMessage field in AGENT_BACKGROUND_TASK_FAILED event
- Review agent CloudWatch logs for detailed error information
- Common causes: AWS credential issues, API throttling, processing errors

**Scenario 4: Missing Completion Event**
```
SESSION_INITIATED → AGENT_RUNTIME_INVOCATION_STARTED → AGENT_RUNTIME_INVOCATION_SUCCEEDED → 
AGENT_ENTRYPOINT_STARTED → AGENT_BACKGROUND_TASK_STARTED → (no completion event)
```
- Agent may have crashed without recording failure event
- Check agent CloudWatch logs for unexpected termination
- Check Step Function execution for timeout errors
- Common causes: Out of memory, unhandled exceptions, container crashes

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
   - Look for ErrorMessage fields in failure events
   - Cross-reference with CloudWatch logs for detailed traces

5. **Verify Event Sequence**
   - Ensure events follow the expected order
   - Missing events indicate component failures
   - Gaps in timestamps may indicate delays or retries

6. **Review Component Logs**
   - **Step Function**: AWS Console → Step Functions → Execution details
   - **Lambda Invoker**: CloudWatch Logs → `/aws/lambda/agent-invoker-function`
   - **Agent Runtime**: CloudWatch Logs → AgentCore log group

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
  --output json | jq '[.Items[0].Timestamp.S, .Items[-1].Timestamp.S]'
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
