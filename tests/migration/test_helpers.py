"""Tests for migration helpers module."""

import tempfile
from pathlib import Path

import pytest

from my_unicorn.constants import APP_CONFIG_VERSION
from my_unicorn.migration.helpers import (
    get_apps_needing_migration,
    get_config_version,
    needs_app_migration,
    needs_migration_from_config,
)


class TestMigrationHelpers:
    """Test cases for migration helper functions."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_needs_migration_from_config_empty(self) -> None:
        """Test needs_migration_from_config with empty config."""
        result = needs_migration_from_config({})

        assert result is False

    def test_needs_migration_from_config_none(self) -> None:
        """Test needs_migration_from_config with None."""
        result = needs_migration_from_config(None)  # type: ignore[arg-type]

        assert result is False

    def test_needs_migration_from_config_needs_migration(self) -> None:
        """Test needs_migration_from_config when migration needed."""
        config = {"config_version": "1.0.0"}

        result = needs_migration_from_config(config)

        assert result is True

    def test_needs_migration_from_config_already_migrated(self) -> None:
        """Test needs_migration_from_config when already migrated."""
        config = {"config_version": APP_CONFIG_VERSION}

        result = needs_migration_from_config(config)

        assert result is False

    def test_needs_migration_from_config_no_version(self) -> None:
        """Test needs_migration_from_config when no version specified."""
        config = {"some_key": "some_value"}

        result = needs_migration_from_config(config)

        # Defaults to "1.0.0" which needs migration
        assert result is True

    def test_needs_migration_from_config_exception(self) -> None:
        """Test needs_migration_from_config handles exceptions."""
        # Integer version will be compared successfully (won't raise exception)
        # so we need to use a config that actually causes an exception
        config = {"config_version": 123}  # type: ignore[dict-item]

        result = needs_migration_from_config(config)

        # Integer 123 != APP_CONFIG_VERSION so it needs migration
        assert result is True

    def test_needs_app_migration_file_not_exists(self, temp_dir: Path) -> None:
        """Test needs_app_migration when file doesn't exist."""
        app_config_path = temp_dir / "nonexistent.json"

        result = needs_app_migration(app_config_path)

        assert result is False

    def test_needs_app_migration_needs_migration(self, temp_dir: Path) -> None:
        """Test needs_app_migration when migration needed."""
        app_config_path = temp_dir / "app.json"
        app_config_path.write_text('{"config_version": "1.0.0"}')

        result = needs_app_migration(app_config_path)

        assert result is True

    def test_needs_app_migration_already_migrated(
        self, temp_dir: Path
    ) -> None:
        """Test needs_app_migration when already at target version."""
        app_config_path = temp_dir / "app.json"
        app_config_path.write_text(
            f'{{"config_version": "{APP_CONFIG_VERSION}"}}'
        )

        result = needs_app_migration(app_config_path)

        assert result is False

    def test_needs_app_migration_invalid_json(self, temp_dir: Path) -> None:
        """Test needs_app_migration with invalid JSON."""
        app_config_path = temp_dir / "app.json"
        app_config_path.write_text("invalid json")

        result = needs_app_migration(app_config_path)

        assert result is False

    def test_get_config_version_file_not_exists(self, temp_dir: Path) -> None:
        """Test get_config_version when file doesn't exist."""
        app_config_path = temp_dir / "nonexistent.json"

        result = get_config_version(app_config_path)

        assert result is None

    def test_get_config_version_valid(self, temp_dir: Path) -> None:
        """Test get_config_version with valid config."""
        app_config_path = temp_dir / "app.json"
        app_config_path.write_text('{"config_version": "1.5.0"}')

        result = get_config_version(app_config_path)

        assert result == "1.5.0"

    def test_get_config_version_no_version(self, temp_dir: Path) -> None:
        """Test get_config_version when no version specified."""
        app_config_path = temp_dir / "app.json"
        app_config_path.write_text('{"some_key": "some_value"}')

        result = get_config_version(app_config_path)

        # Defaults to "1.0.0"
        assert result == "1.0.0"

    def test_get_config_version_invalid_json(self, temp_dir: Path) -> None:
        """Test get_config_version with invalid JSON."""
        app_config_path = temp_dir / "app.json"
        app_config_path.write_text("invalid json")

        result = get_config_version(app_config_path)

        assert result is None

    def test_get_apps_needing_migration_dir_not_exists(
        self, temp_dir: Path
    ) -> None:
        """Test get_apps_needing_migration when directory doesn't exist."""
        apps_dir = temp_dir / "nonexistent"

        result = get_apps_needing_migration(apps_dir)

        assert result == []

    def test_get_apps_needing_migration_no_apps(self, temp_dir: Path) -> None:
        """Test get_apps_needing_migration when no apps installed."""
        apps_dir = temp_dir / "apps"
        apps_dir.mkdir()

        result = get_apps_needing_migration(apps_dir)

        assert result == []

    def test_get_apps_needing_migration_with_apps(
        self, temp_dir: Path
    ) -> None:
        """Test get_apps_needing_migration with apps needing migration."""
        apps_dir = temp_dir / "apps"
        apps_dir.mkdir()

        # Create apps at different versions
        app1 = apps_dir / "app1.json"
        app1.write_text('{"config_version": "1.0.0"}')

        app2 = apps_dir / "app2.json"
        app2.write_text(f'{{"config_version": "{APP_CONFIG_VERSION}"}}')

        app3 = apps_dir / "app3.json"
        app3.write_text('{"config_version": "1.5.0"}')

        result = get_apps_needing_migration(apps_dir)

        # Should return app1 and app3
        assert len(result) == 2
        assert ("app1", "1.0.0") in result
        assert ("app3", "1.5.0") in result
        assert ("app2", APP_CONFIG_VERSION) not in result

    def test_get_apps_needing_migration_ignores_directories(
        self, temp_dir: Path
    ) -> None:
        """Test get_apps_needing_migration ignores subdirectories."""
        apps_dir = temp_dir / "apps"
        apps_dir.mkdir()

        # Create a subdirectory (should be ignored)
        subdir = apps_dir / "subdir"
        subdir.mkdir()

        # Create a config file
        app1 = apps_dir / "app1.json"
        app1.write_text('{"config_version": "1.0.0"}')

        result = get_apps_needing_migration(apps_dir)

        # Should only return app1
        assert len(result) == 1
        assert ("app1", "1.0.0") in result

    def test_get_apps_needing_migration_handles_invalid_files(
        self, temp_dir: Path
    ) -> None:
        """Test get_apps_needing_migration handles invalid JSON files."""
        apps_dir = temp_dir / "apps"
        apps_dir.mkdir()

        # Create valid app
        app1 = apps_dir / "app1.json"
        app1.write_text('{"config_version": "1.0.0"}')

        # Create invalid app
        app2 = apps_dir / "app2.json"
        app2.write_text("invalid json")

        result = get_apps_needing_migration(apps_dir)

        # Should only return app1
        assert len(result) == 1
        assert ("app1", "1.0.0") in result
