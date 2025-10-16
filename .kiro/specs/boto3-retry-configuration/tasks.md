# Implementation Plan

- [x] 1. Set up configuration module with boto3 defaults
  - Create configuration constants for boto3 default values
  - Implement create_boto_config function with botocore Config
  - Set Claude 4 as default model ID
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2_

- [x] 2. Implement agent factory with retry configuration
  - [x] 2.1 Create agent factory function with boto_client_config support
    - Write create_agent function that accepts boto_config parameter
    - Integrate botocore Config with BedrockModel initialization
    - Use Claude 4 as default model with configurable override
    - _Requirements: 1.1, 2.1, 2.2_

  - [x] 2.2 Add agent wrapper with error handling
    - Implement invoke function with comprehensive try/catch blocks
    - Handle common Bedrock exceptions (ClientError, NoCredentialsError)
    - Include specific error handling for ThrottlingException and AccessDeniedException
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 3. Create test structure and unit tests for invoke function
  - [x] 3.1 Set up test directory structure and configuration
    - Create tests/ directory with __init__.py
    - Add pytest and pytest-mock to pyproject.toml dev dependencies
    - Configure tests to run via "uv run pytest"
    - _Requirements: 5.1, 5.2_

  - [x] 3.2 Implement invoke function unit tests with mocked agent
    - Mock the global agent to avoid actual AWS calls
    - Test successful agent response: agent returns response, invoke returns string
    - Test NoCredentialsError: agent raises exception, invoke returns credentials error message
    - Test ClientError with ThrottlingException: invoke returns throttling message
    - Test ClientError with AccessDeniedException: invoke returns permissions message
    - Test ClientError with unknown error code: invoke returns generic technical difficulties message
    - Test generic Exception: invoke returns unexpected error message
    - Test edge cases: malformed error responses, missing prompt in payload
    - Create conftest.py with shared fixtures for error objects and test data
    - Add make test target to Makefile for easy test execution
    - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.4, 5.1, 5.2_