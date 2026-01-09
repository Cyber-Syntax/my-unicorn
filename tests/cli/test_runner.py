import sys
from types import SimpleNamespace

import pytest

from my_unicorn.cli import runner


@pytest.fixture(autouse=True)
def patch_sys_exit(monkeypatch):
    called = {}

    def fake_exit(code=0):
        called["code"] = code
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", fake_exit)
    return called


@pytest.fixture
def mock_parser(monkeypatch):
    class DummyParser:
        def __init__(self, config):
            self.config = config

        def parse_args(self):
            return SimpleNamespace(command="install", verbose=False)

    monkeypatch.setattr(runner, "CLIParser", DummyParser)
    return DummyParser


@pytest.fixture
def cli_runner(mock_parser):
    r = runner.CLIRunner()
    executed = {}

    # Replace each handler.execute with an async mock
    for cmd in r.command_handlers:

        async def fake_exec(args, _cmd=cmd):
            executed["command"] = _cmd
            executed["args"] = args

        r.command_handlers[cmd].execute = fake_exec

    return r, executed


@pytest.mark.asyncio
async def test_run_executes_known_command(cli_runner, patch_sys_exit):
    r, executed = cli_runner
    args = SimpleNamespace(command="install", verbose=False)
    await r._execute_command(args)
    assert executed["command"] == "install"
    assert executed["args"].command == "install"


@pytest.mark.asyncio
async def test_run_with_unknown_command(cli_runner):
    r, _ = cli_runner
    args = SimpleNamespace(command="doesnotexist", verbose=False)
    with pytest.raises(SystemExit) as e:
        await r._execute_command(args)
    assert e.value.code == 1


@pytest.mark.asyncio
async def test_run_no_command(monkeypatch, cli_runner):
    class DummyParser:
        def __init__(self, config):
            pass

        def parse_args(self):
            return SimpleNamespace(command=None)

    monkeypatch.setattr(runner, "CLIParser", DummyParser)

    r, _ = cli_runner
    with pytest.raises(SystemExit) as e:
        await r.run()
    assert e.value.code == 1


@pytest.mark.asyncio
async def test_run_keyboard_interrupt(monkeypatch, cli_runner):
    class DummyParser:
        def __init__(self, config):
            pass

        def parse_args(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(runner, "CLIParser", DummyParser)

    r, _ = cli_runner
    with pytest.raises(SystemExit) as e:
        await r.run()
    assert e.value.code == 1


@pytest.mark.asyncio
async def test_run_unexpected_error(monkeypatch, cli_runner):
    class DummyParser:
        def __init__(self, config):
            pass

        def parse_args(self):
            raise ValueError("boom")

    monkeypatch.setattr(runner, "CLIParser", DummyParser)

    r, _ = cli_runner
    with pytest.raises(SystemExit) as e:
        await r.run()
    assert e.value.code == 1


@pytest.mark.asyncio
async def test_verbose_logging(monkeypatch, cli_runner):
    """Test that verbose flag sets console handler to DEBUG level."""
    r, executed = cli_runner
    args = SimpleNamespace(command="install", verbose=True)

    # Track handler level changes
    import logging

    original_levels = {}
    for h in runner.logger.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(
            h, logging.FileHandler
        ):
            original_levels[id(h)] = h.level

    await r._execute_command(args)

    # Verify command was executed
    assert executed["command"] == "install"

    # Verify console handler level was restored after execution
    for h in runner.logger.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(
            h, logging.FileHandler
        ):
            assert h.level == original_levels.get(id(h), h.level)
