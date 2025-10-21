"""Integration tests for upgrade functionality with version mocking.

This module tests the complete upgrade flow including:
- Directory structure (verify no source/ subdirectory bug)
- Version progression (1.9.1 -> 1.9.2 -> 2.0.0 -> future)
- File operations (copy from correct source to destination)
- Installer execution (setup.sh can find required files)

The tests use local project files to simulate git clone, and mock
both current version and target version to test upgrade paths.
"""

import re
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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


async def mock_git_clone_with_version(
    _source_dir: Path | None, dest_dir: Path, target_version: str
) -> None:
    """Simulate git clone by copying from actual project with version override.

    Args:
        _source_dir: Source directory (unused, we use project root)
        dest_dir: Destination directory for cloned repo
        target_version: Version to simulate in the cloned code

    """
    # Get the actual project root
    project_root = Path(__file__).parent.parent.parent

    # Copy the entire project (simulating git clone)
    # Note: dest_dir might already exist (created by upgrade.py)
    # so we use dirs_exist_ok=True
    shutil.copytree(
        project_root,
        dest_dir,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", "*.pyc", ".pytest_cache"
        ),
        dirs_exist_ok=True,
    )

    # Modify pyproject.toml to reflect the target version
    # This simulates checking out a specific release tag
    pyproject_path = dest_dir / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text()
        # Update version in pyproject.toml
        content = re.sub(
            r'version = "[^"]+"', f'version = "{target_version}"', content
        )
        pyproject_path.write_text(content)


@pytest.fixture
def mock_git_subprocess():
    """Mock asyncio.create_subprocess_exec for git clone operations.

    Returns:
        callable: Async function that mocks subprocess execution

    """

    async def _mock_subprocess(*args, **kwargs):
        """Mock subprocess that simulates git clone.

        Args:
            *args: Command arguments
            **kwargs: Additional keyword arguments

        Returns:
            AsyncMock: Mocked process with success exit code

        """
        # Extract the destination directory from git clone command
        # Command format: ['git', 'clone', '--depth', '1', url, dest_dir]
        if len(args) > 0 and args[0] == "git" and "clone" in args:
            dest_dir = Path(args[-1])  # Last argument is destination

            # Get target version from kwargs (passed from test)
            target_version = kwargs.pop("_target_version", "1.9.2")

            await mock_git_clone_with_version(None, dest_dir, target_version)

            # Return a mock process with successful exit code
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.stdout = AsyncMock()
            mock_process.stdout.readline = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock(return_value=0)
            return mock_process

        # For other subprocess calls (like setup.sh), return success
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.pid = 12345
        return mock_process

    return _mock_subprocess


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_version,new_version",
    [
        ("1.9.1", "1.9.2"),  # Test immediate next version
        ("1.9.2", "2.0.0"),  # Test major version upgrade
        ("2.0.0", "2.1.0"),  # Test future minor upgrade
    ],
)
async def test_upgrade_version_progression(
    temp_install_dirs, mock_git_subprocess, current_version, new_version
):
    """Verify upgrade works for version progression paths.

    This test ensures that:
    1. Users on v1.9.1 can upgrade to v1.9.2
    2. Users on v1.9.2 can upgrade to v2.0.0
    3. The fix continues to work for future versions

    Args:
        temp_install_dirs: Temporary directory fixture
        mock_git_subprocess: Mock subprocess fixture
        current_version: Current installed version
        new_version: Version to upgrade to

    """
    with (
        patch(
            "asyncio.create_subprocess_exec", side_effect=mock_git_subprocess
        ),
        patch("my_unicorn.upgrade.metadata") as mock_metadata,
        patch.object(SelfUpdater, "get_latest_release") as mock_get_release,
    ):
        # Mock current installed version
        mock_metadata.return_value = {"Version": current_version}

        # Mock latest release version
        mock_get_release.return_value = {
            "tag_name": f"v{new_version}",
            "version": new_version,
            "prerelease": False,
        }

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
        result = await updater.perform_update()

        # CRITICAL ASSERTIONS: Verify directory structure
        repo_dir = temp_install_dirs["repo"]
        package_dir = temp_install_dirs["package"]

        # 1. Verify NO source/ subdirectory exists (the bug we fixed)
        assert not (repo_dir / "source").exists(), (
            f"Bug regression: 'source/' subdirectory should not exist "
            f"in {repo_dir}"
        )

        # 2. Verify files copied to correct location in package_dir
        assert (package_dir / "my_unicorn").exists(), (
            f"my_unicorn/ should exist in {package_dir}"
        )
        assert (package_dir / "setup.sh").exists(), (
            f"setup.sh should exist in {package_dir}"
        )
        assert (package_dir / "scripts").exists(), (
            f"scripts/ should exist in {package_dir}"
        )

        # 3. Verify upgrade succeeded
        assert result is True, (
            f"Upgrade from {current_version} to {new_version} should succeed"
        )


