"""Unit tests for InstallHandler class.

This module tests the InstallHandler class, focusing on:
- Delegation to catalog and URL installation modules
- Concurrent multi-app installations
- Concurrency control with semaphores
- Error handling in various scenarios
- Factory method for default dependency creation
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from my_unicorn.core.install.handler import InstallHandler
from my_unicorn.exceptions import (
    InstallationError,
    InstallError,
    VerificationError,
)


@pytest.fixture
def install_handler(
    mock_download_service: AsyncMock,
    mock_storage_service: MagicMock,
    mock_config_manager: MagicMock,
    mock_github_client: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> InstallHandler:
    """Provide configured InstallHandler with all mocked dependencies.

    Returns:
        Configured InstallHandler instance.

    """
    return InstallHandler(
        download_service=mock_download_service,
        storage_service=mock_storage_service,
        config_manager=mock_config_manager,
        github_client=mock_github_client,
        post_download_processor=mock_post_download_processor,
    )


@pytest.mark.asyncio
async def test_install_from_catalog_delegation(
    install_handler: InstallHandler,
    sample_install_result_success: dict[str, Any],
) -> None:
    """Verify delegation to catalog module.

    The handler should call install_from_catalog function with all required
    parameters and return the result unchanged.
    """
    # Arrange
    handler = install_handler

    app_name = "qownnotes"
    expected_result = sample_install_result_success

    with patch(
        "my_unicorn.core.install.handler.install_from_catalog"
    ) as mock_install:
        mock_install.return_value = expected_result

        # Act
        result = await handler.install_from_catalog(
            app_name, verify_downloads=True
        )

        # Assert
        assert result == expected_result
        mock_install.assert_called_once()
        call_kwargs = mock_install.call_args.kwargs
        assert call_kwargs["app_name"] == app_name
        assert call_kwargs["verify_downloads"] is True
        # Verify dependencies are passed (we check presence, not identity)
        assert "config_manager" in call_kwargs
        assert "download_service" in call_kwargs
        assert "post_download_processor" in call_kwargs


@pytest.mark.asyncio
async def test_install_from_url_delegation(
    install_handler: InstallHandler,
    sample_install_result_success: dict[str, Any],
) -> None:
    """Verify delegation to url module.

    The handler should call install_from_url function with all required
    parameters and return the result unchanged.
    """
    # Arrange
    handler = install_handler

    github_url = "https://github.com/pbek/QOwnNotes"
    expected_result = sample_install_result_success

    with patch(
        "my_unicorn.core.install.handler.install_from_url"
    ) as mock_install:
        mock_install.return_value = expected_result

        # Act
        result = await handler.install_from_url(
            github_url, verify_downloads=True
        )

        # Assert
        assert result == expected_result
        mock_install.assert_called_once()
        call_kwargs = mock_install.call_args.kwargs
        assert call_kwargs["github_url"] == github_url
        assert call_kwargs["verify_downloads"] is True
        # Verify dependencies are passed (we check presence, not identity)
        assert "download_service" in call_kwargs
        assert "github_client" in call_kwargs
        assert "post_download_processor" in call_kwargs


@pytest.mark.asyncio
async def test_install_multiple_concurrent_success(
    mock_download_service: AsyncMock,
    mock_storage_service: MagicMock,
    mock_config_manager: MagicMock,
    mock_github_client: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test successful concurrent installation of multiple apps.

    All catalog and URL installs should complete successfully with proper
    results returned for each.
    """
    # Arrange
    handler = InstallHandler(
        download_service=mock_download_service,
        storage_service=mock_storage_service,
        config_manager=mock_config_manager,
        github_client=mock_github_client,
        post_download_processor=mock_post_download_processor,
    )

    catalog_apps = ["app1", "app2"]
    url_apps = [
        "https://github.com/user/repo1",
        "https://github.com/user/repo2",
    ]

    results = [
        {"success": True, "app_name": "app1"},
        {"success": True, "app_name": "app2"},
        {"success": True, "app_name": "repo1"},
        {"success": True, "app_name": "repo2"},
    ]

    with (
        patch(
            "my_unicorn.core.install.handler.install_from_catalog"
        ) as mock_catalog,
        patch("my_unicorn.core.install.handler.install_from_url") as mock_url,
    ):
        mock_catalog.side_effect = results[:2]
        mock_url.side_effect = results[2:]

        # Act
        install_results = await handler.install_multiple(
            catalog_apps=catalog_apps,
            url_apps=url_apps,
            concurrent=2,
        )

        # Assert
        assert len(install_results) == 4
        assert all(result["success"] for result in install_results)
        assert mock_catalog.call_count == 2
        assert mock_url.call_count == 2


