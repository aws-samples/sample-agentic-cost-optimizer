# Implementation Plan

- [x] 1. Update journaling tool imports and client initialization
  - Replace `strands_tools.use_aws` import with `boto3` import
  - Initialize DynamoDB client using `boto3.client('dynamodb')`
  - Update error handling imports to use `botocore.exceptions`
  - _Requirements: 1.2, 6.2_

- [x] 2. Migrate check_journal_table_exists tool to boto3
  - Replace `use_aws` call with direct `boto3` DescribeTable operation
  - Map `ClientError` exceptions to existing error response format
  - Preserve existing retry logic and response structure
  - _Requirements: 1.2, 5.5, 6.2_

- [x] 3. Migrate create_session_record tool to boto3
  - Replace `use_aws` call with direct `boto3` PutItem operation
  - Update exception handling for `boto3` ClientError types
  - Maintain existing response format and TTL calculation
  - _Requirements: 1.2, 2.2, 5.3_

- [x] 4. Migrate update_session_record tool to boto3
  - Replace `use_aws` call with direct `boto3` UpdateItem operation
  - Preserve existing duration calculation and error categorization
  - Maintain backward compatibility for response format
  - _Requirements: 1.2, 2.4, 5.5_

- [x] 5. Migrate create_task_record tool to boto3
  - Replace `use_aws` call with direct `boto3` PutItem operation
  - Update exception mapping for task creation errors
  - Preserve task timestamp generation and TTL settings
  - _Requirements: 1.2, 2.2, 5.3_

- [x] 6. Update update_task_record tool to remove resource_count
  - Remove `resource_count` parameter from function signature
  - Remove resource_count from UpdateItem expression and response
  - Replace `use_aws` call with direct `boto3` UpdateItem operation
  - Update docstring to reflect parameter removal
  - _Requirements: 1.2, 2.4, 5.5_

- [x] 7. Simplify tool docstrings for readability
  - Reduce verbose documentation while keeping essential Args sections
  - Ensure Strands can still parse tool specifications correctly
  - Focus on concise descriptions of parameters and return values
  - _Requirements: 3.2, 4.1_

- [x] 8. Update agent prompt to use modified tools
  - Remove `resource_count` parameter from all `update_task_record` calls in prompt
  - Verify all journaling tool calls use correct parameter names
  - Maintain existing error handling patterns in prompt
  - _Requirements: 7.1, 7.2, 7.4_