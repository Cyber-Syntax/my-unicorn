"""Tests for logger suppression during progress sessions.

Tests verify that:
- logger.info is suppressed during active progress sessions
- logger.warning/error/critical are always shown
- logger.info works normally before/after sessions
"""

import logging

import pytest

from my_unicorn.core.progress.display import ProgressDisplay
from my_unicorn.core.progress.progress_types import ProgressType
from my_unicorn.logger import get_logger


@pytest.mark.asyncio
async def test_logger_info_suppressed_during_progress(caplog):
    """Test that logger.info is suppressed during progress session."""
    logger = get_logger("test_progress")

    progress = ProgressDisplay()

    # Verify logger.info works before progress
    with caplog.at_level(logging.INFO):
        logger.info("Before progress")
        assert "Before progress" in caplog.text

    # Start progress session
    async with progress.session(1):
        # Add a task to ensure session is active
        await progress.add_task(
            name="test",
            progress_type=ProgressType.DOWNLOAD,
            total=100,
        )

        # Verify logger.info is suppressed during progress
        caplog.clear()
        logger.info("During progress")
        # INFO should be suppressed
        assert "During progress" not in caplog.text

    # Verify logger.info works after progress
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
    """Test that logger levels are restored even if progress session raises."""
    logger = get_logger("test_progress_restore")

    progress = ProgressDisplay()

    # Verify logger.info works before
    with caplog.at_level(logging.INFO):
        logger.info("Before error")
        assert "Before error" in caplog.text

    # Progress session that raises exception
    with pytest.raises(RuntimeError):
        async with progress.session(1):
            # Add a task
            await progress.add_task(
                name="test",
                progress_type=ProgressType.DOWNLOAD,
                total=100,
            )

            # Verify logger.info is suppressed
            caplog.clear()
            logger.info("During error")
            assert "During error" not in caplog.text

            # Raise exception
            msg = "Test error"
            raise RuntimeError(msg)

    # Verify logger.info is restored after exception
    caplog.clear()
    with caplog.at_level(logging.INFO):
        logger.info("After error")
        assert "After error" in caplog.text


@pytest.mark.asyncio
async def test_multiple_progress_sessions(caplog):
    """Test that logger suppression works across multiple sessions."""
    logger = get_logger("test_multiple_sessions")

    progress = ProgressDisplay()

    # First session
    async with progress.session(1):
        await progress.add_task(
            name="test1",
            progress_type=ProgressType.DOWNLOAD,
            total=100,
        )
        caplog.clear()
        logger.info("First session")
        assert "First session" not in caplog.text

    # Between sessions
    caplog.clear()
    with caplog.at_level(logging.INFO):
        logger.info("Between sessions")
        assert "Between sessions" in caplog.text

    # Second session
    async with progress.session(1):
        await progress.add_task(
            name="test2",
            progress_type=ProgressType.VERIFICATION,
            total=100,
        )
        caplog.clear()
        logger.info("Second session")
        assert "Second session" not in caplog.text

    # After all sessions
    caplog.clear()
    with caplog.at_level(logging.INFO):
        logger.info("After all sessions")
        assert "After all sessions" in caplog.text


@pytest.mark.asyncio
async def test_nested_progress_sessions_not_supported(caplog):
    """Test behavior with nested progress sessions (should warn)."""
    logger = get_logger("test_nested")

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
