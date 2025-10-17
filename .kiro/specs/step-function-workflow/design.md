# Design Document

## Overview

This design implements a Step Function workflow that orchestrates agent invocation through EventBridge triggers, monitors session status via DynamoDB polling, and handles success/failure paths. The solution integrates with the existing CDK infrastructure and requires minimal modifications to existing code.

## Architecture

### High-Level Flow
```
EventBridge Event → Step Function → Lambda Invoker → Agent → DynamoDB Session Status
                        ↓                                        ↑
                   Status Polling ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
```

### Component Interactions

1. **EventBridge** publishes manual trigger events with unique event IDs
2. **Step Function** receives event ID as session_id and orchestrates the workflow
3. **Lambda Invoker** receives session context and invokes the agent with environment variables
4. **Agent** processes requests and updates session status in DynamoDB via journal tool
5. **Step Function** polls DynamoDB for session status until completion or failure

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
1. **InvokeAgent**: Call Lambda invoker function
2. **CheckStatus**: Query DynamoDB for session status
3. **WaitForCompletion**: Wait state with retry logic
4. **Success**: Terminal success state
5. **Failure**: Terminal failure state

**Interface**:
```json
{
  "session_id": "string",
  "status": "BUSY|COMPLETED|FAILED",
  "error": "string (optional)"
}
```

### 3. Lambda Invoker Function (Modified)

**Purpose**: Invoke AgentCore runtime with session context

**Input**:
```typescript
{
  session_id: string;
  prompt?: string;
}
```

**Environment Variables Passed to Agent**:
- `SESSION_ID`: From Step Function input
- `S3_BUCKET_NAME`: From existing CDK stack
- `JOURNAL_TABLE_NAME`: From existing CDK stack

**Output**:
```typescript
{
  status: number;
  sessionId: string;
}
```

### 4. Agent (Modified)

**Purpose**: Process requests and update session status

**Environment Variables Read**:
- `SESSION_ID`: Session identifier
- `S3_BUCKET_NAME`: S3 bucket for data storage
- `JOURNAL_TABLE_NAME`: DynamoDB table for journaling

**Journal Tool Integration**:
- Set status to "BUSY" at start of processing
- Set status to "COMPLETED" or "FAILED" at end

### 5. DynamoDB Status Polling

**Purpose**: Monitor agent session completion

**Query Pattern**:
- PK: `session_id`
- SK: `SESSION`

**Status Values**:
- `BUSY`: Agent is processing
- `COMPLETED`: Agent finished successfully
- `FAILED`: Agent encountered an error

## Data Models

### EventBridge Event
```json
{
  "id": "event-uuid-12345",
  "source": "manual-trigger",
  "detail-type": "execute-agent",
  "detail": {}
}
```

### Step Function Input
```json
{
  "session_id": "event-uuid-12345"
}
```

### DynamoDB Session Record
```json
{
  "PK": "event-uuid-12345",
  "SK": "SESSION", 
  "status": "BUSY|COMPLETED|FAILED",
  "start_time": "2024-10-16T10:30:00Z",
  "end_time": "2024-10-16T10:35:00Z",
  "duration_seconds": 300,
  "error_message": "optional error details"
}
```

## Error Handling

### Lambda Invocation Failures
- Step Function catches Lambda errors
- Transitions to Failure state
- Logs error details for debugging

### DynamoDB Polling Errors
- Built-in Step Function retry mechanisms
- Exponential backoff for transient errors
- Maximum retry attempts before failure

### Agent Processing Errors
- Agent sets session status to "FAILED"
- Step Function detects failed status
- Transitions to Failure state

### Missing Session Records
- Step Function continues polling
- Handles case where agent hasn't created record yet
- Times out after maximum attempts

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

### Status Verification
```bash
# Check Step Function execution
aws stepfunctions describe-execution --execution-arn <arn>

# Check DynamoDB session record
aws dynamodb get-item \
  --table-name agents-table-dev \
  --key '{"PK":{"S":"session-id"},"SK":{"S":"SESSION"}}'
```

### Integration Testing
1. Trigger EventBridge event
2. Verify Step Function starts
3. Verify Lambda invocation
4. Verify agent creates session record
5. Verify status polling works
6. Verify completion detection

## Implementation Files

### CDK Infrastructure
- `infra/lib/workflow.ts`: Step Function definition and EventBridge rule
- `infra/lib/infra-stack.ts`: Import and integrate workflow construct

### Lambda Function
- `infra/lambda/agent-invoker.ts`: Modified to accept and pass session context

### Agent Code
- `src/agents/main.py`: Modified to read environment variables
- `src/agents/prompt.md`: Updated to instruct BUSY status setting
- `src/tools/journal.py`: Add BUSY status to SessionStatus enum

### Developer Experience
- `Makefile`: Added `trigger-workflow` target for easy testing (primary testing method)
- `LOCAL_DEVELOPMENT.md`: Comprehensive CLI trigger documentation and updated project structure

## Deployment Considerations

### CDK Stack Updates
- Add workflow construct to main stack
- Grant Step Function permissions for Lambda and DynamoDB
- Output Step Function ARN for reference

### Environment Variables
- Pass DynamoDB table name to Lambda function
- Pass S3 bucket name to Lambda function
- Ensure agent runtime receives session context

### IAM Permissions
- Step Function: `lambda:InvokeFunction`, `dynamodb:GetItem`
- EventBridge: `states:StartExecution`
- Lambda: Existing permissions plus environment variable access

