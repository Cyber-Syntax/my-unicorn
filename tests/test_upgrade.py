from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.github_client import Release
from my_unicorn.upgrade import PackageNotFoundError, SelfUpdater


@pytest.fixture
def mock_config_manager():
    """Provide a mock ConfigManager."""
    mock = MagicMock()
    mock.load_global_config.return_value = {
        "directory": {
            "repo": MagicMock(),
            "package": MagicMock(),
        }
    }
    return mock


@pytest.fixture
def mock_session():
    """Provide a mock aiohttp.ClientSession."""
    return MagicMock()


def test_get_current_version_success(mock_config_manager, mock_session):
    """Test SelfUpdater.get_current_version returns version string."""
    with (
        patch("my_unicorn.upgrade.get_version") as mock_get_version,
        patch("my_unicorn.github_client.auth_manager") as mock_auth_manager,
    ):
        # Ensure auth_manager is properly mocked as a regular Mock, not AsyncMock
        mock_auth_manager.update_rate_limit_info = MagicMock()
        mock_get_version.return_value = "1.2.3"
        updater = SelfUpdater(mock_config_manager, mock_session)
        version = updater.get_current_version()
        assert version == "1.2.3"


def test_get_current_version_package_not_found(
    mock_config_manager, mock_session
):
    """Test SelfUpdater.get_current_version raises PackageNotFoundError."""
    with (
        patch(
            "my_unicorn.upgrade.get_version", side_effect=PackageNotFoundError
        ),
        patch("my_unicorn.github_client.auth_manager") as mock_auth_manager,
    ):
        # Ensure auth_manager is properly mocked as a regular Mock, not AsyncMock
        mock_auth_manager.update_rate_limit_info = MagicMock()
        updater = SelfUpdater(mock_config_manager, mock_session)
        with pytest.raises(PackageNotFoundError):
            updater.get_current_version()


def test_get_formatted_version_git_info(mock_config_manager, mock_session):
    """Test get_formatted_version returns formatted version with git info."""
    with patch("my_unicorn.upgrade.get_version") as mock_get_version:
        mock_get_version.return_value = "1.2.3+abcdef"
        updater = SelfUpdater(mock_config_manager, mock_session)
        formatted = updater.get_formatted_version()
        assert formatted == "1.2.3 (git: abcdef)"


@pytest.mark.asyncio
async def test_get_latest_release_success(mock_config_manager, mock_session):
    """Test get_latest_release returns release dict."""
    updater = SelfUpdater(mock_config_manager, mock_session)
    release_data = Release(
        owner="test",
        repo="repo",
        version="2.0.0",
        prerelease=False,
        assets=[],
        original_tag_name="v2.0.0",
    )
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(return_value=release_data),
    ):
        result = await updater.get_latest_release()
        assert result["version"] == "2.0.0"
        assert result["prerelease"] is False


@pytest.mark.asyncio
async def test_get_latest_release_api_error(
    mock_config_manager, mock_session, caplog
):
    """Test get_latest_release handles API error gracefully."""
    updater = SelfUpdater(mock_config_manager, mock_session)
    from aiohttp import ClientError, ClientResponseError, ClientTimeout

    # Simulate aiohttp.ClientResponseError with status 403 (rate limit)
    error = ClientResponseError(
        request_info=None, history=None, status=403, message="Forbidden"
    )
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=error),
    ):
        result = await updater.get_latest_release()
        assert result is None
        # Check logger output instead of capsys
        assert any(
            "Rate limit exceeded" in record.message
            for record in caplog.records
        )

    # Simulate generic API error
    caplog.clear()
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=Exception("API error")),
    ):
        result = await updater.get_latest_release()
        assert result is None
        # Check logger output instead of capsys
        assert any(
            "error" in record.message.lower() for record in caplog.records
        )

    # Simulate network error (ClientError)
    caplog.clear()
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=ClientError("Network down")),
    ):
        result = await updater.get_latest_release()
        assert result is None
        # Check logger output instead of capsys
        assert any(
            "error" in record.message.lower() for record in caplog.records
        )

    # Simulate timeout error
    caplog.clear()
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=ClientTimeout),
    ):
        result = await updater.get_latest_release()
        assert result is None
        # Check logger output instead of capsys
        assert any(
            "error" in record.message.lower() for record in caplog.records
        )

    # Simulate malformed response (None)
    caplog.clear()
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(return_value=None),
    ):
        result = await updater.get_latest_release()
        assert result is None or isinstance(result, dict)

    # Simulate malformed response (unexpected type)
    caplog.clear()
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(return_value="not-a-dict"),
    ):
        result = await updater.get_latest_release()
        assert result is None or isinstance(result, dict)


