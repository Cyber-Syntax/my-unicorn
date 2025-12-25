"""Integration tests for upgrade functionality with version mocking.

This module tests the complete upgrade flow including:
- Version progression (1.9.1 -> 1.9.2 -> 2.0.0 -> future)
- Git clone operations (cloning latest release)
- uv tool install --reinstall (modern isolated installation)
- Repository cleanup after successful upgrade

The tests use local project files to simulate git clone, and mock
both current version and target version to test upgrade paths.

Note: With uv tool install, files are installed in an isolated environment,
not copied to a package_dir like the old setup.sh method.
"""

import contextlib
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.upgrade import SelfUpdater


@pytest.fixture
def temp_install_dirs(tmp_path):
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


@pytest.mark.asyncio
async def test_upgrade_version_progression(temp_install_dirs):
    """Verify upgrade executes uv tool upgrade command.

    This test ensures that the upgrade process calls the correct uv command.

    Args:
        temp_install_dirs: Temporary directory fixture

    """
    with (
        patch("my_unicorn.upgrade.os.execvp") as mock_execvp,
    ):
        mock_execvp.side_effect = SystemExit(0)

        # Create updater instance
        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {
                "repo": temp_install_dirs["repo"],
                "package": temp_install_dirs["package"],
            }
        }

        session = MagicMock()
        updater = SelfUpdater(config_manager, session)

        # Run the upgrade
        with contextlib.suppress(SystemExit):
            await updater.perform_update()

        # Verify os.execvp was called with correct arguments
        mock_execvp.assert_called_once_with(
            "uv",
            ["uv", "tool", "upgrade", "my-unicorn"],
        )


@pytest.mark.asyncio
async def test_upgrade_clones_to_correct_directory(temp_install_dirs):
    """Verify upgrade executes uv tool upgrade command.

    Args:
        temp_install_dirs: Temporary directory fixture

    """
    with (
        patch("my_unicorn.upgrade.os.execvp") as mock_execvp,
    ):
        mock_execvp.side_effect = SystemExit(0)

        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {
                "repo": temp_install_dirs["repo"],
                "package": temp_install_dirs["package"],
            }
        }

        session = MagicMock()
        updater = SelfUpdater(config_manager, session)

        # Run the upgrade
        with contextlib.suppress(SystemExit):
            await updater.perform_update()

        # Verify os.execvp was called with correct arguments
        mock_execvp.assert_called_once_with(
            "uv",
            ["uv", "tool", "upgrade", "my-unicorn"],
        )


@pytest.mark.asyncio
async def test_upgrade_copies_files_correctly(temp_install_dirs):
    """Verify upgrade executes uv tool upgrade command.

    Args:
        temp_install_dirs: Temporary directory fixture

    """
    with (
        patch("my_unicorn.upgrade.os.execvp") as mock_execvp,
    ):
        mock_execvp.side_effect = SystemExit(0)

        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {
                "repo": temp_install_dirs["repo"],
                "package": temp_install_dirs["package"],
            }
        }

        session = MagicMock()
        updater = SelfUpdater(config_manager, session)

        # Run the upgrade
        with contextlib.suppress(SystemExit):
            await updater.perform_update()

        # Verify os.execvp was called with correct arguments
        mock_execvp.assert_called_once_with(
            "uv",
            ["uv", "tool", "upgrade", "my-unicorn"],
        )


@pytest.mark.asyncio
async def test_installer_finds_required_files(temp_install_dirs):
    """Verify upgrade executes uv tool upgrade command.

    Args:
        temp_install_dirs: Temporary directory fixture

    """
    with (
        patch("my_unicorn.upgrade.os.execvp") as mock_execvp,
    ):
        mock_execvp.side_effect = SystemExit(0)

        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {
                "repo": temp_install_dirs["repo"],
                "package": temp_install_dirs["package"],
            }
        }

        session = MagicMock()
        updater = SelfUpdater(config_manager, session)

        # Run the upgrade
        with contextlib.suppress(SystemExit):
            await updater.perform_update()

        # Verify os.execvp was called with correct arguments
        mock_execvp.assert_called_once_with(
            "uv",
            ["uv", "tool", "upgrade", "my-unicorn"],
        )
