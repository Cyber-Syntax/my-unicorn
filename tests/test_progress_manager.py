import time
import sys
import pytest

from src.progress_manager import (
    BasicMultiAppProgress,
    BasicProgressBar,
    ProgressManager,
    DynamicProgressManager,
)


# Fixtures
@pytest.fixture
def fixed_time(monkeypatch):
    """
    Fixture to monkeypatch time.time() to return a predictable series of values.
    """
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
    """
    Fixture providing a BasicProgressBar with a small total for testing.
    """
    return BasicProgressBar(description="Test", total=4)


@pytest.fixture
def progress_mgr():
    """
    Fixture providing an active ProgressManager with capture of stdout.
    """
    mgr = ProgressManager()
    mgr.start()
    yield mgr
    mgr.stop()


@pytest.fixture
def dynamic_mgr():
    """
    Fixture providing a DynamicProgressManager within a start_progress context.
    """
    mgr = DynamicProgressManager()
    # Enter the context manager manually
    cm = mgr.start_progress(total_items=2, title="UnitTest")
    ctx = cm.__enter__()
    yield ctx
    cm.__exit__(None, None, None)


# Tests for BasicMultiAppProgress


def test_format_size():
    bmp = BasicMultiAppProgress()
    # Bytes
    assert bmp._format_size(0) == "0 B"
    assert bmp._format_size(512) == "512 B"
    # Kilobytes
    assert bmp._format_size(2048) == "2.0 KB"
    # Megabytes
    assert bmp._format_size(5 * 1024 * 1024) == "5.0 MB"


def test_format_speed_and_eta(fixed_time):
    bmp = BasicMultiAppProgress()
    tid = bmp.add_task("dl", total=100)
    # Simulate 50 bytes downloaded after 1s
    bmp.update(tid, completed=50)
    speed = bmp._format_speed(tid)
    assert "MB/s" in speed
    eta = bmp._format_eta(tid)
    assert eta.endswith("s") or "m" in eta


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
