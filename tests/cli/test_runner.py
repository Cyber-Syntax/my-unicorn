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
    r, executed = cli_runner
    args = SimpleNamespace(command="install", verbose=True)

    called = {"set": False, "restore": False}
    monkeypatch.setattr(
        runner.logger,
        "set_console_level_temporarily",
        lambda level: called.__setitem__("set", True),
    )
    monkeypatch.setattr(
        runner.logger, "restore_console_level", lambda: called.__setitem__("restore", True)
    )

    await r._execute_command(args)

    assert executed["command"] == "install"
    assert called["set"] is True
    assert called["restore"] is True
