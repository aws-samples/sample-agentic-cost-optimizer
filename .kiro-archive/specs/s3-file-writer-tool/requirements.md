# Requirements Document

## Introduction

This feature creates a dedicated Strands tool for S3 file writing operations that the cost optimization agent can use to save generated reports and evidence files. Currently, the agent uses the generic `use_aws` tool for S3 operations, which requires the agent to construct complex AWS API calls and handle low-level details. By creating a specialized `storage` tool using the `@tool` decorator, we provide a clean abstraction that simplifies the agent prompt, improves maintainability, and follows the same pattern established by the journaling tool. The storage tool will handle all boto3 S3 operations internally while providing simple, semantic methods for the agent to save text files.

## Glossary

- **Storage Tool**: A Strands tool that provides S3 file writing capabilities through a simple interface
- **Agent**: The cost optimization agent that generates reports and needs to save them to S3
- **Session ID**: A unique identifier for each agent execution session, used as the S3 key prefix
- **Text File**: Plain text content (.txt files) that the agent generates as reports or evidence
- **Strands Tool**: A Python function decorated with `@tool` that the agent can invoke during execution

## Requirements

### Requirement 1

**User Story:** As a developer, I want to create a Strands tool that provides S3 file writing capabilities, so that the agent can easily save text files without constructing complex AWS API calls.

#### Acceptance Criteria

1. WHEN creating the storage tool, THE tool SHALL use the `@tool` decorator from Strands to create a Python function with proper type hints and docstrings
2. WHEN the tool writes a file to S3, THE tool SHALL use `boto3` directly to interact with S3 with proper error handling
3. WHEN the storage tool is called, THE tool SHALL return structured responses with success/error status following Strands patterns
4. WHEN the S3 bucket doesn't exist, THE tool SHALL gracefully handle the error and return appropriate status without breaking agent workflow
5. WHEN the tool encounters AWS authentication or permission errors, THE tool SHALL use proper error handling and return meaningful error messages

### Requirement 2

**User Story:** As a developer, I want the storage tool to automatically manage file paths using session context, so that the agent doesn't need to manually construct S3 keys.

#### Acceptance Criteria

1. WHEN the tool writes a file, THE tool SHALL retrieve the session_id from the Strands ToolContext invocation state
2. WHEN constructing the S3 key, THE tool SHALL automatically prefix the filename with the session_id (e.g., `<session_id>/cost_report.txt`)
3. WHEN the session_id is not available in the context, THE tool SHALL return an error response without attempting the S3 operation
4. WHEN the bucket name is needed, THE tool SHALL retrieve it from the environment variable `S3_BUCKET_NAME`
5. WHEN the environment variable is not set, THE tool SHALL return an error response with clear guidance

### Requirement 3

**User Story:** As a developer, I want the storage tool to handle text content efficiently, so that the agent can save reports of any reasonable size.

#### Acceptance Criteria

1. WHEN the agent provides text content, THE tool SHALL accept it as a string parameter without size restrictions for typical reports
2. WHEN writing to S3, THE tool SHALL encode the text content as UTF-8 bytes for proper storage
3. WHEN the content is successfully written, THE tool SHALL return the full S3 URI (e.g., `s3://bucket-name/session_id/filename.txt`)
4. WHEN the S3 operation completes, THE tool SHALL include metadata such as file size and timestamp in the response
5. WHEN overwriting existing files, THE tool SHALL allow overwrites by default to support idempotent operations

### Requirement 4

**User Story:** As a developer, I want the storage tool to follow Strands best practices, so that it is maintainable, reusable, and well-integrated with the agent framework.

#### Acceptance Criteria

1. WHEN implementing the tool, THE tool SHALL use proper Python type hints for all parameters and return values following Strands patterns
2. WHEN documenting the tool, THE tool SHALL include concise docstrings with essential Args sections that Strands can parse for tool specifications
3. WHEN the tool returns data, THE tool SHALL use a dictionary format with status and content fields for consistent agent integration
4. WHEN the tool is imported, THE tool SHALL be easily added to the agent's tool list as a decorated function without complex configuration
5. WHEN the tool needs AWS credentials, THE tool SHALL use the standard boto3 credential chain without requiring explicit configuration

### Requirement 5

**User Story:** As a developer, I want the storage tool to provide comprehensive error handling, so that the agent can gracefully handle failures and continue its workflow.

#### Acceptance Criteria

1. WHEN S3 operations fail, THE tool SHALL catch `ClientError` exceptions and extract error codes and messages
2. WHEN unexpected errors occur, THE tool SHALL catch generic exceptions and return structured error responses
3. WHEN errors are returned, THE tool SHALL include contextual information such as bucket name, key, and operation type
4. WHEN the tool encounters throttling errors, THE tool SHALL include the error details in the response for the agent to log
5. WHEN errors occur, THE tool SHALL never raise exceptions that would break the agent workflow

### Requirement 6

**User Story:** As a developer, I want the storage tool to integrate seamlessly with the existing agent infrastructure, so that it works reliably in the current environment.

#### Acceptance Criteria

1. WHEN implementing the tool, THE tool SHALL be modular with clear separation of concerns between S3 operations and business logic
2. WHEN the tool interacts with AWS, THE tool SHALL handle authentication and region configuration properly using `boto3` client management
3. WHEN the tool is deployed, THE tool SHALL work seamlessly with existing AWS credentials and IAM roles without requiring additional configuration
4. WHEN the tool is imported, THE tool SHALL integrate easily with the current agent setup by adding it to the tools list alongside the journal tool
5. WHEN the tool needs updates, THE tool SHALL be modifiable without breaking existing agent functionality through backward-compatible interfaces

### Requirement 7

**User Story:** As a developer, I want the agent prompt to be updated to use the new storage tool, so that it becomes cleaner and more focused on cost optimization logic.

#### Acceptance Criteria

1. WHEN updating the agent prompt, THE prompt SHALL replace all `use_aws` S3 write operations with calls to the new `storage` tool
2. WHEN the agent uses the storage tool, THE agent SHALL handle tool responses appropriately by checking success status and extracting S3 URIs
3. WHEN S3 write operations fail, THE agent SHALL continue with the cost optimization workflow and include error details in the final report
4. WHEN the prompt is refactored, THE prompt SHALL maintain the existing workflow structure and only replace S3-related operations with tool calls
5. WHEN the new system is deployed, THE system SHALL provide equivalent S3 writing capabilities with improved maintainability and reduced prompt complexity

### Requirement 8

**User Story:** As a developer, I want the storage tool to provide comprehensive logging, so that I can track operations and debug issues when reviewing observability spans.

#### Acceptance Criteria

1. WHEN the storage tool is initialized, THE tool SHALL configure a logger using Python's logging module with the module name
2. WHEN the tool is invoked, THE tool SHALL log informational messages with `-->` prefix including session_id and filename at INFO level
3. WHEN the tool encounters errors, THE tool SHALL log error messages with `-->` prefix and full context including error codes and messages at ERROR level
4. WHEN the tool successfully completes operations, THE tool SHALL log success messages with `-->` prefix including S3 URI and file size at INFO level
5. WHEN logging messages, THE tool SHALL follow the application's logging pattern using `-->` prefix for operational logs to maintain consistency
