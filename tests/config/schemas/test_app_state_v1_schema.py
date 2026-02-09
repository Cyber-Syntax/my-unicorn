"""Tests for v1 app state schema validation (backward compatibility).

This module tests validation of the legacy v1 app state format to ensure
backward compatibility during migrations and version transitions.
"""

import pytest

from my_unicorn.config.schemas import SchemaValidationError, validate_app_state


class TestAppStateV1SchemaValidation:
    """Test v1 app state schema validation."""

    def test_valid_v1_app_state(self):
        """Test validation of valid v1 app state."""
        app_state = {
            "config_version": "1.0.0",
            "source": "catalog",
            "owner": "obsidianmd",
            "repo": "obsidian-releases",
            "appimage": {
                "rename": "obsidian",
                "name_template": "{rename}-{latest_version}.AppImage",
                "characteristic_suffix": [""],
                "version": "1.10.6",
                "name": "obsidian.AppImage",
                "installed_date": "2025-12-03T19:27:13.584135",
                "digest": (
                    "sha256:162d753076d0610e4dccfdccf391c13a"
                    "f5fcb557ba7574b77f0e90ac3c522b1c"
                ),
            },
            "github": {"repo": True, "prerelease": False},
            "verification": {
                "digest": True,
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            },
            "icon": {
                "extraction": True,
                "url": None,
                "name": "obsidian.png",
                "source": "extraction",
                "installed": True,
                "path": "/home/user/.local/share/icons/obsidian.png",
            },
        }

        # Should not raise
        validate_app_state(app_state, "obsidian")

    def test_v1_app_state_missing_source(self):
        """Test v1 app state with missing source field."""
        app_state = {
            "config_version": "1.0.0",
            # Missing source
            "owner": "obsidianmd",
            "repo": "obsidian-releases",
            "appimage": {
                "rename": "obsidian",
                "name_template": "{rename}-{latest_version}.AppImage",
                "characteristic_suffix": [""],
                "version": "1.10.6",
                "name": "obsidian.AppImage",
                "installed_date": "2025-12-03T19:27:13.584135",
                "digest": (
                    "sha256:162d753076d0610e4dccfdccf391c13a"
                    "f5fcb557ba7574b77f0e90ac3c522b1c"
                ),
            },
            "github": {"repo": True, "prerelease": False},
            "verification": {
                "digest": True,
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            },
            "icon": {
                "extraction": True,
                "url": None,
                "name": "obsidian.png",
                "source": "extraction",
                "installed": True,
            },
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(app_state, "obsidian")

        assert "source" in str(exc_info.value)

    def test_v1_app_state_invalid_date_format(self):
        """Test v1 app state with invalid date format."""
        app_state = {
            "config_version": "1.0.0",
            "source": "catalog",
            "owner": "obsidianmd",
            "repo": "obsidian-releases",
            "appimage": {
                "rename": "obsidian",
                "name_template": "{rename}-{latest_version}.AppImage",
                "characteristic_suffix": [""],
                "version": "1.10.6",
                "name": "obsidian.AppImage",
                "installed_date": "2025-12-03",  # Missing time component
                "digest": (
                    "sha256:162d753076d0610e4dccfdccf391c13a"
                    "f5fcb557ba7574b77f0e90ac3c522b1c"
                ),
            },
            "github": {"repo": True, "prerelease": False},
            "verification": {
                "digest": True,
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            },
            "icon": {
                "extraction": True,
                "url": None,
                "name": "obsidian.png",
                "source": "extraction",
                "installed": True,
            },
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(app_state, "obsidian")

        assert "installed_date" in str(exc_info.value)

    def test_v1_app_state_invalid_digest_format(self):
        """Test v1 app state with invalid digest format."""
        app_state = {
            "config_version": "1.0.0",
            "source": "catalog",
            "owner": "obsidianmd",
            "repo": "obsidian-releases",
            "appimage": {
                "rename": "obsidian",
                "name_template": "{rename}-{latest_version}.AppImage",
                "characteristic_suffix": [""],
                "version": "1.10.6",
                "name": "obsidian.AppImage",
                "installed_date": "2025-12-03T19:27:13.584135",
                "digest": "invalid_digest",  # Invalid format
            },
            "github": {"repo": True, "prerelease": False},
            "verification": {
                "digest": True,
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            },
            "icon": {
                "extraction": True,
                "url": None,
                "name": "obsidian.png",
                "source": "extraction",
                "installed": True,
            },
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(app_state, "obsidian")

        assert "digest" in str(exc_info.value)