@pytest.mark.asyncio
async def test_upgrade_clones_to_correct_directory(
    temp_install_dirs, mock_git_subprocess
):
    """Verify upgrade clones directly to repo_dir, not repo_dir/source/.

    This is the core test for the directory structure bug fix.

    Args:
        temp_install_dirs: Temporary directory fixture
        mock_git_subprocess: Mock subprocess fixture

    """
    with (
        patch(
            "asyncio.create_subprocess_exec", side_effect=mock_git_subprocess
        ),
        patch("my_unicorn.upgrade.metadata") as mock_metadata,
        patch.object(SelfUpdater, "get_latest_release") as mock_get_release,
    ):
        # Mock current version
        mock_metadata.return_value = {"Version": "1.9.1"}

        # Mock latest release
        mock_get_release.return_value = {
            "tag_name": "v1.9.2",
            "version": "1.9.2",
            "prerelease": False,
        }

        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {
                "repo": temp_install_dirs["repo"],
                "package": temp_install_dirs["package"],
            }
        }

        session = MagicMock()
        updater = SelfUpdater(config_manager, session)

        # Run perform_update()
        result = await updater.perform_update()

        # Assert upgrade succeeded
        assert result is True, "Upgrade should succeed"

        # After successful upgrade, repo_dir is cleaned up
        # So we verify files were copied to package_dir correctly
        package_dir = temp_install_dirs["package"]

        # CRITICAL: Verify files copied to package_dir
        # This proves they were sourced from repo_dir/my_unicorn
        # (NOT repo_dir/source/my_unicorn which would have failed)
        assert (package_dir / "my_unicorn").exists(), (
            "my_unicorn should be copied to package_dir"
        )

        # Verify setup.sh was copied
        assert (package_dir / "setup.sh").exists(), (
            "setup.sh should be copied to package_dir"
        )

        # Verify scripts directory was copied
        assert (package_dir / "scripts").exists(), (
            "scripts should be copied to package_dir"
        )

        # CRITICAL: The fact that these files exist in package_dir proves
        # they were successfully copied from repo_dir/my_unicorn
        # If the bug existed (repo_dir/source/my_unicorn), the copy would fail


@pytest.mark.asyncio
async def test_upgrade_copies_files_correctly(
    temp_install_dirs, mock_git_subprocess
):
    """Verify files are copied from repo_dir to package_dir.

    Args:
        temp_install_dirs: Temporary directory fixture
        mock_git_subprocess: Mock subprocess fixture

    """
    with (
        patch(
            "asyncio.create_subprocess_exec", side_effect=mock_git_subprocess
        ),
        patch("my_unicorn.upgrade.metadata") as mock_metadata,
        patch.object(SelfUpdater, "get_latest_release") as mock_get_release,
    ):
        mock_metadata.return_value = {"Version": "1.9.1"}
        mock_get_release.return_value = {
            "tag_name": "v1.9.2",
            "version": "1.9.2",
            "prerelease": False,
        }

        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {
                "repo": temp_install_dirs["repo"],
                "package": temp_install_dirs["package"],
            }
        }

        session = MagicMock()
        updater = SelfUpdater(config_manager, session)

        # Run perform_update()
        await updater.perform_update()

        package_dir = temp_install_dirs["package"]

        # Verify all required files exist in package_dir
        assert (package_dir / "my_unicorn").is_dir(), (
            "my_unicorn/ directory should exist"
        )
        assert (package_dir / "setup.sh").is_file(), (
            "setup.sh file should exist"
        )
        assert (package_dir / "scripts").is_dir(), (
            "scripts/ directory should exist"
        )
        assert (package_dir / "pyproject.toml").is_file(), (
            "pyproject.toml file should exist"
        )


@pytest.mark.asyncio
async def test_installer_finds_required_files(
    temp_install_dirs, mock_git_subprocess
):
    """Verify setup.sh can find all required files after upgrade.

    Args:
        temp_install_dirs: Temporary directory fixture
        mock_git_subprocess: Mock subprocess fixture

    """
    with (
        patch(
            "asyncio.create_subprocess_exec", side_effect=mock_git_subprocess
        ),
        patch("my_unicorn.upgrade.metadata") as mock_metadata,
        patch.object(SelfUpdater, "get_latest_release") as mock_get_release,
    ):
        mock_metadata.return_value = {"Version": "1.9.1"}
        mock_get_release.return_value = {
            "tag_name": "v1.9.2",
            "version": "1.9.2",
            "prerelease": False,
        }

        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {
                "repo": temp_install_dirs["repo"],
                "package": temp_install_dirs["package"],
            }
        }

        session = MagicMock()
        updater = SelfUpdater(config_manager, session)

        # Run perform_update()
        await updater.perform_update()

        package_dir = temp_install_dirs["package"]

        # Verify setup.sh can find all files it needs
        # (These are the files setup.sh looks for)
        required_files = [
            "my_unicorn",  # Source code directory
            "scripts",  # Wrapper scripts
            "pyproject.toml",  # Package configuration
        ]

        for file_name in required_files:
            file_path = package_dir / file_name
            assert file_path.exists(), (
                f"setup.sh requires {file_name} but it's missing"
            )
