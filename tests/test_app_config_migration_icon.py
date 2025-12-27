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


class TestVerificationMigration:
    """Test verification migration logic for v1 to v2."""

    def test_catalog_skip_but_v1_has_digest(self, tmp_path):
        """Test freetube scenario: catalog says skip, but v1 app has digest.

        Catalog verification method is 'skip' (devs might add digest later),
        but v1 app state has actual digest verification that was performed.
        Migration should preserve the digest verification from v1 app state.
        """
        from my_unicorn.config import ConfigManager

        # Setup directories
        config_dir = tmp_path / "config"
        catalog_dir = tmp_path / "catalog"
        apps_dir = config_dir / "apps"
        apps_dir.mkdir(parents=True)
        catalog_dir.mkdir(parents=True)

        # Create v2 catalog with method=skip
        import orjson

        catalog_path = catalog_dir / "freetube.json"
        catalog_path.write_bytes(
            orjson.dumps(
                {
                    "config_version": "2.0.0",
                    "metadata": {
                        "name": "FreeTube",
                        "display_name": "FreeTube",
                        "description": "",
                    },
                    "source": {
                        "type": "github",
                        "owner": "FreeTubeApp",
                        "repo": "FreeTube",
                        "prerelease": True,
                    },
                    "appimage": {
                        "naming": {
                            "template": "{rename}-{latest_version}.AppImage",
                            "target_name": "freetube",
                            "architectures": ["amd64", "x86_64"],
                        }
                    },
                    "verification": {"method": "skip"},
                    "icon": {
                        "method": "extraction",
                        "filename": "freetube.svg",
                    },
                }
            )
        )

        # Create v1 app config with digest (skip=false, digest=true)
        app_path = apps_dir / "freetube.json"
        app_path.write_bytes(
            orjson.dumps(
                {
                    "config_version": "1.0.0",
                    "source": "catalog",
                    "owner": "FreeTubeApp",
                    "repo": "FreeTube",
                    "appimage": {
                        "version": "0.23.12-beta",
                        "name": "freetube.AppImage",
                        "rename": "freetube",
                        "name_template": "{rename}-{latest_version}.AppImage",
                        "characteristic_suffix": ["amd64"],
                        "installed_date": "2025-11-20T17:24:38.772857",
                        "digest": "sha256:2192afeea12f727f83044decbe0bdd92b0e98c78f6d22f9e613640419b16e44a",
                    },
                    "github": {"repo": True, "prerelease": True},
                    "verification": {
                        "digest": True,  # v1 app has digest verification
                        "skip": False,  # Not skipped in v1 app
                        "checksum_file": "",
                        "checksum_hash_type": "sha256",
                    },
                    "icon": {
                        "extraction": True,
                        "url": None,
                        "name": "freetube.png",
                        "source": "extraction",
                        "installed": True,
                        "path": "/icons/freetube.png",
                    },
                }
            )
        )

        # Migrate
        config_manager = ConfigManager(config_dir, catalog_dir)
        migrator = AppConfigMigrator(config_manager)
        result = migrator.migrate_app("freetube")

        assert result["migrated"] is True
        assert result["from"] == "1.0.0"
        assert result["to"] == "2.0.0"

        # Load migrated config
        migrated = config_manager.load_app_config("freetube")

        # Should have digest verification method (from v1 app state)
        methods = migrated["state"]["verification"]["methods"]
        assert len(methods) == 1, "Should have exactly one verification method"
        assert methods[0]["type"] == "digest", "Should preserve digest from v1"
        assert methods[0]["status"] == "passed"
        assert (
            methods[0]["expected"]
            == "2192afeea12f727f83044decbe0bdd92b0e98c78f6d22f9e613640419b16e44a"
        )

        # Verification should be marked as passed
        assert migrated["state"]["verification"]["passed"] is True
