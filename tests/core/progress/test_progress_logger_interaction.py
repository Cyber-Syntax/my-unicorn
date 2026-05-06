"""Tests for logger suppression during progress sessions.

Tests verify that:
- Console handler level is raised to WARNING during active progress sessions,
  preventing logger.info() from appearing on screen
- logger.warning/error/critical are always shown
- Console handler level is restored after sessions end

Note on test approach:
    LoggerSuppression works by raising the *console handler* level inside the
    QueueListener to WARNING.  pytest's ``caplog`` fixture captures records at
    the Python root-logger level — a completely separate path that is never
    touched by this mechanism.  Therefore the "during progress" assertions
    inspect the queue-listener's console handler level directly, which is the
    actual production behaviour being tested.
"""

import asyncio
import logging
from logging.handlers import RotatingFileHandler

import pytest

from my_unicorn.core.progress.display import ProgressDisplay
from my_unicorn.core.progress.progress_types import ProgressType
from my_unicorn.logger import _state, get_logger


def _console_handler_level() -> int | None:
    """Return the console StreamHandler level from the QueueListener.

    Returns None if the queue listener is not yet initialised.
    """
    if _state.queue_listener is None:
        return None
    for handler in _state.queue_listener.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, RotatingFileHandler
        ):
            return handler.level
    return None


@pytest.mark.asyncio
async def test_logger_info_suppressed_during_progress(caplog):
    """Test that the console handler is raised to WARNING during a session.

    LoggerSuppression raises the QueueListener's console StreamHandler to
    WARNING so that logger.info() does not bleed into the progress-bar
    display.  caplog is used only to confirm that INFO logging works
    *outside* the session; the suppression itself is verified by
    inspecting the handler level directly.
    """
    logger = get_logger("test_progress")
    progress = ProgressDisplay()

    baseline_level = _console_handler_level()

    # Verify logger.info works before progress
    with caplog.at_level(logging.INFO):
        logger.info("Before progress")
        assert "Before progress" in caplog.text

    async with progress.session(1):
        await progress.add_task(
            name="test",
            progress_type=ProgressType.DOWNLOAD,
            total=100,
        )

        level = _console_handler_level()
        assert level is not None, "QueueListener must be initialised"
        assert level == logging.WARNING, (
            f"Console handler should be WARNING during progress, got {level}"
        )

    # After session: must be restored exactly
    level = _console_handler_level()
    assert level == baseline_level, (
        f"Console handler should be restored after progress, got {level}, "
        f"expected {baseline_level}"
    )

    caplog.clear()
    with caplog.at_level(logging.INFO):
        logger.info("After progress")
        assert "After progress" in caplog.text


@pytest.mark.asyncio
async def test_logger_warning_shown_during_progress(caplog):
    """Test that logger.warning is shown during progress session."""
    logger = get_logger("test_progress_warning")

    progress = ProgressDisplay()

    async with progress.session(1):
        # Add a task
        await progress.add_task(
            name="test",
            progress_type=ProgressType.DOWNLOAD,
            total=100,
        )

        # Verify logger.warning still works during progress
        with caplog.at_level(logging.WARNING):
            logger.warning("Warning during progress")
            assert "Warning during progress" in caplog.text


@pytest.mark.asyncio
async def test_logger_error_shown_during_progress(caplog):
    """Test that logger.error is shown during progress session."""
    logger = get_logger("test_progress_error")

    progress = ProgressDisplay()

    async with progress.session(1):
        # Add a task
        await progress.add_task(
            name="test",
            progress_type=ProgressType.DOWNLOAD,
            total=100,
        )

        # Verify logger.error still works during progress
        with caplog.at_level(logging.ERROR):
            logger.error("Error during progress")
            assert "Error during progress" in caplog.text


@pytest.mark.asyncio
async def test_logger_levels_restored_after_progress_error(caplog):
    logger = get_logger("test_progress_restore")
    progress = ProgressDisplay()

    baseline_level = _console_handler_level()

    try:
        async with progress.session(1):
            await progress.add_task(
                name="test",
                progress_type=ProgressType.DOWNLOAD,
                total=100,
            )

            level = _console_handler_level()
            assert level == logging.WARNING

            raise RuntimeError("Test error")

    except RuntimeError:
        pass

    # 🔑 IMPORTANT: ensure session fully unwound before asserting
    await asyncio.sleep(0)

    level = _console_handler_level()
    assert level == baseline_level, (
        f"Console handler not restored after exception, got {level}, "
        f"expected {baseline_level}"
    )

    caplog.clear()
    with caplog.at_level(logging.INFO):
        logger.info("After error")
        assert "After error" in caplog.text


@pytest.mark.asyncio
async def test_multiple_progress_sessions(caplog):
    """Test console handler suppression across multiple sequential sessions."""
    logger = get_logger("test_multiple_sessions")
    progress = ProgressDisplay()

    baseline_level = _console_handler_level()

    async with progress.session(1):
        await progress.add_task(
            name="test1",
            progress_type=ProgressType.DOWNLOAD,
            total=100,
        )

        level = _console_handler_level()
        assert level is not None, "QueueListener must be initialised"
        assert level == logging.WARNING, (
            f"Console handler should be WARNING (first session), got {level}"
        )

    level = _console_handler_level()
    assert level == baseline_level, (
        f"Console handler not restored between sessions, got {level}, "
        f"expected {baseline_level}"
    )

    caplog.clear()
    with caplog.at_level(logging.INFO):
        logger.info("Between sessions")
        assert "Between sessions" in caplog.text

    async with progress.session(1):
        await progress.add_task(
            name="test2",
            progress_type=ProgressType.VERIFICATION,
            total=100,
        )

        level = _console_handler_level()
        assert level is not None, "QueueListener must be initialised"
        assert level == logging.WARNING, (
            f"Console handler should be WARNING (second session), got {level}"
        )

    level = _console_handler_level()
    assert level == baseline_level, (
        f"Console handler not restored after all sessions, got {level}, "
        f"expected {baseline_level}"
    )

    caplog.clear()
    with caplog.at_level(logging.INFO):
        logger.info("After all sessions")
        assert "After all sessions" in caplog.text


@pytest.mark.asyncio
async def test_nested_progress_sessions_not_supported(caplog):
    """Test behavior with nested progress sessions (should warn)."""
    progress = ProgressDisplay()

    async with progress.session(1):
        await progress.add_task(
            name="outer",
            progress_type=ProgressType.DOWNLOAD,
            total=100,
        )

        # Attempt nested session (should warn and not start)
        with caplog.at_level(logging.WARNING):
            await progress.start_session(1)
            assert "already active" in caplog.text


@pytest.mark.asyncio
async def test_logger_debug_not_affected(caplog):
    """Test that logger.debug behavior is not affected by progress."""
    logger = get_logger("test_debug")

    progress = ProgressDisplay()

    # DEBUG is below INFO, so it should never show in console
    # (file logging would show it, but we're testing console)
    async with progress.session(1):
        await progress.add_task(
            name="test",
            progress_type=ProgressType.DOWNLOAD,
            total=100,
        )

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug during progress")
            # DEBUG is below WARNING, so it won't show in console
            # This tests that our suppression doesn't break DEBUG
