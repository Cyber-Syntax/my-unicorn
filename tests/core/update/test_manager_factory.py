"""Tests for UpdateManager factory methods and initialization.

This module tests the create_default factory method and its variations
for creating UpdateManager instances with proper dependency injection.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from my_unicorn.core.update.manager import UpdateManager


class TestUpdateManagerFactory:
    """Test cases for UpdateManager factory methods and initialization."""

    def test_create_default_factory_method(self) -> None:
        """Verify UpdateManager.create_default() returns proper instance.

        This test verifies that the factory method creates an UpdateManager
        with all required dependencies properly injected, including:
        - ConfigManager (created or injected)
        - GitHubAuthManager (created with defaults)
        - ReleaseCacheManager (created with defaults)
        - FileOperations (initialized)
        - BackupService (initialized)
        - ProgressReporter (defaults to NullProgressReporter)

        The test also verifies that the instance has all expected attributes.
        """
        with (
            patch(
                "my_unicorn.core.update.manager.ConfigManager"
            ) as mock_config_cls,
            patch("my_unicorn.core.update.manager.GitHubAuthManager"),
            patch("my_unicorn.core.update.manager.FileOperations"),
            patch("my_unicorn.core.update.manager.BackupService"),
            patch("my_unicorn.core.update.manager.ReleaseCacheManager"),
        ):
            mock_config_instance = MagicMock()
            mock_config_cls.return_value = mock_config_instance
            mock_config_instance.load_global_config.return_value = {
                "max_concurrent_downloads": 5,
                "directory": {
                    "storage": Path("/default/storage"),
                    "download": Path("/default/download"),
                    "backup": Path("/default/backup"),
                    "icon": Path("/default/icon"),
                    "cache": Path("/default/cache"),
                },
            }

            # Create instance using factory method with no arguments
            manager = UpdateManager.create_default()

            # Verify ConfigManager was created with defaults
            mock_config_cls.assert_called_once_with()

            # Verify instance is properly typed
            assert isinstance(manager, UpdateManager)

            # Verify all required attributes are initialized
            assert hasattr(manager, "config_manager")
            assert hasattr(manager, "auth_manager")
            assert hasattr(manager, "cache_manager")
            assert hasattr(manager, "progress_reporter")
            assert hasattr(manager, "storage_service")
            assert hasattr(manager, "backup_service")
            assert hasattr(manager, "_shared_api_task_id")
            assert hasattr(manager, "_catalog_cache")

            # Verify progress_reporter is NullProgressReporter (default)
            assert manager.progress_reporter is not None

    def test_create_default_factory_with_custom_config_manager(self) -> None:
        """Verify factory method accepts custom ConfigManager.

        This test verifies that the create_default factory method can accept
        an optional ConfigManager instance that is used instead of creating
        a new one.
        """
        mock_config = MagicMock()
        mock_config.load_global_config.return_value = {
            "max_concurrent_downloads": 3,
            "directory": {
                "storage": Path("/custom/storage"),
                "download": Path("/custom/download"),
                "backup": Path("/custom/backup"),
                "icon": Path("/custom/icon"),
                "cache": Path("/custom/cache"),
            },
        }

        with (
            patch("my_unicorn.core.update.manager.GitHubAuthManager"),
            patch("my_unicorn.core.update.manager.FileOperations"),
            patch("my_unicorn.core.update.manager.BackupService"),
            patch("my_unicorn.core.update.manager.ReleaseCacheManager"),
        ):
            # Create instance using factory method with custom config
            manager = UpdateManager.create_default(config_manager=mock_config)

            # Verify the provided config manager is used
            assert manager.config_manager == mock_config
            mock_config.load_global_config.assert_called()

    def test_create_default_factory_with_custom_progress_reporter(
        self,
    ) -> None:
        """Verify factory method accepts custom ProgressReporter.

        This test verifies that the create_default factory method can accept
        an optional ProgressReporter instance that is used instead of the
        default NullProgressReporter.
        """
        mock_config = MagicMock()
        mock_config.load_global_config.return_value = {
            "max_concurrent_downloads": 3,
            "directory": {
                "storage": Path("/test/storage"),
                "download": Path("/test/download"),
                "backup": Path("/test/backup"),
                "icon": Path("/test/icon"),
                "cache": Path("/test/cache"),
            },
        }
        mock_progress = MagicMock()

        with (
            patch("my_unicorn.core.update.manager.GitHubAuthManager"),
            patch("my_unicorn.core.update.manager.FileOperations"),
            patch("my_unicorn.core.update.manager.BackupService"),
            patch("my_unicorn.core.update.manager.ReleaseCacheManager"),
        ):
            # Create instance with custom progress reporter
            manager = UpdateManager.create_default(
                config_manager=mock_config,
                progress_reporter=mock_progress,
            )

            # Verify custom progress reporter is used
            assert manager.progress_reporter == mock_progress
