"""Unit tests for URL-based installation module.

This module tests validate_and_fetch_release() and install_from_url()
functions with URL parsing, validation, and install workflow.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.core.install.url import (
    install_from_url,
    validate_and_fetch_release,
)
from my_unicorn.exceptions import InstallationError, VerificationError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def valid_github_url() -> str:
    """Provide a valid GitHub URL."""
    return "https://github.com/pbek/QOwnNotes"


@pytest.fixture
def invalid_github_url() -> str:
    """Provide an invalid GitHub URL."""
    return "https://github.com/invalid"


# =============================================================================
# validate_and_fetch_release() Tests
# =============================================================================


@pytest.mark.asyncio
async def test_validate_and_fetch_release_success(
    sample_asset: Asset,
    sample_release: Release,
) -> None:
    """Test validate_and_fetch_release with valid owner/repo.

    Verifies successful validation and release fetching with AppImage asset.
    """
    # Arrange
    owner = "pbek"
    repo = "QOwnNotes"
    mock_fetch_release = AsyncMock(return_value=sample_release)

    # Act
    release, asset = await validate_and_fetch_release(
        owner, repo, fetch_release_fn=mock_fetch_release
    )

    # Assert
    assert release == sample_release
    assert asset == sample_asset
    mock_fetch_release.assert_called_once_with(owner, repo)


@pytest.mark.asyncio
async def test_validate_and_fetch_release_invalid_identifiers() -> None:
    """Test validate_and_fetch_release with invalid identifiers.

    Verifies that validation fails for invalid GitHub identifiers
    (e.g., missing owner or repo).
    """
    # Arrange
    owner = "invalid-owner-with-invalid-chars!@#"
    repo = "invalid-repo-!@#"
    mock_fetch_release = AsyncMock()

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid GitHub owner"):
        await validate_and_fetch_release(
            owner, repo, fetch_release_fn=mock_fetch_release
        )


@pytest.mark.asyncio
async def test_validate_and_fetch_release_no_appimage(
    sample_release: Release,
) -> None:
    """Test validate_and_fetch_release when no AppImage found.

    Verifies error when release has no suitable AppImage asset
    (filters unstable for URL installs).
    """
    # Arrange
    owner = "pbek"
    repo = "QOwnNotes"
    # Create release with no AppImage assets
    non_appimage_release = Release(
        owner=owner,
        repo=repo,
        version="1.0.0",
        prerelease=False,
        assets=[],
        original_tag_name="v1.0.0",
    )
    mock_fetch_release = AsyncMock(return_value=non_appimage_release)

    # Act & Assert
    with pytest.raises(InstallationError):
        await validate_and_fetch_release(
            owner, repo, fetch_release_fn=mock_fetch_release
        )


@pytest.mark.asyncio
async def test_validate_and_fetch_release_api_failure() -> None:
    """Test validate_and_fetch_release with GitHub API error.

    Verifies proper propagation of GitHub API client errors.
    """
    # Arrange
    owner = "pbek"
    repo = "QOwnNotes"
    mock_fetch_release = AsyncMock(side_effect=Exception("GitHub API error"))

    # Act & Assert
    with pytest.raises(Exception, match="GitHub API error"):
        await validate_and_fetch_release(
            owner, repo, fetch_release_fn=mock_fetch_release
        )


# =============================================================================
# install_from_url() Tests
# =============================================================================


@pytest.mark.asyncio
async def test_install_from_url_success(  # noqa: PLR0913
    valid_github_url: str,
    sample_asset: Asset,
    sample_release: Release,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
    sample_install_result_success: dict[str, Any],
) -> None:
    """Test install_from_url with full success path.

    Verifies complete workflow from URL parsing through successful
    installation with all dependencies working correctly.
    """
    # Arrange
    mock_fetch_release = AsyncMock(return_value=sample_release)
    mock_install_workflow = AsyncMock(
        return_value=sample_install_result_success
    )

    with patch("my_unicorn.core.install.url.parse_github_url") as mock_parse:
        mock_parse.return_value = {
            "owner": "pbek",
            "repo": "QOwnNotes",
            "app_name": "qownnotes",
            "prerelease": False,
        }

        with patch(
            "my_unicorn.core.install.url.get_github_config"
        ) as mock_get_config:
            mock_get_config.return_value = None

            with patch(
                "my_unicorn.core.install.url.select_best_appimage_asset"
            ) as mock_select:
                mock_select.return_value = sample_asset

                with patch(
                    "my_unicorn.core.install.url.build_url_install_config"
                ) as mock_build_config:
                    mock_build_config.return_value = {
                        "config_version": "2.0.0",
                        "source": {
                            "owner": "pbek",
                            "repo": "QOwnNotes",
                        },
                    }

                    # Act
                    result = await install_from_url(
                        valid_github_url,
                        mock_download_service,
                        MagicMock(),  # github_client
                        mock_post_download_processor,
                        fetch_release_fn=mock_fetch_release,
                        install_workflow_fn=mock_install_workflow,
                    )

    # Assert
    assert result["success"] is True
    assert result["app_name"] == "qownnotes"
    mock_fetch_release.assert_called_once()
    mock_install_workflow.assert_called_once()


@pytest.mark.asyncio
async def test_install_from_url_invalid_format() -> None:
    """Test install_from_url with invalid URL format.

    Verifies proper error handling when URL parsing fails.
    """
    # Arrange
    invalid_url = "not-a-github-url"
    mock_download_service = AsyncMock()
    mock_post_download_processor = AsyncMock()
    mock_fetch_release = AsyncMock()
    mock_install_workflow = AsyncMock()

    with patch("my_unicorn.core.install.url.parse_github_url") as mock_parse:
        mock_parse.side_effect = ValueError("Invalid URL format")

        # Act
        result = await install_from_url(
            invalid_url,
            mock_download_service,
            MagicMock(),  # github_client
            mock_post_download_processor,
            fetch_release_fn=mock_fetch_release,
            install_workflow_fn=mock_install_workflow,
        )

    # Assert
    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_install_from_url_validation_failure(
    valid_github_url: str,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test install_from_url when validate_and_fetch_release fails.

    Verifies error handling when release validation or asset selection fails.
    """
    # Arrange
    mock_fetch_release = AsyncMock()
    mock_install_workflow = AsyncMock()

    with patch("my_unicorn.core.install.url.parse_github_url") as mock_parse:
        mock_parse.return_value = {
            "owner": "pbek",
            "repo": "QOwnNotes",
            "app_name": "qownnotes",
            "prerelease": False,
        }

        with patch(
            "my_unicorn.core.install.url.get_github_config"
        ) as mock_get_config:
            mock_get_config.return_value = None

            with patch(
                "my_unicorn.core.install.url.select_best_appimage_asset"
            ) as mock_select:
                mock_select.return_value = None  # No AppImage found

                # Act
                result = await install_from_url(
                    valid_github_url,
                    mock_download_service,
                    MagicMock(),  # github_client
                    mock_post_download_processor,
                    fetch_release_fn=mock_fetch_release,
                    install_workflow_fn=mock_install_workflow,
                )

    # Assert
    assert result["success"] is False
    assert "error" in result
    mock_install_workflow.assert_not_called()


