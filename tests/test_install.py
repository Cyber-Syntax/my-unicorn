"""Tests for InstallHandler and AppImage rename behavior."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from my_unicorn.constants import InstallSource
from my_unicorn.core.github import Asset, Release
from my_unicorn.core.install import InstallHandler
from my_unicorn.core.post_download import PostDownloadResult
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
)
from my_unicorn.core.services.install_service import (
    InstallStateChecker,
    TargetResolver,
)
from my_unicorn.exceptions import (
    InstallationError,
    InstallError,
    VerificationError,
)


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
        # Create a mock PostDownloadProcessor with AsyncMock
        mock_processor = AsyncMock()
        # Configure process method to return a successful result
        mock_processor.process.return_value = PostDownloadResult(
            success=True,
            install_path=Path("/tmp/install/test-app.AppImage"),
            verification_result={"sha256": "abc123"},
            icon_result={"path": "/tmp/icons/test-app.png"},
            config_result={"saved": True},
            desktop_result={"path": "/tmp/desktop/test-app.desktop"},
            error=None,
        )

        return InstallHandler(
            **mock_services, post_download_processor=mock_processor
        )

    @pytest.mark.asyncio
    async def test_install_from_catalog_success(
        self, install_service, mock_services
    ):
        """Test successful installation from catalog."""
        with patch(
            "my_unicorn.core.post_download.VerificationService"
        ) as mock_verification:

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
                "my_unicorn.utils.appimage_setup.DesktopEntry"
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
            "my_unicorn.core.post_download.VerificationService"
        ) as mock_verification:

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
                "my_unicorn.utils.appimage_setup.DesktopEntry"
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
            "my_unicorn.core.post_download.VerificationService"
        ) as mock_verification:

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
                "my_unicorn.utils.appimage_setup.DesktopEntry"
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
        """Ensure download failure is handled.

        Tests that download failure doesn't raise UnboundLocalError
        referring to installation_task_id.
        """
        # Simulate async download raising an exception
        mock_services["download_service"].download_appimage = AsyncMock(
            side_effect=Exception("download failed")
        )

        with patch(
            "my_unicorn.core.post_download.VerificationService"
        ) as mock_verification:
            mock_verification.return_value.verify_file = AsyncMock(
                return_value=Mock(passed=True, methods={}, updated_config={})
            )

            res = await install_service.install_from_catalog("test-app")
            assert res["success"] is False
            assert (
                "download" in res.get("error", "").lower()
                or "failed" in res.get("error", "").lower()
            )

    def test_separate_targets(self, install_service, mock_services):
        """Test separate_targets splits URLs and catalog names.

        Also tests that unknown entries are rejected.
        """
        # Set catalog listing
        mock_services["config_manager"].list_catalog_apps.return_value = [
            "app1",
            "app2",
        ]

        url_targets, catalog_targets = TargetResolver.separate_targets(
            install_service.config_manager,
            ["app1", "https://github.com/foo/bar"],
        )
        assert url_targets == ["https://github.com/foo/bar"]
        assert catalog_targets == ["app1"]

        # Unknown target should raise InstallationError
        with pytest.raises(InstallationError):
            TargetResolver.separate_targets(
                install_service.config_manager, ["missing-app"]
            )

    @pytest.mark.asyncio
    async def test_check_apps_needing_work(
        self, tmp_path, install_service, mock_services
    ):
        """Check logic for already-installed vs needing work."""
        # Provide catalog app with installed config pointing to a real file
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

        checker = InstallStateChecker()
        plan = await checker.get_apps_needing_installation(
            install_service.config_manager,
            ["https://github.com/owner/repo"],
            ["app1"],
            False,
        )
        urls_needing = plan.urls_needing_work
        catalog_needing = plan.catalog_needing_work
        already = plan.already_installed

        assert urls_needing == ["https://github.com/owner/repo"]
        assert catalog_needing == []
        assert already == ["app1"]

        # If force=True, then even existing installs should be reinstalled
        plan = await checker.get_apps_needing_installation(
            install_service.config_manager,
            [],
            ["app1"],
            True,
        )
        catalog_needing = plan.catalog_needing_work
        already = plan.already_installed
        assert catalog_needing == ["app1"]
        assert already == []


class TestInstallWorkflowProtocolUsage:
    """Tests for InstallWorkflow ProgressReporter protocol usage (Task 3.1)."""

    @pytest.fixture
    def base_mock_services(self):
        """Create base mock services for testing."""
        download_service = Mock()
        download_service.session = Mock()
        download_service.download_appimage = AsyncMock(
            return_value=Path("/tmp/test.appimage")
        )

        storage_service = Mock()
        storage_service.install_appimage = Mock(
            return_value=Path("/install/test.appimage")
        )

        config_manager = Mock()
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

        config_manager.load_catalog = Mock(
            return_value={
                "source": {"owner": "test-owner", "repo": "test-repo"},
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

        post_processor = AsyncMock()
        post_processor.process.return_value = PostDownloadResult(
            success=True,
            install_path=Path("/tmp/install/test-app.AppImage"),
            verification_result={"sha256": "abc123"},
            icon_result={"path": "/tmp/icons/test-app.png"},
            config_result={"saved": True},
            desktop_result={"path": "/tmp/desktop/test-app.desktop"},
            error=None,
        )

        return {
            "download_service": download_service,
            "storage_service": storage_service,
            "config_manager": config_manager,
            "github_client": github_client,
            "post_download_processor": post_processor,
        }

    def test_accepts_progress_reporter_protocol(self, base_mock_services):
        """Test InstallHandler accepts ProgressReporter protocol type."""

        class MockProgressReporter:
            """Mock progress reporter implementing the protocol."""

            def is_active(self) -> bool:
                return True

            def add_task(
                self,
                name: str,
                progress_type: ProgressType,
                total: float | None = None,
            ) -> str:
                return "mock-task-id"

            def update_task(
                self,
                task_id: str,
                completed: float | None = None,
                description: str | None = None,
            ) -> None:
                pass

            def finish_task(
                self,
                task_id: str,
                *,
                success: bool = True,
                description: str | None = None,
            ) -> None:
                pass

            def get_task_info(self, task_id: str) -> dict[str, object]:
                return {"completed": 0.0, "total": None, "description": ""}

        mock_reporter = MockProgressReporter()
        assert isinstance(mock_reporter, ProgressReporter)

        handler = InstallHandler(
            **base_mock_services, progress_reporter=mock_reporter
        )
        assert handler.progress_reporter is mock_reporter

    def test_uses_null_reporter_when_none_provided(self, base_mock_services):
        """Test InstallHandler uses NullProgressReporter when None provided."""
        handler = InstallHandler(**base_mock_services, progress_reporter=None)
        assert isinstance(handler.progress_reporter, NullProgressReporter)

    def test_uses_null_reporter_by_default(self, base_mock_services):
        """Test InstallHandler uses NullProgressReporter by default."""
        handler = InstallHandler(**base_mock_services)
        assert isinstance(handler.progress_reporter, NullProgressReporter)

    def test_progress_reporter_attribute_accessible(self, base_mock_services):
        """Test progress_reporter attribute is accessible."""

        class TestReporter:
            """Test reporter for attribute access test."""

            def is_active(self) -> bool:
                return True

            def add_task(self, name, progress_type, total=None) -> str:
                return "test-id"

            def update_task(
                self, task_id, completed=None, description=None
            ) -> None:
                pass

            def finish_task(
                self, task_id, *, success=True, description=None
            ) -> None:
                pass

            def get_task_info(self, task_id) -> dict:
                return {}

        reporter = TestReporter()
        handler = InstallHandler(
            **base_mock_services, progress_reporter=reporter
        )

        assert hasattr(handler, "progress_reporter")
        assert handler.progress_reporter is reporter
        assert handler.progress_reporter.is_active() is True

    def test_null_reporter_is_active_returns_false(self, base_mock_services):
        """Test NullProgressReporter.is_active() returns False."""
        handler = InstallHandler(**base_mock_services, progress_reporter=None)
        assert handler.progress_reporter.is_active() is False

    @pytest.mark.asyncio
    async def test_null_reporter_add_task_returns_null_task(
        self, base_mock_services
    ):
        """Test NullProgressReporter.add_task() returns 'null-task'."""
        handler = InstallHandler(**base_mock_services, progress_reporter=None)

        task_id = await handler.progress_reporter.add_task(
            "Test Task", ProgressType.INSTALLATION, total=100.0
        )
        assert task_id == "null-task"


class TestInstallWorkflowDomainExceptions:
    """Tests for InstallWorkflow domain exception usage (Task 3.2)."""

    @pytest.fixture
    def mock_services_for_exceptions(self):
        """Create mock services for exception testing."""
        download_service = Mock()
        download_service.session = Mock()
        download_service.download_appimage = AsyncMock(
            return_value=Path("/tmp/test.appimage")
        )

        storage_service = Mock()
        config_manager = Mock()
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

        post_processor = AsyncMock()
        post_processor.process.return_value = PostDownloadResult(
            success=True,
            install_path=Path("/tmp/install/test-app.AppImage"),
            verification_result={"sha256": "abc123"},
            icon_result={"path": "/tmp/icons/test-app.png"},
            config_result={"saved": True},
            desktop_result={"path": "/tmp/desktop/test-app.desktop"},
            error=None,
        )

        return {
            "download_service": download_service,
            "storage_service": storage_service,
            "config_manager": config_manager,
            "github_client": github_client,
            "post_download_processor": post_processor,
        }

    @pytest.mark.asyncio
    async def test_install_error_when_catalog_not_found(
        self, mock_services_for_exceptions
    ):
        """Test InstallError context when catalog app not found."""
        mock_services_for_exceptions[
            "config_manager"
        ].load_catalog.side_effect = FileNotFoundError("App not found")

        handler = InstallHandler(**mock_services_for_exceptions)
        result = await handler.install_from_catalog("nonexistent-app")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_install_error_when_no_appimage_asset(
        self, mock_services_for_exceptions
    ):
        """Test InstallError is raised when no AppImage asset found."""
        mock_services_for_exceptions[
            "config_manager"
        ].load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
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

        # Return release with no AppImage assets
        empty_release = Release(
            owner="test-owner",
            repo="test-repo",
            version="1.0.0",
            prerelease=False,
            assets=[],
            original_tag_name="v1.0.0",
        )
        mock_services_for_exceptions[
            "github_client"
        ].get_latest_release = AsyncMock(return_value=empty_release)

        handler = InstallHandler(**mock_services_for_exceptions)
        result = await handler.install_from_catalog("test-app")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_install_error_includes_context_on_failure(
        self, mock_services_for_exceptions
    ):
        """Test InstallError includes rich context data."""
        mock_services_for_exceptions[
            "config_manager"
        ].load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
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

        # Simulate GitHub API failure
        mock_services_for_exceptions[
            "github_client"
        ].get_latest_release.side_effect = Exception("API timeout")

        handler = InstallHandler(**mock_services_for_exceptions)
        result = await handler.install_from_catalog("test-app")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_install_error_wraps_unexpected_exceptions(
        self, mock_services_for_exceptions
    ):
        """Test unexpected exceptions are wrapped in InstallError."""
        mock_services_for_exceptions[
            "config_manager"
        ].load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
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

        # Simulate unexpected exception
        mock_services_for_exceptions[
            "github_client"
        ].get_latest_release.side_effect = RuntimeError(
            "Unexpected internal error"
        )

        handler = InstallHandler(**mock_services_for_exceptions)
        result = await handler.install_from_catalog("test-app")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_install_error_from_url_includes_url_context(
        self, mock_services_for_exceptions
    ):
        """Test InstallError from URL install includes URL in context."""
        # Simulate GitHub API failure for URL install
        mock_services_for_exceptions[
            "github_client"
        ].get_latest_release.side_effect = Exception("API error")

        handler = InstallHandler(**mock_services_for_exceptions)
        result = await handler.install_from_url(
            "https://github.com/test-owner/test-repo"
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_verification_error_is_handled_gracefully(
        self, mock_services_for_exceptions
    ):
        """Test VerificationError is caught and returns failure result."""
        mock_services_for_exceptions[
            "config_manager"
        ].load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
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
        mock_services_for_exceptions[
            "github_client"
        ].get_latest_release = AsyncMock(return_value=release)

        # Simulate verification error during post-processing
        mock_services_for_exceptions[
            "post_download_processor"
        ].process.side_effect = VerificationError(
            "Hash mismatch",
            context={"expected": "abc", "actual": "xyz"},
        )

        handler = InstallHandler(**mock_services_for_exceptions)
        result = await handler.install_from_catalog("test-app")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_domain_exceptions_preserve_cause_chain(
        self, mock_services_for_exceptions
    ):
        """Test domain exceptions preserve cause chain for debugging."""
        original_error = ConnectionError("Network unreachable")

        # Create InstallError with cause
        install_error = InstallError(
            "Download failed",
            context={"app_name": "test-app", "source": "catalog"},
            cause=original_error,
        )

        assert install_error.__cause__ is original_error
        assert "Download failed" in str(install_error)
        assert install_error.context["app_name"] == "test-app"

    @pytest.mark.asyncio
    async def test_install_error_context_contains_source(
        self, mock_services_for_exceptions
    ):
        """Test InstallError context includes source information."""
        error = InstallError(
            "Failed to install",
            context={
                "app_name": "test-app",
                "owner": "test-owner",
                "repo": "test-repo",
                "source": InstallSource.CATALOG,
            },
        )

        assert error.context["source"] == InstallSource.CATALOG
        assert error.context["app_name"] == "test-app"
        assert error.context["owner"] == "test-owner"
        assert error.context["repo"] == "test-repo"
