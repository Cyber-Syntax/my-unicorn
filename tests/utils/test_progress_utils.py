from my_unicorn.utils.progress_utils import calculate_speed


def test_calculate_speed_zero_time_returns_zero():
    avg, hist = calculate_speed(
        prev_completed=100.0,
        prev_time=1000.0,
        speed_history=None,
        completed=150.0,
        current_time=1000.0,
        max_history=5,
    )

    assert avg == 0.0
    assert hist is None or len(hist) == 0


def test_calculate_speed_negative_time_returns_zero():
    avg, hist = calculate_speed(
        prev_completed=100.0,
        prev_time=1001.0,
        speed_history=None,
        completed=150.0,
        current_time=1000.0,
        max_history=5,
    )

    assert avg == 0.0


def test_calculate_speed_zero_progress_returns_zero():
    avg, hist = calculate_speed(
        prev_completed=200.0,
        prev_time=1000.0,
        speed_history=None,
        completed=200.0,
        current_time=1001.0,
        max_history=5,
    )

    assert avg == 0.0


def test_calculate_speed_normal_and_history():
    # First measurement
    avg1, hist1 = calculate_speed(
        prev_completed=0.0,
        prev_time=1000.0,
        speed_history=None,
        completed=100.0,
        current_time=1001.0,
        max_history=5,
    )

    # raw speed should be 100 bytes/sec for this interval
    assert abs(avg1 - 100.0) < 1e-6
    assert hist1 is not None and len(hist1) == 1

    # Second measurement - should average over history
    avg2, hist2 = calculate_speed(
        prev_completed=100.0,
        prev_time=1001.0,
        speed_history=hist1,
        completed=300.0,
        current_time=1003.0,
        max_history=5,
    )

    # raw speeds were 100 (first interval) and 100 (second interval of 200/2s)
    assert abs(avg2 - 100.0) < 1e-6
    assert hist2 is not None and len(hist2) == 2


"""Comprehensive tests for progress_utils module.

Tests cover all utility functions for ASCII rendering and data formatting
including edge cases and boundary conditions.
"""


from my_unicorn.utils.progress_utils import (
    GIB,
    KIB,
    MIB,
    format_eta,
    format_percentage,
    human_mib,
    human_speed_bps,
    pad_left,
    pad_right,
    render_bar,
    truncate_text,
)


class TestConstants:
    """Test byte conversion constants."""

    def test_kib_value(self) -> None:
        """Test KiB constant value."""
        assert KIB == 1024

    def test_mib_value(self) -> None:
        """Test MiB constant value."""
        assert MIB == 1024 * 1024

    def test_gib_value(self) -> None:
        """Test GiB constant value."""
        assert GIB == 1024 * 1024 * 1024


class TestHumanMib:
    """Test human_mib function."""

    def test_zero_bytes(self) -> None:
        """Test zero bytes returns '0 B'."""
        assert human_mib(0) == "0 B"

    def test_negative_bytes(self) -> None:
        """Test negative bytes returns '0 B'."""
        assert human_mib(-100) == "0 B"

    def test_bytes_less_than_kib(self) -> None:
        """Test bytes less than 1 KiB."""
        assert human_mib(512) == "0.5 KiB"

    def test_exact_one_kib(self) -> None:
        """Test exactly 1 KiB."""
        assert human_mib(1024) == "1.0 KiB"

    def test_kib_range(self) -> None:
        """Test values in KiB range."""
        assert human_mib(512 * 1024) == "512.0 KiB"

    def test_one_mib(self) -> None:
        """Test exactly 1 MiB."""
        result = human_mib(1024 * 1024)
        assert result == "1.0 MiB"

    def test_mib_range(self) -> None:
        """Test values in MiB range."""
        assert human_mib(15.5 * 1024 * 1024) == "15.5 MiB"

    def test_large_mib(self) -> None:
        """Test large MiB value."""
        assert human_mib(500 * 1024 * 1024) == "500.0 MiB"

    def test_one_gib(self) -> None:
        """Test exactly 1 GiB."""
        result = human_mib(1024 * 1024 * 1024)
        assert result == "1.00 GiB"

    def test_gib_range(self) -> None:
        """Test values in GiB range."""
        assert human_mib(2.5 * 1024 * 1024 * 1024) == "2.50 GiB"

    def test_fractional_mib(self) -> None:
        """Test fractional MiB values."""
        result = human_mib(1.234 * 1024 * 1024)
        assert "1.2 MiB" in result