@pytest.mark.asyncio
async def test_install_from_url_installation_error(
    valid_github_url: str,
    sample_asset: Asset,
    sample_release: Release,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test install_from_url with InstallationError from workflow.

    Verifies proper error handling and result formatting when
    the install workflow raises InstallationError.
    """
    # Arrange
    error_message = "Installation failed: disk full"
    mock_fetch_release = AsyncMock(return_value=sample_release)
    mock_install_workflow = AsyncMock(
        side_effect=InstallationError(error_message)
    )

    with patch("my_unicorn.core.install.url.parse_github_url") as mock_parse:
        mock_parse.return_value = {
            "owner": "pbek",
            "repo": "QOwnNotes",
            "app_name": "qownnotes",
            "prerelease": False,
        }

        with (
            patch("my_unicorn.core.install.url.get_github_config"),
            patch(
                "my_unicorn.core.install.url.select_best_appimage_asset"
            ) as mock_select,
        ):
            mock_select.return_value = sample_asset

            with patch(
                "my_unicorn.core.install.url.build_url_install_config"
            ) as mock_build_config:
                mock_build_config.return_value = {}

                # Act
                result = await install_from_url(
                    valid_github_url,
                    mock_download_service,
                    MagicMock(),  # github_client
                    mock_post_download_processor,
                    fetch_release_fn=mock_fetch_release,
                    install_workflow_fn=mock_install_workflow,
                )

    # Assert
    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_install_from_url_verification_error(
    valid_github_url: str,
    sample_asset: Asset,
    sample_release: Release,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test install_from_url with VerificationError from workflow.

    Verifies proper error handling and result formatting when
    the install workflow raises VerificationError.
    """
    # Arrange
    error_message = "SHA256 checksum mismatch"
    mock_fetch_release = AsyncMock(return_value=sample_release)
    mock_install_workflow = AsyncMock(
        side_effect=VerificationError(error_message)
    )

    with patch("my_unicorn.core.install.url.parse_github_url") as mock_parse:
        mock_parse.return_value = {
            "owner": "pbek",
            "repo": "QOwnNotes",
            "app_name": "qownnotes",
            "prerelease": False,
        }

        with (
            patch("my_unicorn.core.install.url.get_github_config"),
            patch(
                "my_unicorn.core.install.url.select_best_appimage_asset"
            ) as mock_select,
        ):
            mock_select.return_value = sample_asset

            with patch(
                "my_unicorn.core.install.url.build_url_install_config"
            ) as mock_build_config:
                mock_build_config.return_value = {}

                # Act
                result = await install_from_url(
                    valid_github_url,
                    mock_download_service,
                    MagicMock(),  # github_client
                    mock_post_download_processor,
                    fetch_release_fn=mock_fetch_release,
                    install_workflow_fn=mock_install_workflow,
                )

    # Assert
    assert result["success"] is False
    assert "error" in result
