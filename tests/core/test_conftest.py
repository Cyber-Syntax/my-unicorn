"""Tests for core module fixtures in tests/core/conftest.py.

Validates that all shared fixtures are correctly configured for
use across core module tests.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.github import Asset, Release
from tests.core.conftest import MockProgressReporter, async_chunk_gen


@pytest.mark.asyncio
async def test_mock_session_fixture(mock_session: Any) -> None:
    """Test mock_session is AsyncMock for HTTP operations."""
    assert isinstance(mock_session, AsyncMock)


def test_mock_progress_reporter_fixture() -> None:
    """Test MockProgressReporter class exists and works."""
    reporter = MockProgressReporter()
    assert reporter.is_active() is True
    assert isinstance(reporter.tasks, dict)
    assert isinstance(reporter.updates, list)
    assert isinstance(reporter.finished, list)


@pytest.mark.asyncio
async def test_async_chunk_gen_helper() -> None:
    """Test async_chunk_gen helper generates chunks correctly."""
    chunks = [b"hello", b"world"]
    result = [chunk async for chunk in async_chunk_gen(chunks)]
    assert result == chunks


def test_tmp_file_fixture(tmp_file: Any) -> None:
    """Test tmp_file creates valid path."""
    assert isinstance(tmp_file, Path)
    assert tmp_file.parent.exists()


@pytest.mark.asyncio
async def test_mock_progress_reporter_add_task() -> None:
    """Test MockProgressReporter.add_task returns task ID."""
    reporter = MockProgressReporter()
    task_id = await reporter.add_task("test", "download", 100)
    assert task_id.startswith("mock-task-")
    assert task_id in reporter.tasks


@pytest.mark.asyncio
async def test_mock_progress_reporter_update_task() -> None:
    """Test MockProgressReporter.update_task records updates."""
    reporter = MockProgressReporter()
    task_id = await reporter.add_task("test", "download", 100)
    await reporter.update_task(task_id, completed=50, description="halfway")
    assert (task_id, 50, "halfway") in reporter.updates


@pytest.mark.asyncio
async def test_mock_progress_reporter_finish_task() -> None:
    """Test MockProgressReporter.finish_task records completion."""
    reporter = MockProgressReporter()
    task_id = await reporter.add_task("test", "download", 100)
    await reporter.finish_task(task_id, success=True, description="done")
    assert (task_id, True, "done") in reporter.finished


def test_sample_asset_fixture(sample_asset: Any) -> None:
    """Test sample_asset has correct structure."""
    assert isinstance(sample_asset, Asset)
    assert sample_asset.name == "test-app-1.0.0-x86_64.AppImage"
    assert sample_asset.size > 0
    assert sample_asset.digest
    assert sample_asset.browser_download_url


def test_sample_release_fixture(sample_release: Any) -> None:
    """Test sample_release has correct structure."""
    assert isinstance(sample_release, Release)
    assert sample_release.owner == "test-owner"
    assert sample_release.repo == "test-repo"
    assert sample_release.version == "1.0.0"
    assert sample_release.prerelease is False
    assert len(sample_release.assets) > 0
    assert isinstance(sample_release.assets[0], Asset)


def test_mock_download_service_fixture(mock_download_service: Any) -> None:
    """Test mock_download_service is AsyncMock."""
    assert isinstance(mock_download_service, AsyncMock)


def test_mock_file_operations_fixture(mock_file_operations: Any) -> None:
    """Test mock_file_operations is AsyncMock."""
    assert isinstance(mock_file_operations, AsyncMock)


def test_mock_verification_service_fixture(
    mock_verification_service: Any,
) -> None:
    """Test mock_verification_service is AsyncMock."""
    assert isinstance(mock_verification_service, AsyncMock)


def test_mock_backup_service_fixture(mock_backup_service: Any) -> None:
    """Test mock_backup_service is AsyncMock."""
    assert isinstance(mock_backup_service, AsyncMock)


def test_mock_config_manager_fixture(mock_config_manager: Any) -> None:
    """Test mock_config_manager is MagicMock."""
    assert isinstance(mock_config_manager, MagicMock)