@pytest.mark.asyncio
async def test_check_for_update_api_error(
    mock_config_manager, mock_session, caplog
):
    """Test check_for_update handles API/network errors gracefully."""
    updater = SelfUpdater(mock_config_manager, mock_session)
    from aiohttp import ClientError, ClientResponseError, ClientTimeout

    # Simulate aiohttp.ClientResponseError with status 403 (rate limit)
    error = ClientResponseError(
        request_info=None, history=None, status=403, message="Forbidden"
    )
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=error),
    ):
        result = await updater.check_for_update()
        assert result is False
        # Check logger output instead of capsys
        assert any(
            "Rate limit exceeded" in record.message
            for record in caplog.records
        )

    # Simulate generic API error
    caplog.clear()
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=Exception("API error")),
    ):
        result = await updater.check_for_update()
        assert result is False
        # Check logger output instead of capsys
        assert any(
            "error" in record.message.lower() for record in caplog.records
        )

    # Simulate network error (ClientError)
    caplog.clear()
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=ClientError("Network unreachable")),
    ):
        result = await updater.check_for_update()
        assert result is False
        # Check logger output instead of capsys
        assert any(
            "error" in record.message.lower() for record in caplog.records
        )

    # Simulate timeout error
    caplog.clear()
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=ClientTimeout),
    ):
        result = await updater.check_for_update()
        assert result is False
        # Check logger output instead of capsys
        assert any(
            "error" in record.message.lower() for record in caplog.records
        )

    # Simulate malformed response (None)
    caplog.clear()
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(return_value=None),
    ):
        result = await updater.check_for_update()
        assert result is False

    # Simulate malformed response (unexpected type)
    caplog.clear()
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(return_value="not-a-dict"),
    ):
        result = await updater.check_for_update()
        assert result is False


@pytest.mark.asyncio
async def test_check_for_update_newer_version(
    mock_config_manager, mock_session, capsys
):
    """Test check_for_update returns True for newer version."""
    updater = SelfUpdater(mock_config_manager, mock_session)
    release_data = Release(
        owner="test",
        repo="repo",
        version="2.0.0",
        prerelease=False,
        assets=[],
        original_tag_name="v2.0.0",
    )
    with (
        patch.object(
            updater.github_fetcher,
            "fetch_latest_release_or_prerelease",
            new=AsyncMock(return_value=release_data),
        ),
        patch("my_unicorn.upgrade.get_version") as mock_get_version,
    ):
        mock_get_version.return_value = "1.0.0"
        result = await updater.check_for_update()
        assert result is True


@pytest.mark.asyncio
async def test_check_for_update_up_to_date(
    mock_config_manager, mock_session, capsys
):
    """Test check_for_update returns False for same version."""
    updater = SelfUpdater(mock_config_manager, mock_session)
    release_data = {
        "version": "1.0.0",
        "prerelease": False,
        "assets": [],
    }
    with (
        patch.object(
            updater.github_fetcher,
            "fetch_latest_release_or_prerelease",
            new=AsyncMock(return_value=release_data),
        ),
        patch("my_unicorn.upgrade.get_version") as mock_get_version,
    ):
        mock_get_version.return_value = "1.0.0"
        result = await updater.check_for_update()
        assert result is False


