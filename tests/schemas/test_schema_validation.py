"""Tests for JSON schema validation."""

import pytest

from my_unicorn.schemas import (
    SchemaValidationError,
    validate_app_state,
    validate_catalog,
)


class TestCatalogSchemaValidation:
    """Test catalog schema validation."""

    def test_valid_catalog_with_digest(self):
        """Test validation of catalog with digest verification."""
        catalog = {
            "config_version": "2.0.0",
            "metadata": {
                "name": "obsidian",
                "display_name": "Obsidian",
                "description": "Note-taking app",
            },
            "source": {
                "type": "github",
                "owner": "obsidianmd",
                "repo": "obsidian-releases",
                "prerelease": False,
            },
            "appimage": {
                "naming": {
                    "template": "",
                    "target_name": "obsidian",
                    "architectures": ["amd64", "x86_64"],
                }
            },
            "verification": {"method": "digest"},
            "icon": {"method": "extraction", "filename": "obsidian.png"},
        }

        # Should not raise
        validate_catalog(catalog, "obsidian")

    def test_valid_catalog_with_checksum_file(self):
        """Test validation of catalog with checksum_file verification."""
        catalog = {
            "config_version": "2.0.0",
            "metadata": {
                "name": "tagspaces",
                "display_name": "TagSpaces",
                "description": "",
            },
            "source": {
                "type": "github",
                "owner": "tagspaces",
                "repo": "tagspaces",
                "prerelease": False,
            },
            "appimage": {
                "naming": {
                    "template": "{repo}-{latest_version}.AppImage",
                    "target_name": "tagspaces",
                    "architectures": ["amd64"],
                }
            },
            "verification": {
                "method": "checksum_file",
                "checksum_file": {
                    "filename": "SHA256SUMS.txt",
                    "algorithm": "sha256",
                },
            },
            "icon": {
                "method": "download",
                "filename": "tagspaces.png",
                "download_url": "https://example.com/icon.png",
            },
        }

        # Should not raise
        validate_catalog(catalog, "tagspaces")

    def test_invalid_config_version(self):
        """Test catalog with wrong config version."""
        catalog = {
            "config_version": "1.0.0",
            "metadata": {"name": "test", "display_name": "Test"},
            "source": {
                "type": "github",
                "owner": "test",
                "repo": "test",
                "prerelease": False,
            },
            "appimage": {
                "naming": {
                    "target_name": "test",
                    "architectures": ["amd64"],
                }
            },
            "verification": {"method": "digest"},
            "icon": {"method": "extraction", "filename": "test.png"},
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_catalog(catalog, "test")

        assert "config_version" in str(exc_info.value)
        assert "2.0.0" in str(exc_info.value)

    def test_missing_required_field(self):
        """Test catalog missing required field."""
        catalog = {
            "config_version": "2.0.0",
            "metadata": {"name": "test", "display_name": "Test"},
            # Missing source
            "appimage": {
                "naming": {
                    "target_name": "test",
                    "architectures": ["amd64"],
                }
            },
            "verification": {"method": "digest"},
            "icon": {"method": "extraction", "filename": "test.png"},
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_catalog(catalog, "test")

        assert "required" in str(exc_info.value).lower()

    def test_invalid_verification_method(self):
        """Test catalog with invalid verification method."""
        catalog = {
            "config_version": "2.0.0",
            "metadata": {"name": "test", "display_name": "Test"},
            "source": {
                "type": "github",
                "owner": "test",
                "repo": "test",
                "prerelease": False,
            },
            "appimage": {
                "naming": {
                    "target_name": "test",
                    "architectures": ["amd64"],
                }
            },
            "verification": {"method": "invalid_method"},
            "icon": {"method": "extraction", "filename": "test.png"},
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_catalog(catalog, "test")

        assert "verification.method" in str(exc_info.value)

    def test_checksum_file_missing_when_required(self):
        """Test catalog with checksum_file method but missing object."""
        catalog = {
            "config_version": "2.0.0",
            "metadata": {"name": "test", "display_name": "Test"},
            "source": {
                "type": "github",
                "owner": "test",
                "repo": "test",
                "prerelease": False,
            },
            "appimage": {
                "naming": {
                    "target_name": "test",
                    "architectures": ["amd64"],
                }
            },
            "verification": {"method": "checksum_file"},
            "icon": {"method": "extraction", "filename": "test.png"},
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_catalog(catalog, "test")

        assert "checksum_file" in str(exc_info.value)

    def test_download_url_missing_when_required(self):
        """Test icon with download method but no download_url."""
        catalog = {
            "config_version": "2.0.0",
            "metadata": {"name": "test", "display_name": "Test"},
            "source": {
                "type": "github",
                "owner": "test",
                "repo": "test",
                "prerelease": False,
            },
            "appimage": {
                "naming": {
                    "target_name": "test",
                    "architectures": ["amd64"],
                }
            },
            "verification": {"method": "digest"},
            "icon": {
                "method": "download",
                "filename": "test.png",
            },
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_catalog(catalog, "test")

        assert "download_url" in str(exc_info.value)


class TestAppStateSchemaValidation:
    """Test app state schema validation."""

    def test_valid_catalog_app_state(self):
        """Test validation of catalog-sourced app state."""
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "obsidian",
            "state": {
                "version": "1.10.6",
                "installed_date": "2025-12-27T10:00:00.000000",
                "installed_path": "/home/user/Applications/obsidian.AppImage",
                "verification": {
                    "passed": True,
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                            "algorithm": "SHA256",
                            "expected": "abc123",
                            "computed": "abc123",
                            "source": "github_api",
                        }
                    ],
                },
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": "/home/user/Applications/icons/obsidian.png",
                },
            },
        }

        # Should not raise
        validate_app_state(app_state, "obsidian")

    def test_valid_url_app_state(self):
        """Test validation of URL-sourced app state."""
        app_state = {
            "config_version": "2.0.0",
            "source": "url",
            "catalog_ref": None,
            "state": {
                "version": "1.0.0",
                "installed_date": "2025-12-27T10:00:00.000000",
                "installed_path": "/home/user/Applications/custom.AppImage",
                "verification": {
                    "passed": False,
                    "methods": [{"type": "skip", "status": "skipped"}],
                },
                "icon": {
                    "installed": False,
                    "method": "none",
                },
            },
            "overrides": {
                "metadata": {
                    "name": "custom",
                    "display_name": "Custom App",
                    "description": "",
                },
                "source": {
                    "type": "github",
                    "owner": "test",
                    "repo": "test",
                    "prerelease": False,
                },
                "appimage": {
                    "naming": {
                        "template": "",
                        "target_name": "custom",
                        "architectures": ["amd64"],
                    }
                },
                "verification": {"method": "skip"},
                "icon": {"method": "extraction", "filename": "custom.png"},
            },
        }

        # Should not raise
        validate_app_state(app_state, "custom")

    def test_catalog_app_cannot_have_overrides(self):
        """Test that catalog apps cannot have overrides."""
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "obsidian",
            "state": {
                "version": "1.10.6",
                "installed_date": "2025-12-27T10:00:00.000000",
                "installed_path": "/home/user/Applications/obsidian.AppImage",
                "verification": {
                    "passed": True,
                    "methods": [{"type": "digest", "status": "passed"}],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
            "overrides": {},  # Should not be present
        }

        with pytest.raises(SchemaValidationError):
            validate_app_state(app_state, "obsidian")

    def test_url_app_must_have_overrides(self):
        """Test that URL apps must have overrides."""
        app_state = {
            "config_version": "2.0.0",
            "source": "url",
            "catalog_ref": None,
            "state": {
                "version": "1.0.0",
                "installed_date": "2025-12-27T10:00:00.000000",
                "installed_path": "/home/user/Applications/custom.AppImage",
                "verification": {
                    "passed": False,
                    "methods": [{"type": "skip", "status": "skipped"}],
                },
                "icon": {"installed": False, "method": "none"},
            },
            # Missing overrides
        }

        with pytest.raises(SchemaValidationError):
            validate_app_state(app_state, "custom")

    def test_catalog_ref_must_be_string_for_catalog_source(self):
        """Test catalog_ref validation for catalog source."""
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": None,  # Should be string
            "state": {
                "version": "1.10.6",
                "installed_date": "2025-12-27T10:00:00.000000",
                "installed_path": "/home/user/Applications/obsidian.AppImage",
                "verification": {
                    "passed": True,
                    "methods": [{"type": "digest", "status": "passed"}],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        with pytest.raises(SchemaValidationError):
            validate_app_state(app_state, "obsidian")

    def test_catalog_ref_must_be_null_for_url_source(self):
        """Test catalog_ref validation for URL source."""
        app_state = {
            "config_version": "2.0.0",
            "source": "url",
            "catalog_ref": "something",  # Should be null
            "state": {
                "version": "1.0.0",
                "installed_date": "2025-12-27T10:00:00.000000",
                "installed_path": "/home/user/Applications/custom.AppImage",
                "verification": {
                    "passed": False,
                    "methods": [{"type": "skip", "status": "skipped"}],
                },
                "icon": {"installed": False, "method": "none"},
            },
            "overrides": {
                "metadata": {"name": "custom", "display_name": "Custom"},
                "source": {
                    "type": "github",
                    "owner": "test",
                    "repo": "test",
                    "prerelease": False,
                },
                "appimage": {
                    "naming": {
                        "target_name": "custom",
                        "architectures": ["amd64"],
                    }
                },
                "verification": {"method": "skip"},
                "icon": {"method": "extraction", "filename": "custom.png"},
            },
        }

        with pytest.raises(SchemaValidationError):
            validate_app_state(app_state, "custom")

    def test_invalid_verification_status(self):
        """Test app state with invalid verification status."""
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "obsidian",
            "state": {
                "version": "1.10.6",
                "installed_date": "2025-12-27T10:00:00.000000",
                "installed_path": "/home/user/Applications/obsidian.AppImage",
                "verification": {
                    "passed": True,
                    "methods": [
                        {
                            "type": "digest",
                            "status": "invalid_status",  # Invalid
                        }
                    ],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(app_state, "obsidian")

        assert "status" in str(exc_info.value)


class TestCatalogV1SchemaValidation:
    """Test v1 catalog schema validation."""

    def test_valid_v1_catalog(self):
        """Test validation of valid v1 catalog."""
        catalog = {
            "owner": "obsidianmd",
            "repo": "obsidian-releases",
            "appimage": {
                "rename": "obsidian",
                "name_template": "{rename}-{latest_version}.AppImage",
                "characteristic_suffix": [""],
            },
            "github": {"repo": True, "prerelease": False},
            "verification": {
                "digest": True,
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            },
            "icon": {"extraction": True, "url": "", "name": "obsidian.png"},
        }

        # Should not raise
        validate_catalog(catalog, "obsidian")

    def test_v1_catalog_missing_required_field(self):
        """Test v1 catalog with missing required field."""
        catalog = {
            "owner": "obsidianmd",
            "repo": "obsidian-releases",
            "appimage": {
                "rename": "obsidian",
                "name_template": "{rename}-{latest_version}.AppImage",
                # Missing characteristic_suffix
            },
            "github": {"repo": True, "prerelease": False},
            "verification": {
                "digest": True,
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            },
            "icon": {"extraction": True, "url": "", "name": "obsidian.png"},
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_catalog(catalog, "obsidian")

        assert "characteristic_suffix" in str(exc_info.value)

    def test_v1_catalog_invalid_hash_type(self):
        """Test v1 catalog with invalid hash type."""
        catalog = {
            "owner": "obsidianmd",
            "repo": "obsidian-releases",
            "appimage": {
                "rename": "obsidian",
                "name_template": "{rename}-{latest_version}.AppImage",
                "characteristic_suffix": [""],
            },
            "github": {"repo": True, "prerelease": False},
            "verification": {
                "digest": True,
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "md5",  # Invalid - not in enum
            },
            "icon": {"extraction": True, "url": "", "name": "obsidian.png"},
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_catalog(catalog, "obsidian")

        assert "checksum_hash_type" in str(exc_info.value)


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
                "digest": "sha256:162d753076d0610e4dccfdccf391c13af5fcb557ba7574b77f0e90ac3c522b1c",
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
                "digest": "sha256:162d753076d0610e4dccfdccf391c13af5fcb557ba7574b77f0e90ac3c522b1c",
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
                "digest": "sha256:162d753076d0610e4dccfdccf391c13af5fcb557ba7574b77f0e90ac3c522b1c",
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
