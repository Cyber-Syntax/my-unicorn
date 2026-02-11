"""Tests for InstallStateChecker.

This test suite validates the installation state checking logic for
determining which apps need installation work.
"""

from unittest.mock import Mock, patch

import pytest

from my_unicorn.core.services.install_service import InstallStateChecker
from my_unicorn.types import InstallPlan


class TestInstallStateChecker:
    """Test cases for InstallStateChecker."""

    @pytest.mark.asyncio
    async def test_get_apps_needing_installation_all_new(self) -> None:
        """Test when all apps need installation (not installed yet)."""
        config_manager = Mock()
        config_manager.load_catalog.return_value = {"name": "test-app"}
        config_manager.load_app_config.side_effect = FileNotFoundError

        checker = InstallStateChecker()
        plan = await checker.get_apps_needing_installation(
            config_manager=config_manager,
            url_targets=["https://github.com/user/repo"],
            catalog_targets=["test-app"],
            force=False,
        )

        assert isinstance(plan, InstallPlan)
        assert plan.urls_needing_work == ["https://github.com/user/repo"]
        assert plan.catalog_needing_work == ["test-app"]
        assert plan.already_installed == []

    @pytest.mark.asyncio
    async def test_get_apps_needing_installation_already_installed(
        self,
    ) -> None:
        """Test when app is already installed and file exists."""
        config_manager = Mock()
        config_manager.load_catalog.return_value = {"name": "test-app"}
        config_manager.load_app_config.return_value = {
            "installed_path": "/tmp/test-app.AppImage"
        }

        checker = InstallStateChecker()

        # Mock the path existence check
        with patch(
            "my_unicorn.core.services.install_service.Path.exists",
            return_value=True,
        ):
            plan = await checker.get_apps_needing_installation(
                config_manager=config_manager,
                url_targets=[],
                catalog_targets=["test-app"],
                force=False,
            )

        assert plan.urls_needing_work == []
        assert plan.catalog_needing_work == []
        assert plan.already_installed == ["test-app"]

    @pytest.mark.asyncio
    async def test_get_apps_needing_installation_force_reinstall(
        self,
    ) -> None:
        """Test force flag overrides already installed check."""
        config_manager = Mock()
        config_manager.load_catalog.return_value = {"name": "test-app"}
        config_manager.load_app_config.return_value = {
            "installed_path": "/tmp/test-app.AppImage"
        }

        checker = InstallStateChecker()

        with patch(
            "my_unicorn.core.services.install_service.Path.exists",
            return_value=True,
        ):
            plan = await checker.get_apps_needing_installation(
                config_manager=config_manager,
                url_targets=[],
                catalog_targets=["test-app"],
                force=True,  # Force installation
            )

        assert plan.urls_needing_work == []
        assert plan.catalog_needing_work == ["test-app"]
        assert plan.already_installed == []

    @pytest.mark.asyncio
    async def test_get_apps_needing_installation_installed_path_missing(
        self,
    ) -> None:
        """Test when config exists but AppImage file is missing."""
        config_manager = Mock()
        config_manager.load_catalog.return_value = {"name": "test-app"}
        config_manager.load_app_config.return_value = {
            "installed_path": "/tmp/test-app.AppImage"
        }

        checker = InstallStateChecker()

        with patch(
            "my_unicorn.core.services.install_service.Path.exists",
            return_value=False,
        ):
            plan = await checker.get_apps_needing_installation(
                config_manager=config_manager,
                url_targets=[],
                catalog_targets=["test-app"],
                force=False,
            )

        assert plan.catalog_needing_work == ["test-app"]
        assert plan.already_installed == []

    @pytest.mark.asyncio
    async def test_get_apps_needing_installation_catalog_missing(
        self,
    ) -> None:
        """Test when app not in catalog."""
        config_manager = Mock()
        config_manager.load_catalog.side_effect = FileNotFoundError

        checker = InstallStateChecker()
        plan = await checker.get_apps_needing_installation(
            config_manager=config_manager,
            url_targets=[],
            catalog_targets=["missing-app"],
            force=False,
        )

        assert plan.catalog_needing_work == ["missing-app"]
        assert plan.already_installed == []

    @pytest.mark.asyncio
    async def test_get_apps_needing_installation_mixed_states(self) -> None:
        """Test with multiple apps in different states."""
        config_manager = Mock()

        def mock_load_catalog(app_name: str) -> dict:
            if app_name == "installed-app":
                return {"name": "installed-app"}
            if app_name == "new-app":
                return {"name": "new-app"}
            raise FileNotFoundError

        def mock_load_app_config(app_name: str) -> dict:
            if app_name == "installed-app":
                return {"installed_path": "/tmp/installed-app.AppImage"}
            raise FileNotFoundError

        config_manager.load_catalog.side_effect = mock_load_catalog
        config_manager.load_app_config.side_effect = mock_load_app_config

        checker = InstallStateChecker()

        with patch(
            "my_unicorn.core.services.install_service.Path.exists",
            return_value=True,
        ):
            plan = await checker.get_apps_needing_installation(
                config_manager=config_manager,
                url_targets=[
                    "https://github.com/user/repo1",
                    "https://github.com/user/repo2",
                ],
                catalog_targets=["installed-app", "new-app"],
                force=False,
            )

        assert plan.urls_needing_work == [
            "https://github.com/user/repo1",
            "https://github.com/user/repo2",
        ]
        assert plan.catalog_needing_work == ["new-app"]
        assert plan.already_installed == ["installed-app"]

    @pytest.mark.asyncio
    async def test_get_apps_needing_installation_empty_targets(self) -> None:
        """Test with no targets."""
        config_manager = Mock()
        checker = InstallStateChecker()

        plan = await checker.get_apps_needing_installation(
            config_manager=config_manager,
            url_targets=[],
            catalog_targets=[],
            force=False,
        )

        assert plan.urls_needing_work == []
        assert plan.catalog_needing_work == []
        assert plan.already_installed == []

    @pytest.mark.asyncio
    async def test_get_apps_needing_installation_exception_handling(
        self,
    ) -> None:
        """Test that exceptions during check default to needing work."""
        config_manager = Mock()
        config_manager.load_catalog.return_value = {"name": "test-app"}
        config_manager.load_app_config.side_effect = Exception(
            "Unexpected error"
        )

        checker = InstallStateChecker()
        plan = await checker.get_apps_needing_installation(
            config_manager=config_manager,
            url_targets=[],
            catalog_targets=["test-app"],
            force=False,
        )

        # Should default to needing work if we can't determine state
        assert plan.catalog_needing_work == ["test-app"]
        assert plan.already_installed == []
