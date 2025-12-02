"""Unit tests for the shared event_validation module."""

import pytest

from src.shared.event_validation import (
    DYNAMIC_STATUS_PATTERN,
    MAX_PHASE_NAME_LENGTH,
    PHASE_NAME_PATTERN,
    validate_event_status,
)


class TestValidationConstants:
    """Test cases for validation constants."""

    def test_phase_name_pattern_accepts_valid_characters(self):
        """Test that PHASE_NAME_PATTERN accepts alphanumeric, underscore, and dash."""
        assert PHASE_NAME_PATTERN.match("valid_phase")
        assert PHASE_NAME_PATTERN.match("VALID_PHASE")
        assert PHASE_NAME_PATTERN.match("valid-phase")
        assert PHASE_NAME_PATTERN.match("ValidPhase123")
        assert PHASE_NAME_PATTERN.match("123")
        assert PHASE_NAME_PATTERN.match("_")
        assert PHASE_NAME_PATTERN.match("-")

    def test_phase_name_pattern_rejects_invalid_characters(self):
        """Test that PHASE_NAME_PATTERN rejects special characters."""
        assert not PHASE_NAME_PATTERN.match("phase@name")
        assert not PHASE_NAME_PATTERN.match("phase name")
        assert not PHASE_NAME_PATTERN.match("phase.name")
        assert not PHASE_NAME_PATTERN.match("phase$name")
        assert not PHASE_NAME_PATTERN.match("phase!name")

    def test_dynamic_status_pattern_matches_valid_format(self):
        """Test that DYNAMIC_STATUS_PATTERN matches valid TASK_{phase}_{suffix} format."""
        assert DYNAMIC_STATUS_PATTERN.match("TASK_DISCOVERY_STARTED")
        assert DYNAMIC_STATUS_PATTERN.match("TASK_ANALYSIS_COMPLETED")
        assert DYNAMIC_STATUS_PATTERN.match("TASK_PROCESSING_FAILED")
        assert DYNAMIC_STATUS_PATTERN.match("TASK_my-phase_STARTED")
        assert DYNAMIC_STATUS_PATTERN.match("TASK_123_COMPLETED")

    def test_dynamic_status_pattern_rejects_invalid_format(self):
        """Test that DYNAMIC_STATUS_PATTERN rejects invalid formats."""
        assert not DYNAMIC_STATUS_PATTERN.match("TASK_PHASE_INVALID")
        assert not DYNAMIC_STATUS_PATTERN.match("INVALID_PHASE_STARTED")
        assert not DYNAMIC_STATUS_PATTERN.match("TASK_STARTED")
        assert not DYNAMIC_STATUS_PATTERN.match("PHASE_STARTED")
        assert not DYNAMIC_STATUS_PATTERN.match("TASK_PHASE@NAME_STARTED")

    def test_max_phase_name_length_constant(self):
        """Test that MAX_PHASE_NAME_LENGTH is set to 50."""
        assert MAX_PHASE_NAME_LENGTH == 50


class TestValidateEventStatusPredefined:
    """Test cases for predefined status validation."""

    def test_valid_predefined_status_passes(self):
        """Test that valid predefined statuses pass validation."""
        valid_statuses = {
            "SESSION_INITIATED",
            "AGENT_INVOCATION_STARTED",
            "AGENT_INVOCATION_COMPLETED",
        }

        # Should not raise any exception
        validate_event_status("SESSION_INITIATED", valid_statuses)
        validate_event_status("AGENT_INVOCATION_STARTED", valid_statuses)
        validate_event_status("AGENT_INVOCATION_COMPLETED", valid_statuses)

    def test_invalid_predefined_status_raises_error(self):
        """Test that invalid predefined statuses raise ValueError."""
        valid_statuses = {"SESSION_INITIATED", "AGENT_INVOCATION_STARTED"}

        with pytest.raises(ValueError, match="Invalid status 'INVALID_STATUS'"):
            validate_event_status("INVALID_STATUS", valid_statuses)


