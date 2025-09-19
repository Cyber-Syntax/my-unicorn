"""Tests for the CLI --version flag behavior."""

import subprocess
import sys
from pathlib import Path
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
async def test_version_flag_works_even_with_command_present(monkeypatch, capsys):
    """If version is True and command is also set, version should still take precedence."""
    monkeypatch.setattr(
        "my_unicorn.cli.parser.CLIParser.parse_args",
        lambda self: SimpleNamespace(version=True, command="install"),
    )

    runner = CLIRunner()
    await runner.run()
    captured = capsys.readouterr()
    assert captured.out.strip() == __version__


def test_cli_version_integration_subprocess():
    """Run the entrypoint as a subprocess to verify end-to-end wiring."""
    # Repository root (one parent up from tests/ file)
    repo_root = Path(__file__).resolve().parents[1]

    p = subprocess.run(
        [sys.executable, "run.py", "--version"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )

    assert p.returncode == 0
    assert p.stdout.strip() == __version__
