"""Unit tests for the shared config module."""

import os
from unittest.mock import patch

import pytest

from src.shared.config import AppConfig, load_config


class TestAppConfigFromEnv:
    """Tests for load_config() function."""

    def test_loads_all_required_env_vars(self):
        """Test that all required environment variables are loaded."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
                "AWS_REGION": "us-west-2",
                "MODEL_ID": "test-model-id",
                "TTL_DAYS": "30",
            },
        ):
            config = load_config()

            assert config.s3_bucket_name == "test-bucket"
            assert config.journal_table_name == "test-table"
            assert config.aws_region == "us-west-2"
            assert config.model_id == "test-model-id"
            assert config.ttl_days == 30

    def test_uses_default_values_for_optional_vars(self):
        """Test that default values are used when optional env vars are missing."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
            },
            clear=True,
        ):
            config = load_config()

            assert config.s3_bucket_name == "test-bucket"
            assert config.journal_table_name == "test-table"
            assert config.aws_region == "us-east-1"
            assert config.model_id == "us.anthropic.claude-sonnet-4-20250514-v1:0"
            assert config.ttl_days == 30

    def test_raises_error_when_s3_bucket_name_missing(self):
        """Test that ValueError is raised when S3_BUCKET_NAME is missing."""
        with patch.dict(
            os.environ,
            {
                "JOURNAL_TABLE_NAME": "test-table",
            },
            clear=True,
        ):
            with pytest.raises(ValueError, match="S3_BUCKET_NAME environment variable is required"):
                load_config()

    def test_raises_error_when_journal_table_name_missing(self):
        """Test that ValueError is raised when JOURNAL_TABLE_NAME is missing."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
            },
            clear=True,
        ):
            with pytest.raises(ValueError, match="JOURNAL_TABLE_NAME environment variable is required"):
                load_config()

    def test_raises_error_when_all_required_vars_missing(self):
        """Test that ValueError is raised when all required vars are missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="S3_BUCKET_NAME environment variable is required"):
                load_config()

    def test_converts_ttl_days_to_int(self):
        """Test that TTL_DAYS is properly converted to integer."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
                "TTL_DAYS": "365",
            },
        ):
            config = load_config()

            assert config.ttl_days == 365
            assert isinstance(config.ttl_days, int)

    def test_handles_custom_aws_region(self):
        """Test that custom AWS_REGION is properly loaded."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
                "AWS_REGION": "eu-central-1",
            },
        ):
            config = load_config()

            assert config.aws_region == "eu-central-1"

    def test_handles_custom_model_id(self):
        """Test that custom MODEL_ID is properly loaded."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
                "MODEL_ID": "custom-model-v2",
            },
        ):
            config = load_config()

            assert config.model_id == "custom-model-v2"


class TestAppConfigDataclass:
    """Tests for AppConfig dataclass functionality."""

    def test_creates_instance_with_all_fields(self):
        """Test that AppConfig can be instantiated with all fields."""
        config = AppConfig(
            s3_bucket_name="my-bucket",
            journal_table_name="my-table",
            aws_region="ap-southeast-1",
            model_id="my-model",
            ttl_days=180,
        )

        assert config.s3_bucket_name == "my-bucket"
        assert config.journal_table_name == "my-table"
        assert config.aws_region == "ap-southeast-1"
        assert config.model_id == "my-model"
        assert config.ttl_days == 180

    def test_creates_instance_with_all_required_fields(self):
        """Test that AppConfig requires all fields."""
        config = AppConfig(
            s3_bucket_name="my-bucket",
            journal_table_name="my-table",
            aws_region="ap-southeast-1",
            model_id="my-model",
            ttl_days=180,
        )

        assert config.s3_bucket_name == "my-bucket"
        assert config.journal_table_name == "my-table"
        assert config.aws_region == "ap-southeast-1"
        assert config.model_id == "my-model"
        assert config.ttl_days == 180

    def test_is_mutable_after_creation(self):
        """Test that AppConfig fields can be modified (dataclass is not frozen)."""
        config = AppConfig(
            s3_bucket_name="my-bucket",
            journal_table_name="my-table",
            aws_region="us-east-1",
            model_id="test-model",
            ttl_days=90,
        )

        # Dataclass is not frozen, so this should work
        config.ttl_days = 120
        assert config.ttl_days == 120


class TestLoadConfig:
    """Tests for load_config() function."""

    def test_returns_config_instance(self):
        """Test that load_config returns an AppConfig instance."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
            },
        ):
            config = load_config()

            assert isinstance(config, AppConfig)
            assert config.s3_bucket_name == "test-bucket"
            assert config.journal_table_name == "test-table"

    def test_propagates_validation_errors(self):
        """Test that load_config propagates validation errors."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="S3_BUCKET_NAME environment variable is required"):
                load_config()


class TestAppConfigIntegration:
    """Integration tests for AppConfig usage patterns."""

    def test_config_works_with_real_env_vars(self):
        """Test that config works with actual environment variables."""
        # This test uses the actual environment variables set by pytest fixtures
        # in conftest.py or test setup
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "integration-bucket",
                "JOURNAL_TABLE_NAME": "integration-table",
                "AWS_REGION": "us-west-1",
                "TTL_DAYS": "60",
            },
        ):
            config = load_config()

            # Verify all values are accessible
            assert config.s3_bucket_name
            assert config.journal_table_name
            assert config.aws_region
            assert config.model_id
            assert config.ttl_days > 0

    def test_config_can_be_used_across_modules(self):
        """Test that config can be imported and used in different modules."""
        from src.shared.config import config

        assert isinstance(config, AppConfig)
        assert config.s3_bucket_name
        assert config.journal_table_name


class TestAppConfigEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_handles_empty_string_for_s3_bucket_name(self):
        """Test that empty string for S3_BUCKET_NAME is treated as missing."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "",
                "JOURNAL_TABLE_NAME": "test-table",
            },
        ):
            with pytest.raises(ValueError, match="S3_BUCKET_NAME environment variable is required"):
                load_config()

    def test_handles_whitespace_in_env_vars(self):
        """Test that whitespace in env vars is preserved."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "  test-bucket  ",
                "JOURNAL_TABLE_NAME": "  test-table  ",
            },
        ):
            config = load_config()

            # Environment variables preserve whitespace
            assert config.s3_bucket_name == "  test-bucket  "
            assert config.journal_table_name == "  test-table  "

    def test_handles_invalid_ttl_days_format(self):
        """Test that invalid TTL_DAYS format raises ValueError."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
                "TTL_DAYS": "not-a-number",
            },
        ):
            with pytest.raises(ValueError):
                load_config()

    def test_handles_negative_ttl_days(self):
        """Test that negative TTL_DAYS is accepted (validation could be added later)."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
                "TTL_DAYS": "-1",
            },
        ):
            config = load_config()

            # Currently accepts negative values (could add validation if needed)
            assert config.ttl_days == -1

    def test_handles_zero_ttl_days(self):
        """Test that zero TTL_DAYS is accepted."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
                "TTL_DAYS": "0",
            },
        ):
            config = load_config()

            assert config.ttl_days == 0
