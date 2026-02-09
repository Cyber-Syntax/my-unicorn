"""Unit tests for install workflows module.

This module tests the core workflow functions: install_workflow() and
fetch_release(). Tests cover success paths, error handling, and edge cases.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.constants import ERROR_NO_RELEASE_FOUND
from my_unicorn.core.github import Asset, Release
from my_unicorn.core.install.workflows import fetch_release, install_workflow
from my_unicorn.core.post_download import PostDownloadResult
from my_unicorn.exceptions import InstallError, VerificationError


@pytest.mark.asyncio
async def test_install_workflow_success(  # noqa: PLR0913
    sample_asset: Asset,
    sample_release: Release,
    sample_app_config: dict[str, Any],
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
    sample_post_download_result: PostDownloadResult,
) -> None:
    """Test successful installation workflow happy path.

    Verifies that a complete installation workflow executes successfully
    when all services return expected results.
    """
    # Arrange
    mock_download_service.download_appimage.return_value = Path(
        "/test/download/QOwnNotes-1.0.0-x86_64.AppImage"
    )
    mock_post_download_processor.process.return_value = (
        sample_post_download_result
    )
    app_name = "qownnotes"
    source = "catalog"

    mock_github_config = MagicMock()
    mock_github_config.owner = "pbek"
    mock_github_config.repo = "QOwnNotes"

    # Act
    with patch(
        "my_unicorn.core.install.workflows.get_github_config",
        return_value=mock_github_config,
    ):
        result = await install_workflow(
            app_name=app_name,
            asset=sample_asset,
            release=sample_release,
            app_config=sample_app_config,
            source=source,
            download_service=mock_download_service,
            post_download_processor=mock_post_download_processor,
            verify_downloads=True,
            download_dir=Path("/test/download"),
        )

    # Assert
    assert result["success"] is True
    assert result["target"] == app_name
    assert result["name"] == app_name
    assert result["version"] == "1.0.0"
    assert result["source"] == source
    assert isinstance(result["path"], str)
    mock_download_service.download_appimage.assert_called_once()
    mock_post_download_processor.process.assert_called_once()


@pytest.mark.asyncio
async def test_install_workflow_download_failure(
    sample_asset: Asset,
    sample_release: Release,
    sample_app_config: dict[str, Any],
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test install workflow when DownloadService raises an error.

    Verifies that download failures are properly wrapped in InstallError
    with appropriate context information.
    """
    # Arrange
    download_error = OSError("Network connection failed")
    mock_download_service.download_appimage.side_effect = download_error
    app_name = "qownnotes"

    # Act & Assert
    with pytest.raises(InstallError) as exc_info:
        await install_workflow(
            app_name=app_name,
            asset=sample_asset,
            release=sample_release,
            app_config=sample_app_config,
            source="catalog",
            download_service=mock_download_service,
            post_download_processor=mock_post_download_processor,
            download_dir=Path("/test/download"),
        )

    error = exc_info.value
    assert error.context is not None
    assert error.context["app_name"] == app_name
    assert error.context["asset_name"] == sample_asset.name


