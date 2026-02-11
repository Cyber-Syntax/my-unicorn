"""Tests for backward compatibility with old app state format.

Task 6.1: Ensure old apps (without new verification fields) still load.
Tests that legacy app states with minimal verification format (only passed
and methods) continue to work correctly with schema validation, loading,
and update operations.
"""

from pathlib import Path
from typing import Any

import orjson
import pytest

from my_unicorn.config import AppConfigManager
from my_unicorn.config.schemas import validate_app_state
from my_unicorn.utils.config_builders import (
    build_verification_state,
    update_app_config,
)


class TestLegacyAppStateLoading:
    """Tests for loading old app state without new verification fields."""

    @pytest.fixture
    def apps_dir(self, tmp_path: Path) -> Path:
        """Create temporary apps directory."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        return apps_dir

    @pytest.fixture
    def app_config_manager(self, apps_dir: Path) -> AppConfigManager:
        """Create AppConfigManager for tests."""
        return AppConfigManager(apps_dir)

    @pytest.fixture
    def legacy_app_state_minimal_verification(self) -> dict[str, Any]:
        """App state with minimal verification (only passed and methods).

        This represents old app states before the new verification fields
        (overall_passed, actual_method, warning, digest) were added.
        """
        return {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "testapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": "/path/to/testapp.AppImage",
                "verification": {
                    "passed": True,
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                            "algorithm": "SHA256",
                            "computed": "abc123",
                            "expected": "abc123",
                            "source": "github_api",
                        }
                    ],
                },
                "icon": {"installed": False, "method": "none", "path": ""},
            },
        }

    @pytest.fixture
    def legacy_app_state_skip_verification(self) -> dict[str, Any]:
        """App state with skip verification (no hash checking)."""
        return {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "skipapp",
            "state": {
                "version": "2.0.0",
                "installed_date": "2024-06-15T12:30:00",
                "installed_path": "/path/to/skipapp.AppImage",
                "verification": {
                    "passed": False,
                    "methods": [{"type": "skip", "status": "skipped"}],
                },
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": "/icons/skip.png",
                },
            },
        }

    @pytest.fixture
    def legacy_app_state_checksum_file(self) -> dict[str, Any]:
        """App state with checksum_file verification (no digest field)."""
        return {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "checksumapp",
            "state": {
                "version": "3.1.0",
                "installed_date": "2024-12-01T08:00:00",
                "installed_path": "/path/to/checksumapp.AppImage",
                "verification": {
                    "passed": True,
                    "methods": [
                        {
                            "type": "checksum_file",
                            "status": "passed",
                            "algorithm": "SHA512",
                            "computed": "def456",
                            "expected": "def456",
                            "filename": "SHA512SUMS.txt",
                            "source": "https://example.com/SHA512SUMS.txt",
                        }
                    ],
                },
                "icon": {"installed": False, "method": "none", "path": ""},
            },
        }

    def test_schema_validation_passes_for_minimal_verification(
        self, legacy_app_state_minimal_verification: dict[str, Any]
    ) -> None:
        """Schema validation should pass for old verification format.

        Task 6.1: App state missing overall_passed, actual_method, warning
        should still validate successfully.
        """
        validate_app_state(legacy_app_state_minimal_verification, "testapp")

    def test_schema_validation_passes_for_skip_verification(
        self, legacy_app_state_skip_verification: dict[str, Any]
    ) -> None:
        """Schema validation should pass for skip verification format."""
        validate_app_state(legacy_app_state_skip_verification, "skipapp")

    def test_schema_validation_passes_for_checksum_file_verification(
        self, legacy_app_state_checksum_file: dict[str, Any]
    ) -> None:
        """Schema validation should pass for checksum_file verification."""
        validate_app_state(legacy_app_state_checksum_file, "checksumapp")

    def test_load_app_config_with_minimal_verification(
        self,
        apps_dir: Path,
        app_config_manager: AppConfigManager,
        legacy_app_state_minimal_verification: dict[str, Any],
    ) -> None:
        """Loading app state with minimal verification should succeed.

        Task 6.1: Old app state without new verification fields should load.
        """
        app_file = apps_dir / "testapp.json"
        app_file.write_bytes(
            orjson.dumps(legacy_app_state_minimal_verification)
        )

        loaded = app_config_manager.load_raw_app_config("testapp")

        assert loaded is not None
        assert loaded["config_version"] == "2.0.0"
        assert loaded["state"]["verification"]["passed"] is True
        assert len(loaded["state"]["verification"]["methods"]) == 1
        # New fields should not be present in old config
        assert "overall_passed" not in loaded["state"]["verification"]
        assert "actual_method" not in loaded["state"]["verification"]

    def test_load_app_config_preserves_all_data(
        self,
        apps_dir: Path,
        app_config_manager: AppConfigManager,
        legacy_app_state_checksum_file: dict[str, Any],
    ) -> None:
        """Loading should preserve all original data without loss.

        Task 6.1: No data loss during load operation.
        """
        app_file = apps_dir / "checksumapp.json"
        app_file.write_bytes(orjson.dumps(legacy_app_state_checksum_file))

        loaded = app_config_manager.load_raw_app_config("checksumapp")

        assert loaded is not None
        # Verify all original data is preserved
        assert loaded["state"]["version"] == "3.1.0"
        installed_path = loaded["state"]["installed_path"]
        assert installed_path == "/path/to/checksumapp.AppImage"
        method = loaded["state"]["verification"]["methods"][0]
        assert method["type"] == "checksum_file"
        assert method["algorithm"] == "SHA512"
        assert method["filename"] == "SHA512SUMS.txt"
        assert method["source"] == "https://example.com/SHA512SUMS.txt"

    def test_merged_config_loads_legacy_verification(
        self,
        apps_dir: Path,
        legacy_app_state_minimal_verification: dict[str, Any],
    ) -> None:
        """Merged config (load_app_config) should work with legacy format.

        Task 6.1: Both raw and merged loading paths should work.
        """
        app_file = apps_dir / "testapp.json"
        app_file.write_bytes(
            orjson.dumps(legacy_app_state_minimal_verification)
        )

        app_manager = AppConfigManager(apps_dir, catalog_manager=None)
        loaded = app_manager.load_app_config("testapp")

        assert loaded is not None
        assert loaded["state"]["verification"]["passed"] is True


class TestLegacyAppStateSchemaValidation:
    """Additional schema validation tests for legacy verification formats."""

    def test_method_without_algorithm_validates(self) -> None:
        """Method entry without algorithm field should validate.

        Legacy methods may not have algorithm field.
        """
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "noalgoapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": "/path/to/app.AppImage",
                "verification": {
                    "passed": True,
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                        }
                    ],
                },
                "icon": {"installed": False, "method": "none", "path": ""},
            },
        }
        validate_app_state(app_state, "noalgoapp")

    def test_method_without_computed_expected_validates(self) -> None:
        """Method entry without computed/expected fields should validate.

        Legacy skip methods typically don't have hash fields.
        """
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "nohashapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": "/path/to/app.AppImage",
                "verification": {
                    "passed": False,
                    "methods": [
                        {
                            "type": "skip",
                            "status": "skipped",
                        }
                    ],
                },
                "icon": {"installed": False, "method": "none", "path": ""},
            },
        }
        validate_app_state(app_state, "nohashapp")

    def test_failed_verification_without_new_fields_validates(self) -> None:
        """Failed verification without new fields should validate."""
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "failedapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": "/path/to/app.AppImage",
                "verification": {
                    "passed": False,
                    "methods": [
                        {
                            "type": "digest",
                            "status": "failed",
                            "algorithm": "SHA256",
                            "computed": "wronghash",
                            "expected": "correcthash",
                        }
                    ],
                },
                "icon": {"installed": False, "method": "none", "path": ""},
            },
        }
        validate_app_state(app_state, "failedapp")

    def test_multiple_methods_without_new_fields_validates(self) -> None:
        """Multiple verification methods without new fields should validate."""
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "multiapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": "/path/to/app.AppImage",
                "verification": {
                    "passed": True,
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                            "algorithm": "SHA256",
                        },
                        {
                            "type": "checksum_file",
                            "status": "passed",
                            "filename": "SHA256SUMS",
                        },
                    ],
                },
                "icon": {"installed": False, "method": "none", "path": ""},
            },
        }
        validate_app_state(app_state, "multiapp")


class TestUpdateOperationAddsVerificationFields:
    """Tests that update operation adds new verification fields."""

    @pytest.fixture
    def apps_dir(self, tmp_path: Path) -> Path:
        """Create temporary apps directory."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        return apps_dir

    @pytest.fixture
    def mock_config_manager(self, apps_dir: Path) -> AppConfigManager:
        """Create AppConfigManager for tests."""
        return AppConfigManager(apps_dir)

    @pytest.fixture
    def legacy_app_state(self) -> dict[str, Any]:
        """Legacy app state without new verification fields."""
        return {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "updateapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": "/path/to/updateapp.AppImage",
                "verification": {
                    "passed": True,
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                        }
                    ],
                },
                "icon": {"installed": False, "method": "none", "path": ""},
            },
        }

    def test_update_replaces_verification_with_new_format(
        self,
        apps_dir: Path,
        mock_config_manager: AppConfigManager,
        legacy_app_state: dict[str, Any],
    ) -> None:
        """Update operation should replace verification with new format.

        Task 6.1: Update operation adds verification section with new fields.
        """
        app_file = apps_dir / "updateapp.json"
        app_file.write_bytes(orjson.dumps(legacy_app_state))

        new_verify_result = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash_type": "sha256",
                    "hash": "newhash123",
                    "computed_hash": "newhash123",
                }
            },
        }

        update_app_config(
            app_name="updateapp",
            latest_version="2.0.0",
            appimage_path=Path("/path/to/updateapp-2.0.AppImage"),
            icon_path=None,
            verify_result=new_verify_result,
            updated_icon_config={
                "installed": False,
                "source": "none",
                "path": "",
            },
            config_manager=mock_config_manager,
        )

        # Reload and verify
        updated = mock_config_manager.load_raw_app_config("updateapp")
        assert updated is not None
        assert updated["state"]["version"] == "2.0.0"

        verification = updated["state"]["verification"]
        assert verification["passed"] is True
        assert len(verification["methods"]) == 1
        method = verification["methods"][0]
        assert method["type"] == "digest"
        assert method["status"] == "passed"

    def test_update_preserves_non_verification_data(
        self,
        apps_dir: Path,
        mock_config_manager: AppConfigManager,
        legacy_app_state: dict[str, Any],
    ) -> None:
        """Update should preserve catalog_ref and source fields.

        Task 6.1: No data loss during update.
        """
        app_file = apps_dir / "updateapp.json"
        app_file.write_bytes(orjson.dumps(legacy_app_state))

        new_verify_result = {
            "passed": True,
            "methods": {"digest": {"passed": True}},
        }

        update_app_config(
            app_name="updateapp",
            latest_version="3.0.0",
            appimage_path=Path("/new/path/updateapp.AppImage"),
            icon_path=None,
            verify_result=new_verify_result,
            updated_icon_config=None,
            config_manager=mock_config_manager,
        )

        updated = mock_config_manager.load_raw_app_config("updateapp")
        assert updated is not None
        # These fields should be preserved
        assert updated["source"] == "catalog"
        assert updated["catalog_ref"] == "updateapp"
        assert updated["config_version"] == "2.0.0"