class TestHumanSpeedBps:
    """Test human_speed_bps function."""

    def test_zero_speed(self) -> None:
        """Test zero speed."""
        assert human_speed_bps(0) == "-- MB/s"

    def test_negative_speed(self) -> None:
        """Test negative speed."""
        assert human_speed_bps(-100) == "-- MB/s"

    def test_kb_speed(self) -> None:
        """Test speed in KB/s range."""
        result = human_speed_bps(512 * 1024)
        assert "KB/s" in result
        assert "512" in result

    def test_mb_speed(self) -> None:
        """Test speed in MB/s range."""
        result = human_speed_bps(5.2 * 1024 * 1024)
        assert result == "5.2 MB/s"

    def test_large_mb_speed(self) -> None:
        """Test large MB/s speed."""
        result = human_speed_bps(100 * 1024 * 1024)
        assert result == "100.0 MB/s"

    def test_exactly_one_mb(self) -> None:
        """Test exactly 1 MB/s."""
        result = human_speed_bps(1024 * 1024)
        assert result == "1.0 MB/s"

    def test_just_under_one_mb(self) -> None:
        """Test just under 1 MB/s shows KB."""
        result = human_speed_bps(1023 * 1024)
        assert "KB/s" in result


class TestFormatEta:
    """Test format_eta function."""

    def test_zero_seconds(self) -> None:
        """Test zero seconds."""
        assert format_eta(0) == "--:--"

    def test_negative_seconds(self) -> None:
        """Test negative seconds."""
        assert format_eta(-10) == "--:--"

    def test_infinity(self) -> None:
        """Test infinity."""
        assert format_eta(float("inf")) == "--:--"

    def test_seconds_only(self) -> None:
        """Test seconds only (less than 1 minute)."""
        assert format_eta(30) == "30s"
        assert format_eta(59) == "59s"

    def test_minutes_and_seconds(self) -> None:
        """Test minutes and seconds."""
        assert format_eta(90) == "1m 30s"
        assert format_eta(150) == "2m 30s"

    def test_hours_and_minutes(self) -> None:
        """Test hours and minutes."""
        assert format_eta(3600) == "1h 0m"
        assert format_eta(3900) == "1h 5m"
        assert format_eta(7200) == "2h 0m"

    def test_large_hours(self) -> None:
        """Test large hour values."""
        assert format_eta(36000) == "10h 0m"

    def test_one_second(self) -> None:
        """Test exactly 1 second."""
        assert format_eta(1) == "1s"

    def test_one_minute(self) -> None:
        """Test exactly 1 minute."""
        assert format_eta(60) == "1m 0s"


class TestRenderBar:
    """Test render_bar function."""

    def test_zero_total(self) -> None:
        """Test with zero total."""
        result = render_bar(0, 0, width=10)
        assert result == "[          ]"

    def test_negative_total(self) -> None:
        """Test with negative total."""
        result = render_bar(0, -10, width=10)
        assert result == "[          ]"

    def test_empty_progress(self) -> None:
        """Test empty progress bar."""
        result = render_bar(0, 100, width=10)
        assert result == "[          ]"

    def test_partial_progress(self) -> None:
        """Test partial progress."""
        result = render_bar(50, 100, width=10)
        assert ">" in result
        assert "=" in result
        assert " " in result

    def test_full_progress(self) -> None:
        """Test full progress bar."""
        result = render_bar(100, 100, width=10)
        assert result == "[==========]"

    def test_custom_width(self) -> None:
        """Test custom width."""
        result = render_bar(50, 100, width=20)
        assert len(result) == 22  # width + 2 brackets

    def test_small_progress(self) -> None:
        """Test very small progress."""
        result = render_bar(1, 100, width=30)
        assert "[" in result
        assert "]" in result

    def test_over_100_percent(self) -> None:
        """Test progress over 100%."""
        result = render_bar(150, 100, width=10)
        # Should cap at full bar
        assert result == "[==========]"

    def test_default_width(self) -> None:
        """Test default width parameter."""
        result = render_bar(50, 100)
        # Default width is 30
        assert len(result) == 32


