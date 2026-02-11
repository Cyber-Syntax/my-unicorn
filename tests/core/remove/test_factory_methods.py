"""Tests for RemoveService construction and factory methods."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from my_unicorn.core.remove import (
    RemovalOperation,
    RemovalResult,
    RemoveService,
)
from my_unicorn.types import GlobalConfig


class TestRemoveServiceInit:
    """Tests for RemoveService.__init__ method."""

    def test_init_with_all_dependencies(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
        mock_cache_manager: MagicMock,
    ) -> None:
        """Should initialize with all dependencies provided."""
        service = RemoveService(
            config_manager=mock_config_manager,
            global_config=global_config,
            cache_manager=mock_cache_manager,
        )

        assert service.config_manager is mock_config_manager
        assert service.global_config is global_config
        assert service.cache_manager is mock_cache_manager

    def test_init_without_cache_manager(
        self,
        mock_config_manager: MagicMock,
        global_config: GlobalConfig,
    ) -> None:
        """Should initialize with cache_manager=None."""
        service = RemoveService(
            config_manager=mock_config_manager,
            global_config=global_config,
            cache_manager=None,
        )

        assert service.config_manager is mock_config_manager
        assert service.global_config is global_config
        assert service.cache_manager is None


class TestCreateDefault:
    """Tests for RemoveService.create_default factory method."""

    def test_creates_with_default_dependencies(self) -> None:
        """Should create service with default dependencies."""
        with (
            patch("my_unicorn.core.remove.ConfigManager") as mock_cm_class,
            patch(
                "my_unicorn.core.remove.ReleaseCacheManager"
            ) as mock_cache_class,
        ):
            mock_cm_instance = MagicMock()
            mock_cm_instance.load_global_config.return_value = {
                "directory": {
                    "storage": Path("/default/storage"),
                    "icon": Path("/default/icons"),
                    "backup": Path("/default/backups"),
                }
            }
            mock_cm_class.return_value = mock_cm_instance
            mock_cache_instance = MagicMock()
            mock_cache_class.return_value = mock_cache_instance

            service = RemoveService.create_default()

            assert service.config_manager is mock_cm_instance
            assert service.cache_manager is mock_cache_instance
            mock_cm_class.assert_called_once()
            mock_cache_class.assert_called_once_with(mock_cm_instance)

    def test_creates_with_provided_config_manager(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Should use provided config_manager instead of creating new one."""
        mock_config_manager.load_global_config.return_value = {
            "directory": {
                "storage": Path("/custom/storage"),
                "icon": Path("/custom/icons"),
                "backup": Path("/custom/backups"),
            }
        }

        with patch(
            "my_unicorn.core.remove.ReleaseCacheManager"
        ) as mock_cache_class:
            mock_cache_instance = MagicMock()
            mock_cache_class.return_value = mock_cache_instance

            service = RemoveService.create_default(
                config_manager=mock_config_manager
            )

            assert service.config_manager is mock_config_manager
            mock_cache_class.assert_called_once_with(mock_config_manager)

    def test_creates_with_provided_cache_manager(
        self, mock_cache_manager: MagicMock
    ) -> None:
        """Should use provided cache_manager instead of creating new one."""
        with patch("my_unicorn.core.remove.ConfigManager") as mock_cm_class:
            mock_cm_instance = MagicMock()
            mock_cm_instance.load_global_config.return_value = {
                "directory": {
                    "storage": Path("/default/storage"),
                    "icon": Path("/default/icons"),
                    "backup": Path("/default/backups"),
                }
            }
            mock_cm_class.return_value = mock_cm_instance

            service = RemoveService.create_default(
                cache_manager=mock_cache_manager
            )

            assert service.cache_manager is mock_cache_manager
            mock_cm_class.assert_called_once()

    def test_creates_with_both_managers_provided(
        self, mock_config_manager: MagicMock, mock_cache_manager: MagicMock
    ) -> None:
        """Should use both provided managers without creating new ones."""
        mock_config_manager.load_global_config.return_value = {
            "directory": {
                "storage": Path("/custom/storage"),
                "icon": Path("/custom/icons"),
                "backup": Path("/custom/backups"),
            }
        }

        service = RemoveService.create_default(
            config_manager=mock_config_manager,
            cache_manager=mock_cache_manager,
        )

        assert service.config_manager is mock_config_manager
        assert service.cache_manager is mock_cache_manager

    def test_loads_global_config_during_creation(self) -> None:
        """Should load global config during factory method call."""
        with (
            patch("my_unicorn.core.remove.ConfigManager") as mock_cm_class,
            patch("my_unicorn.core.remove.ReleaseCacheManager"),
        ):
            mock_cm_instance = MagicMock()
            expected_config = {
                "directory": {
                    "storage": Path("/loaded/storage"),
                    "icon": Path("/loaded/icons"),
                    "backup": Path("/loaded/backups"),
                }
            }
            mock_cm_instance.load_global_config.return_value = expected_config
            mock_cm_class.return_value = mock_cm_instance

            service = RemoveService.create_default()

            assert service.global_config == expected_config
            mock_cm_instance.load_global_config.assert_called_once()


class TestDataclasses:
    """Tests for RemovalOperation and RemovalResult dataclasses."""

    def test_removal_operation_defaults(self) -> None:
        """RemovalOperation should have proper default values."""
        op = RemovalOperation(success=True)

        assert op.success is True
        assert op.files == []
        assert op.metadata == {}

    def test_removal_operation_with_data(self) -> None:
        """RemovalOperation should store provided data."""
        op = RemovalOperation(
            success=True,
            files=["/path/to/file1", "/path/to/file2"],
            metadata={"key": "value"},
        )

        assert op.success is True
        assert op.files == ["/path/to/file1", "/path/to/file2"]
        assert op.metadata == {"key": "value"}

    def test_removal_result_structure(self) -> None:
        """RemovalResult should contain all expected fields."""
        result = RemovalResult(
            success=True,
            app_name="test-app",
            removed_files=["/test/file"],
            cache_cleared=True,
            cache_owner="owner",
            cache_repo="repo",
            backup_removed=True,
            backup_path="/backup/path",
            desktop_entry_removed=True,
            icon_removed=True,
            icon_path="/icon/path",
            config_removed=True,
            error=None,
        )

        assert result.success is True
        assert result.app_name == "test-app"
        assert result.removed_files == ["/test/file"]
        assert result.cache_cleared is True
        assert result.cache_owner == "owner"
        assert result.cache_repo == "repo"
        assert result.backup_removed is True
        assert result.backup_path == "/backup/path"
        assert result.desktop_entry_removed is True
        assert result.icon_removed is True
        assert result.icon_path == "/icon/path"
        assert result.config_removed is True
        assert result.error is None

    def test_removal_result_with_error(self) -> None:
        """RemovalResult should support error field."""
        result = RemovalResult(
            success=False,
            app_name="failed-app",
            removed_files=[],
            cache_cleared=False,
            cache_owner=None,
            cache_repo=None,
            backup_removed=False,
            backup_path=None,
            desktop_entry_removed=False,
            icon_removed=False,
            icon_path=None,
            config_removed=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