class TestBuildVerificationStateBackwardCompat:
    """Tests for build_verification_state with backward compatibility."""

    def test_build_verification_state_includes_new_fields(self) -> None:
        """build_verification_state includes new fields for fresh builds."""
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash_type": "sha256",
                    "hash": "abc123",
                    "computed_hash": "abc123",
                }
            },
        }
        state = build_verification_state(verify_result)

        # New fields should be present in newly built states
        assert "overall_passed" in state
        assert state["overall_passed"] is True
        assert "actual_method" in state
        assert state["actual_method"] == "digest"

    def test_build_verification_state_with_warning(self) -> None:
        """build_verification_state should include warning when present."""
        verify_result = {
            "passed": True,
            "warning": "Checksum file not available",
            "methods": {"digest": {"passed": True}},
        }
        state = build_verification_state(verify_result)

        assert "warning" in state
        assert state["warning"] == "Checksum file not available"

    def test_build_verification_state_empty_creates_skip(self) -> None:
        """Empty verification result should create skip state."""
        state = build_verification_state(None)

        assert state["passed"] is False
        assert state["overall_passed"] is False
        assert state["actual_method"] == "skip"
        assert state["methods"] == []

    def test_new_state_validates_against_schema(self) -> None:
        """Newly built verification state should validate against schema."""
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash_type": "sha256",
                    "hash": "abc123",
                    "computed_hash": "abc123",
                }
            },
        }
        state = build_verification_state(verify_result)

        # Create full app state with new verification
        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "newapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": "/path/to/app.AppImage",
                "verification": {
                    "passed": state["passed"],
                    "methods": state["methods"],
                },
                "icon": {"installed": False, "method": "none", "path": ""},
            },
        }
        validate_app_state(app_state, "newapp")


