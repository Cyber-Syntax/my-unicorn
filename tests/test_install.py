"""Tests for InstallHandler and AppImage rename behavior."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.core.workflows.install import InstallHandler


class TestInstallHandler:
    """Test cases for InstallHandler."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        download_service = Mock()
        download_service.session = Mock()
        download_service.progress_service = None
        download_service.download_appimage = AsyncMock(
            return_value=Path("/tmp/test.appimage")
        )

        storage_service = Mock()
        storage_service.install_appimage = Mock(
            return_value=Path("/install/test.appimage")
        )

        config_manager = Mock()
        config_manager.save_app_config = Mock(
            return_value=Path("/config/test.json")
        )
        config_manager.load_global_config = Mock(
            return_value={
                "directory": {
                    "icon": "/tmp/icons",
                    "install": "/tmp/install",
                    "desktop": "/tmp/desktop",
                },
            }
        )

        github_client = Mock()
        assets = [
            Asset(
                name="test.appimage",
                size=1024,
                digest="",
                browser_download_url="https://example.com/test.appimage",
            )
        ]
        release = Release(
            owner="test-owner",
            repo="test-repo",
            version="1.0.0",
            prerelease=False,
            assets=assets,
            original_tag_name="v1.0.0",
        )
        github_client.get_latest_release = AsyncMock(return_value=release)

        # Update config_manager to support both catalog and installed config
        config_manager.load_catalog = Mock(
            return_value={
                "source": {
                    "owner": "test-owner",
                    "repo": "test-repo",
                },
                "appimage": {
                    "naming": {
                        "template": "",
                        "target_name": "test",
                        "architectures": [],
                    },
                },
                "verification": {},
                "icon": {"method": "extraction"},
            }
        )

        return {
            "download_service": download_service,
            "storage_service": storage_service,
            "config_manager": config_manager,
            "github_client": github_client,
        }

    @pytest.fixture
    def install_service(self, mock_services):
        """Create InstallHandler instance with mocked dependencies."""
        return InstallHandler(**mock_services)

    @pytest.mark.asyncio
    async def test_install_from_catalog_success(
        self, install_service, mock_services
    ):
        """Test successful installation from catalog."""
        with patch(
            "my_unicorn.core.workflows.install.VerificationService"
        ) as mock_verification:
            from dataclasses import dataclass

            @dataclass
            class MockVerificationResult:
                passed: bool
                methods: dict
                updated_config: dict
                warning: str | None = None

            mock_verification.return_value.verify_file = AsyncMock(
                return_value=MockVerificationResult(
                    passed=True,
                    methods={"sha256": "abc123"},
                    updated_config={},
                    warning=None,
                )
            )

            with patch(
                "my_unicorn.core.workflows.appimage_setup.DesktopEntry"
            ) as mock_desktop:
                mock_desktop.return_value.create = Mock(
                    return_value=Path("/desktop/test.desktop")
                )

                result = await install_service.install_from_catalog("test-app")

                assert result["success"] is True
                assert result["name"] == "test-app"
                assert result["source"] == "catalog"
                assert "path" in result

    @pytest.mark.asyncio
    async def test_install_from_catalog_not_found(
        self, install_service, mock_services
    ):
        """Test installation fails when app not in catalog."""
        mock_services[
            "config_manager"
        ].load_catalog.side_effect = FileNotFoundError("App not found")

        result = await install_service.install_from_catalog("nonexistent")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_install_multiple_concurrent(
        self, install_service, mock_services
    ):
        """Test installing multiple apps concurrently."""
        with patch(
            "my_unicorn.core.workflows.install.VerificationService"
        ) as mock_verification:
            from dataclasses import dataclass

            @dataclass
            class MockVerificationResult:
                passed: bool
                methods: dict
                updated_config: dict
                warning: str | None = None

            mock_verification.return_value.verify_file = AsyncMock(
                return_value=MockVerificationResult(
                    passed=True,
                    methods={"sha256": "abc123"},
                    updated_config={},
                    warning=None,
                )
            )

            with patch(
                "my_unicorn.core.workflows.appimage_setup.DesktopEntry"
            ) as mock_desktop:
                mock_desktop.return_value.create_desktop_file = Mock(
                    return_value=Path("/desktop/test.desktop")
                )

                results = await install_service.install_multiple(
                    catalog_apps=["app1", "app2"],
                    url_apps=[],
                    concurrent=2,
                )

                assert len(results) == 2
                assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_install_from_url_success(
        self, install_service, mock_services
    ):
        """Test successful installation from URL."""
        with patch(
            "my_unicorn.core.workflows.install.VerificationService"
        ) as mock_verification:
            from dataclasses import dataclass

            @dataclass
            class MockVerificationResult:
                passed: bool
                methods: dict
                updated_config: dict
                warning: str | None = None

            mock_verification.return_value.verify_file = AsyncMock(
                return_value=MockVerificationResult(
                    passed=True,
                    methods={"sha256": "abc123"},
                    updated_config={},
                    warning=None,
                )
            )

            with patch(
                "my_unicorn.core.workflows.appimage_setup.DesktopEntry"
            ) as mock_desktop:
                mock_desktop.return_value.create_desktop_file = Mock(
                    return_value=Path("/desktop/test.desktop")
                )

                result = await install_service.install_from_url(
                    "https://github.com/test-owner/test-repo"
                )

                assert result["success"] is True
                assert result["source"] == "url"
                assert "path" in result

            @pytest.mark.asyncio
            async def test_install_download_failure_does_not_raise_unboundlocal(
                self, install_service, mock_services
            ):
                """Ensure download failure is handled and doesn't raise
                UnboundLocalError referring to installation_task_id.
                """
                # Simulate async download raising an exception
                mock_services[
                    "download_service"
                ].download_appimage = AsyncMock(
                    side_effect=Exception("download failed")
                )

                with patch(
                    "my_unicorn.core.workflows.install.VerificationService"
                ) as mock_verification:
                    mock_verification.return_value.verify_file = AsyncMock(
                        return_value=Mock(
                            passed=True, methods={}, updated_config={}
                        )
                    )

                    res = await install_service.install_from_catalog(
                        "test-app"
                    )
                    assert res["success"] is False
                    assert (
                        "download" in res.get("error", "").lower()
                        or "failed" in res.get("error", "").lower()
                    )

    def test_separate_targets(self, install_service, mock_services):
        """Test that separate_targets splits URLs and catalog names and
        rejects unknown entries.
        """
        # Set catalog listing
        mock_services["config_manager"].list_catalog_apps.return_value = [
            "app1",
            "app2",
        ]

        url_targets, catalog_targets = InstallHandler.separate_targets_impl(
            install_service.config_manager,
            ["app1", "https://github.com/foo/bar"],
        )
        assert url_targets == ["https://github.com/foo/bar"]
        assert catalog_targets == ["app1"]

        # Unknown target should raise InstallationError
        from my_unicorn.exceptions import InstallationError

        with pytest.raises(InstallationError):
            InstallHandler.separate_targets_impl(
                install_service.config_manager, ["missing-app"]
            )

    @pytest.mark.asyncio
    async def test_check_apps_needing_work(
        self, tmp_path, install_service, mock_services
    ):
        """Check logic for already-installed vs needing work."""
        # Provide a catalog app with installed config that points to a real file
        # Create a dummy installed file
        installed_file = tmp_path / "app-installed.AppImage"
        installed_file.write_text("x")

        # Configure config manager responses
        mock_services["config_manager"].load_catalog.return_value = {
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
            },
        }
        mock_services["config_manager"].load_app_config.return_value = {
            "installed_path": str(installed_file),
        }

        (
            urls_needing,
            catalog_needing,
            already,
        ) = await InstallHandler.check_apps_needing_work_impl(
            install_service.config_manager,
            ["https://github.com/owner/repo"],
            ["app1"],
            {"force": False},
        )

        assert urls_needing == ["https://github.com/owner/repo"]
        assert catalog_needing == []
        assert already == ["app1"]

        # If force=True, then even existing installs should be reinstalled
        (
            urls_needing,
            catalog_needing,
            already,
        ) = await InstallHandler.check_apps_needing_work_impl(
            install_service.config_manager,
            [],
            ["app1"],
            {"force": True},
        )
        assert catalog_needing == ["app1"]
        assert already == []
