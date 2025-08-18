"""Tests for InstallStrategy base class and exceptions."""

from pathlib import Path

import aiohttp
import pytest

from my_unicorn.config import ConfigManager
from my_unicorn.download import DownloadService
from my_unicorn.storage import StorageService
from my_unicorn.strategies.install import (
    InstallationError,
    InstallStrategy,
    ValidationError,
)


class DummyInstallStrategy(InstallStrategy):
    """Minimal concrete subclass for testing."""

    async def install(self, targets: list[str], **kwargs) -> list[dict]:
        return [{"target": t, "status": "installed"} for t in targets]

    def validate_targets(self, targets: list[str]) -> None:
        if not targets:
            raise ValueError("No targets provided")


@pytest.fixture
async def dummy_strategy():
    """Async fixture for DummyInstallStrategy instance."""
    async with aiohttp.ClientSession() as session:
        install_dir = Path("/tmp/unicorn-test-install")
        strategy = DummyInstallStrategy(
            download_service=DownloadService(session),
            storage_service=StorageService(install_dir),
            session=session,
            config_manager=ConfigManager(),
        )
        yield strategy


def test_installation_error_properties():
    """Test InstallationError properties."""
    err = InstallationError("fail", target="app1")
    assert str(err) == "fail"
    assert err.target == "app1"


def test_validation_error_properties():
    """Test ValidationError can be instantiated."""
    err = ValidationError("invalid target")
    assert str(err) == "invalid target"


@pytest.mark.asyncio
async def test_install_success(dummy_strategy):
    """Test DummyInstallStrategy install method."""
    result = await dummy_strategy.install(["app1", "app2"])
    assert result == [
        {"target": "app1", "status": "installed"},
        {"target": "app2", "status": "installed"},
    ]


@pytest.mark.asyncio
async def test_validate_targets_success(dummy_strategy):
    """Test validate_targets with valid input."""
    dummy_strategy.validate_targets(["app1"])


@pytest.mark.asyncio
async def test_validate_targets_failure(dummy_strategy):
    """Test validate_targets raises ValueError for empty targets."""
    with pytest.raises(ValueError):
        dummy_strategy.validate_targets([])
