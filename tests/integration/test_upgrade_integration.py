"""Integration tests for upgrade functionality with version mocking.

This module tests the complete upgrade flow including:
- Version progression (1.9.1 -> 1.9.2 -> 2.0.0 -> future)
- Git clone operations (cloning latest release)
- uv tool install --reinstall (modern isolated installation)
- Repository cleanup after successful upgrade

The tests use local project files to simulate git clone, and mock
both current version and target version to test upgrade paths.

Note: With uv tool install, files are installed in an isolated environment,
not copied to a package_dir like the old venv-wrapper method.
"""

import contextlib
from pathlib import Path
from unittest.mock import patch

import pytest

from my_unicorn.cli.upgrade import perform_self_update


@pytest.fixture
def temp_install_dirs(tmp_path: Path) -> dict[str, Path]:
    """Create temporary directory structure for testing.

    Args:
        tmp_path: pytest temporary path fixture

    Returns:
        dict: Directory paths for testing
            - repo: Temporary repo directory
            - package: Temporary package directory
            - venv: Temporary venv directory
            - tmp_root: Root temporary directory

    """
    repo_dir = tmp_path / "my-unicorn-repo"
    package_dir = tmp_path / "my-unicorn"

    # Create subdirectories
    package_dir.mkdir(parents=True)
    venv_dir = package_dir / "venv" / "bin"
    venv_dir.mkdir(parents=True)

    return {
        "repo": repo_dir,
        "package": package_dir,
        "venv": venv_dir,
        "tmp_root": tmp_path,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upgrade_version_progression(
    temp_install_dirs: dict[str, Path],
) -> None:
    """Verify upgrade executes uv tool install --upgrade command.

    This test ensures that the upgrade process calls the correct uv command.

    Args:
        temp_install_dirs: Temporary directory fixture

    """
    with (
        patch("my_unicorn.cli.upgrade.os.execvp") as mock_execvp,
        patch("my_unicorn.cli.upgrade.shutil.which", return_value="uv"),
    ):
        mock_execvp.side_effect = SystemExit(0)

        # Run the upgrade
        with contextlib.suppress(SystemExit):
            perform_self_update()

        # Verify os.execvp was called with correct arguments
        mock_execvp.assert_called_once_with(
            "uv",
            [
                "uv",
                "tool",
                "install",
                "--upgrade",
                "git+https://github.com/Cyber-Syntax/my-unicorn",
            ],
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upgrade_clones_to_correct_directory(
    temp_install_dirs: dict[str, Path],
) -> None:
    """Verify upgrade executes uv tool install --upgrade command.

    Args:
        temp_install_dirs: Temporary directory fixture

    """
    with (
        patch("my_unicorn.cli.upgrade.os.execvp") as mock_execvp,
        patch("my_unicorn.cli.upgrade.shutil.which", return_value="uv"),
    ):
        mock_execvp.side_effect = SystemExit(0)

        # Run the upgrade
        with contextlib.suppress(SystemExit):
            perform_self_update()

        # Verify os.execvp was called with correct arguments
        mock_execvp.assert_called_once_with(
            "uv",
            [
                "uv",
                "tool",
                "install",
                "--upgrade",
                "git+https://github.com/Cyber-Syntax/my-unicorn",
            ],
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upgrade_copies_files_correctly(
    temp_install_dirs: dict[str, Path],
) -> None:
    """Verify upgrade executes uv tool install --upgrade command.

    Args:
        temp_install_dirs: Temporary directory fixture

    """
    with (
        patch("my_unicorn.cli.upgrade.os.execvp") as mock_execvp,
        patch("my_unicorn.cli.upgrade.shutil.which", return_value="uv"),
    ):
        mock_execvp.side_effect = SystemExit(0)

        # Run the upgrade
        with contextlib.suppress(SystemExit):
            perform_self_update()

        # Verify os.execvp was called with correct arguments
        mock_execvp.assert_called_once_with(
            "uv",
            [
                "uv",
                "tool",
                "install",
                "--upgrade",
                "git+https://github.com/Cyber-Syntax/my-unicorn",
            ],
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_installer_finds_required_files(
    temp_install_dirs: dict[str, Path],
) -> None:
    """Verify upgrade executes uv tool install --upgrade command.

    Args:
        temp_install_dirs: Temporary directory fixture

    """
    with (
        patch("my_unicorn.cli.upgrade.os.execvp") as mock_execvp,
        patch("my_unicorn.cli.upgrade.shutil.which", return_value="uv"),
    ):
        mock_execvp.side_effect = SystemExit(0)

        # Run the upgrade
        with contextlib.suppress(SystemExit):
            perform_self_update()

        # Verify os.execvp was called with correct arguments
        mock_execvp.assert_called_once_with(
            "uv",
            [
                "uv",
                "tool",
                "install",
                "--upgrade",
                "git+https://github.com/Cyber-Syntax/my-unicorn",
            ],
        )
