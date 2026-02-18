"""Unit tests for catalog-based installation module.

This module tests install_from_catalog() and build_url_install_config()
functions with catalog loading, asset selection, and error scenarios.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.core.install.catalog import (
    build_url_install_config,
    install_from_catalog,
)
from my_unicorn.exceptions import InstallationError

# =============================================================================
# install_from_catalog() Tests
# =============================================================================


@pytest.mark.asyncio
async def test_install_from_catalog_success(  # noqa: PLR0913
    sample_asset: Asset,
    sample_release: Release,
    sample_catalog_entry: dict[str, Any],
    mock_config_manager: MagicMock,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
    sample_install_result_success: dict[str, Any],
) -> None:
    """Test successful installation from catalog.

    Verifies the full success path from catalog entry to installation
    result, including catalog loading, asset selection, and workflow
    execution.
    """
    # Arrange
    app_name = "qownnotes"
    mock_config_manager.load_catalog.return_value = sample_catalog_entry
    mock_fetch_release = AsyncMock(return_value=sample_release)
    mock_install_workflow = AsyncMock(
        return_value=sample_install_result_success
    )

    with (
        patch(
            "my_unicorn.core.install.catalog.get_github_config"
        ) as mock_get_config,
        patch(
            "my_unicorn.core.install.catalog.select_best_appimage_asset"
        ) as mock_select_asset,
    ):
        mock_get_config.return_value = MagicMock(
            owner="pbek", repo="QOwnNotes"
        )
        mock_select_asset.return_value = sample_asset

        # Act
        result = await install_from_catalog(
            app_name,
            mock_config_manager,
            mock_download_service,
            mock_post_download_processor,
            fetch_release_fn=mock_fetch_release,
            install_workflow_fn=mock_install_workflow,
        )

    # Assert
    assert result["success"] is True
    assert result["app_name"] == "qownnotes"
    mock_config_manager.load_catalog.assert_called_once_with(app_name)
    mock_fetch_release.assert_called_once_with("pbek", "QOwnNotes")
    mock_install_workflow.assert_called_once()


@pytest.mark.asyncio
async def test_install_from_catalog_app_not_found(
    mock_config_manager: MagicMock,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test installation fails when app not found in catalog.

    Verifies that FileNotFoundError from missing catalog entry is
    properly handled and wrapped in error result.
    """
    # Arrange
    app_name = "nonexistent-app"
    mock_config_manager.load_catalog.side_effect = FileNotFoundError(
        f"Catalog entry not found: {app_name}"
    )
    mock_fetch_release = AsyncMock()
    mock_install_workflow = AsyncMock()

    # Act
    result = await install_from_catalog(
        app_name,
        mock_config_manager,
        mock_download_service,
        mock_post_download_processor,
        fetch_release_fn=mock_fetch_release,
        install_workflow_fn=mock_install_workflow,
    )

    # Assert
    assert result["success"] is False
    assert result["target"] == app_name
    assert result["name"] == app_name
    assert result["source"] == "catalog"
    assert "error" in result
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_install_from_catalog_invalid_github_config(
    sample_catalog_entry: dict[str, Any],
    mock_config_manager: MagicMock,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test installation fails with invalid GitHub configuration.

    Verifies that missing or incomplete GitHub config (owner/repo)
    raises ValueError that is properly converted to error result.
    """
    # Arrange
    app_name = "qownnotes"
    mock_config_manager.load_catalog.return_value = sample_catalog_entry
    mock_fetch_release = AsyncMock()
    mock_install_workflow = AsyncMock()

    with patch(
        "my_unicorn.core.install.catalog.get_github_config"
    ) as mock_get_config:
        mock_get_config.side_effect = ValueError(
            "Missing required GitHub configuration: owner"
        )

        # Act
        result = await install_from_catalog(
            app_name,
            mock_config_manager,
            mock_download_service,
            mock_post_download_processor,
            fetch_release_fn=mock_fetch_release,
            install_workflow_fn=mock_install_workflow,
        )

    # Assert
    assert result["success"] is False
    assert result["target"] == app_name
    assert result["name"] == app_name
    assert result["source"] == "catalog"
    assert "error" in result


@pytest.mark.asyncio
async def test_install_from_catalog_no_appimage_asset(
    sample_release: Release,
    sample_catalog_entry: dict[str, Any],
    mock_config_manager: MagicMock,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test installation fails when no suitable AppImage asset found.

    Verifies that ERROR_NO_APPIMAGE_ASSET is properly raised and
    formatted in error result when asset selection fails.
    """
    # Arrange
    app_name = "qownnotes"
    mock_config_manager.load_catalog.return_value = sample_catalog_entry
    mock_fetch_release = AsyncMock(return_value=sample_release)
    mock_install_workflow = AsyncMock()

    with (
        patch(
            "my_unicorn.core.install.catalog.get_github_config"
        ) as mock_get_config,
        patch(
            "my_unicorn.core.install.catalog.select_best_appimage_asset"
        ) as mock_select_asset,
    ):
        mock_get_config.return_value = MagicMock(
            owner="pbek", repo="QOwnNotes"
        )
        mock_select_asset.return_value = None

        # Act
        result = await install_from_catalog(
            app_name,
            mock_config_manager,
            mock_download_service,
            mock_post_download_processor,
            fetch_release_fn=mock_fetch_release,
            install_workflow_fn=mock_install_workflow,
        )

    # Assert
    assert result["success"] is False
    assert result["target"] == app_name
    assert result["name"] == app_name
    assert result["source"] == "catalog"
    assert "error" in result
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_install_from_catalog_release_fetch_failure(
    sample_catalog_entry: dict[str, Any],
    mock_config_manager: MagicMock,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test installation fails when GitHub API fetch fails.

    Verifies proper error handling for network/API failures during
    release fetching, including aiohttp exceptions.
    """
    # Arrange
    app_name = "qownnotes"
    mock_config_manager.load_catalog.return_value = sample_catalog_entry
    mock_fetch_release = AsyncMock(
        side_effect=RuntimeError("Network error: Connection timeout")
    )
    mock_install_workflow = AsyncMock()

    with patch(
        "my_unicorn.core.install.catalog.get_github_config"
    ) as mock_get_config:
        mock_get_config.return_value = MagicMock(
            owner="pbek", repo="QOwnNotes"
        )

        # Act
        result = await install_from_catalog(
            app_name,
            mock_config_manager,
            mock_download_service,
            mock_post_download_processor,
            fetch_release_fn=mock_fetch_release,
            install_workflow_fn=mock_install_workflow,
        )

    # Assert
    assert result["success"] is False
    assert result["target"] == app_name
    assert result["source"] == "catalog"
    assert "error" in result


@pytest.mark.asyncio
async def test_install_from_catalog_installation_error(  # noqa: PLR0913
    sample_asset: Asset,
    sample_release: Release,
    sample_catalog_entry: dict[str, Any],
    mock_config_manager: MagicMock,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test proper handling of InstallationError from workflow.

    Verifies that InstallationError exceptions from the install
    workflow are caught and converted to error result dicts.
    """
    # Arrange
    app_name = "qownnotes"
    mock_config_manager.load_catalog.return_value = sample_catalog_entry
    mock_fetch_release = AsyncMock(return_value=sample_release)
    mock_install_workflow = AsyncMock(
        side_effect=InstallationError(
            "Failed to verify downloaded file: SHA256 mismatch"
        )
    )

    with (
        patch(
            "my_unicorn.core.install.catalog.get_github_config"
        ) as mock_get_config,
        patch(
            "my_unicorn.core.install.catalog.select_best_appimage_asset"
        ) as mock_select_asset,
    ):
        mock_get_config.return_value = MagicMock(
            owner="pbek", repo="QOwnNotes"
        )
        mock_select_asset.return_value = sample_asset

        # Act
        result = await install_from_catalog(
            app_name,
            mock_config_manager,
            mock_download_service,
            mock_post_download_processor,
            fetch_release_fn=mock_fetch_release,
            install_workflow_fn=mock_install_workflow,
        )

    # Assert
    assert result["success"] is False
    assert result["target"] == app_name
    assert result["name"] == app_name
    assert result["source"] == "catalog"
    assert "error" in result


@pytest.mark.asyncio
async def test_install_from_catalog_generic_exception(  # noqa: PLR0913
    sample_asset: Asset,
    sample_release: Release,
    sample_catalog_entry: dict[str, Any],
    mock_config_manager: MagicMock,
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test handling of unexpected exceptions during installation.

    Verifies that generic (non-domain) exceptions are properly wrapped
    in InstallError and converted to error result dicts.
    """
    # Arrange
    app_name = "qownnotes"
    mock_config_manager.load_catalog.return_value = sample_catalog_entry
    mock_fetch_release = AsyncMock(return_value=sample_release)
    unexpected_error = RuntimeError("Unexpected system error")
    mock_install_workflow = AsyncMock(side_effect=unexpected_error)

    with (
        patch(
            "my_unicorn.core.install.catalog.get_github_config"
        ) as mock_get_config,
        patch(
            "my_unicorn.core.install.catalog.select_best_appimage_asset"
        ) as mock_select_asset,
    ):
        mock_get_config.return_value = MagicMock(
            owner="pbek", repo="QOwnNotes"
        )
        mock_select_asset.return_value = sample_asset

        # Act
        result = await install_from_catalog(
            app_name,
            mock_config_manager,
            mock_download_service,
            mock_post_download_processor,
            fetch_release_fn=mock_fetch_release,
            install_workflow_fn=mock_install_workflow,
        )

    # Assert
    assert result["success"] is False
    assert result["target"] == app_name
    assert result["name"] == app_name
    assert result["source"] == "catalog"
    assert "error" in result


# =============================================================================
# build_url_install_config() Tests
# =============================================================================


def test_build_url_install_config_structure() -> None:
    """Test build_url_install_config returns proper v2.0.0 schema.

    Verifies the config structure includes all required sections:
    config_version, metadata, source, appimage, verification, icon.
    """
    # Arrange
    app_name = "test-app"
    owner = "test-owner"
    repo = "test-repo"
    prerelease = False

    # Act
    config = build_url_install_config(app_name, owner, repo, prerelease)

    # Assert
    assert config["config_version"] == "2.0.0"
    assert config["metadata"]["name"] == app_name
    assert config["metadata"]["display_name"] == app_name
    assert "description" in config["metadata"]

    assert config["source"]["type"] == "github"
    assert config["source"]["owner"] == owner
    assert config["source"]["repo"] == repo
    assert config["source"]["prerelease"] is False

    assert config["appimage"]["naming"]["target_name"] == app_name
    assert "architectures" in config["appimage"]["naming"]
    assert "amd64" in config["appimage"]["naming"]["architectures"]

    assert config["verification"]["method"] == "digest"
    assert config["icon"]["method"] == "extraction"


def test_build_url_install_config_prerelease() -> None:
    """Test build_url_install_config with prerelease flag.

    Verifies that prerelease setting is properly included in the
    returned configuration dictionary.
    """
    # Arrange
    app_name = "test-app"
    owner = "test-owner"
    repo = "test-repo"
    prerelease = True

    # Act
    config = build_url_install_config(app_name, owner, repo, prerelease)

    # Assert
    assert config["config_version"] == "2.0.0"
    assert config["source"]["prerelease"] is True
    assert config["metadata"]["name"] == app_name
    assert config["appimage"]["naming"]["target_name"] == app_name
