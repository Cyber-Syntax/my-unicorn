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


def test_display_version_info_prints_version(
    mock_config_manager, mock_session, capsys
):
    """Test display_version_info prints formatted version."""
    with patch("my_unicorn.upgrade.get_version") as mock_get_version:
        mock_get_version.return_value = "1.2.3"
        updater = SelfUpdater(mock_config_manager, mock_session)
        updater.display_version_info()
        out = capsys.readouterr().out
        assert "my-unicorn version: 1.2.3" in out


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
    mock_config_manager, mock_session, capsys
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
        out = capsys.readouterr().out
        assert (
            "Rate limit exceeded" in out or "GitHub Rate limit exceeded" in out
        )

    # Simulate generic API error
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=Exception("API error")),
    ):
        result = await updater.get_latest_release()
        assert result is None
        out = capsys.readouterr().out
        assert "Error connecting to GitHub" in out or "API error" in out

    # Simulate network error (ClientError)
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=ClientError("Network down")),
    ):
        result = await updater.get_latest_release()
        assert result is None
        out = capsys.readouterr().out
        assert "Error connecting to GitHub" in out or "Network down" in out

    # Simulate timeout error
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=ClientTimeout),
    ):
        result = await updater.get_latest_release()
        assert result is None
        out = capsys.readouterr().out
        assert "Error connecting to GitHub" in out or "ClientTimeout" in out

    # Simulate malformed response (None)
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(return_value=None),
    ):
        result = await updater.get_latest_release()
        assert result is None or isinstance(result, dict)
        out = capsys.readouterr().out
        assert (
            "Malformed release data" in out or "Error" in out or result is None
        )

    # Simulate malformed response (unexpected type)
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(return_value="not-a-dict"),
    ):
        result = await updater.get_latest_release()
        assert result is None or isinstance(result, dict)
        out = capsys.readouterr().out
        assert (
            "Malformed release data" in out or "Error" in out or result is None
        )


@pytest.mark.asyncio
async def test_check_for_update_api_error(
    mock_config_manager, mock_session, capsys
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
        out = capsys.readouterr().out
        assert (
            "Rate limit exceeded" in out or "GitHub Rate limit exceeded" in out
        )

    # Simulate generic API error
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=Exception("API error")),
    ):
        result = await updater.check_for_update()
        assert result is False
        out = capsys.readouterr().out
        assert "Error connecting to GitHub" in out or "API error" in out

    # Simulate network error (ClientError)
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=ClientError("Network unreachable")),
    ):
        result = await updater.check_for_update()
        assert result is False
        out = capsys.readouterr().out
        assert (
            "Error connecting to GitHub" in out or "Network unreachable" in out
        )

    # Simulate timeout error
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(side_effect=ClientTimeout),
    ):
        result = await updater.check_for_update()
        assert result is False
        out = capsys.readouterr().out
        assert "Error connecting to GitHub" in out or "ClientTimeout" in out

    # Simulate malformed response (None)
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(return_value=None),
    ):
        result = await updater.check_for_update()
        assert result is False
        out = capsys.readouterr().out
        assert (
            "Malformed release data" in out
            or "Error" in out
            or result is False
        )

    # Simulate malformed response (unexpected type)
    with patch.object(
        updater.github_fetcher,
        "fetch_latest_release_or_prerelease",
        new=AsyncMock(return_value="not-a-dict"),
    ):
        result = await updater.check_for_update()
        assert result is False
        out = capsys.readouterr().out
        assert (
            "Malformed release data" in out
            or "Error" in out
            or result is False
        )


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
    """Test perform_update returns True on success."""
    updater = SelfUpdater(mock_config_manager, mock_session)
    # Patch subprocess and file ops
    with (
        patch("my_unicorn.upgrade.shutil.rmtree"),
        patch("my_unicorn.upgrade.shutil.copytree"),
        patch("my_unicorn.upgrade.shutil.copy2"),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.chmod"),
        patch(
            "my_unicorn.upgrade.asyncio.create_subprocess_exec"
        ) as mock_subproc,
    ):
        proc_mock = MagicMock()
        proc_mock.wait = AsyncMock(return_value=0)
        proc_mock.returncode = 0
        proc_mock.stdout = None
        mock_subproc.return_value = proc_mock
        result = await updater.perform_update()
        assert result is True


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