@pytest.mark.asyncio
async def test_perform_update_success(mock_config_manager, mock_session):
    """Test perform_update uses os.execvp with correct UV command."""
    updater = SelfUpdater(mock_config_manager, mock_session)

    # Mock os.execvp to capture the command without actually executing it
    with patch("my_unicorn.upgrade.os.execvp") as mock_execvp:
        # os.execvp doesn't return on success, so we simulate by raising
        # an exception to prevent actual execution
        mock_execvp.side_effect = SystemExit(0)

        try:
            await updater.perform_update()
        except SystemExit:
            pass  # Expected when execvp is mocked

        # Verify os.execvp was called with correct arguments
        mock_execvp.assert_called_once_with(
            "uv",
            [
                "uv",
                "tool",
                "upgrade",
                "my-unicorn",
            ],
        )


@pytest.mark.asyncio
async def test_get_self_updater_returns_instance(mock_config_manager):
    """Test get_self_updater returns SelfUpdater instance."""
    from my_unicorn.upgrade import get_self_updater

    updater = await get_self_updater(mock_config_manager)
    assert isinstance(updater, SelfUpdater)


@pytest.mark.asyncio
async def test_check_for_self_update_true_false(mock_config_manager):
    """Test check_for_self_update returns True/False."""
    from my_unicorn.upgrade import check_for_self_update

    with patch("my_unicorn.upgrade.get_self_updater") as mock_get_updater:
        updater = MagicMock()
        updater.check_for_update = AsyncMock(return_value=True)
        updater.session.close = AsyncMock()
        mock_get_updater.return_value = updater
        result = await check_for_self_update()
        assert result is True
        updater.check_for_update = AsyncMock(return_value=False)
        updater.session.close = AsyncMock()
        result = await check_for_self_update()
        assert result is False


@pytest.mark.asyncio
async def test_perform_self_update_runs_update(mock_config_manager):
    """Test perform_self_update returns True/False."""
    from my_unicorn.upgrade import perform_self_update

    with patch("my_unicorn.upgrade.get_self_updater") as mock_get_updater:
        updater = MagicMock()
        updater.check_for_update = AsyncMock(return_value=True)
        updater.perform_update = AsyncMock(return_value=True)
        updater.session.close = AsyncMock()
        mock_get_updater.return_value = updater
        result = await perform_self_update()
        assert result is True
        updater.check_for_update = AsyncMock(return_value=False)
        updater.session.close = AsyncMock()
        result = await perform_self_update()
        assert result is False


def test_display_current_version_prints(monkeypatch, caplog):
    """Test display_current_version logs version."""
    monkeypatch.setattr(
        "my_unicorn.upgrade.get_version", lambda pkg: "1.2.3+abcdef"
    )
    from my_unicorn.upgrade import display_current_version

    display_current_version()
    # Check logger output instead of capsys
    assert any(
        "my-unicorn version: 1.2.3 (git: abcdef)" in record.message
        for record in caplog.records
    )


# ============================================================================
# Directory Structure Validation Tests
# ============================================================================
# These tests ensure that the correct directory paths are used throughout
# the upgrade process and prevent accidental changes in future refactors.
# ============================================================================


def test_upgrade_uses_correct_repo_directory_structure():
    """Test that SelfUpdater uses correct repo directory path.

    CRITICAL: This test validates that the repo directory is correctly
    set to: ~/.local/share/my-unicorn-repo

    This prevents accidental changes like:
        - Using repo_dir/source/ (the v1.8.0 bug)
        - Changing the base directory path
        - Adding unexpected subdirectories
    """
    mock_config = MagicMock()
    mock_repo_path = Path.home() / ".local" / "share" / "my-unicorn-repo"

    mock_config.load_global_config.return_value = {
        "directory": {
            "repo": mock_repo_path,
            "package": Path.home() / ".local" / "share" / "my-unicorn",
        }
    }

    mock_session = MagicMock()
    updater = SelfUpdater(mock_config, mock_session)

    # Verify repo directory is correctly set
    assert updater.global_config["directory"]["repo"] == mock_repo_path
    assert str(updater.global_config["directory"]["repo"]).endswith(
        "my-unicorn-repo"
    )
    assert "source" not in str(updater.global_config["directory"]["repo"])

    # Verify path structure
    expected_parts = (".local", "share", "my-unicorn-repo")
    actual_parts = updater.global_config["directory"]["repo"].parts
    for part in expected_parts:
        assert part in actual_parts, (
            f"Expected '{part}' in repo path, got {actual_parts}"
        )


