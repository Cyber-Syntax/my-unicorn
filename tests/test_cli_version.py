"""Tests for the CLI --version flag behavior."""

from types import SimpleNamespace

import pytest

from my_unicorn import __version__
from my_unicorn.cli.runner import CLIRunner


@pytest.mark.asyncio
async def test_version_flag_prints_version_and_exits(monkeypatch, capsys):
    """When --version is passed, the CLI should print the package version and return early."""
    monkeypatch.setattr(
        "my_unicorn.cli.parser.CLIParser.parse_args",
        lambda self: SimpleNamespace(version=True),
    )

    runner = CLIRunner()
    await runner.run()
    captured = capsys.readouterr()
    assert captured.out.strip() == __version__


@pytest.mark.asyncio
async def test_version_flag_works_even_with_command_present(
    monkeypatch, capsys
):
    """If version is True and command is also set, version should still take precedence."""
    monkeypatch.setattr(
        "my_unicorn.cli.parser.CLIParser.parse_args",
        lambda self: SimpleNamespace(version=True, command="install"),
    )

    runner = CLIRunner()
    await runner.run()
    captured = capsys.readouterr()
    assert captured.out.strip() == __version__
