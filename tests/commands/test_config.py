from argparse import Namespace
from types import SimpleNamespace

import pytest

from my_unicorn.commands.config import ConfigHandler


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
                "batch_mode": True,
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
async def test_execute_show(monkeypatch, handler, capsys):
    h, _ = handler
    args = Namespace(show=True, reset=False)

    await h.execute(args)

    captured = capsys.readouterr()
    assert "📋 Current Configuration:" in captured.out
    assert "Config Version: 1.0" in captured.out
    assert "Max Downloads: 5" in captured.out
    assert "Batch Mode: True" in captured.out
    assert "Log Level: INFO" in captured.out
    assert "/tmp/storage" in captured.out
    assert "/tmp/download" in captured.out


@pytest.mark.asyncio
async def test_execute_reset(monkeypatch, handler, capsys):
    h, called = handler
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

    captured = capsys.readouterr()
    assert "✅ Configuration reset to defaults" in captured.out
    assert called["file_deleted"] is True


@pytest.mark.asyncio
async def test_execute_no_flags(handler, capsys):
    h, called = handler
    args = Namespace(show=False, reset=False)

    # Should not raise or print anything
    await h.execute(args)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "saved" not in called or called["saved"] is False
