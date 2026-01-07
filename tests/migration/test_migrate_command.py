"""Tests for migrate command handler."""

import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.commands.migrate import MigrateHandler
from my_unicorn.config import ConfigManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config_manager(temp_dir):
    """Create a ConfigManager for testing."""
    config_dir = temp_dir / "config"
    config_dir.mkdir()
    apps_dir = config_dir / "apps"
    apps_dir.mkdir()
    catalog_dir = config_dir / "catalog"
    catalog_dir.mkdir()

    manager = MagicMock(spec=ConfigManager)
    manager.directory_manager = MagicMock()
    manager.directory_manager.apps_dir = apps_dir
    manager.directory_manager.catalog_dir = catalog_dir
    manager.app_config_manager = MagicMock()

    return manager


@pytest.fixture
def handler(config_manager):
    """Create MigrateHandler for testing."""
    auth_manager = MagicMock()
    update_manager = MagicMock()
    return MigrateHandler(config_manager, auth_manager, update_manager)


class TestMigrateHandler:
    """Test cases for MigrateHandler class."""

    @pytest.mark.asyncio
    async def test_execute_no_apps_to_migrate(
        self, handler, config_manager, caplog
    ):
        """Test execute when no apps need migration."""
        # Setup: No apps installed
        config_manager.app_config_manager.list_installed_apps.return_value = []

        with patch(
            "my_unicorn.commands.migrate.get_apps_needing_migration"
        ) as mock_get_apps:
            mock_get_apps.return_value = []

            args = Namespace()
            await handler.execute(args)

            # Should report all configs up to date
            assert "All app configs are already up to date" in caplog.text

    @pytest.mark.asyncio
    async def test_execute_with_apps_to_migrate(
        self, handler, config_manager, caplog
    ):
        """Test execute when apps need migration."""
        # Setup: One app needs migration
        config_manager.app_config_manager.list_installed_apps.return_value = [
            "testapp"
        ]

        with patch(
            "my_unicorn.commands.migrate.get_apps_needing_migration"
        ) as mock_get_apps:
            mock_get_apps.return_value = [("testapp", "1.0.0")]

            with patch.object(
                handler, "_migrate_app_configs", new_callable=AsyncMock
            ) as mock_app_migrate:
                mock_app_migrate.return_value = {
                    "migrated": 1,
                    "errors": 0,
                }

                with patch.object(
                    handler,
                    "_migrate_catalog_configs",
                    new_callable=AsyncMock,
                ) as mock_catalog_migrate:
                    mock_catalog_migrate.return_value = {
                        "migrated": 0,
                        "errors": 0,
                    }

                    args = Namespace()
                    await handler.execute(args)

                    # Should report found apps to migrate
                    assert "Found" in caplog.text
                    assert "to migrate" in caplog.text
                    # Should report success
                    assert "Migration complete" in caplog.text

    @pytest.mark.asyncio
    async def test_execute_with_errors(self, handler, config_manager, caplog):
        """Test execute when migration has errors."""
        config_manager.app_config_manager.list_installed_apps.return_value = [
            "testapp"
        ]

        with patch(
            "my_unicorn.commands.migrate.get_apps_needing_migration"
        ) as mock_get_apps:
            mock_get_apps.return_value = [("testapp", "1.0.0")]

            with patch.object(
                handler, "_migrate_app_configs", new_callable=AsyncMock
            ) as mock_app_migrate:
                mock_app_migrate.return_value = {"migrated": 0, "errors": 1}

                with patch.object(
                    handler,
                    "_migrate_catalog_configs",
                    new_callable=AsyncMock,
                ) as mock_catalog_migrate:
                    mock_catalog_migrate.return_value = {
                        "migrated": 0,
                        "errors": 0,
                    }

                    args = Namespace()
                    await handler.execute(args)

                    # Should report errors
                    assert "completed with" in caplog.text
                    assert "errors" in caplog.text

    @pytest.mark.asyncio
    async def test_execute_already_up_to_date(
        self, handler, config_manager, caplog
    ):
        """Test execute when all configs already up to date."""
        config_manager.app_config_manager.list_installed_apps.return_value = [
            "testapp"
        ]

        with patch(
            "my_unicorn.commands.migrate.get_apps_needing_migration"
        ) as mock_get_apps:
            mock_get_apps.return_value = []

            with patch.object(
                handler, "_migrate_app_configs", new_callable=AsyncMock
            ) as mock_app_migrate:
                mock_app_migrate.return_value = {"migrated": 0, "errors": 0}

                with patch.object(
                    handler,
                    "_migrate_catalog_configs",
                    new_callable=AsyncMock,
                ) as mock_catalog_migrate:
                    mock_catalog_migrate.return_value = {
                        "migrated": 0,
                        "errors": 0,
                    }

                    args = Namespace()
                    await handler.execute(args)

                    # Should report all up to date
                    assert "already up to date" in caplog.text

    @pytest.mark.asyncio
    async def test_migrate_app_configs_no_apps(
        self, handler, config_manager, caplog
    ):
        """Test _migrate_app_configs when no apps installed."""
        config_manager.app_config_manager.list_installed_apps.return_value = []

        result = await handler._migrate_app_configs()

        assert result == {"migrated": 0, "errors": 0}
        assert "No apps installed" in caplog.text

    @pytest.mark.asyncio
    async def test_migrate_app_configs_success(
        self, handler, config_manager, caplog
    ):
        """Test _migrate_app_configs with successful migration."""
        config_manager.app_config_manager.list_installed_apps.return_value = [
            "testapp"
        ]

        with patch(
            "my_unicorn.commands.migrate.AppConfigMigrator"
        ) as mock_migrator_class:
            mock_migrator = MagicMock()
            mock_migrator_class.return_value = mock_migrator
            mock_migrator.migrate_app.return_value = {
                "migrated": True,
                "from": "1.0.0",
                "to": "2.0.0",
            }

            result = await handler._migrate_app_configs()

            assert result == {"migrated": 1, "errors": 0}
            assert "testapp" in caplog.text
            # Check for version transition (v1.0.0 -> v2.0.0)
            assert "v1.0.0" in caplog.text and "v2.0.0" in caplog.text

    @pytest.mark.asyncio
    async def test_migrate_app_configs_already_migrated(
        self, handler, config_manager, caplog
    ):
        """Test _migrate_app_configs when app already at target version."""
        config_manager.app_config_manager.list_installed_apps.return_value = [
            "testapp"
        ]

        with patch(
            "my_unicorn.commands.migrate.AppConfigMigrator"
        ) as mock_migrator_class:
            mock_migrator = MagicMock()
            mock_migrator_class.return_value = mock_migrator
            mock_migrator.migrate_app.return_value = {
                "migrated": False,
                "from": "2.0.0",
                "to": "2.0.0",
            }

            result = await handler._migrate_app_configs()

            # Should not count as migrated
            assert result == {"migrated": 0, "errors": 0}
            # Should not log anything for already-migrated apps
            assert "testapp" not in caplog.text

    @pytest.mark.asyncio
    async def test_migrate_app_configs_with_error(
        self, handler, config_manager, caplog
    ):
        """Test _migrate_app_configs when migration fails."""
        config_manager.app_config_manager.list_installed_apps.return_value = [
            "testapp"
        ]

        with patch(
            "my_unicorn.commands.migrate.AppConfigMigrator"
        ) as mock_migrator_class:
            mock_migrator = MagicMock()
            mock_migrator_class.return_value = mock_migrator
            mock_migrator.migrate_app.side_effect = ValueError(
                "Migration failed"
            )

            result = await handler._migrate_app_configs()

            assert result == {"migrated": 0, "errors": 1}
            assert "❌ testapp" in caplog.text
            assert "Migration failed" in caplog.text

    @pytest.mark.asyncio
    async def test_migrate_catalog_configs_no_files(
        self, handler, config_manager, caplog
    ):
        """Test _migrate_catalog_configs when no catalog files found."""
        result = await handler._migrate_catalog_configs()

        assert result == {"migrated": 0, "errors": 0}
        assert "No catalog files found" in caplog.text

    @pytest.mark.asyncio
    async def test_migrate_catalog_configs_success(
        self, handler, config_manager, caplog
    ):
        """Test _migrate_catalog_configs with successful migration."""
        catalog_dir = config_manager.directory_manager.catalog_dir
        catalog_file = catalog_dir / "testapp.json"

        # Create a v1 catalog file
        catalog_file.write_text(
            '{"config_version": "1.0.0", "owner": "test", "repo": "test"}'
        )

        with patch(
            "my_unicorn.commands.migrate.base.load_json_file"
        ) as mock_load:
            mock_load.return_value = {"config_version": "1.0.0"}

            with patch(
                "my_unicorn.commands.migrate.base.needs_migration"
            ) as mock_needs:
                mock_needs.return_value = True

                with patch(
                    "my_unicorn.commands.migrate.migrate_catalog_v1_to_v2"
                ) as mock_migrate:
                    mock_migrate.return_value = {"config_version": "2.0.0"}

                    with patch(
                        "my_unicorn.commands.migrate.base.save_json_file"
                    ) as mock_save:
                        result = await handler._migrate_catalog_configs()

                        assert result == {"migrated": 1, "errors": 0}
                        assert "testapp" in caplog.text
                        # Check for version transition
                        assert "v1.0.0" in caplog.text
                        assert "v2.0.0" in caplog.text
                        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_migrate_catalog_configs_already_migrated(
        self, handler, config_manager, caplog
    ):
        """Test _migrate_catalog_configs when catalog already at target version."""
        catalog_dir = config_manager.directory_manager.catalog_dir
        catalog_file = catalog_dir / "testapp.json"

        # Create a v2 catalog file
        catalog_file.write_text('{"config_version": "2.0.0"}')

        with patch(
            "my_unicorn.commands.migrate.base.load_json_file"
        ) as mock_load:
            mock_load.return_value = {"config_version": "2.0.0"}

            with patch(
                "my_unicorn.commands.migrate.base.needs_migration"
            ) as mock_needs:
                mock_needs.return_value = False

                result = await handler._migrate_catalog_configs()

                # Should not count as migrated
                assert result == {"migrated": 0, "errors": 0}

    @pytest.mark.asyncio
    async def test_migrate_catalog_configs_with_error(
        self, handler, config_manager, caplog
    ):
        """Test _migrate_catalog_configs when migration fails."""
        catalog_dir = config_manager.directory_manager.catalog_dir
        catalog_file = catalog_dir / "testapp.json"

        # Create a catalog file
        catalog_file.write_text('{"config_version": "1.0.0"}')

        with patch(
            "my_unicorn.commands.migrate.base.load_json_file"
        ) as mock_load:
            mock_load.side_effect = ValueError("Failed to load")

            result = await handler._migrate_catalog_configs()

            assert result == {"migrated": 0, "errors": 1}
            assert "❌" in caplog.text

    @pytest.mark.asyncio
    async def test_migrate_catalog_configs_exception_handling(
        self, handler, config_manager, caplog
    ):
        """Test _migrate_catalog_configs handles general exceptions."""
        # Simulate directory access error
        config_manager.directory_manager.catalog_dir = None

        result = await handler._migrate_catalog_configs()

        assert result == {"migrated": 0, "errors": 1}
        assert "failed" in caplog.text.lower()
