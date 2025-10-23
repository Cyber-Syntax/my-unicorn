"""Tests for InstallHandler."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from my_unicorn.install import InstallHandler


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

        github_client = Mock()
        github_client.get_latest_release = AsyncMock(
            return_value={
                "tag_name": "1.0.0",
                "original_tag_name": "v1.0.0",
                "prerelease": False,
                "assets": [
                    {
                        "name": "test.appimage",
                        "browser_download_url": "https://example.com/test.appimage",
                        "size": 1024,
                    }
                ],
                "html_url": "https://github.com/test-owner/test-repo/releases/tag/v1.0.0",
            }
        )

        catalog_manager = Mock()
        catalog_manager.get_app_config = Mock(
            return_value={
                "owner": "test-owner",
                "repo": "test-repo",
                "appimage": {
                    "rename": "test",
                    "name_template": "",
                    "characteristic_suffix": [],
                },
                "github": {},
                "verification": {},
                "icon": {"extraction": True, "url": None},
            }
        )

        icon_service = Mock()
        icon_service.acquire_icon = AsyncMock(
            return_value=Mock(
                icon_path=Path("/icons/test.png"),
                source="extracted",
                config={},
            )
        )

        return {
            "download_service": download_service,
            "storage_service": storage_service,
            "config_manager": config_manager,
            "github_client": github_client,
            "catalog_manager": catalog_manager,
            "icon_service": icon_service,
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
            "my_unicorn.install.VerificationService"
        ) as mock_verification:
            from dataclasses import dataclass

            @dataclass
            class MockVerificationResult:
                passed: bool
                methods: dict
                updated_config: dict

            mock_verification.return_value.verify_file = AsyncMock(
                return_value=MockVerificationResult(
                    passed=True,
                    methods={"sha256": "abc123"},
                    updated_config={},
                )
            )

            with patch("my_unicorn.install.DesktopEntry") as mock_desktop:
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
        mock_services["catalog_manager"].get_app_config.return_value = None

        result = await install_service.install_from_catalog("nonexistent")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_install_multiple_concurrent(
        self, install_service, mock_services
    ):
        """Test installing multiple apps concurrently."""
        with patch(
            "my_unicorn.install.VerificationService"
        ) as mock_verification:
            from dataclasses import dataclass

            @dataclass
            class MockVerificationResult:
                passed: bool
                methods: dict
                updated_config: dict

            mock_verification.return_value.verify_file = AsyncMock(
                return_value=MockVerificationResult(
                    passed=True,
                    methods={"sha256": "abc123"},
                    updated_config={},
                )
            )

            with patch("my_unicorn.install.DesktopEntry") as mock_desktop:
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
            "my_unicorn.install.VerificationService"
        ) as mock_verification:
            from dataclasses import dataclass

            @dataclass
            class MockVerificationResult:
                passed: bool
                methods: dict
                updated_config: dict

            mock_verification.return_value.verify_file = AsyncMock(
                return_value=MockVerificationResult(
                    passed=True,
                    methods={"sha256": "abc123"},
                    updated_config={},
                )
            )

            with patch("my_unicorn.install.DesktopEntry") as mock_desktop:
                mock_desktop.return_value.create_desktop_file = Mock(
                    return_value=Path("/desktop/test.desktop")
                )

                result = await install_service.install_from_url(
                    "https://github.com/test-owner/test-repo"
                )

                assert result["success"] is True
                assert result["source"] == "url"
                assert "path" in result
