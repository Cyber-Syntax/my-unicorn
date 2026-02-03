"""Tests for InstallApplicationService.

This module tests the application service layer for installation workflows,
ensuring proper orchestration, progress management, and service coordination.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.workflows.services.install_service import (
    InstallApplicationService,
    InstallOptions,
)


@pytest.fixture
def mock_session():
    """Create mock aiohttp session."""
    return AsyncMock()


@pytest.fixture
def mock_github_client():
    """Create mock GitHub client."""
    client = AsyncMock()
    client.set_shared_api_task = MagicMock()
    return client


@pytest.fixture
def mock_config_manager():
    """Create mock config manager."""
    manager = MagicMock()
    # Add list_catalog_apps method for separate_targets_impl
    manager.list_catalog_apps.return_value = ["test-app", "appflowy"]
    # Add load_catalog method
    manager.load_catalog.return_value = {
        "name": "test-app",
        "source": {"owner": "test", "repo": "app"},
    }
    return manager


@pytest.fixture
def mock_progress_service() -> Any:
    """Create mock progress reporter (ProgressReporter protocol)."""
    progress = MagicMock()
    # ProgressReporter protocol methods
    progress.is_active.return_value = True
    progress.add_task = AsyncMock(return_value="api-task-1")
    progress.update_task = AsyncMock()
    progress.finish_task = AsyncMock()
    progress.get_task_info.return_value = {
        "completed": 0.0,
        "total": None,
        "description": "",
    }
    return progress


@pytest.fixture
def install_dir(tmp_path):
    """Create temporary install directory."""
    install_dir = tmp_path / "apps"
    install_dir.mkdir()
    return install_dir


@pytest.fixture
def install_service(
    mock_session,
    mock_github_client,
    mock_config_manager,
    install_dir,
    mock_progress_service,
):
    """Create InstallApplicationService instance."""
    return InstallApplicationService(
        session=mock_session,
        github_client=mock_github_client,
        config_manager=mock_config_manager,
        install_dir=install_dir,
        progress_reporter=mock_progress_service,
    )


class TestInstallOptions:
    """Test InstallOptions data class."""

    def test_default_values(self):
        """Test default option values."""
        options = InstallOptions()
        assert options.concurrent == 3
        assert options.verify_downloads is True
        assert options.force is False
        assert options.update is False
        assert options.download_dir is None

    def test_custom_values(self):
        """Test custom option values."""
        download_dir = Path("/tmp/downloads")
        options = InstallOptions(
            concurrent=5,
            verify_downloads=False,
            force=True,
            update=True,
            download_dir=download_dir,
        )
        assert options.concurrent == 5
        assert options.verify_downloads is False
        assert options.force is True
        assert options.update is True
        assert options.download_dir == download_dir


class TestInstallApplicationService:
    """Test InstallApplicationService."""

    def test_initialization(self, install_service):
        """Test service initialization."""
        assert install_service.session is not None
        assert install_service.github is not None
        assert install_service.config is not None
        assert install_service.install_dir is not None
        assert install_service.progress_reporter is not None

    def test_lazy_download_service_creation(self, install_service):
        """Test download service is created on demand."""
        assert install_service._download_service is None
        download_service = install_service.download_service
        assert download_service is not None
        assert install_service._download_service is download_service
        # Second call returns same instance
        assert install_service.download_service is download_service

    def test_lazy_install_handler_creation(self, install_service):
        """Test install handler is created on demand."""
        assert install_service._install_handler is None
        install_handler = install_service.install_handler
        assert install_handler is not None
        assert install_service._install_handler is install_handler
        # Second call returns same instance
        assert install_service.install_handler is install_handler

    @pytest.mark.asyncio
    async def test_install_successful(self, install_service):
        """Test successful installation workflow."""
        # Mock TargetResolver.separate_targets
        with patch(
            "my_unicorn.core.workflows.services.install_service.TargetResolver.separate_targets"
        ) as mock_separate:
            mock_separate.return_value = ([], ["app1"])

            # Mock InstallStateChecker
            with patch(
                "my_unicorn.core.workflows.services.install_service.InstallStateChecker"
            ) as mock_checker_cls:
                # Create a mock plan object
                from dataclasses import dataclass

                @dataclass
                class MockPlan:
                    urls_needing_work: list[str]
                    catalog_needing_work: list[str]
                    already_installed: list[str]

                mock_checker = AsyncMock()
                mock_checker_cls.return_value = mock_checker
                mock_checker.get_apps_needing_installation.return_value = (
                    MockPlan(
                        urls_needing_work=[],
                        catalog_needing_work=["app1"],
                        already_installed=[],
                    )
                )

                # Mock install_handler.install_multiple
                install_service._install_handler = AsyncMock()
                install_service._install_handler.install_multiple = AsyncMock(
                    return_value=[
                        {
                            "target": "app1",
                            "success": True,
                            "name": "app1",
                            "source": "catalog",
                        }
                    ]
                )

                options = InstallOptions()
                results = await install_service.install(["app1"], options)

                assert len(results) == 1
                assert results[0]["success"] is True
                assert results[0]["target"] == "app1"

    @pytest.mark.asyncio
    async def test_install_already_installed(self, install_service):
        """Test installation when app is already installed."""
        # Mock TargetResolver.separate_targets
        with patch(
            "my_unicorn.core.workflows.services.install_service.TargetResolver.separate_targets"
        ) as mock_separate:
            mock_separate.return_value = ([], ["app1"])

            # Mock InstallStateChecker
            with patch(
                "my_unicorn.core.workflows.services.install_service.InstallStateChecker"
            ) as mock_checker_cls:
                from dataclasses import dataclass

                @dataclass
                class MockPlan:
                    urls_needing_work: list[str]
                    catalog_needing_work: list[str]
                    already_installed: list[str]

                mock_checker = AsyncMock()
                mock_checker_cls.return_value = mock_checker
                mock_checker.get_apps_needing_installation.return_value = (
                    MockPlan(
                        urls_needing_work=[],
                        catalog_needing_work=[],
                        already_installed=["app1"],
                    )
                )

                options = InstallOptions()
                results = await install_service.install(["app1"], options)

                assert len(results) == 1
                assert results[0]["success"] is True
                assert results[0]["status"] == "already_installed"
                assert results[0]["target"] == "app1"

    @pytest.mark.asyncio
    async def test_install_mixed_already_and_new(self, install_service):
        """Test installation with mix of already installed and new apps."""
        # Mock TargetResolver.separate_targets
        with patch(
            "my_unicorn.core.workflows.services.install_service.TargetResolver.separate_targets"
        ) as mock_separate:
            mock_separate.return_value = ([], ["app1", "app2"])

            # Mock InstallStateChecker
            with patch(
                "my_unicorn.core.workflows.services.install_service.InstallStateChecker"
            ) as mock_checker_cls:
                from dataclasses import dataclass

                @dataclass
                class MockPlan:
                    urls_needing_work: list[str]
                    catalog_needing_work: list[str]
                    already_installed: list[str]

                mock_checker = AsyncMock()
                mock_checker_cls.return_value = mock_checker
                mock_checker.get_apps_needing_installation.return_value = (
                    MockPlan(
                        urls_needing_work=[],
                        catalog_needing_work=["app1"],
                        already_installed=["app2"],
                    )
                )

                # Mock install_handler.install_multiple
                install_service._install_handler = AsyncMock()
                install_service._install_handler.install_multiple = AsyncMock(
                    return_value=[
                        {
                            "target": "app1",
                            "success": True,
                            "name": "app1",
                            "source": "catalog",
                        }
                    ]
                )

                options = InstallOptions()
                results = await install_service.install(
                    ["app1", "app2"], options
                )

                assert len(results) == 2
                # Find each result
                app1_result = next(r for r in results if r["target"] == "app1")
                app2_result = next(r for r in results if r["target"] == "app2")

                assert app1_result["success"] is True
                assert app2_result["success"] is True
                assert app2_result["status"] == "already_installed"

    @pytest.mark.asyncio
    async def test_install_with_url_targets(self, install_service):
        """Test installation with URL targets."""
        # Mock TargetResolver.separate_targets
        with patch(
            "my_unicorn.core.workflows.services.install_service.TargetResolver.separate_targets"
        ) as mock_separate:
            mock_separate.return_value = (
                [
                    "https://github.com/test/app/releases/download/v1/app.AppImage"
                ],
                [],
            )

            # Mock InstallStateChecker
            with patch(
                "my_unicorn.core.workflows.services.install_service.InstallStateChecker"
            ) as mock_checker_cls:
                from dataclasses import dataclass

                @dataclass
                class MockPlan:
                    urls_needing_work: list[str]
                    catalog_needing_work: list[str]
                    already_installed: list[str]

                mock_checker = AsyncMock()
                mock_checker_cls.return_value = mock_checker
                values = (
                    [
                        "https://github.com/test/app/releases/download/v1/app.AppImage"
                    ],
                    [],
                    [],
                )
                mock_checker.get_apps_needing_installation.return_value = (
                    MockPlan(
                        urls_needing_work=values[0]
                        if isinstance(values[0], list)
                        else [values[0]]
                        if values[0]
                        else [],
                        catalog_needing_work=values[1]
                        if isinstance(values[1], list)
                        else [values[1]]
                        if values[1]
                        else [],
                        already_installed=values[2]
                        if isinstance(values[2], list)
                        else [values[2]]
                        if values[2]
                        else [],
                    )
                )

                # Mock install_handler.install_multiple
                install_service._install_handler = AsyncMock()
                install_service._install_handler.install_multiple = AsyncMock(
                    return_value=[
                        {
                            "target": "https://github.com/test/app/releases/download/v1/app.AppImage",
                            "success": True,
                            "name": "app",
                            "source": "url",
                        }
                    ]
                )

                options = InstallOptions()
                results = await install_service.install(
                    [
                        "https://github.com/test/app/releases/download/v1/app.AppImage"
                    ],
                    options,
                )

                assert len(results) == 1
                assert results[0]["success"] is True
                assert results[0]["source"] == "url"

    @pytest.mark.asyncio
    async def test_install_with_progress_session(self, install_service):
        """Test that progress session is properly managed."""
        # Mock TargetResolver.separate_targets
        with patch(
            "my_unicorn.core.workflows.services.install_service.TargetResolver.separate_targets"
        ) as mock_separate:
            mock_separate.return_value = ([], ["app1"])

            # Mock InstallStateChecker
            with patch(
                "my_unicorn.core.workflows.services.install_service.InstallStateChecker"
            ) as mock_checker_cls:
                from dataclasses import dataclass

                @dataclass
                class MockPlan:
                    urls_needing_work: list[str]
                    catalog_needing_work: list[str]
                    already_installed: list[str]

                mock_checker = AsyncMock()
                mock_checker_cls.return_value = mock_checker
                values = ([], ["app1"], [])
                mock_checker.get_apps_needing_installation.return_value = (
                    MockPlan(
                        urls_needing_work=values[0]
                        if isinstance(values[0], list)
                        else [values[0]]
                        if values[0]
                        else [],
                        catalog_needing_work=values[1]
                        if isinstance(values[1], list)
                        else [values[1]]
                        if values[1]
                        else [],
                        already_installed=values[2]
                        if isinstance(values[2], list)
                        else [values[2]]
                        if values[2]
                        else [],
                    )
                )

                # Mock install_handler.install_multiple
                install_service._install_handler = AsyncMock()
                install_service._install_handler.install_multiple = AsyncMock(
                    return_value=[
                        {
                            "target": "app1",
                            "success": True,
                            "name": "app1",
                            "source": "catalog",
                        }
                    ]
                )

                options = InstallOptions()
                await install_service.install(["app1"], options)

                # Verify progress reporter was active
                install_service.progress_reporter.is_active.assert_called()
                # Verify GitHub API task was created via add_task()
                install_service.progress_reporter.add_task.assert_called()
                # Verify task was finished
                install_service.progress_reporter.finish_task.assert_called()

    @pytest.mark.asyncio
    async def test_install_sets_shared_api_task(self, install_service):
        """Test that shared API task is set on GitHub client."""
        # Mock TargetResolver.separate_targets
        with patch(
            "my_unicorn.core.workflows.services.install_service.TargetResolver.separate_targets"
        ) as mock_separate:
            mock_separate.return_value = ([], ["app1"])

            # Mock InstallStateChecker
            with patch(
                "my_unicorn.core.workflows.services.install_service.InstallStateChecker"
            ) as mock_checker_cls:
                from dataclasses import dataclass

                @dataclass
                class MockPlan:
                    urls_needing_work: list[str]
                    catalog_needing_work: list[str]
                    already_installed: list[str]

                mock_checker = AsyncMock()
                mock_checker_cls.return_value = mock_checker
                values = ([], ["app1"], [])
                mock_checker.get_apps_needing_installation.return_value = (
                    MockPlan(
                        urls_needing_work=values[0]
                        if isinstance(values[0], list)
                        else [values[0]]
                        if values[0]
                        else [],
                        catalog_needing_work=values[1]
                        if isinstance(values[1], list)
                        else [values[1]]
                        if values[1]
                        else [],
                        already_installed=values[2]
                        if isinstance(values[2], list)
                        else [values[2]]
                        if values[2]
                        else [],
                    )
                )

                # Mock install_handler.install_multiple
                install_service._install_handler = AsyncMock()
                install_service._install_handler.install_multiple = AsyncMock(
                    return_value=[
                        {
                            "target": "app1",
                            "success": True,
                            "name": "app1",
                            "source": "catalog",
                        }
                    ]
                )

                options = InstallOptions()
                await install_service.install(["app1"], options)

                # Verify set_shared_api_task was called
                install_service.github.set_shared_api_task.assert_called_once()

    def test_build_already_installed_results(self, install_service):
        """Test building results for already installed apps."""
        already_installed = ["app1", "app2", "app3"]
        results = install_service._build_already_installed_results(
            already_installed
        )

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["target"] == already_installed[i]
            assert result["success"] is True
            assert result["path"] == "already_installed"
            assert result["name"] == already_installed[i]
            assert result["source"] == "catalog"
            assert result["status"] == "already_installed"

    def test_log_already_installed(self, install_service):
        """Test logging of already installed apps."""
        already_installed = ["app1", "app2"]

        # Should not raise any exceptions
        install_service._log_already_installed(already_installed)
