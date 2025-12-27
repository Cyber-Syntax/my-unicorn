"""Test icon migration from v1 to v2 config format."""

from unittest.mock import MagicMock

from my_unicorn.migration.app_config import AppConfigMigrator


class TestIconMigration:
    """Test icon migration logic fixes."""

    def test_icon_extraction_with_url_tagspaces(self):
        """Test tagspaces: source=extraction with URL stays extraction."""
        # v1 config from real tagspaces installation
        v1_icon = {
            "extraction": True,
            "url": (
                "https://raw.githubusercontent.com/tagspaces/"
                "tagspaces/master/assets/icon.png"
            ),
            "name": "tagspaces.png",
            "source": "extraction",  # This is the authoritative field
            "installed": True,
            "path": "/home/developer/Applications/icons/tagspaces.png",
        }

        migrator = AppConfigMigrator(MagicMock())
        result = migrator._build_icon_state(v1_icon)

        # Should use "extraction" from source field, not "download"
        assert result["method"] == "extraction"
        assert result["installed"] is True
        path = "/home/developer/Applications/icons/tagspaces.png"
        assert result["path"] == path

    def test_icon_extraction_with_url_super_productivity(self):
        """Test super-productivity: source=extraction with URL."""
        # v1 config from real super-productivity installation
        v1_icon = {
            "url": (
                "https://raw.githubusercontent.com/johannesjo/"
                "super-productivity/master/src/assets/icons/"
                "favicon-192x192.png"
            ),
            "name": "super-productivity.png",
            "installed": True,
            "source": "extraction",  # This is the authoritative field
            "path": "/home/developer/Applications/icons/super-productivity.png",
            "extraction": True,
        }

        migrator = AppConfigMigrator(MagicMock())
        result = migrator._build_icon_state(v1_icon)

        # Should use "extraction" from source field
        assert result["method"] == "extraction"
        assert result["installed"] is True
        path = "/home/developer/Applications/icons/super-productivity.png"
        assert result["path"] == path

    def test_icon_download_with_url(self):
        """Test migration when source explicitly says download."""
        v1_icon = {
            "url": "https://example.com/icon.png",
            "name": "app.png",
            "source": "download",  # Explicitly download
            "installed": True,
            "path": "/home/user/icons/app.png",
        }

        migrator = AppConfigMigrator(MagicMock())
        result = migrator._build_icon_state(v1_icon)

        assert result["method"] == "download"
        assert result["installed"] is True
        assert result["path"] == "/home/user/icons/app.png"

    def test_icon_extraction_boolean_fallback(self):
        """Test fallback to extraction boolean when source field missing."""
        v1_icon = {
            "extraction": True,
            "name": "app.png",
            "installed": True,
            "path": "/home/user/icons/app.png",
        }

        migrator = AppConfigMigrator(MagicMock())
        result = migrator._build_icon_state(v1_icon)

        # Should fall back to extraction boolean
        assert result["method"] == "extraction"
        assert result["installed"] is True

    def test_icon_no_source_no_extraction_defaults_extraction(self):
        """Test default to extraction when no source or extraction field."""
        v1_icon = {
            "name": "app.png",
            "installed": False,
            "path": "",
        }

        migrator = AppConfigMigrator(MagicMock())
        result = migrator._build_icon_state(v1_icon)

        # Should default to extraction for safety
        assert result["method"] == "extraction"
        assert result["installed"] is False
        assert result["path"] == ""

    def test_icon_url_without_source_extraction_true(self):
        """Test URL present but extraction=True."""
        v1_icon = {
            "url": "https://example.com/icon.png",
            "extraction": True,
            "name": "app.png",
            "installed": True,
            "path": "/home/user/icons/app.png",
        }

        migrator = AppConfigMigrator(MagicMock())
        result = migrator._build_icon_state(v1_icon)

        # Should use extraction boolean since no source field
        assert result["method"] == "extraction"

    def test_icon_empty_source_uses_extraction_boolean(self):
        """Test empty source string falls back to extraction boolean."""
        v1_icon = {
            "source": "",  # Empty source
            "extraction": True,
            "name": "app.png",
            "installed": True,
            "path": "/home/user/icons/app.png",
        }

        migrator = AppConfigMigrator(MagicMock())
        result = migrator._build_icon_state(v1_icon)

        # Should fall back to extraction boolean
        assert result["method"] == "extraction"
