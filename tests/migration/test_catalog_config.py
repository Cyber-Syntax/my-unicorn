"""Tests for catalog config migration module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.config import ConfigManager
from my_unicorn.config.migration.catalog_config import (
    CatalogMigrator,
    _get_icon_config,
    _get_verification_method,
    migrate_catalog_v1_to_v2,
)
from my_unicorn.domain.constants import CATALOG_CONFIG_VERSION


class TestCatalogMigrationFunctions:
    """Test cases for catalog migration helper functions."""

    def test_migrate_catalog_v1_to_v2_basic(self) -> None:
        """Test basic v1 to v2 catalog migration."""
        old_catalog = {
            "owner": "test-owner",
            "repo": "test-repo",
            "appimage": {
                "name_template": "TestApp-{version}.AppImage",
                "rename": "testapp.AppImage",
            },
            "github": {"prerelease": False},
        }

        result = migrate_catalog_v1_to_v2(old_catalog)

        assert result["config_version"] == CATALOG_CONFIG_VERSION
        assert result["metadata"]["name"] == "test-repo"
        assert result["source"]["owner"] == "test-owner"
        assert result["source"]["repo"] == "test-repo"
        assert result["source"]["prerelease"] is False
        assert (
            result["appimage"]["naming"]["template"]
            == "TestApp-{version}.AppImage"
        )
        assert (
            result["appimage"]["naming"]["target_name"] == "testapp.AppImage"
        )

    def test_migrate_catalog_v1_to_v2_with_prerelease(self) -> None:
        """Test v1 to v2 migration with prerelease enabled."""
        old_catalog = {
            "owner": "test-owner",
            "repo": "test-repo",
            "appimage": {},
            "github": {"prerelease": True},
        }

        result = migrate_catalog_v1_to_v2(old_catalog)

        assert result["source"]["prerelease"] is True

    def test_migrate_catalog_v1_to_v2_empty_appimage(self) -> None:
        """Test v1 to v2 migration with empty appimage config."""
        old_catalog = {
            "owner": "test-owner",
            "repo": "test-repo",
            "appimage": {},
            "github": {},
        }

        result = migrate_catalog_v1_to_v2(old_catalog)

        assert result["appimage"]["naming"]["template"] == ""
        assert result["appimage"]["naming"]["target_name"] == ""

    def test_get_verification_method_skip(self) -> None:
        """Test verification method detection for skip."""
        old_catalog = {"verification": {"skip": True}}

        result = _get_verification_method(old_catalog)

        assert result == "skip"

    def test_get_verification_method_digest(self) -> None:
        """Test verification method detection for digest."""
        old_catalog = {"verification": {"digest": True}}

        result = _get_verification_method(old_catalog)

        assert result == "digest"

    def test_get_verification_method_checksum_file(self) -> None:
        """Test verification method detection for checksum_file."""
        old_catalog = {"verification": {"checksum_file": True}}

        result = _get_verification_method(old_catalog)

        assert result == "checksum_file"

    def test_get_verification_method_default(self) -> None:
        """Test verification method detection defaults to skip."""
        old_catalog = {"verification": {}}

        result = _get_verification_method(old_catalog)

        assert result == "skip"

    def test_get_verification_method_no_verification(self) -> None:
        """Test verification method when verification key missing."""
        old_catalog: dict = {}

        result = _get_verification_method(old_catalog)

        assert result == "skip"

    def test_get_icon_config_with_name(self) -> None:
        """Test icon config extraction with icon name."""
        old_catalog = {"icon": {"name": "app-icon.png"}}

        result = _get_icon_config(old_catalog)

        assert result["method"] == "extraction"
        assert result["filename"] == "app-icon.png"

    def test_get_icon_config_empty(self) -> None:
        """Test icon config extraction when icon config empty."""
        old_catalog = {"icon": {}}

        result = _get_icon_config(old_catalog)

        assert result["method"] == "extraction"
        assert result["filename"] == ""

    def test_get_icon_config_no_icon(self) -> None:
        """Test icon config extraction when icon key missing."""
        old_catalog: dict = {}

        result = _get_icon_config(old_catalog)

        assert result["method"] == "extraction"
        assert result["filename"] == ""


class TestCatalogMigrator:
    """Test cases for CatalogMigrator class."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_manager(self, temp_dir: Path) -> ConfigManager:
        """Create a ConfigManager for testing."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        catalog_dir = config_dir / "catalog"
        catalog_dir.mkdir()

        manager = MagicMock(spec=ConfigManager)
        manager.catalog_dir = catalog_dir

        return manager

    @pytest.fixture
    def migrator(self, config_manager: ConfigManager) -> CatalogMigrator:
        """Create CatalogMigrator for testing."""
        return CatalogMigrator(config_manager)

    def test_migrate_all_no_files(
        self, migrator: CatalogMigrator, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test migrate_all when no catalog files exist."""
        result = migrator.migrate_all()

        assert result == {"migrated": 0, "errors": 0}
        assert "No catalog files found" in caplog.text

    def test_migrate_all_success(
        self,
        migrator: CatalogMigrator,
        config_manager: ConfigManager,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test migrate_all with successful migrations."""
        catalog_dir = config_manager.catalog_dir
        catalog_file = catalog_dir / "testapp.json"

        # Create a v1 catalog file
        catalog_file.write_text(
            '{"config_version": "1.0.0", "owner": "test", "repo": "test"}'
        )

        with patch.object(migrator, "_migrate_catalog_file") as mock_migrate:
            mock_migrate.return_value = True

            result = migrator.migrate_all()

            assert result == {"migrated": 1, "errors": 0}
            mock_migrate.assert_called_once_with(catalog_file)

    def test_migrate_all_with_errors(
        self,
        migrator: CatalogMigrator,
        config_manager: ConfigManager,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test migrate_all with migration errors."""
        catalog_dir = config_manager.catalog_dir
        catalog_file = catalog_dir / "testapp.json"

        catalog_file.write_text('{"config_version": "1.0.0"}')

        with patch.object(migrator, "_migrate_catalog_file") as mock_migrate:
            mock_migrate.side_effect = ValueError("Migration failed")

            result = migrator.migrate_all()

            assert result == {"migrated": 0, "errors": 1}
            assert "Failed to migrate" in caplog.text

    def test_migrate_catalog_file_success(
        self,
        migrator: CatalogMigrator,
        config_manager: ConfigManager,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test _migrate_catalog_file with successful migration."""
        catalog_dir = config_manager.catalog_dir
        catalog_file = catalog_dir / "testapp.json"

        catalog_file.write_text(
            '{"config_version": "1.0.0", "owner": "test", "repo": "test", '
            '"appimage": {}, "github": {}}'
        )

        result = migrator._migrate_catalog_file(catalog_file)  # noqa: SLF001

        assert result is True
        assert "Migrated catalog" in caplog.text

        # Verify migrated content
        import orjson

        with catalog_file.open("rb") as f:
            migrated = orjson.loads(f.read())

        assert migrated["config_version"] == CATALOG_CONFIG_VERSION

    def test_migrate_catalog_file_already_migrated(
        self, migrator: CatalogMigrator, config_manager: ConfigManager
    ) -> None:
        """Test _migrate_catalog_file when already at target version."""
        catalog_dir = config_manager.catalog_dir
        catalog_file = catalog_dir / "testapp.json"

        catalog_file.write_text(
            f'{{"config_version": "{CATALOG_CONFIG_VERSION}"}}'
        )

        result = migrator._migrate_catalog_file(catalog_file)  # noqa: SLF001

        assert result is False

    def test_migrate_catalog_file_unsupported_version(
        self, migrator: CatalogMigrator, config_manager: ConfigManager
    ) -> None:
        """Test _migrate_catalog_file with unsupported old version."""
        catalog_dir = config_manager.catalog_dir
        catalog_file = catalog_dir / "testapp.json"

        # Version 0.9.0 is older and needs migration but not supported
        # (only 1.x → 2.x migration is supported)
        catalog_file.write_text(
            '{"config_version": "0.9.0", "owner": "test", "repo": "test"}'
        )

        # Should raise ValueError for unsupported version
        with pytest.raises(ValueError, match="Unsupported catalog version"):
            migrator._migrate_catalog_file(catalog_file)  # noqa: SLF001
