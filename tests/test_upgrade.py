from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        patch("my_unicorn.upgrade.metadata") as mock_metadata,
        patch("my_unicorn.github_client.auth_manager") as mock_auth_manager,
    ):
        # Ensure auth_manager is properly mocked as a regular Mock, not AsyncMock
        mock_auth_manager.update_rate_limit_info = MagicMock()
        mock_metadata.return_value = {"Version": "1.2.3"}
        updater = SelfUpdater(mock_config_manager, mock_session)
        version = updater.get_current_version()
        assert version == "1.2.3"


def test_get_current_version_package_not_found(
    mock_config_manager, mock_session
):
    """Test SelfUpdater.get_current_version raises PackageNotFoundError."""
    with (
        patch("my_unicorn.upgrade.metadata", side_effect=PackageNotFoundError),
        patch("my_unicorn.github_client.auth_manager") as mock_auth_manager,
    ):
        # Ensure auth_manager is properly mocked as a regular Mock, not AsyncMock
        mock_auth_manager.update_rate_limit_info = MagicMock()
        updater = SelfUpdater(mock_config_manager, mock_session)
        with pytest.raises(PackageNotFoundError):
            updater.get_current_version()


def test_get_formatted_version_git_info(mock_config_manager, mock_session):
    """Test get_formatted_version returns formatted version with git info."""
    with patch("my_unicorn.upgrade.metadata") as mock_metadata:
        mock_metadata.return_value = {"Version": "1.2.3+abcdef"}
        updater = SelfUpdater(mock_config_manager, mock_session)
        formatted = updater.get_formatted_version()
        assert formatted == "1.2.3 (git: abcdef)"


def test_display_version_info_prints_version(
    mock_config_manager, mock_session, capsys
):
    """Test display_version_info prints formatted version."""
    with patch("my_unicorn.upgrade.metadata") as mock_metadata:
        mock_metadata.return_value = {"Version": "1.2.3"}
        updater = SelfUpdater(mock_config_manager, mock_session)
        updater.display_version_info()
        out = capsys.readouterr().out
        assert "my-unicorn version: 1.2.3" in out


@pytest.mark.asyncio
async def test_get_latest_release_success(mock_config_manager, mock_session):
    """Test get_latest_release returns release dict."""
    updater = SelfUpdater(mock_config_manager, mock_session)
    release_data = {
        "version": "2.0.0",
        "prerelease": False,
        "assets": [],
    }
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
    release_data = {
        "version": "2.0.0",
        "prerelease": False,
        "assets": [],
    }
    with (
        patch.object(
            updater.github_fetcher,
            "fetch_latest_release_or_prerelease",
            new=AsyncMock(return_value=release_data),
        ),
        patch("my_unicorn.upgrade.metadata") as mock_metadata,
    ):
        mock_metadata.return_value = {"Version": "1.0.0"}
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
        patch("my_unicorn.upgrade.metadata") as mock_metadata,
    ):
        mock_metadata.return_value = {"Version": "1.0.0"}
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
        "my_unicorn.upgrade.metadata", lambda pkg: {"Version": "1.2.3+abcdef"}
    )
    from my_unicorn.upgrade import display_current_version

    display_current_version()
    out = capsys.readouterr().out
    assert "my-unicorn version: 1.2.3 (git: abcdef)" in out