class TestValidateEventStatusDynamic:
    """Test cases for dynamic status validation."""

    def test_valid_dynamic_status_with_started_suffix(self):
        """Test that valid dynamic status with STARTED suffix passes."""
        valid_statuses = {"SESSION_INITIATED"}

        # Should not raise any exception
        validate_event_status("TASK_DISCOVERY_STARTED", valid_statuses)
        validate_event_status("TASK_my_phase_STARTED", valid_statuses)
        validate_event_status("TASK_phase-name_STARTED", valid_statuses)

    def test_valid_dynamic_status_with_completed_suffix(self):
        """Test that valid dynamic status with COMPLETED suffix passes."""
        valid_statuses = {"SESSION_INITIATED"}

        # Should not raise any exception
        validate_event_status("TASK_ANALYSIS_COMPLETED", valid_statuses)
        validate_event_status("TASK_my_phase_COMPLETED", valid_statuses)

    def test_valid_dynamic_status_with_failed_suffix(self):
        """Test that valid dynamic status with FAILED suffix passes."""
        valid_statuses = {"SESSION_INITIATED"}

        # Should not raise any exception
        validate_event_status("TASK_PROCESSING_FAILED", valid_statuses)
        validate_event_status("TASK_my_phase_FAILED", valid_statuses)

    def test_dynamic_status_with_long_valid_phase_name(self):
        """Test that dynamic status with maximum length phase name passes."""
        valid_statuses = {"SESSION_INITIATED"}
        # Create a phase name exactly at the 50 character limit
        phase_name = "a" * 50
        status = f"TASK_{phase_name}_STARTED"

        # Should not raise any exception
        validate_event_status(status, valid_statuses)

    def test_dynamic_status_with_mixed_case_phase_name(self):
        """Test that dynamic status with mixed case phase name passes."""
        valid_statuses = {"SESSION_INITIATED"}

        # Should not raise any exception
        validate_event_status("TASK_MyPhaseName_STARTED", valid_statuses)
        validate_event_status("TASK_UPPERCASE_STARTED", valid_statuses)
        validate_event_status("TASK_lowercase_STARTED", valid_statuses)

    def test_dynamic_status_with_numeric_phase_name(self):
        """Test that dynamic status with numeric phase name passes."""
        valid_statuses = {"SESSION_INITIATED"}

        # Should not raise any exception
        validate_event_status("TASK_123_STARTED", valid_statuses)
        validate_event_status("TASK_phase123_STARTED", valid_statuses)


