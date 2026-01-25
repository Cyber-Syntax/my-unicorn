"""Tests for CLI command helpers module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from my_unicorn.cli.commands.helpers import (
    ensure_app_directories,
    get_install_paths,
    parse_targets,
)


class TestParseTargets:
    """Tests for parse_targets function."""

    def test_parse_targets_none(self) -> None:
        """Test parse_targets with None input."""
        result = parse_targets(None)
        assert result == []

    def test_parse_targets_empty_list(self) -> None:
        """Test parse_targets with empty list."""
        result = parse_targets([])
        assert result == []

    def test_parse_targets_single_app(self) -> None:
        """Test parse_targets with single app."""
        result = parse_targets(["app1"])
        assert result == ["app1"]

    def test_parse_targets_multiple_apps(self) -> None:
        """Test parse_targets with multiple apps."""
        result = parse_targets(["app1", "app2", "app3"])
        assert result == ["app1", "app2", "app3"]

    def test_parse_targets_comma_separated(self) -> None:
        """Test parse_targets with comma-separated values."""
        result = parse_targets(["app1,app2", "app3"])
        assert result == ["app1", "app2", "app3"]

    def test_parse_targets_mixed_format(self) -> None:
        """Test parse_targets with mixed formats."""
        result = parse_targets(["app1", "app2,app3", "app4"])
        assert result == ["app1", "app2", "app3", "app4"]

    def test_parse_targets_with_spaces(self) -> None:
        """Test parse_targets strips whitespace."""
        result = parse_targets(["app1 , app2", " app3 "])
        assert result == ["app1", "app2", "app3"]

    def test_parse_targets_removes_duplicates(self) -> None:
        """Test parse_targets removes duplicates (case-insensitive)."""
        result = parse_targets(["app1", "App1", "app2", "app1"])
        assert result == ["app1", "app2"]

    def test_parse_targets_preserves_first_occurrence_case(self) -> None:
        """Test parse_targets preserves case of first occurrence."""
        result = parse_targets(["MyApp", "myapp", "MYAPP"])
        assert result == ["MyApp"]

    def test_parse_targets_empty_strings_ignored(self) -> None:
        """Test parse_targets ignores empty strings."""
        result = parse_targets(["app1,,,app2", "", "app3"])
        assert result == ["app1", "app2", "app3"]

    def test_parse_targets_complex_scenario(self) -> None:
        """Test parse_targets with complex real-world scenario."""
        result = parse_targets(
            ["Firefox,Chrome", "VSCode", "firefox", "Gimp, Inkscape"]
        )
        assert result == ["Firefox", "Chrome", "VSCode", "Gimp", "Inkscape"]


class TestGetInstallPaths:
    """Tests for get_install_paths function."""

    def test_get_install_paths_both_present(self) -> None:
        """Test get_install_paths when both paths are present."""
        config = {
            "directory": {
                "storage": "/home/user/apps",
                "download": "/tmp/downloads",
            }
        }
        storage, download = get_install_paths(config)
        assert storage == Path("/home/user/apps")
        assert download == Path("/tmp/downloads")

    def test_get_install_paths_download_missing(self) -> None:
        """Test get_install_paths when download path is missing."""
        config = {"directory": {"storage": "/home/user/apps"}}
        storage, download = get_install_paths(config)
        assert storage == Path("/home/user/apps")
        assert download == Path("/home/user/apps")

    def test_get_install_paths_with_pathlib_paths(self) -> None:
        """Test get_install_paths with Path objects in config."""
        config = {
            "directory": {
                "storage": Path("/home/user/apps"),
                "download": Path("/tmp/downloads"),
            }
        }
        storage, download = get_install_paths(config)
        assert storage == Path("/home/user/apps")
        assert download == Path("/tmp/downloads")

    def test_get_install_paths_missing_storage_raises_error(self) -> None:
        """Test get_install_paths raises KeyError if storage is missing."""
        config = {"directory": {"download": "/tmp/downloads"}}
        with pytest.raises(KeyError):
            get_install_paths(config)

    def test_get_install_paths_missing_directory_raises_error(self) -> None:
        """Test get_install_paths raises KeyError if directory is missing."""
        config = {}
        with pytest.raises(KeyError):
            get_install_paths(config)


class TestEnsureAppDirectories:
    """Tests for ensure_app_directories function."""

    def test_ensure_app_directories_calls_config_manager(self) -> None:
        """Test ensure_app_directories calls ConfigManager method."""
        mock_config_manager = MagicMock()
        global_config = {"directory": {"storage": "/home/user/apps"}}

        ensure_app_directories(mock_config_manager, global_config)

        mock_config_manager.ensure_directories_from_config.assert_called_once_with(
            global_config
        )

    def test_ensure_app_directories_passes_config_unchanged(self) -> None:
        """Test ensure_app_directories passes config without modification."""
        mock_config_manager = MagicMock()
        global_config = {
            "directory": {
                "storage": "/home/user/apps",
                "download": "/tmp/downloads",
                "icon": "/home/user/icons",
            }
        }

        ensure_app_directories(mock_config_manager, global_config)

        call_args = (
            mock_config_manager.ensure_directories_from_config.call_args
        )
        assert call_args[0][0] == global_config
