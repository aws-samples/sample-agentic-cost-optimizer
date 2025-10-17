# Implementation Plan

- [x] 1. Update existing code foundations
- [x] 1.1 Add BUSY status to journal tool SessionStatus enum
  - Modify `src/tools/journal.py` to include `BUSY = "BUSY"` in SessionStatus enum
  - _Requirements: 1.1_

- [x] 1.2 Update agent to read session_id from environment and pass to journal tool
  - Modify `src/agents/main.py` to read SESSION_ID from environment variables
  - Pass session_id to journal tool when creating session (JOURNAL_TABLE_NAME already handled via environment)
  - _Requirements: 1.2, 1.3_

- [x] 1.3 Update agent prompt to instruct BUSY status setting
  - Modify `src/agents/prompt.md` to instruct agent to set status to BUSY at start of processing
  - _Requirements: 1.5_

- [x] 2. Update Lambda invoker function
- [x] 2.1 Modify Lambda function to accept session_id parameter
  - Update `infra/lambda/agent-invoker.ts` to accept session_id in event payload
  - Pass session_id and JOURNAL_TABLE_NAME as environment variables to agent runtime
  - _Requirements: 2.1, 2.2_

- [x] 2.2 Update CDK stack to pass DynamoDB table name to Lambda
  - Modify `infra/lib/infra-stack.ts` to add JOURNAL_TABLE_NAME environment variable to Lambda
  - _Requirements: 2.2_

- [x] 3. Create Step Function workflow
- [x] 3.1 Create workflow.ts file with Step Function definition
  - Create `infra/lib/workflow.ts` with Step Function state machine
  - Define states: InvokeAgent, CheckStatus, WaitForCompletion, Success, Failure
  - Include DynamoDB polling logic for session status
  - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 3.2 Add IAM permissions for Step Function
  - Grant Lambda invocation permissions to Step Function
  - Grant DynamoDB GetItem permissions for session status polling
  - _Requirements: 5.2_

- [x] 4. Create EventBridge integration
- [x] 4.1 Add EventBridge rule to infra-stack.ts
  - Create EventBridge rule with event pattern for manual triggers
  - Configure input transformer to pass event ID as session_id
  - Set Step Function as target
  - _Requirements: 6.1, 6.2, 6.4, 6.5_

- [x] 5. Integrate workflow into main CDK stack
- [x] 5.1 Import and instantiate workflow in infra-stack.ts
  - Import Workflow construct in `infra/lib/infra-stack.ts`
  - Pass existing Lambda function and DynamoDB table references
  - Add Step Function ARN output
  - Add EventBridge rule with manual trigger pattern
  - _Requirements: 5.1, 5.3, 5.4_

- [x] 6. Add CLI trigger documentation
- [x] 6.1 Create example CLI commands for manual triggering
  - Document AWS CLI command for publishing EventBridge events
  - Include example event payload structure
  - _Requirements: 6.3_

- [x] 7. Add developer experience improvements
- [x] 7.1 Add Makefile target for workflow triggering
  - Add `trigger-workflow` target to Makefile for easy testing
  - Update Makefile help section to include new target
  - _Requirements: 7.1, 7.2_

- [x] 7.2 Update development documentation
  - Enhance LOCAL_DEVELOPMENT.md with comprehensive CLI trigger examples
  - Update project structure documentation to reflect current layout
  - _Requirements: 7.3, 7.4_