@pytest.mark.asyncio
async def test_install_multiple_mixed_targets(
    mock_download_service: AsyncMock,
    mock_storage_service: MagicMock,
    mock_config_manager: MagicMock,
    mock_github_client: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test concurrent installation with mix of catalog and URL targets.

    Both catalog and URL installs should work together in concurrent execution.
    """
    # Arrange
    handler = InstallHandler(
        download_service=mock_download_service,
        storage_service=mock_storage_service,
        config_manager=mock_config_manager,
        github_client=mock_github_client,
        post_download_processor=mock_post_download_processor,
    )

    catalog_apps = ["qownnotes"]
    url_apps = ["https://github.com/pbek/QOwnNotes"]

    with (
        patch(
            "my_unicorn.core.install.handler.install_from_catalog"
        ) as mock_catalog,
        patch("my_unicorn.core.install.handler.install_from_url") as mock_url,
    ):
        mock_catalog.return_value = {"success": True, "source": "catalog"}
        mock_url.return_value = {"success": True, "source": "url"}

        # Act
        results = await handler.install_multiple(
            catalog_apps=catalog_apps,
            url_apps=url_apps,
            concurrent=2,
        )

        # Assert
        assert len(results) == 2
        sources = [r["source"] for r in results]
        assert "catalog" in sources
        assert "url" in sources
        mock_catalog.assert_called_once()
        mock_url.assert_called_once()


@pytest.mark.asyncio
async def test_install_multiple_partial_failures(
    mock_download_service: AsyncMock,
    mock_storage_service: MagicMock,
    mock_config_manager: MagicMock,
    mock_github_client: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test concurrent installation with some succeeding and some failing.

    Some installations should succeed while others fail, and the handler should
    return results for all without raising.
    """
    # Arrange
    handler = InstallHandler(
        download_service=mock_download_service,
        storage_service=mock_storage_service,
        config_manager=mock_config_manager,
        github_client=mock_github_client,
        post_download_processor=mock_post_download_processor,
    )

    catalog_apps = ["success_app", "fail_app"]
    url_apps = []

    with patch(
        "my_unicorn.core.install.handler.install_from_catalog"
    ) as mock_catalog:
        mock_catalog.side_effect = [
            {"success": True, "app_name": "success_app"},
            InstallError("App not found"),
        ]

        # Act
        results = await handler.install_multiple(
            catalog_apps=catalog_apps,
            url_apps=url_apps,
            concurrent=2,
        )

        # Assert
        assert len(results) == 2
        success_results = [r for r in results if r["success"]]
        failure_results = [r for r in results if not r["success"]]
        assert len(success_results) == 1
        assert len(failure_results) == 1
        assert failure_results[0]["target"] == "fail_app"


@pytest.mark.asyncio
async def test_install_multiple_all_failures(
    mock_download_service: AsyncMock,
    mock_storage_service: MagicMock,
    mock_config_manager: MagicMock,
    mock_github_client: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test concurrent installation where all installs fail.

    All installations should fail, but handler should return results for all
    without raising exceptions.
    """
    # Arrange
    handler = InstallHandler(
        download_service=mock_download_service,
        storage_service=mock_storage_service,
        config_manager=mock_config_manager,
        github_client=mock_github_client,
        post_download_processor=mock_post_download_processor,
    )

    catalog_apps = ["fail1", "fail2"]
    url_apps = ["https://github.com/fail/repo"]

    with (
        patch(
            "my_unicorn.core.install.handler.install_from_catalog"
        ) as mock_catalog,
        patch("my_unicorn.core.install.handler.install_from_url") as mock_url,
    ):
        mock_catalog.side_effect = InstallError("App not found")
        mock_url.side_effect = InstallError("Invalid URL")

        # Act
        results = await handler.install_multiple(
            catalog_apps=catalog_apps,
            url_apps=url_apps,
            concurrent=3,
        )

        # Assert
        assert len(results) == 3
        assert all(not r["success"] for r in results)
        assert all("error" in r for r in results)


@pytest.mark.asyncio
async def test_install_multiple_exception_handling(
    mock_download_service: AsyncMock,
    mock_storage_service: MagicMock,
    mock_config_manager: MagicMock,
    mock_github_client: AsyncMock,
    mock_post_download_processor: AsyncMock,
) -> None:
    """Test exception handling for various error types in concurrent install.

    Handler should catch InstallationError, InstallError, VerificationError,
    and generic Exception, converting each to error results.
    """
    # Arrange
    handler = InstallHandler(
        download_service=mock_download_service,
        storage_service=mock_storage_service,
        config_manager=mock_config_manager,
        github_client=mock_github_client,
        post_download_processor=mock_post_download_processor,
    )

    catalog_apps = [
        "inst_error",
        "install_error",
        "verify_error",
        "generic_error",
    ]
    url_apps = []

    with patch(
        "my_unicorn.core.install.handler.install_from_catalog"
    ) as mock_catalog:
        mock_catalog.side_effect = [
            InstallationError("Installation failed"),
            InstallError("Install error"),
            VerificationError("Verification failed"),
            ValueError("Unexpected error"),
        ]

        # Act
        results = await handler.install_multiple(
            catalog_apps=catalog_apps,
            url_apps=url_apps,
            concurrent=4,
        )

        # Assert
        assert len(results) == 4
        assert all(not r["success"] for r in results)
        # Each should have error information
        for result in results:
            assert "error" in result
            assert result["target"] in [
                "inst_error",
                "install_error",
                "verify_error",
                "generic_error",
            ]


@pytest.mark.asyncio
async def test_install_multiple_semaphore_limit() -> None:
    """Test that semaphore limits concurrent execution.

    The handler should limit concurrent installations to the specified maximum
    using a semaphore, ensuring no more than max_concurrent tasks run at once.
    """
    # Arrange
    mock_download_service = AsyncMock()
    mock_storage_service = MagicMock()
    mock_config_manager = MagicMock()
    mock_github_client = AsyncMock()
    mock_post_download_processor = AsyncMock()

    handler = InstallHandler(
        download_service=mock_download_service,
        storage_service=mock_storage_service,
        config_manager=mock_config_manager,
        github_client=mock_github_client,
        post_download_processor=mock_post_download_processor,
    )

    max_concurrent = 2
    catalog_apps = ["app1", "app2", "app3", "app4"]
    url_apps = []

    max_concurrent_executions = 0
    current_executions = 0

    async def slow_install(app_name: str, **kwargs: Any) -> dict[str, Any]:
        """Simulate slow installation to track concurrent executions."""
        nonlocal current_executions, max_concurrent_executions

        current_executions += 1
        max_concurrent_executions = max(
            max_concurrent_executions, current_executions
        )

        await asyncio.sleep(0.1)

        current_executions -= 1
        return {"success": True, "app_name": app_name}

    with patch(
        "my_unicorn.core.install.handler.install_from_catalog",
        side_effect=slow_install,
    ):
        # Act
        results = await handler.install_multiple(
            catalog_apps=catalog_apps,
            url_apps=url_apps,
            concurrent=max_concurrent,
        )

        # Assert
        assert len(results) == 4
        assert max_concurrent_executions <= max_concurrent
        assert all(r["success"] for r in results)


@pytest.mark.asyncio
async def test_create_default_factory() -> None:
    """Test factory method creates handler with default dependencies.

    The create_default factory method should properly instantiate all required
    dependencies and return a fully configured InstallHandler instance. Should
    also work without optional progress reporter.
    """
    # Arrange
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_config_manager = MagicMock()
    mock_github_client = AsyncMock()
    mock_progress_reporter = MagicMock()
    install_dir = Path("/test/install")

    # Test with progress reporter
    with (
        patch(
            "my_unicorn.core.install.handler.DownloadService"
        ) as mock_download_cls,
        patch(
            "my_unicorn.core.install.handler.FileOperations"
        ) as mock_storage_cls,
        patch(
            "my_unicorn.core.install.handler.PostDownloadProcessor"
        ) as mock_processor_cls,
    ):
        mock_download_instance = AsyncMock()
        mock_storage_instance = MagicMock()
        mock_processor_instance = AsyncMock()

        mock_download_cls.return_value = mock_download_instance
        mock_storage_cls.return_value = mock_storage_instance
        mock_processor_cls.return_value = mock_processor_instance

        handler = InstallHandler.create_default(
            session=mock_session,
            config_manager=mock_config_manager,
            github_client=mock_github_client,
            install_dir=install_dir,
            progress_reporter=mock_progress_reporter,
        )

        # Assert with progress reporter
        assert isinstance(handler, InstallHandler)
        assert handler.download_service == mock_download_instance
        assert handler.storage_service == mock_storage_instance
        assert handler.config_manager == mock_config_manager
        assert handler.github_client == mock_github_client
        assert handler.progress_reporter == mock_progress_reporter
        assert handler.post_download_processor == mock_processor_instance

        # Verify correct classes were instantiated
        mock_download_cls.assert_called_once_with(
            mock_session, mock_progress_reporter
        )
        mock_storage_cls.assert_called_once_with(install_dir)
        mock_processor_cls.assert_called_once()

    # Test without progress reporter (None)
    with (
        patch(
            "my_unicorn.core.install.handler.DownloadService"
        ) as mock_download_cls_2,
        patch(
            "my_unicorn.core.install.handler.FileOperations"
        ) as mock_storage_cls_2,
        patch(
            "my_unicorn.core.install.handler.PostDownloadProcessor"
        ) as mock_processor_cls_2,
    ):
        mock_download_instance_2 = AsyncMock()
        mock_storage_instance_2 = MagicMock()
        mock_processor_instance_2 = AsyncMock()

        mock_download_cls_2.return_value = mock_download_instance_2
        mock_storage_cls_2.return_value = mock_storage_instance_2
        mock_processor_cls_2.return_value = mock_processor_instance_2

        handler_no_reporter = InstallHandler.create_default(
            session=mock_session,
            config_manager=mock_config_manager,
            github_client=mock_github_client,
            install_dir=install_dir,
        )

        # Assert without progress reporter
        assert isinstance(handler_no_reporter, InstallHandler)
        assert handler_no_reporter.download_service == mock_download_instance_2
        assert handler_no_reporter.progress_reporter is not None
