"""Tests for verification method type enum validation."""

import pytest

from my_unicorn.config.schemas import SchemaValidationError, validate_app_state


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