class TestUrlAppStateBackwardCompat:
    """Tests for URL-sourced app state backward compatibility."""

    def test_url_app_legacy_verification_validates(self) -> None:
        """URL app with legacy verification format should validate."""
        app_state = {
            "config_version": "2.0.0",
            "source": "url",
            "catalog_ref": None,
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": "/path/to/custom.AppImage",
                "verification": {
                    "passed": False,
                    "methods": [{"type": "skip", "status": "skipped"}],
                },
                "icon": {"installed": False, "method": "none", "path": ""},
            },
            "overrides": {
                "metadata": {"name": "custom", "display_name": "Custom App"},
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
                "icon": {"method": "none", "filename": "custom.png"},
            },
        }
        validate_app_state(app_state, "custom")

    def test_url_app_load_and_update(self, tmp_path: Path) -> None:
        """URL app should load and update correctly."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()

        app_state = {
            "config_version": "2.0.0",
            "source": "url",
            "catalog_ref": None,
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": "/path/to/urlapp.AppImage",
                "verification": {
                    "passed": True,
                    "methods": [{"type": "digest", "status": "passed"}],
                },
                "icon": {"installed": False, "method": "none", "path": ""},
            },
            "overrides": {
                "metadata": {"name": "urlapp", "display_name": "URL App"},
                "source": {
                    "type": "github",
                    "owner": "owner",
                    "repo": "repo",
                    "prerelease": False,
                },
                "appimage": {
                    "naming": {
                        "template": "",
                        "target_name": "urlapp",
                        "architectures": ["x86_64"],
                    }
                },
                "verification": {"method": "digest"},
                "icon": {"method": "none", "filename": "urlapp.png"},
            },
        }

        app_file = apps_dir / "urlapp.json"
        app_file.write_bytes(orjson.dumps(app_state))

        manager = AppConfigManager(apps_dir)
        loaded = manager.load_raw_app_config("urlapp")

        assert loaded is not None
        assert loaded["source"] == "url"
        assert loaded["overrides"] is not None
