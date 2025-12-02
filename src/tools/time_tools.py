"""Time Tools for Cost Optimization Agent"""

import logging
import time
from datetime import datetime, timezone

from strands import tool

logger = logging.getLogger(__name__)


@tool
def current_time_unix_utc() -> int:
    """Get the current Unix timestamp in UTC (seconds since epoch).

    Returns:
        int: Current Unix timestamp
    """
    timestamp = int(time.time())
    logger.info(f"CURRENT_TIME_UNIX_UTC: {timestamp}")
    return timestamp


@tool
def convert_time_unix_to_iso(unix_timestamp: int) -> str:
    """Convert Unix timestamp to ISO 8601 format for AWS APIs.

    Args:
        unix_timestamp: Unix timestamp in seconds since epoch

    Returns:
        str: ISO 8601 formatted timestamp (e.g., '2025-11-28T11:18:45Z')
    """
    iso_time = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.info(f"CONVERT_TIME_UNIX_TO_ISO: {unix_timestamp} → {iso_time}")
    return iso_time
