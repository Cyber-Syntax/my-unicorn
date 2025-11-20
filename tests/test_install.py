"""Tests for InstallHandler and AppImage rename behavior."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from my_unicorn.file_ops import FileOperations
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
                "html_url": "https://github.com/test-owner/test-repo/"
                "releases/tag/v1.0.0",
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


def make_handler_with_storage(install_dir: Path) -> InstallHandler:
    """Create an InstallHandler using real FileOperations."""
    storage = FileOperations(install_dir)
    # Use Mock objects for required services to satisfy type hints
    download_service = Mock()
    config_manager = Mock()
    github_client = Mock()
    catalog_manager = Mock()
    icon_service = Mock()

    handler = InstallHandler(
        download_service=download_service,
        storage_service=storage,
        config_manager=config_manager,
        github_client=github_client,
        catalog_manager=catalog_manager,
        icon_service=icon_service,
    )
    return handler


def test_install_and_rename_adds_appimage_extension(tmp_path: Path):
    """_install_and_rename should ensure resulting file ends with .AppImage."""
    install_dir = tmp_path / "install"
    install_dir.mkdir()

    handler = make_handler_with_storage(install_dir)

    # Simulate a downloaded AppImage asset
    downloaded = tmp_path / "downloaded-temp.AppImage"
    downloaded.write_text("content", encoding="utf-8")

    app_config = {"appimage": {"rename": "mycoolapp"}}

    result_path = handler._install_and_rename(
        downloaded, "mycoolapp", app_config
    )

    # File should have .AppImage with correct casing
    assert result_path.name == "mycoolapp.AppImage"
    assert result_path.exists()
    assert result_path.read_text(encoding="utf-8") == "content"


def test_install_and_rename_normalizes_existing_extensions(tmp_path: Path):
    """Normalize provided extensions to canonical form.

    Ensure rename values with any casing or extension normalize to
    '.AppImage'.
    """
    install_dir = tmp_path / "install2"
    install_dir.mkdir()

    handler = make_handler_with_storage(install_dir)

    downloaded = tmp_path / "some-download.AppImage"
    downloaded.write_text("x", encoding="utf-8")

    # Provided rename has a lowercase extension
    app_config_lower = {"appimage": {"rename": "NeatApp.appimage"}}
    result_lower = handler._install_and_rename(
        downloaded, "NeatApp", app_config_lower
    )
    assert result_lower.name == "NeatApp.AppImage"
    assert result_lower.exists()

    # Now try with an uppercase extension already present
    # Create another downloaded file to avoid reuse
    downloaded2 = tmp_path / "some-download-2.AppImage"
    downloaded2.write_text("y", encoding="utf-8")
    app_config_upper = {"appimage": {"rename": "NeatApp.AppImage"}}
    result_upper = handler._install_and_rename(
        downloaded2, "NeatApp", app_config_upper
    )
    assert result_upper.name == "NeatApp.AppImage"
    assert result_upper.exists()
