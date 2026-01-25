from argparse import Namespace
from types import SimpleNamespace

import pytest

from my_unicorn.cli.commands.base import BaseCommandHandler


class DummyHandler(BaseCommandHandler):
    """Concrete subclass for testing BaseCommandHandler."""

    async def execute(self, args: Namespace) -> None:
        self.executed_args = args


@pytest.fixture
def mock_config_manager(monkeypatch):
    called = {"loaded": False, "ensured": False}

    class DummyConfigManager:
        def load_global_config(self):
            called["loaded"] = True
            return {"dirs": {"data": "/tmp/test"}}

        def ensure_directories_from_config(self, config):
            called["ensured"] = True
            called["config"] = config

    return DummyConfigManager(), called


@pytest.fixture
def handler(mock_config_manager):
    config_manager, called = mock_config_manager
    dummy_auth = SimpleNamespace()
    dummy_update = SimpleNamespace()
    h = DummyHandler(config_manager, dummy_auth, dummy_update)
    return h, called


@pytest.mark.asyncio
async def test_execute_implemented(handler):
    h, _ = handler
    args = Namespace(foo="bar")
    await h.execute(args)
    assert h.executed_args.foo == "bar"


def test_global_config_loaded(handler):
    _, called = handler
    assert called["loaded"] is True


def test_ensure_directories(handler):
    h, called = handler
    h._ensure_directories()
    assert called["ensured"] is True
    assert "dirs" in called["config"]