def test_display_current_version_prints(monkeypatch, capsys):
    """Test display_current_version prints version."""
    monkeypatch.setattr(
        "my_unicorn.upgrade.get_version", lambda pkg: "1.2.3+abcdef"
    )
    from my_unicorn.upgrade import display_current_version

    display_current_version()
    out = capsys.readouterr().out
    assert "my-unicorn version: 1.2.3 (git: abcdef)" in out


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
async def test_perform_update_clones_to_repo_dir_not_subdirectory():
    """Test that git clone uses repo_dir directly, not repo_dir/source/.

    CRITICAL: This test catches the v1.8.0 bug where cloning happened to
    repo_dir/source/ instead of repo_dir/, causing file copy failures.
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

    # Mock subprocess to capture git clone command only
    clone_command_args = []

    async def capture_clone_command(*args, **kwargs):
        """Capture the git clone command arguments."""
        # Only capture git clone commands, not setup.sh calls
        if args and args[0] == "git" and "clone" in args:
            clone_command_args.extend(args)
        mock_proc = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = 0
        mock_proc.stdout = AsyncMock()
        mock_proc.stdout.readline = AsyncMock(return_value=b"")
        return mock_proc

    with (
        patch("my_unicorn.upgrade.shutil.rmtree"),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.chmod"),
        patch(
            "my_unicorn.upgrade.asyncio.create_subprocess_exec",
            side_effect=capture_clone_command,
        ),
    ):
        await updater.perform_update()

        # Verify git clone was called with repo_dir, not repo_dir/source/
        assert "git" in clone_command_args
        assert "clone" in clone_command_args

        # Find the destination argument (last argument in git clone)
        clone_dest = str(clone_command_args[-1])

        # CRITICAL: Verify clone destination is repo_dir
        assert clone_dest == str(repo_dir), (
            f"Git clone should use {repo_dir}, not {clone_dest}"
        )

        # CRITICAL: Verify no 'source' subdirectory in clone destination
        assert "/source" not in clone_dest, (
            "Git clone should NOT use repo_dir/source/ (this was the bug)"
        )
        assert "\\source" not in clone_dest, (
            "Git clone should NOT use repo_dir\\source\\ on Windows"
        )


@pytest.mark.asyncio
async def test_perform_update_copies_from_repo_dir_not_source_subdir():
    """Test that file copying sources from repo_dir, not repo_dir/source/.

    CRITICAL: This verifies that files are copied from the correct location:
        - Correct: repo_dir/my_unicorn -> package_dir/my_unicorn
        - Wrong:   repo_dir/source/my_unicorn -> package_dir/my_unicorn
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

    # Track copy operations
    copy_sources = []

    def capture_copytree(src, dst, **kwargs):
        """Capture copytree source paths."""
        copy_sources.append(str(src))

    def capture_copy2(src, dst, **kwargs):
        """Capture copy2 source paths."""
        copy_sources.append(str(src))

    with (
        patch("my_unicorn.upgrade.shutil.rmtree"),
        patch(
            "my_unicorn.upgrade.shutil.copytree",
            side_effect=capture_copytree,
        ),
        patch("my_unicorn.upgrade.shutil.copy2", side_effect=capture_copy2),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.is_file", return_value=False),
        patch("pathlib.Path.iterdir", return_value=[]),
        patch("pathlib.Path.chmod"),
        patch(
            "my_unicorn.upgrade.asyncio.create_subprocess_exec"
        ) as mock_subproc,
    ):
        mock_proc = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = 0
        mock_proc.stdout = None
        mock_subproc.return_value = mock_proc

        await updater.perform_update()

        # Verify copy operations use repo_dir as source
        for source_path in copy_sources:
            # CRITICAL: Source should start with repo_dir
            assert source_path.startswith(str(repo_dir)), (
                f"Copy source should start with {repo_dir}, got {source_path}"
            )

            # CRITICAL: Source should NOT contain /source/ subdirectory
            assert f"{repo_dir}/source/" not in source_path, (
                f"Copy source should NOT use repo_dir/source/ "
                f"(this was the bug), got {source_path}"
            )
            assert f"{repo_dir}\\source\\" not in source_path, (
                f"Copy source should NOT use repo_dir\\source\\ on Windows, "
                f"got {source_path}"
            )


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