class TestValidateEventStatusInvalidDynamic:
    """Test cases for invalid dynamic status validation."""

    def test_dynamic_status_with_invalid_suffix_raises_error(self):
        """Test that dynamic status with invalid suffix raises ValueError."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status 'TASK_PHASE_INVALID'"):
            validate_event_status("TASK_PHASE_INVALID", valid_statuses)

        with pytest.raises(ValueError, match="Invalid status 'TASK_PHASE_RUNNING'"):
            validate_event_status("TASK_PHASE_RUNNING", valid_statuses)

    def test_dynamic_status_with_special_characters_raises_error(self):
        """Test that dynamic status with special characters in phase name raises ValueError."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status 'TASK_PHASE@NAME_STARTED'"):
            validate_event_status("TASK_PHASE@NAME_STARTED", valid_statuses)

        with pytest.raises(ValueError, match="Invalid status 'TASK_PHASE\\$NAME_STARTED'"):
            validate_event_status("TASK_PHASE$NAME_STARTED", valid_statuses)

        with pytest.raises(ValueError, match="Invalid status 'TASK_PHASE\\.NAME_STARTED'"):
            validate_event_status("TASK_PHASE.NAME_STARTED", valid_statuses)

    def test_dynamic_status_with_spaces_raises_error(self):
        """Test that dynamic status with spaces in phase name raises ValueError."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status 'TASK_PHASE NAME_STARTED'"):
            validate_event_status("TASK_PHASE NAME_STARTED", valid_statuses)

    def test_dynamic_status_exceeding_max_length_raises_error(self):
        """Test that dynamic status with phase name exceeding max length raises ValueError."""
        valid_statuses = {"SESSION_INITIATED"}
        # Create a phase name that exceeds the 50 character limit
        phase_name = "a" * 51
        status = f"TASK_{phase_name}_STARTED"

        with pytest.raises(
            ValueError,
            match=f"Phase name '{phase_name}' exceeds maximum length of {MAX_PHASE_NAME_LENGTH} characters",
        ):
            validate_event_status(status, valid_statuses)

    def test_dynamic_status_with_very_long_phase_name_raises_error(self):
        """Test that dynamic status with very long phase name raises ValueError."""
        valid_statuses = {"SESSION_INITIATED"}
        # Create a phase name significantly longer than the limit
        phase_name = "a" * 100
        status = f"TASK_{phase_name}_STARTED"

        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_event_status(status, valid_statuses)

    def test_malformed_dynamic_status_missing_prefix_raises_error(self):
        """Test that malformed dynamic status missing TASK_ prefix raises ValueError."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status 'PHASE_STARTED'"):
            validate_event_status("PHASE_STARTED", valid_statuses)

        with pytest.raises(ValueError, match="Invalid status 'DISCOVERY_STARTED'"):
            validate_event_status("DISCOVERY_STARTED", valid_statuses)

    def test_malformed_dynamic_status_missing_phase_raises_error(self):
        """Test that malformed dynamic status missing phase name raises ValueError."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status 'TASK__STARTED'"):
            validate_event_status("TASK__STARTED", valid_statuses)

        with pytest.raises(ValueError, match="Invalid status 'TASK_STARTED'"):
            validate_event_status("TASK_STARTED", valid_statuses)


class TestValidateEventStatusEdgeCases:
    """Test cases for edge cases in event status validation."""

    def test_empty_status_raises_error(self):
        """Test that empty status string raises ValueError."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status ''"):
            validate_event_status("", valid_statuses)

    def test_empty_valid_statuses_set(self):
        """Test validation with empty predefined statuses set."""
        valid_statuses = set()

        # Valid dynamic status should still pass
        validate_event_status("TASK_PHASE_STARTED", valid_statuses)

        # Invalid status should raise error
        with pytest.raises(ValueError, match="Invalid status 'INVALID'"):
            validate_event_status("INVALID", valid_statuses)

    def test_case_sensitive_validation(self):
        """Test that validation is case-sensitive for predefined statuses."""
        valid_statuses = {"SESSION_INITIATED"}

        # Exact match should pass
        validate_event_status("SESSION_INITIATED", valid_statuses)

        # Different case should fail (not in predefined set)
        with pytest.raises(ValueError, match="Invalid status 'session_initiated'"):
            validate_event_status("session_initiated", valid_statuses)

    def test_dynamic_status_with_single_character_phase(self):
        """Test that dynamic status with single character phase name passes."""
        valid_statuses = {"SESSION_INITIATED"}

        # Should not raise any exception
        validate_event_status("TASK_A_STARTED", valid_statuses)
        validate_event_status("TASK_1_COMPLETED", valid_statuses)
        validate_event_status("TASK___FAILED", valid_statuses)

    def test_dynamic_status_with_only_underscores(self):
        """Test that dynamic status with only underscores in phase name passes."""
        valid_statuses = {"SESSION_INITIATED"}

        # Should not raise any exception
        validate_event_status("TASK____STARTED", valid_statuses)

    def test_dynamic_status_with_only_dashes(self):
        """Test that dynamic status with only dashes in phase name passes."""
        valid_statuses = {"SESSION_INITIATED"}

        # Should not raise any exception
        validate_event_status("TASK_---_STARTED", valid_statuses)

    def test_phase_name_pattern_explicit_validation(self):
        """Test explicit phase name pattern validation (line 52 coverage)."""
        valid_statuses = {"SESSION_INITIATED"}

        # This should pass - valid characters
        validate_event_status("TASK_Valid-Phase_123_STARTED", valid_statuses)

        # This should fail - invalid characters
        with pytest.raises(ValueError, match="Invalid status"):
            validate_event_status("TASK_phase!name_STARTED", valid_statuses)


class TestValidateEventStatusSecurityCases:
    """Test cases for security-related validation scenarios."""

    def test_sql_injection_attempt_raises_error(self):
        """Test that SQL injection attempts are rejected."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status"):
            validate_event_status("TASK_'; DROP TABLE events;--_STARTED", valid_statuses)

    def test_command_injection_attempt_raises_error(self):
        """Test that command injection attempts are rejected."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status"):
            validate_event_status("TASK_$(rm -rf /)_STARTED", valid_statuses)

        with pytest.raises(ValueError, match="Invalid status"):
            validate_event_status("TASK_`whoami`_STARTED", valid_statuses)

    def test_path_traversal_attempt_raises_error(self):
        """Test that path traversal attempts are rejected."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status"):
            validate_event_status("TASK_../../etc/passwd_STARTED", valid_statuses)

        with pytest.raises(ValueError, match="Invalid status"):
            validate_event_status("TASK_..\\..\\windows\\system32_STARTED", valid_statuses)

    def test_xss_attempt_raises_error(self):
        """Test that XSS attempts are rejected."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status"):
            validate_event_status("TASK_<script>alert('xss')</script>_STARTED", valid_statuses)

    def test_unicode_characters_raises_error(self):
        """Test that unicode characters in phase name are rejected."""
        valid_statuses = {"SESSION_INITIATED"}

        with pytest.raises(ValueError, match="Invalid status"):
            validate_event_status("TASK_phase\u00e9_STARTED", valid_statuses)

        with pytest.raises(ValueError, match="Invalid status"):
            validate_event_status("TASK_\u4e2d\u6587_STARTED", valid_statuses)
