# Design Document

## Overview

This design implements event journaling for the Step Function workflow and agent invocation process. Instead of updating a single SESSION record, the system creates immutable event records in DynamoDB for each significant state transition. This provides a complete audit trail similar to CloudFormation's event journaling approach, enabling better observability and debugging capabilities.

## Architecture

### High-Level Flow
```
EventBridge Event → Step Function → Record SESSION_INITIATED Event
                        ↓
                   Lambda Invoker → Record AGENT_INVOCATION_STARTED Event
                        ↓
                   AgentCore Runtime
                        ↓
                   Agent Entrypoint → Record AGENT_ENTRYPOINT_STARTED Event
                        ↓
                   Background Task → Record AGENT_BACKGROUND_TASK_STARTED Event
                        ↓
                   Agent Processing
                        ↓
                   Record AGENT_BACKGROUND_TASK_COMPLETED/FAILED Event
                        ↑
                   Step Function Polls for Completion Events ←←←←←←←←←←←←←←←←←←←
```

### Component Interactions

1. **Step Function** creates SESSION_INITIATED event in DynamoDB
2. **Lambda Invoker** creates AGENT_INVOCATION_STARTED event before calling AgentCore
3. **Lambda Invoker** creates AGENT_INVOCATION_SUCCEEDED or AGENT_INVOCATION_FAILED event after AgentCore responds
4. **Agent Entrypoint** creates AGENT_ENTRYPOINT_STARTED event when request is received
5. **Agent Entrypoint** creates AGENT_BACKGROUND_TASK_STARTED event when background task is created
6. **Agent Background Task** creates AGENT_BACKGROUND_TASK_COMPLETED or AGENT_BACKGROUND_TASK_FAILED event when processing finishes
7. **Step Function** polls DynamoDB for completion events (AGENT_BACKGROUND_TASK_COMPLETED or AGENT_BACKGROUND_TASK_FAILED)

## Components and Interfaces

### 1. EventBridge Rule

**Purpose**: Trigger Step Function executions via manual events

**Configuration**:
- Event Pattern: `{"source": ["manual-trigger"], "detail-type": ["execute-agent"]}`
- Target: Step Function ARN
- Input Transformer: Extract event ID as session_id

**Interface**:
```json
{
  "Input": "$.id",
  "InputPathsMap": {
    "session_id": "$.id"
  }
}
```

### 2. Step Function State Machine

**Purpose**: Orchestrate agent invocation and monitor completion

**States**:
1. **InitializeSession**: Create DynamoDB record with status "INITIATED"
2. **InvokeAgent**: Call Lambda invoker function
3. **CheckStatus**: Query DynamoDB for session status
4. **WaitForCompletion**: Wait state with retry logic
5. **Success**: Terminal success state
6. **Failure**: Terminal failure state

**InitializeSession State Configuration**:
```typescript
new DynamoPutItem(this, 'InitializeSession', {
  table: props.journalTable,
  item: {
    PK: DynamoAttributeValue.fromString(JsonPath.stringAt('$.session_id')),
    SK: DynamoAttributeValue.fromString('SESSION'),
    status: DynamoAttributeValue.fromString('INITIATED'),
    start_time: DynamoAttributeValue.fromString(JsonPath.stringAt('$$.State.EnteredTime')),
    created_at: DynamoAttributeValue.fromString(JsonPath.stringAt('$$.State.EnteredTime'))
  },
  resultPath: '$.initResult'
})
```

**Interface**:
```json
{
  "session_id": "string",
  "status": "INITIATED|BUSY|COMPLETED|FAILED",
  "error": "string (optional)"
}
```

### 3. Lambda Invoker Function

**Purpose**: Invoke AgentCore runtime and record invocation events

**Event Recording Logic**:
1. Record AGENT_INVOCATION_STARTED event before calling AgentCore
2. Call AgentCore InvokeAgentRuntimeCommand
3. Record AGENT_INVOCATION_SUCCEEDED event on success
4. Record AGENT_INVOCATION_FAILED event on error (with ErrorMessage)

