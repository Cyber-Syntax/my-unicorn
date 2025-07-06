import time

import pytest

from my_unicorn.progress import AppImageProgressMeter, format_number
from my_unicorn.progress_manager import (
    BasicProgressBar,
    DynamicProgressManager,
    ProgressManager,
)


# Fixtures
@pytest.fixture
def fixed_time(monkeypatch):
    """Fixture to monkeypatch time.time() to return a predictable series of values."""
    # Create a mutable list to act as a counter
    times = [1000.0]

    def fake_time():
        # Each call increments time by 1 second
        current = times[0]
        times[0] += 1.0
        return current

    monkeypatch.setattr(time, "time", fake_time)
    return fake_time


@pytest.fixture
def basic_bar():
    """Fixture providing a BasicProgressBar with a small total for testing."""
    return BasicProgressBar(description="Test", total=4)


@pytest.fixture
def progress_mgr():
    """Fixture providing an active ProgressManager with capture of stdout."""
    mgr = ProgressManager()
    mgr.start()
    yield mgr
    mgr.stop()


@pytest.fixture
def dynamic_mgr():
    """Fixture providing a DynamicProgressManager within a start_progress context."""
    mgr = DynamicProgressManager()
    # Enter the context manager manually
    cm = mgr.start_progress(total_items=2, title="UnitTest")
    ctx = cm.__enter__()
    yield ctx
    cm.__exit__(None, None, None)


# Tests for AppImageProgressMeter


def test_format_number():
    # Bytes
    assert format_number(0) == "0 B"
    assert format_number(512) == "512 B"
    # Kilobytes
    assert format_number(2048) == "2.0 KB"
    # Megabytes
    assert format_number(5 * 1024 * 1024) == "5.0 MB"


def test_progress_meter_basic():
    import io

    # Use StringIO to capture output instead of stderr
    output = io.StringIO()
    meter = AppImageProgressMeter(fo=output)

    # Test basic functionality
    meter.start(2)

    # Add downloads
    download1 = meter.add_download("dl1", "test1.AppImage", 1000, "[1/2] ")
    download2 = meter.add_download("dl2", "test2.AppImage", 2000, "[2/2] ")

    # Update progress
    meter.update_progress("dl1", 500)
    meter.update_progress("dl2", 1000)

    # Complete downloads
    meter.complete_download("dl1", success=True)
    meter.complete_download("dl2", success=True)

    # Stop meter
    meter.stop()

    # Verify downloads were tracked
    assert len(meter.downloads) == 2
    assert meter.completed_downloads == 2
    assert meter.downloads["dl1"]["status"] == "completed"
    assert meter.downloads["dl2"]["status"] == "completed"


def test_progress_meter_failed_download():
    import io

    output = io.StringIO()
    meter = AppImageProgressMeter(fo=output)

    meter.start(1)
    meter.add_download("fail1", "failed.AppImage", 1000, "[1/1] ")
    meter.complete_download("fail1", success=False, error_msg="Network error")
    meter.stop()

    assert meter.downloads["fail1"]["status"] == "failed"
    assert meter.downloads["fail1"]["error"] == "Network error"


# Tests for BasicProgressBar


def test_basic_progress_bar_render(basic_bar, fixed_time):
    # Initially 0/4
    out = basic_bar.render()
    assert "0.0%" in out and "(0/4)" in out

    # Advance by 2
    basic_bar.update(advance=2, status="Halfway")
    out2 = basic_bar.render()
    assert "50.0%" in out2
    assert "Halfway" in out2


# Tests for ProgressManager


def test_progress_manager_add_update_remove(progress_mgr, capsys):
    # Add two tasks
    t1 = progress_mgr.add_task("A", total=2)
    t2 = progress_mgr.add_task("B", total=3)

    # Update tasks
    progress_mgr.update(t1, advance=1)
    progress_mgr.update(t2, completed=3)

    # Render and capture
    progress_mgr.render()
    captured = capsys.readouterr().out
    assert "A:" in captured and "50.0%" in captured
    assert "B:" in captured and "100.0%" in captured

    # Remove a task and ensure no errors
    progress_mgr.remove_task(t1)
    progress_mgr.render()
    # Should only contain B
    captured2 = capsys.readouterr().out
    assert "A:" not in captured2 and "B:" in captured2


# Tests for DynamicProgressManager


def test_dynamic_progress_manager_lifecycle(dynamic_mgr, capsys):
    mgr = dynamic_mgr
    # Add two items with two steps each
    mgr.add_item("item1", "Item1", steps=["s1", "s2"])
    mgr.add_item("item2", "Item2", steps=["s1", "s2"])

    # Start and complete steps
    mgr.start_item_step("item1", "s1")
    mgr.update_item_step("item1", "s1", completed=True)
    mgr.complete_item("item1", success=True)

    # Second item fails
    mgr.start_item_step("item2", "s1")
    mgr.update_item_step("item2", "s1", completed=True)
    mgr.complete_item("item2", success=False)

    # Exit context to print summary
    # Summary should report 1 success, 1 failed
    summary = mgr.get_summary()
    assert "Success" in summary
    assert "Failed" in summary
    assert "1/2" in summary
