"""
Centralized configuration management for the agent application.

This module provides a single source of truth for environment-based configuration,
eliminating duplicate environment variable reads across the codebase.
"""

import os
from dataclasses import dataclass

from .constants import DEFAULT_AWS_REGION, DEFAULT_MODEL_ID, DEFAULT_TTL_DAYS


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
    aws_region: str
    model_id: str
    ttl_days: int


def load_config() -> AppConfig:
    """Load configuration from environment variables.

    Returns:
        AppConfig instance with values from environment

    Raises:
        ValueError: If required environment variables are missing
    """
    if "BYPASS_TOOL_CONSENT" not in os.environ:
        os.environ["BYPASS_TOOL_CONSENT"] = "true"

    s3_bucket_name = os.environ.get("S3_BUCKET_NAME")
    if not s3_bucket_name:
        raise ValueError("S3_BUCKET_NAME environment variable is required")

    journal_table_name = os.environ.get("JOURNAL_TABLE_NAME")
    if not journal_table_name:
        raise ValueError("JOURNAL_TABLE_NAME environment variable is required")

    aws_region = os.environ.get("AWS_REGION", DEFAULT_AWS_REGION)
    model_id = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    ttl_days = int(os.environ.get("TTL_DAYS", str(DEFAULT_TTL_DAYS)))

    return AppConfig(
        s3_bucket_name=s3_bucket_name,
        journal_table_name=journal_table_name,
        aws_region=aws_region,
        model_id=model_id,
        ttl_days=ttl_days,
    )


config = load_config()
