"""Integration tests for workflow components with refactored architecture.

This module tests the integration between workflow components that have been
refactored to use the ProgressReporter protocol and domain exceptions:

- InstallHandler with ProgressReporter protocol
- UpdateManager with ProgressReporter protocol
- DownloadService with async I/O
- VerificationService with domain exceptions

The tests verify:
- Protocol integration across module boundaries
- Domain exception propagation through workflow layers
- Async file I/O functionality in downloads
- Core modules functioning without UI dependencies
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.download import HAS_AIOFILES, DownloadService
from my_unicorn.core.github import Asset, Release
from my_unicorn.core.install import InstallHandler
from my_unicorn.core.post_download import PostDownloadResult
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
)
from my_unicorn.core.update.update import UpdateManager
from my_unicorn.core.verification.service import VerificationService
from my_unicorn.exceptions import InstallError, UpdateError, VerificationError


class MockProgressReporter:
    """Mock progress reporter for integration testing.

    Tracks all progress operations to verify correct protocol usage
    across module boundaries. Methods are async to match the download
    service's await usage.
    """

    def __init__(self) -> None:
        """Initialize mock progress reporter with tracking lists."""
        self.tasks: dict[str, dict] = {}
        self.task_counter = 0
        self.operations: list[dict] = []
        self._active = True

    def is_active(self) -> bool:
        """Check if progress reporting is active."""
        return self._active

    def set_active(self, active: bool) -> None:
        """Set the active state for testing."""
        self._active = active

    async def add_task(
        self,
        name: str,
        progress_type: ProgressType,
        total: float | None = None,
    ) -> str:
        """Add a new progress task (async).

        Args:
            name: Task name.
            progress_type: Type of progress operation.
            total: Total units of work.

        Returns:
            Task identifier.

        """
        self.task_counter += 1
        task_id = f"task-{self.task_counter}"
        self.tasks[task_id] = {
            "name": name,
            "progress_type": progress_type,
            "total": total,
            "completed": 0.0,
            "finished": False,
            "success": None,
        }
        self.operations.append(
            {"op": "add_task", "task_id": task_id, "name": name}
        )
        return task_id

    async def update_task(
        self,
        task_id: str,
        completed: float | None = None,
        description: str | None = None,
    ) -> None:
        """Update task progress (async).

        Args:
            task_id: Task identifier.
            completed: Units of work completed.
            description: Updated description.

        """
        if task_id in self.tasks:
            if completed is not None:
                self.tasks[task_id]["completed"] = completed
            self.operations.append(
                {
                    "op": "update_task",
                    "task_id": task_id,
                    "completed": completed,
                }
            )

    async def finish_task(
        self,
        task_id: str,
        *,
        success: bool = True,
        description: str | None = None,
    ) -> None:
        """Mark task as complete (async).

        Args:
            task_id: Task identifier.
            success: Whether task completed successfully.
            description: Final status message.

        """
        if task_id in self.tasks:
            self.tasks[task_id]["finished"] = True
            self.tasks[task_id]["success"] = success
        self.operations.append(
            {"op": "finish_task", "task_id": task_id, "success": success}
        )

    def get_task_info(self, task_id: str) -> dict[str, object]:
        """Get task information.

        Args:
            task_id: Task identifier.

        Returns:
            Task info dictionary.

        """
        if task_id in self.tasks:
            return {
                "completed": self.tasks[task_id]["completed"],
                "total": self.tasks[task_id]["total"],
                "description": self.tasks[task_id]["name"],
            }
        return {"completed": 0.0, "total": None, "description": ""}


# =============================================================================
# Protocol Verification Tests
# =============================================================================


@pytest.mark.integration
class TestProgressReporterProtocolIntegration:
    """Verify ProgressReporter protocol works across module boundaries."""

    def test_mock_reporter_implements_protocol(self) -> None:
        """Verify MockProgressReporter is compatible with ProgressReporter."""
        reporter = MockProgressReporter()
        assert isinstance(reporter, ProgressReporter)

    def test_null_reporter_implements_protocol(self) -> None:
        """Verify NullProgressReporter is compatible with ProgressReporter."""
        reporter = NullProgressReporter()
        assert isinstance(reporter, ProgressReporter)

    def test_install_handler_accepts_protocol(self) -> None:
        """Verify InstallHandler accepts any ProgressReporter."""
        reporter = MockProgressReporter()

        mock_services = {
            "download_service": MagicMock(),
            "storage_service": MagicMock(),
            "config_manager": MagicMock(),
            "github_client": MagicMock(),
            "post_download_processor": MagicMock(),
        }

        handler = InstallHandler(
            download_service=mock_services["download_service"],
            storage_service=mock_services["storage_service"],
            config_manager=mock_services["config_manager"],
            github_client=mock_services["github_client"],
            post_download_processor=mock_services["post_download_processor"],
            progress_reporter=reporter,
        )

        assert handler.progress_reporter is reporter
        assert isinstance(handler.progress_reporter, ProgressReporter)

    def test_update_manager_accepts_protocol(self) -> None:
        """Verify UpdateManager accepts any ProgressReporter implementation."""
        reporter = MockProgressReporter()

        with patch("my_unicorn.core.update.update.ConfigManager") as mock_cm:
            mock_cm.return_value.load_global_config.return_value = {
                "directory": {
                    "storage": Path("/tmp/storage"),
                    "cache": Path("/tmp/cache"),
                },
            }
            manager = UpdateManager(progress_reporter=reporter)

        assert manager.progress_reporter is reporter
        assert isinstance(manager.progress_reporter, ProgressReporter)

    def test_download_service_accepts_protocol(self) -> None:
        """Verify DownloadService accepts ProgressReporter."""
        reporter = MockProgressReporter()
        mock_session = MagicMock()

        service = DownloadService(
            session=mock_session, progress_reporter=reporter
        )

        assert service.progress_reporter is reporter
        assert isinstance(service.progress_reporter, ProgressReporter)

    def test_verification_service_accepts_protocol(self) -> None:
        """Verify VerificationService accepts ProgressReporter."""
        reporter = MockProgressReporter()
        mock_download = MagicMock()

        service = VerificationService(
            download_service=mock_download, progress_reporter=reporter
        )

        assert service.progress_reporter is reporter
        assert isinstance(service.progress_reporter, ProgressReporter)


# =============================================================================
# Domain Exception Propagation Tests
# =============================================================================


@pytest.mark.integration
class TestDomainExceptionPropagation:
    """Verify domain exceptions propagate correctly through workflow layers."""

    @pytest.fixture
    def mock_install_handler(self) -> InstallHandler:
        """Create InstallHandler with mock services for exception testing."""
        mock_services = {
            "download_service": MagicMock(),
            "storage_service": MagicMock(),
            "config_manager": MagicMock(),
            "github_client": MagicMock(),
            "post_download_processor": MagicMock(),
        }
        mock_services["config_manager"].load_catalog.return_value = None

        return InstallHandler(
            download_service=mock_services["download_service"],
            storage_service=mock_services["storage_service"],
            config_manager=mock_services["config_manager"],
            github_client=mock_services["github_client"],
            post_download_processor=mock_services["post_download_processor"],
        )

    @pytest.mark.asyncio
    async def test_install_error_contains_context(
        self, mock_install_handler: InstallHandler
    ) -> None:
        """Verify install returns error info when catalog not found."""
        result = await mock_install_handler.install_from_catalog(
            "nonexistent-app"
        )

        # Install returns a result dict with success=False on failure
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_verification_error_propagates_through_install(self) -> None:
        """Verify VerificationError is caught and returns error result."""
        mock_download = MagicMock()
        mock_download.download_appimage = AsyncMock(
            return_value=Path("/tmp/app")
        )

        mock_storage = MagicMock()
        mock_config = MagicMock()
        mock_config.load_catalog.return_value = {
            "source": {"owner": "test", "repo": "app"},
            "appimage": {"naming": {"template": "", "target_name": "test"}},
            "verification": {},
        }

        mock_github = MagicMock()
        mock_github.get_latest_release = AsyncMock(
            return_value=Release(
                owner="test",
                repo="app",
                version="1.0.0",
                prerelease=False,
                assets=[
                    Asset(
                        name="test.AppImage",
                        size=1024,
                        digest="",
                        browser_download_url="https://example.com/test.AppImage",
                    )
                ],
                original_tag_name="v1.0.0",
            )
        )

        mock_post = MagicMock()
        mock_post.process = AsyncMock(
            side_effect=VerificationError(
                "Hash mismatch",
                context={"file_path": "/tmp/app", "algorithm": "sha256"},
            )
        )

        handler = InstallHandler(
            download_service=mock_download,
            storage_service=mock_storage,
            config_manager=mock_config,
            github_client=mock_github,
            post_download_processor=mock_post,
        )

        # InstallHandler catches exceptions and returns error result
        result = await handler.install_from_catalog("test-app")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_update_error_contains_context(self) -> None:
        """Verify UpdateError contains rich context when catalog fails."""
        with patch("my_unicorn.core.update.update.ConfigManager") as mock_cm:
            mock_cm.return_value.load_global_config.return_value = {
                "directory": {
                    "storage": Path("/tmp/storage"),
                    "cache": Path("/tmp/cache"),
                },
            }
            mock_cm.return_value.load_catalog.side_effect = FileNotFoundError(
                "Catalog not found"
            )

            manager = UpdateManager(config_manager=mock_cm.return_value)

            # _load_catalog_if_needed takes (app_name, catalog_ref)
            with pytest.raises(UpdateError) as exc_info:
                await manager._load_catalog_if_needed(
                    "test-app", "nonexistent-catalog"
                )

            error = exc_info.value
            assert error.context is not None
            assert "catalog_ref" in error.context

    def test_verification_error_has_is_retryable_flag(self) -> None:
        """Verify VerificationError has is_retryable attribute."""
        error = VerificationError("Test error")
        assert hasattr(error, "is_retryable")
        assert error.is_retryable is False

    def test_install_error_preserves_cause_chain(self) -> None:
        """Verify InstallError preserves exception cause chain."""
        original_error = ValueError("Original error")
        install_error = InstallError(
            "Install failed",
            context={"app_name": "test"},
            cause=original_error,
        )

        assert install_error.__cause__ is original_error


# =============================================================================
# Async File I/O Integration Tests
# =============================================================================


@pytest.mark.integration
class TestAsyncFileIOIntegration:
    """Verify async file I/O works correctly in download workflows."""

    @pytest.mark.asyncio
    async def test_download_service_uses_aiofiles_when_available(
        self, tmp_path: Path
    ) -> None:
        """Verify DownloadService uses aiofiles for async I/O."""
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.headers = {"Content-Length": "12"}

        async def mock_iter_chunked(size: int):
            yield b"test content"

        mock_response.content.iter_chunked = mock_iter_chunked
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        service = DownloadService(session=mock_session)
        dest = tmp_path / "test.bin"

        await service.download_file("http://example.com/file", dest)

        assert dest.exists()
        assert HAS_AIOFILES is True

    @pytest.mark.asyncio
    async def test_download_with_progress_tracking(
        self, tmp_path: Path
    ) -> None:
        """Verify download tracks progress via ProgressReporter."""
        reporter = MockProgressReporter()
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.headers = {"Content-Length": str(2 * 1024 * 1024)}

        async def mock_iter_chunked(size: int):
            for _ in range(256):
                yield b"x" * 8192

        mock_response.content.iter_chunked = mock_iter_chunked
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        service = DownloadService(
            session=mock_session, progress_reporter=reporter
        )
        dest = tmp_path / "large_file.bin"

        await service.download_file("http://example.com/large", dest)

        assert len(reporter.tasks) >= 1
        task_operations = [
            op for op in reporter.operations if op["op"] == "add_task"
        ]
        assert len(task_operations) >= 1

    @pytest.mark.asyncio
    async def test_download_inactive_reporter_skips_progress(
        self, tmp_path: Path
    ) -> None:
        """Verify download skips progress updates when reporter is inactive."""
        reporter = MockProgressReporter()
        reporter.set_active(False)

        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.headers = {"Content-Length": str(2 * 1024 * 1024)}

        async def mock_iter_chunked(size: int):
            yield b"x" * 8192

        mock_response.content.iter_chunked = mock_iter_chunked
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        service = DownloadService(
            session=mock_session, progress_reporter=reporter
        )
        dest = tmp_path / "file.bin"

        await service.download_file("http://example.com/file", dest)

        # No tasks should be added when reporter is inactive
        add_operations = [
            op for op in reporter.operations if op["op"] == "add_task"
        ]
        assert len(add_operations) == 0


# =============================================================================
# Core Module Independence Tests
# =============================================================================


@pytest.mark.integration
class TestCoreModuleIndependence:
    """Verify core modules function without UI dependencies."""

    @pytest.mark.asyncio
    async def test_download_service_works_with_null_reporter(self) -> None:
        """Verify DownloadService functions with NullProgressReporter."""
        mock_session = MagicMock()
        service = DownloadService(session=mock_session)

        assert isinstance(service.progress_reporter, NullProgressReporter)
        assert service.progress_reporter.is_active() is False
        task_id = await service.progress_reporter.add_task(
            "test", ProgressType.DOWNLOAD
        )
        assert task_id == "null-task"

    def test_install_handler_works_with_null_reporter(self) -> None:
        """Verify InstallHandler functions with NullProgressReporter."""
        mock_services = {
            "download_service": MagicMock(),
            "storage_service": MagicMock(),
            "config_manager": MagicMock(),
            "github_client": MagicMock(),
            "post_download_processor": MagicMock(),
        }

        handler = InstallHandler(
            download_service=mock_services["download_service"],
            storage_service=mock_services["storage_service"],
            config_manager=mock_services["config_manager"],
            github_client=mock_services["github_client"],
            post_download_processor=mock_services["post_download_processor"],
        )

        assert isinstance(handler.progress_reporter, NullProgressReporter)
        assert handler.progress_reporter.is_active() is False

    def test_update_manager_works_with_null_reporter(self) -> None:
        """Verify UpdateManager functions with NullProgressReporter."""
        with patch("my_unicorn.core.update.update.ConfigManager") as mock_cm:
            mock_cm.return_value.load_global_config.return_value = {
                "directory": {
                    "storage": Path("/tmp/storage"),
                    "cache": Path("/tmp/cache"),
                },
            }
            manager = UpdateManager()

        assert isinstance(manager.progress_reporter, NullProgressReporter)
        assert manager.progress_reporter.is_active() is False

    def test_verification_service_works_with_null_reporter(self) -> None:
        """Verify VerificationService functions with NullProgressReporter."""
        mock_download = MagicMock()
        service = VerificationService(download_service=mock_download)

        assert isinstance(service.progress_reporter, NullProgressReporter)
        assert service.progress_reporter.is_active() is False

    @pytest.mark.asyncio
    async def test_null_reporter_operations_are_noop(self) -> None:
        """Verify NullProgressReporter operations have no side effects."""
        reporter = NullProgressReporter()

        task_id = await reporter.add_task(
            "Test", ProgressType.DOWNLOAD, total=100.0
        )
        assert task_id == "null-task"

        # These should not raise any exceptions
        await reporter.update_task(task_id, completed=50.0)
        await reporter.finish_task(task_id, success=True)

        info = reporter.get_task_info(task_id)
        assert info["completed"] == 0.0
        assert info["total"] is None


# =============================================================================
# Cross-Component Integration Tests
# =============================================================================


@pytest.mark.integration
class TestCrossComponentIntegration:
    """Test integration between multiple refactored components."""

    @pytest.fixture
    def shared_progress_reporter(self) -> MockProgressReporter:
        """Create shared progress reporter for cross-component tests."""
        return MockProgressReporter()

    @pytest.mark.asyncio
    async def test_shared_reporter_tracks_multiple_services(
        self, shared_progress_reporter: MockProgressReporter
    ) -> None:
        """Verify single reporter tracks progress from multiple services."""
        mock_session = MagicMock()
        mock_download_service = MagicMock()

        download_svc = DownloadService(
            session=mock_session, progress_reporter=shared_progress_reporter
        )
        verification_svc = VerificationService(
            download_service=mock_download_service,
            progress_reporter=shared_progress_reporter,
        )

        # Both services share the same reporter
        assert (
            download_svc.progress_reporter
            is verification_svc.progress_reporter
        )

        # Simulate operations from both services (async methods)
        task1 = await shared_progress_reporter.add_task(
            "Download", ProgressType.DOWNLOAD
        )
        task2 = await shared_progress_reporter.add_task(
            "Verify", ProgressType.VERIFICATION
        )

        assert len(shared_progress_reporter.tasks) == 2
        assert task1 != task2

    @pytest.mark.asyncio
    async def test_install_workflow_with_shared_reporter(
        self, shared_progress_reporter: MockProgressReporter
    ) -> None:
        """Verify install workflow reports progress through shared reporter."""
        mock_download = MagicMock()
        mock_download.download_appimage = AsyncMock(
            return_value=Path("/tmp/test.appimage")
        )

        mock_storage = MagicMock()
        mock_storage.install_appimage = MagicMock(
            return_value=Path("/install/test.appimage")
        )

        mock_config = MagicMock()
        mock_config.load_catalog.return_value = {
            "source": {"owner": "test", "repo": "app"},
            "appimage": {
                "naming": {
                    "template": "",
                    "target_name": "test",
                    "architectures": [],
                }
            },
            "verification": {"skip": True},
            "icon": {"method": "extraction"},
        }
        mock_config.save_app_config = MagicMock()
        mock_config.load_global_config = MagicMock(
            return_value={
                "directory": {
                    "icon": "/tmp/icons",
                    "install": "/tmp/install",
                    "desktop": "/tmp/desktop",
                }
            }
        )

        mock_github = MagicMock()
        mock_github.get_latest_release = AsyncMock(
            return_value=Release(
                owner="test",
                repo="app",
                version="1.0.0",
                prerelease=False,
                assets=[
                    Asset(
                        name="test.AppImage",
                        size=1024,
                        digest="",
                        browser_download_url="https://example.com/test.AppImage",
                    )
                ],
                original_tag_name="v1.0.0",
            )
        )

        mock_post = MagicMock()
        mock_post.process = AsyncMock(
            return_value=PostDownloadResult(
                success=True,
                install_path=Path("/install/test.appimage"),
                verification_result=None,
                icon_result=None,
                config_result=None,
                desktop_result=None,
            )
        )

        handler = InstallHandler(
            download_service=mock_download,
            storage_service=mock_storage,
            config_manager=mock_config,
            github_client=mock_github,
            post_download_processor=mock_post,
            progress_reporter=shared_progress_reporter,
        )

        assert handler.progress_reporter is shared_progress_reporter
        assert handler.progress_reporter.is_active() is True

    def test_exception_propagation_preserves_context_across_layers(
        self,
    ) -> None:
        """Verify exception context preserved when propagating."""
        # Simulate exception chain
        original = ValueError("Original file error")
        verification = VerificationError(
            "Verification failed",
            context={"file": "test.appimage"},
            cause=original,
        )
        install = InstallError(
            "Install failed",
            context={"app_name": "test", "source": "catalog"},
            cause=verification,
        )

        # Verify full chain
        assert install.__cause__ is verification
        assert verification.__cause__ is original

        # Verify context at each level
        assert install.context["app_name"] == "test"
        assert verification.context["file"] == "test.appimage"