**DynamoDB Helper Function**:
```typescript
async function recordEvent(
  sessionId: string,
  status: string,
  errorMessage?: string
): Promise<void> {
  const timestamp = new Date().toISOString();
  const item = {
    PK: `SESSION#${sessionId}`,
    SK: `EVENT#${timestamp}`,
    Status: status,
    Timestamp: timestamp,
    ...(errorMessage && { ErrorMessage: errorMessage })
  };
  await dynamoClient.send(new PutItemCommand({
    TableName: process.env.JOURNAL_TABLE_NAME,
    Item: marshall(item)
  }));
}
```

### 4. Agent Main (src/agents/main.py)

**Purpose**: Process requests and record agent lifecycle events

**Event Recording Points**:

**In `invoke()` entrypoint:**
1. Record AGENT_ENTRYPOINT_STARTED when request received
2. Record AGENT_BACKGROUND_TASK_STARTED after creating background task
3. Record AGENT_ENTRYPOINT_FAILED on error

**In `background_agent_task()`:**
1. Record AGENT_BACKGROUND_TASK_COMPLETED on successful completion
2. Record AGENT_BACKGROUND_TASK_FAILED on NoCredentialsError (with error message)
3. Record AGENT_BACKGROUND_TASK_FAILED on ClientError (with error code and message)
4. Record AGENT_BACKGROUND_TASK_FAILED on Exception (with error type and message)

**DynamoDB Helper Function**:
```python
def record_event(session_id: str, status: str, error_message: str = None):
    """Record an event in DynamoDB"""
    timestamp = datetime.now(timezone.utc).isoformat()
    item = {
        'PK': f'SESSION#{session_id}',
        'SK': f'EVENT#{timestamp}',
        'Status': status,
        'Timestamp': timestamp
    }
    if error_message:
        item['ErrorMessage'] = error_message
    
    table_name = os.environ.get('JOURNAL_TABLE_NAME')
    table = dynamodb.Table(table_name)
    table.put_item(Item=item)
```

### 5. Step Function Event Polling

**Purpose**: Monitor for agent completion events

**Query Logic**:
1. Query DynamoDB with PK="SESSION#{session_id}"
2. Scan results for Status="AGENT_BACKGROUND_TASK_COMPLETED" or "AGENT_BACKGROUND_TASK_FAILED"
3. If completion event found, transition to Success or Failure state
4. If no completion event found, wait and retry
5. After maximum retries, transition to Failure state

**Query Configuration**:
```typescript
{
  KeyConditionExpression: 'PK = :pk',
  ExpressionAttributeValues: {
    ':pk': 'SESSION#{session_id}'
  },
  ScanIndexForward: false, // Most recent events first
  Limit: 20 // Check last 20 events
}
```

## Data Models

### DynamoDB Event Record Structure
```json
{
  "PK": "SESSION#{session_id}",
  "SK": "EVENT#{ISO_timestamp}",
  "Status": "SESSION_INITIATED | AGENT_INVOCATION_STARTED | AGENT_INVOCATION_SUCCEEDED | AGENT_INVOCATION_FAILED | AGENT_ENTRYPOINT_STARTED | AGENT_BACKGROUND_TASK_STARTED | AGENT_BACKGROUND_TASK_COMPLETED | AGENT_BACKGROUND_TASK_FAILED | AGENT_ENTRYPOINT_FAILED",
  "Timestamp": "2024-11-04T10:30:00.123Z",
  "ErrorMessage": "optional error details (only for failure events)"
}
```

### Event Status Types

**Step Function Events:**
- `SESSION_INITIATED`: Step Function starts workflow

**Lambda Invoker Events:**
- `AGENT_INVOCATION_STARTED`: Lambda invoker calls AgentCore
- `AGENT_INVOCATION_SUCCEEDED`: AgentCore responds successfully
- `AGENT_INVOCATION_FAILED`: AgentCore invocation fails

**Agent Entrypoint Events:**
- `AGENT_ENTRYPOINT_STARTED`: Agent entrypoint receives request
- `AGENT_BACKGROUND_TASK_STARTED`: Background task created successfully
- `AGENT_ENTRYPOINT_FAILED`: Entrypoint encounters error

**Agent Background Task Events:**
- `AGENT_BACKGROUND_TASK_COMPLETED`: Agent processing completes successfully
- `AGENT_BACKGROUND_TASK_FAILED`: Agent processing fails (NoCredentialsError, ClientError, or Exception)

### Example Event Records

**Session Initiated:**
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:00.000Z",
  "Status": "SESSION_INITIATED",
  "Timestamp": "2024-11-04T10:30:00.000Z"
}
```

