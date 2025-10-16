# Design Document

## Overview

This design implements configurable retry and backoff functionality for the Agent using botocore's built-in Config mechanism. The solution leverages boto3's proven retry mechanisms with sensible defaults, supports Claude 4 Sonnet as the default model with configurable alternatives, and includes comprehensive mocked unit tests focused on error handling. The implementation prioritizes simplicity as a POC solution, with retry logic handled by boto3 and comprehensive error handling in the invoke function.

## Architecture

The architecture consists of three main components:

1. **Agent Configuration Module** - Handles botocore Config setup with sensible defaults
2. **Agent Wrapper** - Provides error handling around agent invocation
3. **Test Suite** - Mocked unit tests for retry scenarios and error handling

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Agent Config  │───▶│  BedrockModel    │───▶│     Agent       │
│   (BotocoreConfig)│    │  (with config)   │    │   (with model)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Error Handler  │
                                               │  (try/catch)    │
                                               └─────────────────┘
```

## Components and Interfaces

### 1. Configuration Component

**Purpose**: Create and manage botocore Config with retry settings

**Interface**:
```python
def create_boto_config(
    max_attempts: int = 3,        # boto3 default
    retry_mode: str = "legacy",   # boto3 default
    connect_timeout: int = 60,    # boto3 default
    read_timeout: int = 60,       # boto3 default
    max_pool_connections: int = 10  # boto3 default
) -> BotocoreConfig
```

**Default Values** (using boto3's actual defaults per Requirement 1):
- `max_attempts`: 3 (boto3 default)
- `retry_mode`: "legacy" (boto3 default)
- `connect_timeout`: 60 seconds (boto3 default)
- `read_timeout`: 60 seconds (boto3 default)
- `max_pool_connections`: 10 (boto3 default)

**Design Rationale**: Uses hardcoded boto3 default values to ensure consistent behavior while leveraging existing retry mechanisms without custom logic, as specified in Requirement 1.

### 2. Agent Factory Component

**Purpose**: Create configured Agent instances with proper model setup

**Interface**:
```python
def create_agent(
    model_id: str = "us.anthropic.claude-4-20250514-v1:0",  # Claude 4 default
    region_name: str = "us-east-1",
    boto_config: Optional[BotocoreConfig] = None
) -> Agent
```

**Design Rationale**: Claude 4 is set as the default model per Requirement 2, but the model_id parameter allows easy configuration changes without code modifications.

### 3. Invoke Function Component

**Purpose**: Provide error handling around agent invocation with BedrockAgentCore integration

**Interface**:
```python
@app.entrypoint
def invoke(payload) -> str
```

**Error Handling Strategy**:
- Catch NoCredentialsError and return credentials setup message
- Catch ClientError and handle specific error codes (ThrottlingException, AccessDeniedException)
- Return user-friendly error messages for all scenarios
- Log errors for debugging
- Focus on most common Bedrock error scenarios

## Data Models

### Default Configuration
```python
# Default boto3 configuration constants
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_MODE = "legacy"
DEFAULT_CONNECT_TIMEOUT = 60
DEFAULT_READ_TIMEOUT = 60
DEFAULT_MAX_POOL_CONNECTIONS = 10

# Default model settings
DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"  # Claude 4 Sonnet
DEFAULT_REGION = "us-east-1"
```

**Design Rationale**: Groups boto3 configuration in a single BotocoreConfig object to avoid over-engineering while maintaining simplicity per Requirement 6.

### Response Format
```python
# Simple tuple or dictionary response format
# Success: (True, "response_message")
# Error: (False, "error_message", "error_type")
```

## Error Handling

### Common Bedrock Exceptions to Handle:
1. **ClientError** - Invalid requests, authentication issues
2. **ServiceException** - Service unavailable, throttling
3. **ConnectionError** - Network connectivity issues
4. **TimeoutError** - Request timeouts

### Error Response Strategy:
```python
try:
    response = agent(user_message)
    return (True, response)
except ClientError as e:
    return (False, "Service error occurred", "client_error")
except Exception as e:
    return (False, "Unexpected error occurred", "unknown")
```

## Testing Strategy

### Test Structure:
```
tests/
├── __init__.py
├── test_invoke_function.py   # Invoke function error handling tests
└── conftest.py              # Shared fixtures for error objects and payloads
```

### Test Scenarios:

#### 1. Happy Path Tests
- Test successful agent response with mocked agent
- Test default prompt handling when payload is empty
- Verify expected response format

#### 2. Error Handling Tests
- Test NoCredentialsError handling with user-friendly message
- Test ClientError with ThrottlingException returning throttling message
- Test ClientError with AccessDeniedException returning permissions message
- Test ClientError with unknown error codes returning generic message
- Test generic Exception handling with unexpected error message
- Test edge cases like malformed error responses

### Mocking Strategy:
- Use `unittest.mock.patch` to mock the agent at the function level
- Mock agent to return specific responses or raise specific exceptions
- Use conftest.py fixtures for reusable error objects and test data
- Focus on testing error message conversion rather than retry behavior

### Test Execution:
- Tests runnable via `uv run pytest` and `make test`
- Use pytest as test framework with pytest-mock for enhanced mocking
- 9 focused test cases covering all error scenarios and edge cases

## Implementation Notes

1. **Simplicity First**: Follow POC principles - minimal, readable code
2. **Leverage Existing Libraries**: Use boto3's proven retry mechanisms
3. **Configuration Over Code**: Make settings easily changeable
4. **Fail Gracefully**: Handle errors without crashing
5. **Test Thoroughly**: Ensure retry behavior works without real API calls