"""Tests for URLInstallStrategy: validation and install logic."""

from unittest.mock import MagicMock

import aiohttp
import pytest

from my_unicorn.strategies.install import ValidationError
from my_unicorn.strategies.install_url import URLInstallStrategy


@pytest.fixture
async def url_strategy():
    """Async fixture for URLInstallStrategy with mocked dependencies."""
    github_client = MagicMock()
    config_manager = MagicMock()
    global_config = {"max_concurrent_downloads": 2}
    config_manager.load_global_config.return_value = global_config
    download_service = MagicMock()
    storage_service = MagicMock()
    async with aiohttp.ClientSession() as session:
        strategy = URLInstallStrategy(
            github_client=github_client,
            config_manager=config_manager,
            download_service=download_service,
            storage_service=storage_service,
            session=session,
        )
        yield strategy


def test_validate_targets_valid(url_strategy):
    """Test validate_targets with valid GitHub URLs."""
    url_strategy.validate_targets(
        ["https://github.com/owner/repo", "https://github.com/anotheruser/anotherrepo"]
    )


@pytest.mark.asyncio
async def test_install_success(mocker, url_strategy):
    """Test install returns success for valid URLs."""
    mocker.patch.object(
        url_strategy,
        "_install_single_repo",
        side_effect=lambda sem, url, **kwargs: {
            "target": url,
            "success": True,
            "path": f"/fake/path/{url.split('/')[-1]}.AppImage",
            "name": f"{url.split('/')[-1]}.AppImage",
            "source": "url",
        },
    )
    urls = ["https://github.com/owner/repo", "https://github.com/anotheruser/anotherrepo"]
    result = await url_strategy.install(urls)
    assert all(r["success"] for r in result)
    assert result[0]["target"] == urls[0]
    assert result[1]["target"] == urls[1]


@pytest.mark.asyncio
async def test_install_failure(mocker, url_strategy):
    """Test install returns error for failed install."""

    def fail_install(sem, url, **kwargs):
        raise Exception("Install failed")

    mocker.patch.object(url_strategy, "_install_single_repo", side_effect=fail_install)
    urls = ["https://github.com/owner/repo"]
    result = await url_strategy.install(urls)
    assert not result[0]["success"]
    assert "Install failed" in result[0]["error"]


@pytest.mark.asyncio
async def test_install_mixed_results(mocker, url_strategy):
    """Test install returns mixed success/error for multiple URLs."""

    def mixed_install(sem, url, **kwargs):
        if url == "https://github.com/owner/repo":
            return {
                "target": url,
                "success": True,
                "path": f"/fake/path/{url.split('/')[-1]}.AppImage",
                "name": f"{url.split('/')[-1]}.AppImage",
                "source": "url",
            }
        else:
            raise Exception("Install failed")

    mocker.patch.object(url_strategy, "_install_single_repo", side_effect=mixed_install)
    urls = ["https://github.com/owner/repo", "https://github.com/anotheruser/anotherrepo"]
    result = await url_strategy.install(urls)
    assert result[0]["success"]
    assert not result[1]["success"]
    assert "Install failed" in result[1]["error"]


def test_validate_targets_invalid(url_strategy):
    """Test validate_targets raises ValidationError for invalid URLs."""
    with pytest.raises(ValidationError):
        url_strategy.validate_targets(["not_a_github_url"])


def test_validate_targets_partial_invalid(url_strategy):
    """Test validate_targets raises ValidationError if any target is invalid."""
    with pytest.raises(ValidationError):
        url_strategy.validate_targets(
            ["https://github.com/owner/repo", "ftp://example.com/notgithub"]
        )
