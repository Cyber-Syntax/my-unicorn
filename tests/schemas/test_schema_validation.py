"""Tests for JSON schema validation."""

import pytest

from my_unicorn.config.schemas import SchemaValidationError, validate_app_state

# NOTE: Catalog validation tests removed - catalogs are bundled and trusted.
# Developers ensure catalog correctness before release.
# Simple version checks are done at runtime instead of full schema validation.


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


class TestVerificationMethodTypeValidation:
    """Test schema validation for verification method types.

    These tests ensure invalid method types (like 'checksum_file_0',
    'checksum_file_1') raise SchemaValidationError, providing regression
    protection for Issue 4.
    """

    @pytest.fixture
    def valid_app_state_template(self) -> dict:
        """Return a valid app state that can be modified for tests."""
        return {
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
                        }
                    ],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

    def test_valid_method_type_digest(
        self, valid_app_state_template: dict
    ) -> None:
        """Test validation passes with 'digest' method type."""
        valid_app_state_template["state"]["verification"]["methods"] = [
            {"type": "digest", "status": "passed", "algorithm": "SHA256"}
        ]

        validate_app_state(valid_app_state_template, "obsidian")

    def test_valid_method_type_checksum_file(
        self, valid_app_state_template: dict
    ) -> None:
        """Test validation passes with 'checksum_file' method type."""
        valid_app_state_template["state"]["verification"]["methods"] = [
            {
                "type": "checksum_file",
                "status": "passed",
                "filename": "SHA256SUMS.txt",
            }
        ]

        validate_app_state(valid_app_state_template, "obsidian")

    def test_valid_method_type_skip(
        self, valid_app_state_template: dict
    ) -> None:
        """Test validation passes with 'skip' method type."""
        valid_app_state_template["state"]["verification"]["methods"] = [
            {"type": "skip", "status": "skipped"}
        ]
        valid_app_state_template["state"]["verification"]["passed"] = False

        validate_app_state(valid_app_state_template, "obsidian")

    def test_invalid_method_type_checksum_file_0(
        self, valid_app_state_template: dict
    ) -> None:
        """Test validation fails with indexed 'checksum_file_0' type.

        This is the regression test for Issue 4 - indexed checksum method
        types should never be persisted.
        """
        valid_app_state_template["state"]["verification"]["methods"] = [
            {
                "type": "checksum_file_0",
                "status": "passed",
                "filename": "SHA256SUMS.txt",
            }
        ]

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(valid_app_state_template, "obsidian")

        assert "type" in str(exc_info.value)

    def test_invalid_method_type_checksum_file_1(
        self, valid_app_state_template: dict
    ) -> None:
        """Test validation fails with indexed 'checksum_file_1' type."""
        valid_app_state_template["state"]["verification"]["methods"] = [
            {
                "type": "checksum_file_1",
                "status": "passed",
                "filename": "SHA256SUMS.txt",
            }
        ]

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(valid_app_state_template, "obsidian")

        assert "type" in str(exc_info.value)

    def test_invalid_method_type_arbitrary_string(
        self, valid_app_state_template: dict
    ) -> None:
        """Test validation fails with arbitrary invalid type string."""
        valid_app_state_template["state"]["verification"]["methods"] = [
            {"type": "invalid_type", "status": "passed"}
        ]

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(valid_app_state_template, "obsidian")

        assert "type" in str(exc_info.value)

    def test_invalid_method_type_empty_string(
        self, valid_app_state_template: dict
    ) -> None:
        """Test validation fails with empty string type."""
        valid_app_state_template["state"]["verification"]["methods"] = [
            {"type": "", "status": "passed"}
        ]

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(valid_app_state_template, "obsidian")

        assert "type" in str(exc_info.value)

    def test_invalid_method_type_numeric_suffix_pattern(
        self, valid_app_state_template: dict
    ) -> None:
        """Test validation fails with numeric suffix pattern like 'digest_2'.

        Ensures indexed types with other base names also fail.
        """
        valid_app_state_template["state"]["verification"]["methods"] = [
            {"type": "digest_2", "status": "passed"}
        ]

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(valid_app_state_template, "obsidian")

        assert "type" in str(exc_info.value)

    def test_full_app_state_with_invalid_method_type_fails(self) -> None:
        """Test complete app state with invalid method type fails validation.

        This tests the full integration path to ensure invalid method types
        are caught during app state persistence.
        """
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "legcord",
            "state": {
                "version": "1.0.8",
                "installed_date": "2026-02-05T10:00:00.000000",
                "installed_path": "/home/user/Applications/legcord.AppImage",
                "verification": {
                    "passed": True,
                    "overall_passed": True,
                    "actual_method": "checksum_file",
                    "methods": [
                        {
                            "type": "checksum_file_0",  # Invalid indexed type
                            "status": "passed",
                            "algorithm": "sha256",
                            "filename": "latest-linux.yml",
                        }
                    ],
                },
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": "/home/user/Applications/icons/legcord.png",
                },
            },
        }

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(app_state, "legcord")

        assert "type" in str(exc_info.value)

    def test_mixed_valid_and_invalid_method_types_fails(
        self, valid_app_state_template: dict
    ) -> None:
        """Test that having one invalid type among valid types fails."""
        valid_app_state_template["state"]["verification"]["methods"] = [
            {"type": "digest", "status": "passed"},
            {"type": "checksum_file_1", "status": "passed"},  # Invalid
        ]

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_app_state(valid_app_state_template, "obsidian")

        assert "type" in str(exc_info.value)


# NOTE: Catalog V1 schema validation tests removed.
# Catalogs are bundled and trusted - no runtime validation needed.


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


# NOTE: Catalog files validation test removed.
# Catalogs are bundled and trusted - no runtime validation needed.
