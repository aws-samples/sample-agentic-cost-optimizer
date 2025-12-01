"""
Centralized configuration management for the agent application.

This module provides a single source of truth for environment-based configuration,
eliminating duplicate environment variable reads across the codebase.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
    """Application configuration loaded from environment variables.

    Attributes:
        s3_bucket_name: S3 bucket for file storage
        journal_table_name: DynamoDB table for event journaling
        aws_region: AWS region for services
        model_id: Bedrock model identifier
        ttl_days: Number of days before records expire
    """

    s3_bucket_name: str
    journal_table_name: str
    aws_region: str = "us-east-1"
    model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    ttl_days: int = 90

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment variables.

        Returns:
            AppConfig instance with values from environment

        Raises:
            ValueError: If required environment variables are missing
        """
        s3_bucket_name = os.environ.get("S3_BUCKET_NAME")
        if not s3_bucket_name:
            raise ValueError("S3_BUCKET_NAME environment variable is required")

        journal_table_name = os.environ.get("JOURNAL_TABLE_NAME")
        if not journal_table_name:
            raise ValueError("JOURNAL_TABLE_NAME environment variable is required")

        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        model_id = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
        ttl_days = int(os.environ.get("TTL_DAYS", "90"))

        return cls(
            s3_bucket_name=s3_bucket_name,
            journal_table_name=journal_table_name,
            aws_region=aws_region,
            model_id=model_id,
            ttl_days=ttl_days,
        )


# Global configuration instance - loaded once at module import
config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the global configuration instance.

    Lazily loads configuration on first access. Subsequent calls return
    the cached instance, which is efficient for Lambda container reuse.

    Returns:
        AppConfig instance

    Raises:
        ValueError: If required environment variables are missing
    """
    global config
    if config is None:
        config = AppConfig.from_env()
    return config
