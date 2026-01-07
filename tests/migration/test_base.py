"""Tests for migration base utilities."""

import tempfile
from pathlib import Path

import orjson
import pytest

from my_unicorn.migration.base import (
    compare_versions,
    create_backup,
    load_json_file,
    needs_migration,
    save_json_file,
)


class TestVersionComparison:
    """Test cases for version comparison functions."""

    def test_compare_versions_equal(self) -> None:
        """Test comparing equal versions."""
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("2.1.3", "2.1.3") == 0

    def test_compare_versions_less_than(self) -> None:
        """Test comparing when version1 < version2."""
        assert compare_versions("1.0.0", "2.0.0") == -1
        assert compare_versions("1.0.0", "1.1.0") == -1
        assert compare_versions("1.0.0", "1.0.1") == -1

    def test_compare_versions_greater_than(self) -> None:
        """Test comparing when version1 > version2."""
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.1.0", "1.0.0") == 1
        assert compare_versions("1.0.1", "1.0.0") == 1

    def test_compare_versions_different_lengths(self) -> None:
        """Test comparing versions with different part counts."""
        assert compare_versions("1.0", "1.0.0") == 0
        assert compare_versions("1.0.1", "1.0") == 1
        assert compare_versions("1.0", "1.0.1") == -1

    def test_compare_versions_invalid_format(self) -> None:
        """Test comparing invalid version formats."""
        # Should fallback to [0, 0, 0] for invalid versions
        result = compare_versions("invalid", "1.0.0")
        assert result == -1  # [0,0,0] < [1,0,0]

    def test_needs_migration_true(self) -> None:
        """Test needs_migration when migration is needed."""
        assert needs_migration("1.0.0", "2.0.0") is True
        assert needs_migration("1.5.0", "2.0.0") is True

    def test_needs_migration_false(self) -> None:
        """Test needs_migration when already at target version."""
        assert needs_migration("2.0.0", "2.0.0") is False
        assert needs_migration("3.0.0", "2.0.0") is False


class TestBackupOperations:
    """Test cases for backup file operations."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_create_backup_default_dir(self, temp_dir: Path) -> None:
        """Test creating backup in default backups directory."""
        source_file = temp_dir / "test.json"
        source_file.write_text('{"test": "data"}')

        backup_path = create_backup(source_file)

        assert backup_path.exists()
        assert backup_path.name == "test.json.backup"
        assert backup_path.parent.name == "backups"
        assert backup_path.read_text() == '{"test": "data"}'

    def test_create_backup_custom_dir(self, temp_dir: Path) -> None:
        """Test creating backup in custom directory."""
        source_file = temp_dir / "test.json"
        source_file.write_text('{"test": "data"}')

        custom_backup_dir = temp_dir / "custom_backups"
        backup_path = create_backup(source_file, custom_backup_dir)

        assert backup_path.exists()
        assert backup_path.parent == custom_backup_dir
        assert backup_path.read_text() == '{"test": "data"}'

    def test_create_backup_creates_dir(self, temp_dir: Path) -> None:
        """Test that backup directory is created if it doesn't exist."""
        source_file = temp_dir / "test.json"
        source_file.write_text('{"test": "data"}')

        # Backup dir doesn't exist yet
        backup_dir = temp_dir / "backups"
        assert not backup_dir.exists()

        create_backup(source_file)

        # Should be created
        assert backup_dir.exists()


class TestJSONFileOperations:
    """Test cases for JSON file load/save operations."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_load_json_file_success(self, temp_dir: Path) -> None:
        """Test loading valid JSON file."""
        json_file = temp_dir / "test.json"
        data = {"key": "value", "number": 42}
        json_file.write_bytes(orjson.dumps(data))

        loaded = load_json_file(json_file)

        assert loaded == data

    def test_load_json_file_not_found(self, temp_dir: Path) -> None:
        """Test loading non-existent JSON file."""
        json_file = temp_dir / "nonexistent.json"

        with pytest.raises(FileNotFoundError, match="File not found"):
            load_json_file(json_file)

    def test_load_json_file_invalid_json(self, temp_dir: Path) -> None:
        """Test loading invalid JSON file."""
        json_file = temp_dir / "invalid.json"
        json_file.write_text("not valid json {")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_json_file(json_file)

    def test_save_json_file_success(self, temp_dir: Path) -> None:
        """Test saving data to JSON file."""
        json_file = temp_dir / "output.json"
        data = {"key": "value", "list": [1, 2, 3]}

        save_json_file(json_file, data)

        assert json_file.exists()
        loaded = orjson.loads(json_file.read_bytes())
        assert loaded == data

    def test_save_json_file_formatting(self, temp_dir: Path) -> None:
        """Test that saved JSON is formatted with indentation."""
        json_file = temp_dir / "formatted.json"
        data = {"key": "value"}

        save_json_file(json_file, data)

        # Check that file has newlines (formatted)
        content = json_file.read_text()
        assert "\n" in content

    def test_save_json_file_overwrites_existing(self, temp_dir: Path) -> None:
        """Test that saving overwrites existing file."""
        json_file = temp_dir / "existing.json"
        json_file.write_text('{"old": "data"}')

        new_data = {"new": "data"}
        save_json_file(json_file, new_data)

        loaded = orjson.loads(json_file.read_bytes())
        assert loaded == new_data
        assert "old" not in loaded
