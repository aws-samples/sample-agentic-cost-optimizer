# Implementation Plan

- [x] 1. Enhance Storage Tool with Read Action
  - Add read action to existing src/tools/storage.py
  - Read action accepts filename parameter and retrieves session_id from tool_context.invocation_state
  - Read action reads from S3 at path {session_id}/{filename}
  - Returns dictionary with success status, content, s3_uri, or error message
  - Include error handling for ClientError and missing files
  - Add logging for debugging
  - _Requirements: 3.1, 3.2, 3.3, 3.5_

- [x] 1.1 Write unit tests for storage tool read action
  - Test read action with existing file
  - Test read action with missing file
  - Test error handling for S3 ClientError
  - Test session_id retrieval from invocation_state
  - Mock boto3 S3 operations
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 2. Create Analysis Agent Prompt
  - Create src/agents/analysis_prompt.md file
  - Extract phases 1-5 from current src/agents/prompt.md:
    - Discovery (Inventory)
    - Usage and Metrics Collection
    - Analysis and Decision Rules
    - Recommendation Format
    - Cost Estimation Method
  - Add instructions to save complete analysis results using storage tool
  - Use filename="analysis.txt" and structured text format
  - Ensure all discovery data, metrics, recommendations, and evidence are included
  - Remove any references to phases 6-7 (Output Contract, S3 Write)
  - _Requirements: 1.1, 1.3, 4.1, 4.2, 4.3_

- [x] 3. Create Report Agent Prompt
  - Create src/agents/report_prompt.md file
  - Extract phases 6-7 from current src/agents/prompt.md:
    - Output Contract (plain text)
    - S3 Write Requirements
  - Add instructions to load analysis results using storage tool with filename="analysis.txt"
  - Add error handling for missing analysis results
  - Include instructions to record TASK_REPORT_GENERATION_FAILED if data missing
  - Remove any references to phases 1-5 (Discovery, Metrics, Analysis, Recommendations, Cost Estimation)
  - _Requirements: 1.2, 1.4, 4.4, 4.5_

- [x] 4. Refactor Main Agent for Sequential Invocation
  - Update src/agents/main.py to create two separate agents
  - Create analysis_agent with analysis_prompt.md and tools [use_aws, journal, calculator, storage]
  - Create report_agent with report_prompt.md and tools [storage, journal]
  - Update background_task to sequentially invoke both agents
  - First: await analysis_agent.invoke_async() with session_id parameter
  - Second: await report_agent.invoke_async() with session_id parameter
  - Keep existing background_task decorator and entrypoint pattern
  - Add try-catch error handling with AGENT_BACKGROUND_TASK_FAILED events
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 8.4, 9.1, 9.2_

- [x] 5. Test Sequential Agent Invocation End-to-End
  - Trigger workflow via EventBridge
  - Monitor CloudWatch logs for analysis_agent and report_agent invocations
  - Verify Analysis Agent completes phases 1-5
  - Verify analysis.txt written to S3 at {session_id}/analysis.txt
  - Verify Report Agent reads analysis.txt from S3
  - Verify Report Agent completes phases 6-7
  - Verify cost_report.txt and evidence.txt written to S3
  - Verify events recorded to Journal_Table
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 10.1, 10.2, 10.3_

- [x] 6. Validate Backward Compatibility
  - Compare cost_report.txt format with baseline from current system
  - Compare evidence.txt format with baseline from current system
  - Verify all expected event types in Journal_Table
  - Verify S3 URIs are returned in storage tool responses
  - Verify session lifecycle events match current system
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_


