"""
Application-wide constants and default values.

This module centralizes all hardcoded default values used across the application,
making them easy to find, update, and maintain.
"""

# AWS Configuration Defaults
DEFAULT_AWS_REGION = "us-east-1"
DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
DEFAULT_TTL_DAYS = 30

# Boto3 Configuration Defaults
DEFAULT_MAX_ATTEMPTS = 5  # Increased from default 3 for better resilience with Bedrock
DEFAULT_RETRY_MODE = "standard"  # AWS recommended mode with exponential backoff + jitter
DEFAULT_CONNECT_TIMEOUT = 60  # Time allowed for establishing connection to Bedrock
DEFAULT_READ_TIMEOUT = 600  # Time allowed for streaming responses from model
DEFAULT_MAX_POOL_CONNECTIONS = 10
