"""Test module for dynamic progress manager functionality.

This module tests the DynamicProgressManager class which provides
multi-level progress tracking for concurrent operations.
"""

import os
import threading
import time
from typing import List, Set, Dict, Any, TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from rich.live import Live
from rich.console import Console

from src.progress_manager import DynamicProgressManager

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


@pytest.fixture(autouse=True)
def cleanup_progress_manager() -> None:
    """Reset the DynamicProgressManager singleton between tests."""
    # Reset before test
    DynamicProgressManager._instance = None

    # Run the test
    yield

    # Reset after test
    if DynamicProgressManager._instance is not None:
        with DynamicProgressManager._instance._lock:
            if DynamicProgressManager._instance._live is not None:
                try:
                    DynamicProgressManager._instance._live.stop()
                except Exception:
                    pass  # Ignore errors in cleanup
            DynamicProgressManager._instance = None


@pytest.fixture
def mock_live(monkeypatch: "MonkeyPatch") -> MagicMock:
    """Mock Rich Live for testing progress rendering.

    Args:
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        MagicMock: Mocked Live instance
    """
    mock = MagicMock(spec=Live)

    # Mock the __enter__ and __exit__ methods
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=None)

    # Patch the Live class constructor
    monkeypatch.setattr("rich.live.Live", MagicMock(return_value=mock))

    return mock


def test_progress_manager_singleton() -> None:
    """Test that DynamicProgressManager maintains a single instance."""
    # Create two instances
    manager1 = DynamicProgressManager[str]()
    manager2 = DynamicProgressManager[str]()

    # Verify they're the same object
    assert manager1 is manager2
    assert id(manager1) == id(manager2)


def test_start_progress_lifecycle(mock_live: MagicMock) -> None:
    """Test the lifecycle of starting and stopping progress tracking.

    Args:
        mock_live: Mocked Rich Live instance
    """
    manager = DynamicProgressManager[str]()

    # Test initial state
    assert manager._live is None
    assert manager._user_count == 0

    # Start progress
    with manager.start_progress(5, "Testing progress"):
        # Check that Live was started
        assert manager._user_count == 1
        assert manager._live is not None
        mock_live.start.assert_called_once()

        # Check overall progress was initialized correctly
        assert manager._overall_progress.tasks[manager._overall_task_id].total == 5

    # Check cleanup after context exit
    assert manager._user_count == 0
    mock_live.stop.assert_called_once()


def test_nested_progress_contexts() -> None:
    """Test that nested progress contexts work correctly."""
    manager = DynamicProgressManager[str]()

    # Create nested contexts
    with manager.start_progress(3, "Outer progress"):
        assert manager._user_count == 1

        with manager.start_progress(2, "Inner progress"):
            assert manager._user_count == 2

            # The inner context shouldn't change the total or reset the display
            assert manager._overall_progress.tasks[manager._overall_task_id].total == 3

        # After inner context exits, outer should still be active
        assert manager._user_count == 1
        assert manager._live is not None

    # After both contexts exit, everything should be cleaned up
    assert manager._user_count == 0
    assert manager._live is None


def test_add_and_complete_item() -> None:
    """Test adding and completing an item in the progress manager."""
    manager = DynamicProgressManager[str]()

    with manager.start_progress(2, "Testing items"):
        # Add an item
        manager.add_item("item1", "Test Item 1", steps=["step1", "step2"])

        # Check that the item was added correctly
        assert "item1" in manager._items
        assert "item1" in manager._active_items
        assert len(manager._completed_items) == 0

        # Complete the item
        manager.complete_item("item1", success=True)

        # Check that the item was marked as completed
        assert "item1" not in manager._active_items
        assert "item1" in manager._completed_items

        # Check the overall progress was updated
        assert manager._overall_progress.tasks[manager._overall_task_id].completed == 1


def test_item_step_tracking() -> None:
    """Test tracking steps for an item."""
    manager = DynamicProgressManager[str]()

    with manager.start_progress(1, "Testing steps"):
        # Add an item with steps
        manager.add_item("item1", "Test Item 1", steps=["step1", "step2", "step3"])

        # Start and complete steps
        step1_id = manager.start_item_step("item1", "step1")
        assert step1_id is not None

        # Update the step progress
        manager.update_item_step("item1", "step1", advance=50)

        # Complete the step
        manager.update_item_step("item1", "step1", completed=True)

        # Check step was marked as completed
        assert "step1" in manager._items["item1"]["completed_steps"]

        # Check item progress was updated (1/3 steps = 33%)
        item_task_id = manager._items["item1"]["current_task_id"]
        item_progress = manager._current_item_progress.tasks[item_task_id].completed
        assert 30 <= item_progress <= 35  # Allow for small rounding differences


def test_download_tracking() -> None:
    """Test tracking downloads for an item."""
    manager = DynamicProgressManager[str]()

    with manager.start_progress(1, "Testing downloads"):
        # Add an item
        manager.add_item("item1", "Test Item 1")

        # Start a download
        download_id = manager.start_download("item1", "test.file", 1000)
        assert download_id is not None

        # Update download progress
        manager.update_download("item1", "test.file", advance=500)

        # Check download progress was updated
        download_task_id = manager._items["item1"]["download_task_ids"]["test.file"]
        download_progress = manager._download_progress.tasks[download_task_id].completed
        assert download_progress == 500

        # Complete the download
        manager.update_download("item1", "test.file", finished=True)

        # Check download was marked as finished (hidden)
        assert not manager._download_progress.tasks[download_task_id].visible


def test_thread_safety(monkeypatch: "MonkeyPatch") -> None:
    """Test thread safety of the progress manager.

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    # Patch Live to avoid actually rendering to the console
    monkeypatch.setattr("rich.live.Live.start", lambda self: None)
    monkeypatch.setattr("rich.live.Live.stop", lambda self: None)

    manager = DynamicProgressManager[str]()

    # Shared variables to track thread execution
    thread_count = 5
    items_per_thread = 2
    successful_operations = 0
    operation_errors = 0
    threads_completed = threading.Event()
    lock = threading.Lock()

    def thread_function(thread_id: int) -> None:
        """Function executed by each thread."""
        nonlocal successful_operations, operation_errors

        try:
            # Each thread adds and completes multiple items
            with manager.start_progress(thread_count * items_per_thread, "Thread test"):
                for i in range(items_per_thread):
                    item_id = f"thread{thread_id}_item{i}"

                    # Add an item
                    manager.add_item(item_id, f"Thread {thread_id} Item {i}")

                    # Start and complete some steps
                    manager.start_item_step(item_id, "step1")
                    manager.update_item_step(item_id, "step1", completed=True)

                    # Start and update a download
                    manager.start_download(item_id, "test.file", 1000)
                    manager.update_download(item_id, "test.file", advance=1000)
                    manager.update_download(item_id, "test.file", finished=True)

                    # Complete the item
                    manager.complete_item(item_id, success=True)

                    # Record successful operation
                    with lock:
                        successful_operations += 1
        except Exception as e:
            # Record error
            with lock:
                operation_errors += 1
                print(f"Thread {thread_id} error: {str(e)}")

    # Create and start threads
    threads = []
    for i in range(thread_count):
        thread = threading.Thread(target=thread_function, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Check results
    assert operation_errors == 0
    assert successful_operations == thread_count * items_per_thread

    # Check that the progress manager state is consistent
    assert len(manager._completed_items) == thread_count * items_per_thread
    assert len(manager._active_items) == 0
