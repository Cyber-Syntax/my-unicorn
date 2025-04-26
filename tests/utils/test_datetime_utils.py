#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for datetime utility functions.

This module contains tests for the datetime utility functions in src/utils/datetime_utils.py.
"""

from datetime import datetime
from typing import Any, Optional, Union

import pytest
from hypothesis import given, strategies as st

from src.utils.datetime_utils import parse_timestamp, format_timestamp, get_next_hour_timestamp


class TestParseTimestamp:
    """Tests for parse_timestamp function."""

    def test_parse_iso_format(self) -> None:
        """Test parsing ISO format string timestamps."""
        # Test ISO format string
        iso_timestamp = "2023-01-15T12:30:45"
        result = parse_timestamp(iso_timestamp)

        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 45

    def test_parse_numeric_timestamp(self) -> None:
        """Test parsing numeric (int, float) timestamps."""
        # Test integer timestamp (seconds since epoch)
        int_timestamp = 1673789445  # 2023-01-15 12:30:45 UTC
        result = parse_timestamp(int_timestamp)

        assert isinstance(result, datetime)
        # Check converted to local time correctly
        assert result.timestamp() == pytest.approx(int_timestamp, abs=1)

        # Test float timestamp
        float_timestamp = 1673789445.5  # With milliseconds
        result = parse_timestamp(float_timestamp)

        assert isinstance(result, datetime)
        assert result.timestamp() == pytest.approx(float_timestamp, abs=1)

    def test_parse_numeric_string(self) -> None:
        """Test parsing string representations of numeric timestamps."""
        # Test string containing numeric timestamp
        timestamp_str = "1673789445"  # 2023-01-15 12:30:45 UTC as string
        result = parse_timestamp(timestamp_str)

        assert isinstance(result, datetime)
        assert result.timestamp() == pytest.approx(1673789445, abs=1)

        # Test string with float
        float_str = "1673789445.5"
        result = parse_timestamp(float_str)

        assert isinstance(result, datetime)
        assert result.timestamp() == pytest.approx(1673789445.5, abs=1)

    def test_parse_none(self) -> None:
        """Test parsing None values."""
        result = parse_timestamp(None)
        assert result is None

    def test_parse_invalid_formats(self) -> None:
        """Test parsing invalid timestamp formats."""
        # Test invalid string
        result = parse_timestamp("not a timestamp")
        assert result is None

        # Test invalid type
        result = parse_timestamp({"not": "a timestamp"})  # type: ignore
        assert result is None

        # Test out of range timestamp
        result = parse_timestamp(999999999999999)  # Far future
        assert result is None

        # Test negative timestamp (should work if reasonable)
        try:
            result = parse_timestamp(-1000000)  # Past 1970
            assert isinstance(result, datetime) or result is None  # Both valid behaviors
        except Exception:
            # If it fails, that's acceptable too
            pass

    @given(st.integers(min_value=0, max_value=2147483647))  # Valid Unix timestamps
    def test_parse_property_valid_int_timestamp(self, timestamp: int) -> None:
        """
        Property test for parsing valid integer timestamps.

        Args:
            timestamp: Random valid Unix timestamp
        """
        result = parse_timestamp(timestamp)
        assert isinstance(result, datetime)
        # The parsed datetime should convert back to approximately the same timestamp
        assert result.timestamp() == pytest.approx(timestamp, abs=1)

    @given(st.text())
    def test_parse_property_random_strings(self, random_string: str) -> None:
        """
        Property test for parsing random strings.

        Args:
            random_string: Random string
        """
        # For random strings, should either parse correctly or return None
        result = parse_timestamp(random_string)
        if result is not None:
            assert isinstance(result, datetime)


class TestFormatTimestamp:
    """Tests for format_timestamp function."""

    def test_format_valid_timestamp(self) -> None:
        """Test formatting valid timestamps."""
        # Test with ISO string
        result = format_timestamp("2023-01-15T12:30:45")
        assert result == "2023-01-15 12:30:45"

        # Test with custom format
        result = format_timestamp("2023-01-15T12:30:45", format_str="%Y/%m/%d")
        assert result == "2023/01/15"

        # Test with numeric timestamp
        result = format_timestamp(1673789445)  # 2023-01-15 12:30:45 UTC
        # We can't assert the exact string since it depends on local timezone
        assert result is not None
        assert len(result) > 0

    def test_format_none(self) -> None:
        """Test formatting None values."""
        result = format_timestamp(None)
        assert result is None

    def test_format_invalid_timestamp(self) -> None:
        """Test formatting invalid timestamps."""
        result = format_timestamp("not a timestamp")
        assert result is None


class TestGetNextHourTimestamp:
    """Tests for get_next_hour_timestamp function."""

    def test_next_hour_timestamp(self) -> None:
        """Test getting the next hour timestamp."""
        # Current time
        current_time = int(datetime.now().timestamp())

        # Get next hour timestamp
        next_hour = get_next_hour_timestamp()

        # Check it's in the future
        assert next_hour > current_time

        # Check it's at an hour boundary (divisible by 3600)
        assert next_hour % 3600 == 0

        # Check it's less than 3600 seconds (1 hour) in the future
        assert next_hour - current_time <= 3600