**Agent Invocation Started:**
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:30:01.234Z",
  "Status": "AGENT_INVOCATION_STARTED",
  "Timestamp": "2024-11-04T10:30:01.234Z"
}
```

**Agent Background Task Failed:**
```json
{
  "PK": "SESSION#abc-123-def",
  "SK": "EVENT#2024-11-04T10:35:45.678Z",
  "Status": "AGENT_BACKGROUND_TASK_FAILED",
  "Timestamp": "2024-11-04T10:35:45.678Z",
  "ErrorMessage": "ClientError: ThrottlingException - Rate exceeded"
}
```

## Error Handling

### Event Recording Failures
- All components log errors if event recording fails
- Event recording failures should not block primary operations
- Consider adding retry logic for transient DynamoDB errors

### Lambda Invocation Failures
- Lambda records AGENT_INVOCATION_FAILED event with error details
- Step Function catches Lambda errors and transitions to Failure state
- Error details available in both CloudWatch logs and DynamoDB events

### Session Initialization Errors
- Step Function catches DynamoDB PutItem errors
- Transitions to Failure state if SESSION_INITIATED event creation fails
- Logs error details for debugging

### Agent Processing Errors
- Agent records AGENT_BACKGROUND_TASK_FAILED event with error message
- Step Function detects failed event during polling
- Transitions to Failure state with error context

### Polling Timeout
- Step Function has maximum retry attempts for polling
- If no completion event found after max retries, workflow fails
- Timeout indicates agent may be stuck or crashed without recording failure event

## Testing Strategy

### Manual Trigger Testing
```bash
# Trigger via Makefile (recommended for development)
make trigger-workflow

# Or trigger directly via AWS CLI
aws events put-events --entries '[
  {
    "Source": "manual-trigger",
    "DetailType": "execute-agent",
    "Detail": "{}"
  }
]'
```

### Event Verification
```bash
# Query all events for a session
aws dynamodb query \
  --table-name agents-table-dev \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"SESSION#abc-123-def"}}' \
  --scan-index-forward

# Check for specific event types
aws dynamodb query \
  --table-name agents-table-dev \
  --key-condition-expression "PK = :pk" \
  --filter-expression "Status = :status" \
  --expression-attribute-values '{
    ":pk":{"S":"SESSION#abc-123-def"},
    ":status":{"S":"AGENT_BACKGROUND_TASK_COMPLETED"}
  }'
```

### Integration Testing
1. Trigger EventBridge event
2. Verify Step Function creates SESSION_INITIATED event
3. Verify Lambda creates AGENT_INVOCATION_STARTED event
4. Verify Lambda creates AGENT_INVOCATION_SUCCEEDED event
5. Verify Agent creates AGENT_ENTRYPOINT_STARTED event
6. Verify Agent creates AGENT_BACKGROUND_TASK_STARTED event
7. Verify Agent creates AGENT_BACKGROUND_TASK_COMPLETED or FAILED event
8. Verify Step Function detects completion event and completes workflow
9. Query all events and verify chronological order

## Implementation Files

### CDK Infrastructure
- `infra/lib/workflow.ts`: Step Function definition with event recording and polling logic
- `infra/lib/infra-stack.ts`: IAM permissions for DynamoDB PutItem on journal table

### Lambda Function
- `infra/lambda/agent-invoker.ts`: Add event recording before/after AgentCore invocation

### Agent Code
- `src/agents/main.py`: Add event recording at all lifecycle points (entrypoint and background task)

### Developer Experience
- `LOCAL_DEVELOPMENT.md`: Document event journaling approach and DynamoDB query examples

## Deployment Considerations

### IAM Permissions
- **Step Function**: `dynamodb:PutItem`, `dynamodb:Query` on journal table
- **Lambda Invoker**: `dynamodb:PutItem` on journal table
- **Agent Runtime**: `dynamodb:PutItem` on journal table (via AgentCore execution role)

### DynamoDB Table
- No schema changes required (existing table supports flexible attributes)
- Consider adding GSI if querying by Status becomes common
- TTL already configured for automatic cleanup

### Backward Compatibility
- Event journaling is additive (doesn't break existing SESSION records)
- Old polling logic can coexist during migration
- Agent tools and prompts unchanged (separate PR)