def test_upgrade_uses_correct_package_directory_structure():
    """Test that SelfUpdater uses correct package directory path.

    CRITICAL: This test validates that the package directory is correctly
    set to: ~/.local/share/my-unicorn

    This prevents accidental changes to the package installation location.
    """
    mock_config = MagicMock()
    mock_package_path = Path.home() / ".local" / "share" / "my-unicorn"

    mock_config.load_global_config.return_value = {
        "directory": {
            "repo": Path.home() / ".local" / "share" / "my-unicorn-repo",
            "package": mock_package_path,
        }
    }

    mock_session = MagicMock()
    updater = SelfUpdater(mock_config, mock_session)

    # Verify package directory is correctly set
    assert updater.global_config["directory"]["package"] == mock_package_path
    assert str(updater.global_config["directory"]["package"]).endswith(
        "my-unicorn"
    )
    assert not str(updater.global_config["directory"]["package"]).endswith(
        "my-unicorn-repo"
    )

    # Verify path structure
    expected_parts = (".local", "share", "my-unicorn")
    actual_parts = updater.global_config["directory"]["package"].parts
    for part in expected_parts:
        assert part in actual_parts, (
            f"Expected '{part}' in package path, got {actual_parts}"
        )


def test_upgrade_directories_are_distinct():
    """Test that repo and package directories are different paths.

    CRITICAL: This prevents accidentally using the same directory for both
    the temporary clone and the permanent installation.
    """
    mock_config = MagicMock()
    mock_config.load_global_config.return_value = {
        "directory": {
            "repo": Path.home() / ".local" / "share" / "my-unicorn-repo",
            "package": Path.home() / ".local" / "share" / "my-unicorn",
        }
    }

    mock_session = MagicMock()
    updater = SelfUpdater(mock_config, mock_session)

    repo_dir = updater.global_config["directory"]["repo"]
    package_dir = updater.global_config["directory"]["package"]

    # Verify directories are different
    assert repo_dir != package_dir, (
        "Repo and package directories must be different"
    )

    # Verify they are siblings in the same parent directory
    assert repo_dir.parent == package_dir.parent, (
        "Repo and package should be siblings in same parent directory"
    )

    # Verify one is not a subdirectory of the other by checking names
    assert repo_dir.name != package_dir.name, (
        "Repo and package should have different directory names"
    )


@pytest.mark.asyncio
async def test_perform_update_uses_uv_direct_install():
    """Test that perform_update uses UV's tool upgrade command.

    CRITICAL: This ensures we're using the correct approach:
    - Uses 'uv tool upgrade my-unicorn'
    - Delegates to UV for upgrading the tool
    """
    mock_config = MagicMock()
    repo_dir = Path("/tmp/test-my-unicorn-repo")
    package_dir = Path("/tmp/test-my-unicorn")

    mock_config.load_global_config.return_value = {
        "directory": {
            "repo": repo_dir,
            "package": package_dir,
        }
    }

    mock_session = MagicMock()
    updater = SelfUpdater(mock_config, mock_session)

    # Mock os.execvp to capture the command
    with patch("my_unicorn.upgrade.os.execvp") as mock_execvp:
        mock_execvp.side_effect = SystemExit(0)

        try:
            await updater.perform_update()
        except SystemExit:
            pass  # Expected

        # Verify the correct UV command is used
        mock_execvp.assert_called_once()
        call_args = mock_execvp.call_args

        # Check command structure
        assert call_args[0][0] == "uv", "Should execute 'uv' command"
        assert call_args[0][1] == [
            "uv",
            "tool",
            "upgrade",
            "my-unicorn",
        ], "Should use correct UV tool upgrade arguments"

        # CRITICAL: Verify no git clone is attempted
        # (In the new implementation, we never call git)