class TestTruncateText:
    """Test truncate_text function."""

    def test_text_shorter_than_max(self) -> None:
        """Test text shorter than max length."""
        assert truncate_text("hello", 10) == "hello"

    def test_text_equal_to_max(self) -> None:
        """Test text equal to max length."""
        assert truncate_text("hello", 5) == "hello"

    def test_text_longer_than_max(self) -> None:
        """Test text longer than max length."""
        result = truncate_text("hello world", 8)
        assert result == "hello..."
        assert len(result) == 8

    def test_custom_ellipsis(self) -> None:
        """Test custom ellipsis."""
        result = truncate_text("hello world", 7, ellipsis="…")
        assert result == "hello …"

    def test_max_length_shorter_than_ellipsis(self) -> None:
        """Test max length shorter than ellipsis."""
        result = truncate_text("hello", 2, ellipsis="...")
        assert result == ".."
        assert len(result) == 2

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert truncate_text("", 10) == ""

    def test_unicode_text(self) -> None:
        """Test unicode text."""
        result = truncate_text("Hello 世界 World", 10)
        assert len(result) <= 10

    def test_long_text_truncation(self) -> None:
        """Test long text truncation."""
        long_text = "a" * 100
        result = truncate_text(long_text, 20)
        assert len(result) == 20
        assert result.endswith("...")


class TestFormatPercentage:
    """Test format_percentage function."""

    def test_zero_total(self) -> None:
        """Test with zero total."""
        assert format_percentage(0, 0) == "0%"

    def test_negative_total(self) -> None:
        """Test with negative total."""
        assert format_percentage(0, -10) == "0%"

    def test_zero_percent(self) -> None:
        """Test 0% completion."""
        assert format_percentage(0, 100) == "  0%"

    def test_fifty_percent(self) -> None:
        """Test 50% completion."""
        result = format_percentage(50, 100)
        assert "50%" in result

    def test_one_hundred_percent(self) -> None:
        """Test 100% completion."""
        result = format_percentage(100, 100)
        assert "100%" in result

    def test_over_hundred_percent(self) -> None:
        """Test over 100% (should cap at 100)."""
        result = format_percentage(150, 100)
        assert "100%" in result

    def test_fractional_percentage(self) -> None:
        """Test fractional percentage rounds correctly."""
        result = format_percentage(33, 100)
        assert "33%" in result

    def test_negative_completed(self) -> None:
        """Test negative completed (should show 0%)."""
        result = format_percentage(-10, 100)
        assert "0%" in result

    def test_right_aligned(self) -> None:
        """Test that percentage is right-aligned."""
        result = format_percentage(5, 100)
        # Should be right-aligned with width 4 (including % sign)
        assert len(result) == 4


class TestPadRight:
    """Test pad_right function."""

    def test_pad_short_text(self) -> None:
        """Test padding short text."""
        result = pad_right("hi", 10)
        assert result == "hi        "
        assert len(result) == 10

    def test_no_padding_needed(self) -> None:
        """Test text already at desired width."""
        result = pad_right("hello", 5)
        assert result == "hello"

    def test_text_longer_than_width(self) -> None:
        """Test text longer than width."""
        result = pad_right("hello world", 5)
        assert result == "hello world"

    def test_empty_string(self) -> None:
        """Test empty string."""
        result = pad_right("", 5)
        assert result == "     "


class TestPadLeft:
    """Test pad_left function."""

    def test_pad_short_text(self) -> None:
        """Test padding short text."""
        result = pad_left("hi", 10)
        assert result == "        hi"
        assert len(result) == 10

    def test_no_padding_needed(self) -> None:
        """Test text already at desired width."""
        result = pad_left("hello", 5)
        assert result == "hello"

    def test_text_longer_than_width(self) -> None:
        """Test text longer than width."""
        result = pad_left("hello world", 5)
        assert result == "hello world"

    def test_empty_string(self) -> None:
        """Test empty string."""
        result = pad_left("", 5)
        assert result == "     "


class TestEdgeCases:
    """Test edge cases across multiple functions."""

    def test_human_mib_very_large_value(self) -> None:
        """Test human_mib with very large value."""
        result = human_mib(10 * 1024 * 1024 * 1024)
        assert "GiB" in result

    def test_render_bar_width_one(self) -> None:
        """Test render_bar with width of 1."""
        result = render_bar(50, 100, width=1)
        assert len(result) == 3  # [x]

    def test_format_eta_fractional_seconds(self) -> None:
        """Test format_eta with fractional seconds."""
        result = format_eta(30.7)
        assert result == "30s"

    def test_truncate_text_exact_boundary(self) -> None:
        """Test truncate_text at exact boundary."""
        text = "12345678"
        result = truncate_text(text, 8)
        assert result == text

    def test_format_percentage_precision(self) -> None:
        """Test format_percentage with precision."""
        result = format_percentage(33.333, 100)
        assert "33%" in result