@pytest.mark.asyncio
async def test_install_workflow_processor_failure(
    sample_asset: Asset,
    sample_release: Release,
    sample_app_config: dict[str, Any],
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test install workflow when PostDownloadProcessor returns failure.

    Verifies that processor failures are translated into InstallError
    with appropriate messaging.
    """
    # Arrange
    mock_download_service.download_appimage.return_value = Path(
        "/test/download/QOwnNotes-1.0.0-x86_64.AppImage"
    )
    failure_result = PostDownloadResult(
        success=False,
        install_path=None,
        verification_result=None,
        icon_result=None,
        config_result=None,
        desktop_result=None,
        error="Verification failed: hash mismatch",
    )
    mock_post_download_processor.process.return_value = failure_result

    mock_github_config = MagicMock()
    mock_github_config.owner = "pbek"
    mock_github_config.repo = "QOwnNotes"

    # Act & Assert
    with (
        patch(
            "my_unicorn.core.install.workflows.get_github_config",
            return_value=mock_github_config,
        ),
        pytest.raises(InstallError) as exc_info,
    ):
        await install_workflow(
            app_name="qownnotes",
            asset=sample_asset,
            release=sample_release,
            app_config=sample_app_config,
            source="catalog",
            download_service=mock_download_service,
            post_download_processor=mock_post_download_processor,
            download_dir=Path("/test/download"),
        )

    assert "Verification failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_install_workflow_verification_disabled(  # noqa: PLR0913
    sample_asset: Asset,
    sample_release: Release,
    sample_app_config: dict[str, Any],
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
    sample_post_download_result: PostDownloadResult,
) -> None:
    """Test install workflow with verify_downloads=False option.

    Verifies that verification can be disabled and the workflow
    completes successfully.
    """
    # Arrange
    mock_download_service.download_appimage.return_value = Path(
        "/test/download/QOwnNotes-1.0.0-x86_64.AppImage"
    )
    mock_post_download_processor.process.return_value = (
        sample_post_download_result
    )

    mock_github_config = MagicMock()
    mock_github_config.owner = "pbek"
    mock_github_config.repo = "QOwnNotes"

    # Act
    with patch(
        "my_unicorn.core.install.workflows.get_github_config",
        return_value=mock_github_config,
    ):
        result = await install_workflow(
            app_name="qownnotes",
            asset=sample_asset,
            release=sample_release,
            app_config=sample_app_config,
            source="catalog",
            download_service=mock_download_service,
            post_download_processor=mock_post_download_processor,
            verify_downloads=False,
            download_dir=Path("/test/download"),
        )

    # Assert
    assert result["success"] is True
    # Verify processor was called with verify_downloads=False
    call_args = mock_post_download_processor.process.call_args
    assert call_args is not None
    context = call_args[0][0]
    assert context.verify_downloads is False


@pytest.mark.asyncio
async def test_install_workflow_with_warnings(
    sample_asset: Asset,
    sample_release: Release,
    sample_app_config: dict[str, Any],
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test install workflow when verification has warnings.

    Verifies that warnings from verification are properly propagated
    in the result while still returning success.
    """
    # Arrange
    mock_download_service.download_appimage.return_value = Path(
        "/test/download/QOwnNotes-1.0.0-x86_64.AppImage"
    )
    result_with_warning = PostDownloadResult(
        success=True,
        install_path=Path("/opt/appimages/qownnotes.AppImage"),
        verification_result={
            "passed": True,
            "warning": (
                "Asset was manually verified but no hash found in release"
            ),
        },
        icon_result={"installed": True},
        config_result={"saved": True},
        desktop_result={"success": True},
        error=None,
    )
    mock_post_download_processor.process.return_value = result_with_warning

    mock_github_config = MagicMock()
    mock_github_config.owner = "pbek"
    mock_github_config.repo = "QOwnNotes"

    # Act
    with patch(
        "my_unicorn.core.install.workflows.get_github_config",
        return_value=mock_github_config,
    ):
        result = await install_workflow(
            app_name="qownnotes",
            asset=sample_asset,
            release=sample_release,
            app_config=sample_app_config,
            source="catalog",
            download_service=mock_download_service,
            post_download_processor=mock_post_download_processor,
            download_dir=Path("/test/download"),
        )

    # Assert
    assert result["success"] is True
    warning_msg = "Asset was manually verified but no hash found in release"
    assert result["warning"] == warning_msg


@pytest.mark.asyncio
async def test_install_workflow_verification_error(
    sample_asset: Asset,
    sample_release: Release,
    sample_app_config: dict[str, Any],
    mock_download_service: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test install workflow when VerificationError is raised.

    Verifies that VerificationError exceptions are re-raised without
    being wrapped in additional context.
    """
    # Arrange
    mock_download_service.download_appimage.return_value = Path(
        "/test/download/QOwnNotes-1.0.0-x86_64.AppImage"
    )
    verification_error = VerificationError(
        "SHA256 hash mismatch",
        context={"expected": "abc123", "computed": "def456"},
    )
    mock_post_download_processor.process.side_effect = verification_error

    mock_github_config = MagicMock()
    mock_github_config.owner = "pbek"
    mock_github_config.repo = "QOwnNotes"

    # Act & Assert
    with (
        patch(
            "my_unicorn.core.install.workflows.get_github_config",
            return_value=mock_github_config,
        ),
        pytest.raises(VerificationError) as exc_info,
    ):
        await install_workflow(
            app_name="qownnotes",
            asset=sample_asset,
            release=sample_release,
            app_config=sample_app_config,
            source="catalog",
            download_service=mock_download_service,
            post_download_processor=mock_post_download_processor,
            download_dir=Path("/test/download"),
        )

    # Verify the original exception is re-raised with context intact
    assert exc_info.value is verification_error
    assert "hash mismatch" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_release_success(
    sample_release: Release,
    mock_github_client: AsyncMock,
) -> None:
    """Test successful release fetch from GitHub API.

    Verifies that a valid release is returned when the GitHub API
    provides release data.
    """
    # Arrange
    mock_github_client.get_latest_release.return_value = sample_release

    # Act
    result = await fetch_release(
        github_client=mock_github_client,
        owner="pbek",
        repo="QOwnNotes",
    )

    # Assert
    assert result is sample_release
    assert result.version == "1.0.0"
    assert result.owner == "pbek"
    assert result.repo == "QOwnNotes"
    mock_github_client.get_latest_release.assert_called_once_with(
        "pbek", "QOwnNotes"
    )


@pytest.mark.asyncio
async def test_fetch_release_no_release_found(
    mock_github_client: AsyncMock,
) -> None:
    """Test fetch_release when no release is available.

    Verifies that InstallError with ERROR_NO_RELEASE_FOUND message
    is raised when the API returns no release.
    """
    # Arrange
    mock_github_client.get_latest_release.return_value = None
    owner = "unknown"
    repo = "repository"

    # Act & Assert
    with pytest.raises(InstallError) as exc_info:
        await fetch_release(
            github_client=mock_github_client,
            owner=owner,
            repo=repo,
        )

    error = exc_info.value
    expected_message = ERROR_NO_RELEASE_FOUND.format(owner=owner, repo=repo)
    assert expected_message in str(error)
    assert error.context is not None
    assert error.context["owner"] == owner
    assert error.context["repo"] == repo


@pytest.mark.asyncio
async def test_fetch_release_api_failure(
    mock_github_client: AsyncMock,
) -> None:
    """Test fetch_release when GitHub API raises an error.

    Verifies that API errors are wrapped in InstallError with
    appropriate context information while preserving the cause.
    """
    # Arrange
    api_error = ConnectionError("Network timeout")
    mock_github_client.get_latest_release.side_effect = api_error
    owner = "pbek"
    repo = "QOwnNotes"

    # Act & Assert
    with pytest.raises(InstallError) as exc_info:
        await fetch_release(
            github_client=mock_github_client,
            owner=owner,
            repo=repo,
        )

    error = exc_info.value
    assert "Failed to fetch release" in str(error)
    assert error.context is not None
    assert error.context["owner"] == owner
    assert error.context["repo"] == repo
    assert error.__cause__ is api_error
