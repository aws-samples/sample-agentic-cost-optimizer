# Implementation Plan

- [x] 1. Create storage tool module with core S3 writing functionality
  - Create `src/tools/storage.py` file with module structure
  - Import required dependencies: boto3, botocore.exceptions, strands, logging, os, datetime
  - Initialize S3 resource using `boto3.resource("s3")` at module level
  - Configure logger using `logging.getLogger(__name__)`
  - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.5, 8.1_

- [x] 2. Implement internal storage function with session context handling
  - Create `_write_to_s3()` internal function with parameters: filename, content, tool_context
  - Implement session_id retrieval from `tool_context.invocation_state`
  - Implement bucket name retrieval from `S3_BUCKET_NAME` environment variable
  - Add validation for required parameters and configuration
  - Return error responses for missing configuration with appropriate messages
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. Implement S3 key construction and file writing logic
  - Construct S3 key using pattern: `{session_id}/{filename}`
  - Encode content as UTF-8 bytes
  - Get S3 bucket object using `s3.Bucket(bucket_name)`
  - Call `bucket.put_object()` with Key, Body, and ContentType='text/plain'
  - Calculate file size from encoded content
  - _Requirements: 2.1, 3.1, 3.2, 3.3_

- [x] 4. Implement comprehensive error handling for S3 operations
  - Wrap S3 operations in try/except blocks
  - Catch `ClientError` and extract error code and message
  - Catch generic `Exception` for unexpected errors
  - Create structured error responses with success=False, error message, and context
  - Include bucket, key, and error_code in error responses
  - _Requirements: 1.4, 1.5, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 5. Implement success response with S3 URI and metadata
  - Construct S3 URI: `s3://{bucket}/{key}`
  - Create success response dictionary with success=True
  - Include s3_uri, bucket, key, size_bytes, and timestamp in response
  - Generate ISO 8601 timestamp for operation completion
  - Return structured response following Strands patterns
  - _Requirements: 3.3, 3.4, 3.5, 4.3_

- [x] 6. Add comprehensive logging throughout storage operations
  - Add DEBUG level logging for tool invocation with filename and session_id
  - Add DEBUG level logging for S3 key construction
  - Add INFO level logging for successful writes with S3 URI and file size
  - Add ERROR level logging for all error scenarios with full context
  - Include error codes, bucket, and key in error logs
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 7. Create public storage tool function with @tool decorator
  - Create `storage()` function decorated with `@tool(context=True)`
  - Define parameters: filename (str), content (str), tool_context (ToolContext)
  - Add comprehensive docstring with Args and Returns sections
  - Call internal `_write_to_s3()` function and return result
  - Ensure function signature matches Strands tool requirements
  - _Requirements: 1.1, 4.1, 4.2, 4.4_

- [x] 8. Integrate storage tool with agent
  - Import storage tool in `src/tools/__init__.py`
  - Add storage to agent tools list in `src/agents/main.py`
  - Verify tool is available alongside journal and use_aws tools
  - _Requirements: 4.4, 6.3, 6.4_

- [ ] 9. Update agent prompt to use storage tool
  - Replace `use_aws` S3 write operations in `src/agents/prompt.md`
  - Update S3 Write Requirements section with storage tool usage
  - Add instructions for calling storage tool with filename and content parameters
  - Update error handling instructions for storage tool responses
  - Maintain existing workflow structure and only replace S3 operations
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 10. Create unit tests for storage tool
- [x]* 10.1 Create test file and fixtures
  - Create `tests/test_storage.py` file
  - Implement `mock_tool_context` fixture with session_id
  - Implement `mock_s3_bucket` fixture with put_object mock
  - Implement `setup_env` fixture for S3_BUCKET_NAME environment variable
  - _Requirements: 1.3, 4.3_

- [x]* 10.2 Write success scenario tests
  - Test successful file write with valid parameters
  - Verify S3 bucket.put_object called with correct Key, Body, ContentType
  - Verify response contains success=True, s3_uri, bucket, key, size_bytes, timestamp
  - Mock boto3.resource and verify S3 operations
  - _Requirements: 3.3, 3.4, 4.3_

- [x]* 10.3 Write configuration error tests
  - Test with missing session_id in invocation_state
  - Test with missing S3_BUCKET_NAME environment variable
  - Verify error responses with success=False and appropriate error messages
  - _Requirements: 2.3, 2.5, 5.3_

- [x]* 10.4 Write validation error tests
  - Test with missing filename parameter
  - Test with missing content parameter
  - Test with empty content string
  - Verify validation error responses
  - _Requirements: 5.3_

- [x]* 10.5 Write S3 error handling tests
  - Test S3 ClientError scenarios (NoSuchBucket, AccessDenied)
  - Test generic exceptions
  - Verify error responses include error codes and context
  - Verify success field is False in all error cases
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x]* 10.6 Write key construction and encoding tests
  - Verify correct key format: `{session_id}/{filename}`
  - Test with various filename formats
  - Verify UTF-8 encoding applied to content
  - Verify ContentType set to 'text/plain'
  - _Requirements: 2.1, 3.1, 3.2_
