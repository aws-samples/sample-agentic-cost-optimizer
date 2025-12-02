"""Tests for time tools"""

import time
from datetime import datetime, timezone

from src.tools.time_tools import convert_time_unix_to_iso, current_time_unix_utc


def test_current_time_unix_utc():
    """Test current_time_unix_utc returns valid Unix timestamp."""
    result = current_time_unix_utc()

    assert isinstance(result, int)

    # Verify it's a reasonable timestamp (after 2024-01-01)
    assert result > 1704067200  # 2024-01-01 00:00:00 UTC

    # Verify it's close to now (within 2 seconds)
    actual_time = int(time.time())
    assert abs(result - actual_time) <= 2


def test_convert_time_unix_to_iso():
    """Test Unix timestamp to ISO 8601 conversion."""
    # Test with a known timestamp: 2024-12-02 15:18:45 UTC
    unix_timestamp = 1733152725
    result = convert_time_unix_to_iso(unix_timestamp)

    assert isinstance(result, str)
    assert result == "2024-12-02T15:18:45Z"

    # Verify it matches expected ISO format pattern
    assert len(result) == 20
    assert result.endswith("Z")
    assert "T" in result


def test_convert_time_unix_to_iso_with_current_time():
    """Test conversion with current time to ensure consistency."""
    unix_timestamp = current_time_unix_utc()

    iso_time = convert_time_unix_to_iso(unix_timestamp)

    parsed_time = datetime.strptime(iso_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    parsed_unix = int(parsed_time.timestamp())

    # Should match within 1 second (accounting for execution time)
    assert abs(parsed_unix - unix_timestamp) <= 1


def test_convert_time_unix_to_iso_edge_cases():
    """Test conversion with various edge case timestamps."""
    # Test epoch (1970-01-01 00:00:00 UTC)
    assert convert_time_unix_to_iso(0) == "1970-01-01T00:00:00Z"

    # Test a specific date: 2025-01-01 00:00:00 UTC
    assert convert_time_unix_to_iso(1735689600) == "2025-01-01T00:00:00Z"

    # Test another specific date: 2024-06-15 12:30:45 UTC
    assert convert_time_unix_to_iso(1718454645) == "2024-06-15T12:30:45Z"


def test_time_range_calculation_pattern():
    """Test the pattern used in prompts for time range calculations."""
    # This simulates how the agent would use the tools
    current_time = current_time_unix_utc()

    # Calculate 30 days back (as the agent would with calculator)
    thirty_days_seconds = 30 * 86400
    start_time = current_time - thirty_days_seconds

    # Verify the calculation makes sense
    assert start_time < current_time
    assert (current_time - start_time) == thirty_days_seconds

    # Convert both to ISO for AWS APIs that need it
    start_iso = convert_time_unix_to_iso(start_time)
    end_iso = convert_time_unix_to_iso(current_time)

    # Verify both are valid ISO strings
    assert start_iso.endswith("Z")
    assert end_iso.endswith("Z")
    assert start_iso < end_iso  # Lexicographic comparison works for ISO format


def test_iso_format_consistency():
    """Test that ISO format is consistent and parseable."""
    test_timestamps = [0, 1704067200, 1733152725, 1735689600]

    for ts in test_timestamps:
        iso_str = convert_time_unix_to_iso(ts)

        assert iso_str.endswith("Z")
        assert "T" in iso_str
        assert len(iso_str) == 20

        parsed = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        assert int(parsed.timestamp()) == ts
