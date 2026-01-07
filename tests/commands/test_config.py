from argparse import Namespace
from types import SimpleNamespace

import pytest

from my_unicorn.cli.commands.config import ConfigHandler


@pytest.fixture
def mock_config_manager():
    called = {}

    class DummyGlobalConfigManager:
        def __init__(self):
            self.default = {"mock": "default"}
            self.converted = {"mock": "converted"}

        def get_default_global_config(self):
            called["get_default"] = True
            return self.default

        def _convert_to_global_config(self, data):
            called["converted_data"] = data
            called["converted"] = self.converted
            return self.converted

    class DummyDirectoryManager:
        def __init__(self):
            from pathlib import Path

            self.settings_file = Path("/tmp/dummy_settings.conf")

    class DummyConfigManager:
        def __init__(self):
            self.global_config_manager = DummyGlobalConfigManager()
            self.directory_manager = DummyDirectoryManager()
            called["saved"] = False

        def load_global_config(self):
            return {
                "config_version": "1.0",
                "max_concurrent_downloads": 5,
                "log_level": "INFO",
                "directory": {
                    "storage": "/tmp/storage",
                    "download": "/tmp/download",
                    "icon": "/tmp/icon",
                    "backup": "/tmp/backup",
                },
            }

        def save_global_config(self, config):
            called["saved"] = True
            called["saved_config"] = config

    return DummyConfigManager(), called


@pytest.fixture
def handler(mock_config_manager):
    config_manager, called = mock_config_manager
    dummy_auth = SimpleNamespace()
    dummy_update = SimpleNamespace()
    h = ConfigHandler(config_manager, dummy_auth, dummy_update)
    return h, called


@pytest.mark.asyncio
async def test_execute_show(monkeypatch, handler, mocker):
    h, _ = handler
    mock_logger = mocker.patch("my_unicorn.cli.commands.config.logger")
    args = Namespace(show=True, reset=False)

    await h.execute(args)

    mock_logger.info.assert_any_call("📋 Current Configuration:")
    mock_logger.info.assert_any_call("  Config Version: %s", "1.0")
    mock_logger.info.assert_any_call("  Max Downloads: %s", 5)
    mock_logger.info.assert_any_call("  Log Level: %s", "INFO")
    mock_logger.info.assert_any_call("  Storage Dir: %s", "/tmp/storage")
    mock_logger.info.assert_any_call("  Download Dir: %s", "/tmp/download")


@pytest.mark.asyncio
async def test_execute_reset(monkeypatch, handler, mocker):
    h, called = handler
    mock_logger = mocker.patch("my_unicorn.cli.commands.config.logger")
    args = Namespace(show=False, reset=True)

    # Mock file operations using monkeypatch
    def mock_exists(self):
        return True

    def mock_unlink(self):
        called["file_deleted"] = True

    # Patch the Path methods
    monkeypatch.setattr("pathlib.Path.exists", mock_exists)
    monkeypatch.setattr("pathlib.Path.unlink", mock_unlink)

    await h.execute(args)

    mock_logger.info.assert_any_call("✅ Configuration reset to defaults")
    assert called["file_deleted"] is True


@pytest.mark.asyncio
async def test_execute_no_flags(handler, mocker):
    h, called = handler
    mock_logger = mocker.patch("my_unicorn.cli.commands.config.logger")
    args = Namespace(show=False, reset=False)

    # Should not raise or log anything
    await h.execute(args)
    mock_logger.info.assert_not_called()
    assert "saved" not in called or called["saved"] is False
