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


class TestDynamicProgressManager:
    """Tests for the DynamicProgressManager class."""

    @pytest.fixture
    def progress_manager(self) -> DynamicProgressManager[str]:
        """Create a DynamicProgressManager instance for testing.

        Returns:
            DynamicProgressManager: A new progress manager instance
        """
        return DynamicProgressManager()

    def test_init(self, progress_manager: DynamicProgressManager[str]) -> None:
        """Test that the progress manager initializes correctly."""
        # Check initial state
        assert hasattr(progress_manager, "console")
        assert hasattr(progress_manager, "progress")
        assert hasattr(progress_manager, "task_map")
        assert progress_manager.task_map == {}
        assert progress_manager.task_stats == {
            "start_time": None,
            "items": 0,
            "completed": 0,
            "failed": 0,
        }
        assert progress_manager._live is None
        assert progress_manager._layout is None
        assert progress_manager._download_in_progress == {}

    def test_start_progress(self, progress_manager: DynamicProgressManager[str]) -> None:
        """Test starting progress display."""
        with patch.object(Live, "__init__", return_value=None) as mock_live_init, patch.object(
            Live, "start"
        ) as mock_live_start, patch.object(Live, "stop") as mock_live_stop, patch.object(
            Live, "refresh"
        ) as mock_live_refresh:
            # Start progress
            with progress_manager.start_progress(total_items=3, title="Test Progress"):
                # Verify that Live was initialized and started
                mock_live_init.assert_called_once()
                mock_live_start.assert_called_once()

                # Check task stats were initialized
                assert progress_manager.task_stats["items"] == 3
                assert progress_manager.task_stats["start_time"] is not None

                # Check layout was created
                assert progress_manager._layout is not None
                assert "header" in progress_manager._layout.layouts
                assert "progress" in progress_manager._layout.layouts
                assert "footer" in progress_manager._layout.layouts

            # Verify that Live was stopped after the context manager
            mock_live_stop.assert_called_once()
            # Verify the footer was updated with completion info
            mock_live_refresh.assert_called_once()

            # Check task map was reset
            assert progress_manager.task_map == {}
            assert progress_manager._download_in_progress == {}

    def test_add_item(self, progress_manager: DynamicProgressManager[str]) -> None:
        """Test adding an item to track."""
        with patch.object(Progress, "add_task", return_value=123) as mock_add_task:
            # Add an item
            progress_manager.add_item(
                item_id="test_item", name="Test Item", steps=["step1", "step2", "step3"]
            )

            # Verify task was added to progress
            mock_add_task.assert_called_once()
            assert "Test Item" in mock_add_task.call_args[0][0]

            # Verify item was tracked properly
            assert "test_item" in progress_manager.task_map
            assert progress_manager.task_map["test_item"]["name"] == "Test Item"
            assert progress_manager.task_map["test_item"]["task_id"] == 123
            assert progress_manager.task_map["test_item"]["steps"] == ["step1", "step2", "step3"]
            assert progress_manager.task_map["test_item"]["completed_steps"] == set()
            assert progress_manager.task_map["test_item"]["success"] is None

            # Verify download tracking was initialized
            assert "test_item" in progress_manager._download_in_progress
            assert progress_manager._download_in_progress["test_item"] is False

    def test_start_item_step(self, progress_manager: DynamicProgressManager[str]) -> None:
        """Test starting a step for an item."""
        with patch.object(Progress, "add_task", return_value=123) as mock_add_task, patch.object(
            Progress, "update"
        ) as mock_update:
            # Add an item
            progress_manager.add_item(
                item_id="test_item", name="Test Item", steps=["step1", "step2", "step3"]
            )

            # Start a step
            progress_manager.start_item_step(item_id="test_item", step="step1")

            # Verify progress was updated
            mock_update.assert_called_once_with(123, status="[yellow]Working on step1...[/]")

            # Verify internal state update
            assert progress_manager.task_map["test_item"]["current_step"] == "step1"

    def test_update_item_step(self, progress_manager: DynamicProgressManager[str]) -> None:
        """Test updating a step for an item."""
        with patch.object(Progress, "add_task", return_value=123) as mock_add_task, patch.object(
            Progress, "update"
        ) as mock_update:
            # Add an item
            progress_manager.add_item(
                item_id="test_item", name="Test Item", steps=["step1", "step2", "step3"]
            )

            # Update a step (not completed)
            progress_manager.update_item_step(item_id="test_item", step="step1", completed=False)

            # Should not update progress for non-completion
            mock_update.assert_not_called()
            assert "step1" not in progress_manager.task_map["test_item"]["completed_steps"]

            # Update a step (completed)
            progress_manager.update_item_step(item_id="test_item", step="step1", completed=True)

            # Verify progress was updated
            mock_update.assert_called_once()
            assert mock_update.call_args[0][0] == 123  # task_id
            assert mock_update.call_args[1]["completed"] == 1  # 1 step completed
            assert "[green]Completed step1" in mock_update.call_args[1]["status"]

            # Verify internal state update
            assert "step1" in progress_manager.task_map["test_item"]["completed_steps"]

    def test_complete_item(self, progress_manager: DynamicProgressManager[str]) -> None:
        """Test marking an item as completed."""
        with patch.object(Progress, "add_task", return_value=123) as mock_add_task, patch.object(
            Progress, "update"
        ) as mock_update:
            # Add an item
            progress_manager.add_item(
                item_id="test_item", name="Test Item", steps=["step1", "step2", "step3"]
            )

            # Initial stats
            assert progress_manager.task_stats["completed"] == 0
            assert progress_manager.task_stats["failed"] == 0

            # Complete item successfully
            progress_manager.complete_item(item_id="test_item", success=True)

            # Verify progress was updated
            mock_update.assert_called_once()
            assert mock_update.call_args[0][0] == 123  # task_id
            assert mock_update.call_args[1]["completed"] == 3  # All 3 steps marked complete
            assert "[bold green]✓ Success" in mock_update.call_args[1]["status"]

            # Verify internal state update
            assert progress_manager.task_map["test_item"]["success"] is True
            assert progress_manager.task_stats["completed"] == 1
            assert progress_manager.task_stats["failed"] == 0
            assert progress_manager._download_in_progress["test_item"] is False

            # Reset mock
            mock_update.reset_mock()

            # Add another item
            progress_manager.add_item(
                item_id="test_item2", name="Test Item 2", steps=["step1", "step2"]
            )
            mock_add_task.return_value = 456

            # Complete item with failure
            progress_manager.complete_item(item_id="test_item2", success=False)

            # Verify progress was updated
            assert mock_update.call_args[0][0] == 456  # task_id
            assert mock_update.call_args[1]["completed"] == 2  # All steps marked complete
            assert "[bold red]✗ Failed" in mock_update.call_args[1]["status"]

            # Verify internal state update
            assert progress_manager.task_map["test_item2"]["success"] is False
            assert progress_manager.task_stats["completed"] == 1
            assert progress_manager.task_stats["failed"] == 1
            assert progress_manager._download_in_progress["test_item2"] is False

    def test_start_download(self, progress_manager: DynamicProgressManager[str]) -> None:
        """Test starting a download for an item."""
        with patch.object(Progress, "add_task", return_value=123) as mock_add_task, patch.object(
            Progress, "update"
        ) as mock_update:
            # Add an item
            progress_manager.add_item(
                item_id="test_item", name="Test Item", steps=["download", "verify"]
            )

            # Start a download
            task_id = progress_manager.start_download(
                item_id="test_item", filename="test.AppImage", total_size=1024000
            )

            # Verify task was returned
            assert task_id == 123

            # Verify main task was updated
            mock_update.assert_called_once()
            assert mock_update.call_args[0][0] == 123  # main task_id
            assert "[blue]Downloading test.AppImage" in mock_update.call_args[1]["status"]

            # Verify download tracking was updated
            assert progress_manager._download_in_progress["test_item"] is True

    def test_update_download(self, progress_manager: DynamicProgressManager[str]) -> None:
        """Test updating a download for an item."""
        with patch.object(Progress, "add_task", return_value=123) as mock_add_task, patch.object(
            Progress, "update"
        ) as mock_update:
            # Add an item
            progress_manager.add_item(
                item_id="test_item", name="Test Item", steps=["download", "verify"]
            )

            # Start a download
            progress_manager.start_download(
                item_id="test_item", filename="test.AppImage", total_size=1024000
            )

            mock_update.reset_mock()

            # Update download progress
            progress_manager.update_download(
                item_id="test_item",
                filename="test.AppImage",
                advance=102400,  # 100KB
                finished=False,
            )

            # Verify main task was updated
            mock_update.assert_called_once()
            assert mock_update.call_args[0][0] == 123  # main task_id
            assert "[blue]Downloading test.AppImage" in mock_update.call_args[1]["status"]

            mock_update.reset_mock()

            # Complete download
            progress_manager.update_download(
                item_id="test_item", filename="test.AppImage", advance=0, finished=True
            )

            # Verify main task was updated
            mock_update.assert_called_once()
            assert mock_update.call_args[0][0] == 123  # main task_id
            assert "[green]Download completed" in mock_update.call_args[1]["status"]

            # Verify download tracking was updated
            assert progress_manager._download_in_progress["test_item"] is False

    def test_get_summary(self, progress_manager: DynamicProgressManager[str]) -> None:
        """Test generating a summary table."""
        # Add some items with different states
        with patch.object(Progress, "add_task") as mock_add_task:
            mock_add_task.side_effect = [123, 456, 789]

            # Add items
            progress_manager.add_item("item1", "Success Item", ["step1", "step2"])
            progress_manager.add_item("item2", "Failed Item", ["step1", "step2"])
            progress_manager.add_item("item3", "In Progress Item", ["step1", "step2"])

            # Set completion states
            progress_manager.task_map["item1"]["success"] = True
            progress_manager.task_map["item1"]["completed_steps"] = {"step1", "step2"}

            progress_manager.task_map["item2"]["success"] = False
            progress_manager.task_map["item2"]["completed_steps"] = {"step1"}

            # Item 3 stays in progress
            progress_manager.task_map["item3"]["completed_steps"] = {"step1"}

            # Get summary table
            table = progress_manager.get_summary()

            # Check table structure
            assert table.title == "Operation Summary"
            assert len(table.columns) == 3

            # Table contents are harder to verify directly without rendering
            # but we can check the internal task states that would be used
            assert progress_manager.task_map["item1"]["success"] is True
            assert len(progress_manager.task_map["item1"]["completed_steps"]) == 2

            assert progress_manager.task_map["item2"]["success"] is False
            assert len(progress_manager.task_map["item2"]["completed_steps"]) == 1

            assert progress_manager.task_map["item3"]["success"] is None
            assert len(progress_manager.task_map["item3"]["completed_steps"]) == 1
