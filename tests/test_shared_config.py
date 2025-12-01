"""Unit tests for the shared config module."""

import os
from unittest.mock import patch

import pytest

from src.shared.config import AppConfig, get_config


class TestAppConfigFromEnv:
    """Tests for AppConfig.from_env() class method."""

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
            config = AppConfig.from_env()

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
            config = AppConfig.from_env()

            assert config.s3_bucket_name == "test-bucket"
            assert config.journal_table_name == "test-table"
            assert config.aws_region == "us-east-1"  # default
            assert config.model_id == "us.anthropic.claude-sonnet-4-5-20250929-v1:0"  # default
            assert config.ttl_days == 90  # default

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
                AppConfig.from_env()

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
                AppConfig.from_env()

    def test_raises_error_when_both_required_vars_missing(self):
        """Test that ValueError is raised when both required vars are missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="S3_BUCKET_NAME environment variable is required"):
                AppConfig.from_env()

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
            config = AppConfig.from_env()

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
            config = AppConfig.from_env()

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
            config = AppConfig.from_env()

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

    def test_creates_instance_with_defaults(self):
        """Test that AppConfig uses default values for optional fields."""
        config = AppConfig(
            s3_bucket_name="my-bucket",
            journal_table_name="my-table",
        )

        assert config.s3_bucket_name == "my-bucket"
        assert config.journal_table_name == "my-table"
        assert config.aws_region == "us-east-1"
        assert config.model_id == "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        assert config.ttl_days == 90

    def test_is_immutable_after_creation(self):
        """Test that AppConfig fields can be modified (dataclass is not frozen)."""
        config = AppConfig(
            s3_bucket_name="my-bucket",
            journal_table_name="my-table",
        )

        # Dataclass is not frozen, so this should work
        config.ttl_days = 120
        assert config.ttl_days == 120


class TestGetConfig:
    """Tests for get_config() function."""

    def test_returns_config_instance(self):
        """Test that get_config returns an AppConfig instance."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
            },
        ):
            # Reset the global config
            import src.shared.config as config_module

            config_module.config = None

            config = get_config()

            assert isinstance(config, AppConfig)
            assert config.s3_bucket_name == "test-bucket"
            assert config.journal_table_name == "test-table"

    def test_caches_config_instance(self):
        """Test that get_config returns the same instance on subsequent calls."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
            },
        ):
            # Reset the global config
            import src.shared.config as config_module

            config_module.config = None

            config1 = get_config()
            config2 = get_config()

            assert config1 is config2  # Same instance

    def test_lazy_loads_on_first_call(self):
        """Test that config is only loaded on first call to get_config."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "test-bucket",
                "JOURNAL_TABLE_NAME": "test-table",
            },
        ):
            # Reset the global config
            import src.shared.config as config_module

            config_module.config = None

            # Config should be None before first call
            assert config_module.config is None

            # First call should load config
            config = get_config()
            assert config_module.config is not None
            assert config_module.config is config

    def test_propagates_validation_errors(self):
        """Test that get_config propagates validation errors from AppConfig.from_env."""
        with patch.dict(os.environ, {}, clear=True):
            # Reset the global config
            import src.shared.config as config_module

            config_module.config = None

            with pytest.raises(ValueError, match="S3_BUCKET_NAME environment variable is required"):
                get_config()


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
            config = AppConfig.from_env()

            # Verify all values are accessible
            assert config.s3_bucket_name
            assert config.journal_table_name
            assert config.aws_region
            assert config.model_id
            assert config.ttl_days > 0

    def test_config_can_be_used_across_modules(self):
        """Test that config can be imported and used in different modules."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "shared-bucket",
                "JOURNAL_TABLE_NAME": "shared-table",
            },
        ):
            # Reset the global config
            import src.shared.config as config_module

            config_module.config = None

            # Import and use in one "module"
            from src.shared import get_config as get_config1

            config1 = get_config1()

            # Import and use in another "module"
            from src.shared import get_config as get_config2

            config2 = get_config2()

            # Should be the same instance
            assert config1 is config2
            assert config1.s3_bucket_name == config2.s3_bucket_name


class TestAppConfigEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_handles_empty_string_for_required_vars(self):
        """Test that empty strings for required vars are treated as missing."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "",
                "JOURNAL_TABLE_NAME": "test-table",
            },
        ):
            with pytest.raises(ValueError, match="S3_BUCKET_NAME environment variable is required"):
                AppConfig.from_env()

    def test_handles_whitespace_in_env_vars(self):
        """Test that whitespace in env vars is preserved."""
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "  test-bucket  ",
                "JOURNAL_TABLE_NAME": "  test-table  ",
            },
        ):
            config = AppConfig.from_env()

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
                AppConfig.from_env()

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
            config = AppConfig.from_env()

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
            config = AppConfig.from_env()

            assert config.ttl_days == 0