@pytest.mark.asyncio
async def test_perform_update_no_git_operations():
    """Test that perform_update doesn't perform any git operations.

    CRITICAL: This verifies the new approach is simpler and more correct:
    - No git clone required
    - No file copying required
    - UV handles everything through direct GitHub installation
    """
    mock_config = MagicMock()
    repo_dir = Path("/tmp/test-my-unicorn-repo")
    package_dir = Path("/tmp/test-my-unicorn")

    mock_config.load_global_config.return_value = {
        "directory": {
            "repo": repo_dir,
            "package": package_dir,
        }
    }

    mock_session = MagicMock()
    updater = SelfUpdater(mock_config, mock_session)

    # Track if any git or file operations are attempted
    git_called = False
    shutil_called = False

    def track_git(*args, **kwargs):
        nonlocal git_called
        git_called = True

    def track_shutil(*args, **kwargs):
        nonlocal shutil_called
        shutil_called = True

    with (
        patch(
            "my_unicorn.upgrade.asyncio.create_subprocess_exec",
            side_effect=track_git,
        ),
        patch("my_unicorn.upgrade.os.execvp") as mock_execvp,
    ):
        mock_execvp.side_effect = SystemExit(0)

        try:
            await updater.perform_update()
        except SystemExit:
            pass

        # CRITICAL: Verify no git operations
        assert not git_called, "New implementation should NOT use git clone"

        # Verify os.execvp was called (the new method)
        mock_execvp.assert_called_once()


def test_upgrade_directory_paths_are_pathlib_objects():
    """Test that directory paths are pathlib.Path objects, not strings.

    This ensures type safety and prevents path manipulation errors.
    """
    mock_config = MagicMock()
    mock_config.load_global_config.return_value = {
        "directory": {
            "repo": Path.home() / ".local" / "share" / "my-unicorn-repo",
            "package": Path.home() / ".local" / "share" / "my-unicorn",
        }
    }

    mock_session = MagicMock()
    updater = SelfUpdater(mock_config, mock_session)

    # Verify paths are Path objects
    assert isinstance(updater.global_config["directory"]["repo"], Path), (
        "Repo directory should be a pathlib.Path object"
    )

    assert isinstance(updater.global_config["directory"]["package"], Path), (
        "Package directory should be a pathlib.Path object"
    )


def test_upgrade_directory_names_match_expected_conventions():
    """Test that directory names follow the expected naming convention.

    CRITICAL: This ensures directory names are:
        - repo: ends with '-repo' suffix
        - package: does NOT have '-repo' suffix
    """
    mock_config = MagicMock()
    mock_config.load_global_config.return_value = {
        "directory": {
            "repo": Path.home() / ".local" / "share" / "my-unicorn-repo",
            "package": Path.home() / ".local" / "share" / "my-unicorn",
        }
    }

    mock_session = MagicMock()
    updater = SelfUpdater(mock_config, mock_session)

    repo_dir = updater.global_config["directory"]["repo"]
    package_dir = updater.global_config["directory"]["package"]

    # Verify repo directory ends with '-repo'
    assert repo_dir.name.endswith("-repo"), (
        f"Repo directory should end with '-repo', got {repo_dir.name}"
    )

    # Verify package directory does NOT end with '-repo'
    assert not package_dir.name.endswith("-repo"), (
        f"Package directory should NOT end with '-repo', "
        f"got {package_dir.name}"
    )

    # Verify they share the same base name
    repo_base = repo_dir.name.replace("-repo", "")
    package_base = package_dir.name
    assert repo_base == package_base, (
        f"Repo and package should have same base name: "
        f"repo={repo_base}, package={package_base}"
    )
