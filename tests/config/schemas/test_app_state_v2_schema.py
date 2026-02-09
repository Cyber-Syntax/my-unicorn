"""Tests for app state v2 schema validation."""

import pytest

from my_unicorn.config.schemas import SchemaValidationError, validate_app_state


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

    def test_valid_verification_with_overall_passed(self):
        """Test validation passes with optional overall_passed field."""
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
                    "overall_passed": True,
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                            "algorithm": "SHA256",
                            "expected": "abc123",
                            "computed": "abc123",
                        }
                    ],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "obsidian")

    def test_valid_verification_with_actual_method(self):
        """Test validation passes with optional actual_method field."""
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
                    "actual_method": "digest",
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                        }
                    ],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "obsidian")

    def test_valid_verification_actual_method_checksum_file(self):
        """Test validation passes with actual_method set to checksum_file."""
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
                    "actual_method": "checksum_file",
                    "methods": [
                        {
                            "type": "checksum_file",
                            "status": "passed",
                            "filename": "SHA256SUMS.txt",
                        }
                    ],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "obsidian")

    def test_valid_verification_actual_method_skip(self):
        """Test validation passes with actual_method set to skip."""
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "obsidian",
            "state": {
                "version": "1.10.6",
                "installed_date": "2025-12-27T10:00:00.000000",
                "installed_path": "/home/user/Applications/obsidian.AppImage",
                "verification": {
                    "passed": False,
                    "actual_method": "skip",
                    "methods": [{"type": "skip", "status": "skipped"}],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "obsidian")

    def test_invalid_actual_method_enum(self):
        """Test validation fails with invalid actual_method enum value."""
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
                    "actual_method": "invalid_method",
                    "methods": [{"type": "digest", "status": "passed"}],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(app_state, "obsidian")

        assert "actual_method" in str(exc_info.value)

    def test_valid_verification_with_warning(self):
        """Test validation passes with optional warning field."""
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
                    "warning": "Checksum file not found, using digest",
                    "methods": [{"type": "digest", "status": "passed"}],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "obsidian")

    def test_valid_method_with_digest_field(self):
        """Test validation passes with digest field in method item."""
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
                            "digest": "sha256:abc123def456",
                            "source": "github_api",
                        }
                    ],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "obsidian")

    def test_valid_verification_all_new_fields(self):
        """Test validation passes with all new optional fields combined."""
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
                    "overall_passed": True,
                    "actual_method": "digest",
                    "warning": "Some warning message",
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                            "algorithm": "SHA256",
                            "digest": "sha256:abc123",
                            "source": "github_api",
                        }
                    ],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "obsidian")

    def test_backward_compatible_verification_without_new_fields(self):
        """Test validation passes for legacy verification format."""
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
                            "computed": "abc123",
                            "expected": "abc123",
                        }
                    ],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "obsidian")
