"""Tests for PostDownloadProcessor initialization.

Tests cover processor creation, dependency injection, and handling of
optional dependencies like progress reporter.
"""

from unittest.mock import MagicMock

from my_unicorn.core.post_download import PostDownloadProcessor
from my_unicorn.core.protocols.progress import NullProgressReporter


class TestProcessorInitialization:
    """Test PostDownloadProcessor initialization."""

    def test_processor_initialization_with_all_dependencies(
        self,
        processor_instance: PostDownloadProcessor,
    ) -> None:
        """Verify processor creates correctly with all dependencies.

        Args:
            processor_instance: Fixture providing fully configured processor.

        """
        assert processor_instance is not None
        assert isinstance(processor_instance, PostDownloadProcessor)

    def test_processor_stores_dependencies_correctly(  # noqa: PLR0913
        self,
        processor_instance: PostDownloadProcessor,
        mock_download_service_post: MagicMock,
        mock_storage_service_post: MagicMock,
        mock_config_manager_post: MagicMock,
        mock_backup_service_post: MagicMock,
        mock_verification_service_post: MagicMock,
        mock_progress_reporter_post: MagicMock,
    ) -> None:
        """Verify all dependencies are stored correctly.

        Args:
            processor_instance: Processor with injected dependencies.
            mock_download_service_post: Expected download service mock.
            mock_storage_service_post: Expected storage service mock.
            mock_config_manager_post: Expected config manager mock.
            mock_backup_service_post: Expected backup service mock.
            mock_verification_service_post: Expected verification service mock.
            mock_progress_reporter_post: Expected progress reporter mock.

        """
        assert (
            processor_instance.download_service is mock_download_service_post
        )
        assert processor_instance.storage_service is mock_storage_service_post
        assert processor_instance.config_manager is mock_config_manager_post
        assert processor_instance.backup_service is mock_backup_service_post
        assert (
            processor_instance._verification_service
            is mock_verification_service_post
        )
        assert (
            processor_instance.progress_reporter is mock_progress_reporter_post
        )

    def test_processor_initialization_with_null_progress_reporter(
        self,
        mock_download_service_post: MagicMock,
        mock_storage_service_post: MagicMock,
        mock_config_manager_post: MagicMock,
    ) -> None:
        """Verify processor handles NullProgressReporter when none provided.

        Args:
            mock_download_service_post: Mocked download service.
            mock_storage_service_post: Mocked storage service.
            mock_config_manager_post: Mocked config manager.

        """
        processor = PostDownloadProcessor(
            download_service=mock_download_service_post,
            storage_service=mock_storage_service_post,
            config_manager=mock_config_manager_post,
            progress_reporter=None,
        )

        assert processor is not None
        assert isinstance(processor.progress_reporter, NullProgressReporter)
