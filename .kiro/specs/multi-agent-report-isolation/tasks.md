# Implementation Plan

- [ ] 1. Create Data Store Tool
  - Implement data_store tool in src/tools/data_store.py with write and read actions
  - Tool retrieves session_id from tool_context.invocation_state
  - Write action stores data to Data_Store_Table with PK=SESSION#{session_id}, SK=DATA#{data_key}
  - Read action queries Data_Store_Table and returns data_content or error
  - Include error handling for ClientError and missing data
  - Add logging for debugging
  - _Requirements: 3.1, 3.2, 3.3_

- [ ]* 1.1 Write unit tests for data_store tool
  - Test write action with valid data
  - Test read action with existing data
  - Test read action with missing data
  - Test error handling for DynamoDB ClientError
  - Test session_id retrieval from invocation_state
  - Mock boto3 DynamoDB operations
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 2. Create Data Store Table Infrastructure
  - Add Data_Store_Table definition to infra/lib/infra-stack.ts
  - Configure table with PK=PK (String), SK=SK (String)
  - Set billing mode to PAY_PER_REQUEST
  - Enable TTL on ttl attribute
  - Set removal policy to DESTROY for dev
  - Enable point-in-time recovery
  - _Requirements: 3.4_

- [ ] 2.1 Update AgentCore Runtime IAM permissions
  - Add Data_Store_Table read/write permissions to AgentCore Runtime role
  - Grant dynamodb:PutItem, dynamodb:GetItem, dynamodb:Query actions
  - Scope permissions to Data_Store_Table ARN
  - _Requirements: 3.4_

- [ ] 2.2 Add Data_Store_Table environment variable
  - Add DATA_STORE_TABLE_NAME to AgentCore Runtime environment variables
  - Pass table name from CDK stack to runtime
  - _Requirements: 3.4_

- [ ] 3. Create Analysis Agent Prompt
  - Create src/agents/analysis_prompt.md file
  - Extract phases 1-5 from current src/agents/prompt.md:
    - Discovery (Inventory)
    - Usage and Metrics Collection
    - Analysis and Decision Rules
    - Recommendation Format
    - Cost Estimation Method
  - Add instructions to save complete analysis results using data_store tool
  - Include data_key="ANALYSIS_RESULTS" and structured text format
  - Ensure all discovery data, metrics, recommendations, and evidence are included
  - Remove any references to phases 6-7 (Output Contract, S3 Write)
  - _Requirements: 1.1, 1.4, 4.1, 4.2, 4.3_

- [ ] 4. Create Report Agent Prompt
  - Create src/agents/report_prompt.md file
  - Extract phases 6-7 from current src/agents/prompt.md:
    - Output Contract (plain text)
    - S3 Write Requirements
  - Add instructions to load analysis results using data_store tool with data_key="ANALYSIS_RESULTS"
  - Add error handling for missing analysis results
  - Include instructions to record TASK_REPORT_GENERATION_FAILED if data missing
  - Remove any references to phases 1-5 (Discovery, Metrics, Analysis, Recommendations, Cost Estimation)
  - _Requirements: 1.2, 1.5, 4.4, 4.5_

- [ ] 5. Create Main Agent Prompt
  - Create src/agents/main_prompt.md file
  - Write orchestrator prompt that uses workflow tool
  - Define task 1 (analysis) with Analysis Agent prompt, dependencies=[], priority=5
  - Define task 2 (report) with Report Agent prompt, dependencies=["analysis"], priority=3
  - Include instructions to create workflow, start workflow, and check status
  - Ensure invocation_state (with session_id) is passed to workflow
  - _Requirements: 1.5, 2.1, 2.2, 2.3, 9.1_

- [ ] 6. Refactor Main Agent to Use Workflow Tool
  - Update src/agents/main.py to import workflow tool from strands_tools
  - Change agent tools from [use_aws, journal, storage, calculator] to [workflow]
  - Load main_prompt.md as SYSTEM_PROMPT
  - Ensure invocation_state with session_id is passed to agent
  - Keep existing background_task decorator and entrypoint pattern
  - _Requirements: 1.5, 2.1, 2.4, 8.4, 9.1, 9.2_

- [ ] 7. Update Tool Imports and Exports
  - Add data_store to src/tools/__init__.py exports
  - Verify use_aws, journal, storage, calculator are still exported
  - Ensure workflow tool is imported from strands_tools in main.py
  - _Requirements: 7.1, 7.2, 7.3_

- [ ] 8. Update Dependencies
  - Add strands_tools to pyproject.toml dependencies if not already present
  - Verify strands version supports workflow tool
  - Run uv lock to update uv.lock
  - _Requirements: 2.1_

- [ ] 9. Deploy Infrastructure Changes
  - Deploy CDK stack with Data_Store_Table
  - Verify table creation in AWS Console
  - Verify AgentCore Runtime has correct IAM permissions
  - Verify DATA_STORE_TABLE_NAME environment variable is set
  - _Requirements: 2.1, 2.2, 3.4_

- [ ] 10. Test Data Store Tool in Isolation
  - Deploy agent code with data_store tool
  - Manually invoke data_store tool with write action
  - Verify data written to Data_Store_Table
  - Manually invoke data_store tool with read action
  - Verify data retrieved correctly
  - Test error handling with missing data
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 11. Test Multi-Agent Workflow End-to-End
  - Trigger workflow via EventBridge
  - Monitor CloudWatch logs for Main Agent, Analysis Agent, Report Agent
  - Verify Analysis Agent completes phases 1-5
  - Verify analysis results written to Data_Store_Table
  - Verify Report Agent reads analysis results
  - Verify Report Agent completes phases 6-7
  - Verify cost_report.txt and evidence.txt written to S3
  - Verify events recorded to Journal_Table
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 10.1, 10.2, 10.3_

- [ ] 12. Validate Backward Compatibility
  - Compare cost_report.txt format with baseline from current system
  - Compare evidence.txt format with baseline from current system
  - Verify all expected event types in Journal_Table
  - Verify S3 URIs are returned in storage tool responses
  - Verify session lifecycle events match current system
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 13. Test Failure Scenarios
  - Simulate Analysis Agent failure (mock AWS API error)
  - Verify workflow halts without invoking Report Agent
  - Verify FAILED event recorded to Journal_Table
  - Simulate Report Agent failure (mock S3 error)
  - Verify analysis results preserved in Data_Store_Table
  - Verify FAILED event recorded to Journal_Table
  - Simulate data_store tool failure
  - Verify error handling and FAILED event recording
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

