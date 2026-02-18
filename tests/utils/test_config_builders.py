"""Tests for configuration builder utilities."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from my_unicorn.config.schemas import validate_app_state
from my_unicorn.core.github import Asset, Release
from my_unicorn.utils.config_builders import (
    build_method_entry,
    build_overrides_from_template,
    build_verification_state,
    create_app_config_v2,
    get_stored_hash,
    update_app_config,
)


class TestBuildMethodEntry:
    """Test build_method_entry function."""

    def test_build_method_entry_with_dict_result_digest(self):
        """Test building method entry from dict result (digest type)."""
        result = {
            "passed": True,
            "hash_type": "sha256",
            "hash": "abc123def456",
            "computed_hash": "abc123def456",
        }
        entry = build_method_entry("digest", result)

        assert entry["type"] == "digest"
        assert entry["status"] == "passed"
        assert entry["algorithm"] == "SHA256"
        assert entry["expected"] == "abc123def456"
        assert entry["computed"] == "abc123def456"
        assert entry["source"] == "github_api"

    def test_build_method_entry_with_dict_result_checksum_file(self):
        """Test building method entry from dict result (checksum_file)."""
        result = {
            "passed": True,
            "hash_type": "sha512",
            "hash": "xyz789",
            "computed_hash": "xyz789",
            "url": "https://example.com/checksums.txt",
        }
        entry = build_method_entry("checksum_file", result)

        assert entry["type"] == "checksum_file"
        assert entry["status"] == "passed"
        assert entry["algorithm"] == "SHA512"
        assert entry["expected"] == "xyz789"
        assert entry["computed"] == "xyz789"
        assert entry["source"] == "https://example.com/checksums.txt"

    def test_build_method_entry_with_failed_result(self):
        """Test building method entry from failed verification."""
        result = {
            "passed": False,
            "hash_type": "sha256",
            "hash": "expected123",
            "computed_hash": "actual456",
        }
        entry = build_method_entry("digest", result)

        assert entry["type"] == "digest"
        assert entry["status"] == "failed"
        assert entry["algorithm"] == "SHA256"
        assert entry["expected"] == "expected123"
        assert entry["computed"] == "actual456"

    def test_build_method_entry_with_bool_result_true(self):
        """Test building method entry from simple boolean (True)."""
        entry = build_method_entry("digest", True)

        assert entry["type"] == "digest"
        assert entry["status"] == "passed"
        assert "algorithm" not in entry

    def test_build_method_entry_with_bool_result_false(self):
        """Test building method entry from simple boolean (False)."""
        entry = build_method_entry("checksum_file", False)

        assert entry["type"] == "checksum_file"
        assert entry["status"] == "failed"
        assert "algorithm" not in entry

    def test_build_method_entry_with_missing_hash_type(self):
        """Test building method entry when hash_type is missing."""
        result = {
            "passed": True,
            "hash": "abc123",
            "computed_hash": "abc123",
        }
        entry = build_method_entry("digest", result)

        assert entry["algorithm"] == "SHA256"  # Default

    def test_build_method_entry_normalizes_checksum_file_0(self):
        """Test that checksum_file_0 is normalized to checksum_file."""
        result = {
            "passed": True,
            "hash_type": "sha256",
            "hash": "abc123",
            "computed_hash": "abc123",
            "url": "https://example.com/SHA256SUMS",
        }
        entry = build_method_entry("checksum_file_0", result)

        assert entry["type"] == "checksum_file"
        assert entry["status"] == "passed"

    def test_build_method_entry_normalizes_checksum_file_1(self):
        """Test that checksum_file_1 is normalized to checksum_file."""
        result = {
            "passed": True,
            "hash_type": "sha512",
            "hash": "def456",
            "computed_hash": "def456",
            "url": "https://example.com/SHA512SUMS",
        }
        entry = build_method_entry("checksum_file_1", result)

        assert entry["type"] == "checksum_file"
        assert entry["status"] == "passed"

    def test_build_method_entry_normalizes_checksum_file_with_high_index(self):
        """Test that checksum_file_99 is normalized to checksum_file."""
        entry = build_method_entry("checksum_file_99", True)

        assert entry["type"] == "checksum_file"
        assert entry["status"] == "passed"

    def test_build_method_entry_keeps_plain_checksum_file_unchanged(self):
        """Test that plain checksum_file type remains unchanged."""
        result = {
            "passed": True,
            "hash_type": "sha256",
            "hash": "abc123",
            "computed_hash": "abc123",
            "url": "https://example.com/checksums.txt",
        }
        entry = build_method_entry("checksum_file", result)

        assert entry["type"] == "checksum_file"

    def test_build_method_entry_keeps_digest_unchanged(self):
        """Test that digest method type remains unchanged."""
        result = {"passed": True, "hash_type": "sha256"}
        entry = build_method_entry("digest", result)

        assert entry["type"] == "digest"

    def test_build_method_entry_keeps_skip_unchanged(self):
        """Test that skip method type remains unchanged."""
        entry = build_method_entry("skip", True)

        assert entry["type"] == "skip"


class TestBuildVerificationState:
    """Test build_verification_state function."""

    def test_build_verification_state_with_valid_result(self):
        """Test building verification state from valid result."""
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

        assert state["passed"] is True
        assert state["actual_method"] == "digest"
        assert len(state["methods"]) == 1
        assert state["methods"][0]["type"] == "digest"
        assert state["methods"][0]["status"] == "passed"

    def test_build_verification_state_with_multiple_methods(self):
        """Test building verification state with multiple methods."""
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {"passed": True, "hash_type": "sha256"},
                "checksum_file": {
                    "passed": True,
                    "hash_type": "sha512",
                    "url": "https://example.com/sums",
                },
            },
        }
        state = build_verification_state(verify_result)

        assert state["passed"] is True
        assert state["actual_method"] == "digest"  # First method
        assert len(state["methods"]) == 2

    def test_build_verification_state_with_none_result(self):
        """Test building verification state when result is None."""
        state = build_verification_state(None)

        assert state["passed"] is False
        assert state["actual_method"] == "skip"
        assert state["methods"] == []

    def test_build_verification_state_with_empty_methods(self):
        """Test building verification state with empty methods dict."""
        verify_result = {"passed": False, "methods": {}}
        state = build_verification_state(verify_result)

        assert state["passed"] is False
        assert state["actual_method"] == "skip"
        assert state["methods"] == []

    def test_build_verification_state_with_failed_verification(self):
        """Test building verification state when verification failed."""
        verify_result = {
            "passed": False,
            "methods": {
                "digest": {
                    "passed": False,
                    "hash_type": "sha256",
                    "hash": "expected",
                    "computed_hash": "actual",
                }
            },
        }
        state = build_verification_state(verify_result)

        assert state["passed"] is False
        assert state["actual_method"] == "digest"
        assert state["methods"][0]["status"] == "failed"

    def test_build_verification_state_includes_overall_passed(self):
        """Test that build_verification_state always includes overall_passed.

        Schema compatibility test: overall_passed is now a valid optional field
        in app_state_v2.schema.json and config_builders must include it.
        """
        verify_result = {
            "passed": True,
            "methods": {"digest": {"passed": True, "hash_type": "sha256"}},
        }
        state = build_verification_state(verify_result)

        assert "overall_passed" in state
        assert state["overall_passed"] is True
        assert state["overall_passed"] == state["passed"]

    def test_build_verification_state_includes_actual_method(self):
        """Test that build_verification_state always includes actual_method.

        Schema compatibility test: actual_method is now a valid optional
        field in app_state_v2.schema.json with enum values: digest,
        checksum_file, skip.
        """
        verify_result = {
            "passed": True,
            "methods": {"digest": {"passed": True, "hash_type": "sha256"}},
        }
        state = build_verification_state(verify_result)

        assert "actual_method" in state
        assert state["actual_method"] in ("digest", "checksum_file", "skip")

    def test_build_verification_state_actual_method_prefers_digest(self):
        """Test actual_method prefers digest over checksum_file."""
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {"passed": True, "hash_type": "sha256"},
                "checksum_file": {
                    "passed": True,
                    "hash_type": "sha512",
                    "url": "https://example.com/SHA512SUMS.txt",
                },
            },
        }
        state = build_verification_state(verify_result)

        assert state["actual_method"] == "digest"

    def test_build_verification_state_empty_returns_skip(self):
        """Test actual_method is 'skip' when no verification data available."""
        state = build_verification_state(None)

        assert state["actual_method"] == "skip"
        assert state["overall_passed"] is False
        assert state["passed"] is False

    def test_build_verification_state_with_warning(self):
        """Test that warnings are included when present in verify result.

        Schema compatibility test: warning is now a valid optional field
        in app_state_v2.schema.json.
        """
        verify_result = {
            "passed": True,
            "warning": "Hash algorithm is deprecated",
            "methods": {"digest": {"passed": True, "hash_type": "sha256"}},
        }
        state = build_verification_state(verify_result)

        assert "warning" in state
        assert state["warning"] == "Hash algorithm is deprecated"


class TestBuildVerificationStateSchemaCompatibility:
    """Test build_verification_state output matches the app state schema.

    These tests validate the contract between config_builders and the schema.
    They ensure that verification objects created by config_builders will pass
    schema validation when saved as part of app state.
    """

    def test_verification_state_validates_against_schema(self):
        """Test that build_verification_state output passes schema validation.

        This is the primary integration test ensuring config_builders output
        is compatible with app_state_v2.schema.json.
        """
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash_type": "sha256",
                    "hash": "abc123def456",
                    "computed_hash": "abc123def456",
                }
            },
        }
        state = build_verification_state(verify_result)

        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "testapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2026-02-04T10:00:00.000000",
                "installed_path": "/home/user/Applications/testapp.AppImage",
                "verification": {
                    "passed": state["passed"],
                    "overall_passed": state["overall_passed"],
                    "actual_method": state["actual_method"],
                    "methods": state["methods"],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "testapp")

    def test_verification_state_with_checksum_file_validates(self):
        """Test checksum_file verification state passes schema validation."""
        verify_result = {
            "passed": True,
            "methods": {
                "checksum_file": {
                    "passed": True,
                    "hash_type": "sha512",
                    "hash": "xyz789",
                    "computed_hash": "xyz789",
                    "url": "https://example.com/SHA512SUMS.txt",
                }
            },
        }
        state = build_verification_state(verify_result)

        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "testapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2026-02-04T10:00:00.000000",
                "installed_path": "/home/user/Applications/testapp.AppImage",
                "verification": {
                    "passed": state["passed"],
                    "overall_passed": state["overall_passed"],
                    "actual_method": state["actual_method"],
                    "methods": state["methods"],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "testapp")

    def test_verification_state_with_warning_validates(self):
        """Test verification state with warning passes schema validation."""
        verify_result = {
            "passed": True,
            "warning": "Checksum algorithm SHA1 is deprecated",
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

        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "testapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2026-02-04T10:00:00.000000",
                "installed_path": "/home/user/Applications/testapp.AppImage",
                "verification": {
                    "passed": state["passed"],
                    "overall_passed": state["overall_passed"],
                    "actual_method": state["actual_method"],
                    "warning": state["warning"],
                    "methods": state["methods"],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "testapp")

    def test_empty_verification_state_validates(self):
        """Test empty verification state passes schema validation."""
        state = build_verification_state(None)

        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "testapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2026-02-04T10:00:00.000000",
                "installed_path": "/home/user/Applications/testapp.AppImage",
                "verification": {
                    "passed": state["passed"],
                    "methods": [{"type": "skip", "status": "skipped"}],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "testapp")

    def test_multi_method_verification_state_validates(self):
        """Test verification state with multiple methods passes validation."""
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash_type": "sha256",
                    "hash": "abc123",
                    "computed_hash": "abc123",
                },
                "checksum_file": {
                    "passed": True,
                    "hash_type": "sha512",
                    "hash": "xyz789",
                    "computed_hash": "xyz789",
                    "url": "https://example.com/SHA512SUMS.txt",
                },
            },
        }
        state = build_verification_state(verify_result)

        app_state = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "testapp",
            "state": {
                "version": "1.0.0",
                "installed_date": "2026-02-04T10:00:00.000000",
                "installed_path": "/home/user/Applications/testapp.AppImage",
                "verification": {
                    "passed": state["passed"],
                    "overall_passed": state["overall_passed"],
                    "actual_method": state["actual_method"],
                    "methods": state["methods"],
                },
                "icon": {"installed": True, "method": "extraction"},
            },
        }

        validate_app_state(app_state, "testapp")


class TestBuildOverridesFromTemplate:
    """Test build_overrides_from_template function."""

    def test_build_overrides_with_complete_template(self):
        """Test building overrides from complete app config template."""
        template = {
            "source": {
                "owner": "myowner",
                "repo": "myrepo",
                "prerelease": True,
            },
            "appimage": {
                "naming": {
                    "template": "{repo}-{version}.AppImage",
                    "target_name": "MyApp.AppImage",
                }
            },
            "verification": {"method": "digest"},
            "icon": {"method": "extraction", "filename": "app.png"},
        }
        overrides = build_overrides_from_template(template)

        assert overrides["metadata"]["name"] == "myrepo"
        assert overrides["source"]["owner"] == "myowner"
        assert overrides["source"]["repo"] == "myrepo"
        assert overrides["source"]["prerelease"] is True
        assert (
            overrides["appimage"]["naming"]["template"]
            == "{repo}-{version}.AppImage"
        )
        assert overrides["verification"]["method"] == "digest"
        assert overrides["icon"]["method"] == "extraction"
        assert overrides["icon"]["filename"] == "app.png"

    def test_build_overrides_with_minimal_template(self):
        """Test building overrides from minimal template with defaults."""
        template = {"source": {"owner": "foo", "repo": "bar"}}
        overrides = build_overrides_from_template(template)

        assert overrides["source"]["owner"] == "foo"
        assert overrides["source"]["repo"] == "bar"
        assert overrides["source"]["prerelease"] is False  # Default
        assert overrides["verification"]["method"] == "skip"  # Default
        assert overrides["icon"]["method"] == "extraction"  # Default

    def test_build_overrides_with_empty_template(self):
        """Test building overrides from empty template."""
        template = {}
        overrides = build_overrides_from_template(template)

        assert overrides["source"]["owner"] == ""
        assert overrides["source"]["repo"] == ""
        assert overrides["metadata"]["name"] == ""


class TestCreateAppConfigV2:
    """Test create_app_config_v2 function."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create mock config manager."""
        config_mgr = Mock()
        config_mgr.apps_dir = Path("/config/apps")
        config_mgr.save_app_config = Mock()
        return config_mgr

    @pytest.fixture
    def mock_release(self):
        """Create mock release."""
        release = Mock(spec=Release)
        release.version = "1.2.3"
        return release

    def test_create_app_config_catalog_install(
        self, mock_config_manager, mock_release
    ):
        """Test creating config for catalog install."""
        app_config = {"source": {"owner": "foo", "repo": "bar"}}
        verify_result = {
            "passed": True,
            "methods": {"digest": {"passed": True, "hash_type": "sha256"}},
        }
        icon_result = {
            "icon_path": "/icons/myapp.png",
            "source": "extraction",
        }

        result = create_app_config_v2(
            app_name="myapp",
            app_path=Path("/apps/myapp.AppImage"),
            app_config=app_config,
            release=mock_release,
            verify_result=verify_result,
            icon_result=icon_result,
            source="catalog",
            config_manager=mock_config_manager,
        )

        assert result["success"] is True
        assert "config" in result
        assert result["config"]["source"] == "catalog"
        assert result["config"]["catalog_ref"] == "myapp"
        assert "overrides" not in result["config"]
        assert result["config"]["state"]["version"] == "1.2.3"
        assert result["config"]["state"]["verification"]["passed"] is True
        assert result["config"]["state"]["icon"]["installed"] is True

        mock_config_manager.save_app_config.assert_called_once()

    def test_create_app_config_url_install(
        self, mock_config_manager, mock_release
    ):
        """Test creating config for URL install."""
        app_config = {
            "source": {"owner": "foo", "repo": "bar"},
            "verification": {"method": "digest"},
            "icon": {"method": "extraction", "filename": "app.png"},
        }
        verify_result = {
            "passed": True,
            "methods": {"digest": {"passed": True, "hash_type": "sha256"}},
        }
        icon_result = {
            "icon_path": "/icons/myapp.png",
            "source": "extraction",
        }

        result = create_app_config_v2(
            app_name="myapp",
            app_path=Path("/apps/myapp.AppImage"),
            app_config=app_config,
            release=mock_release,
            verify_result=verify_result,
            icon_result=icon_result,
            source="url",
            config_manager=mock_config_manager,
        )

        assert result["success"] is True
        assert result["config"]["source"] == "url"
        assert result["config"]["catalog_ref"] is None
        assert "overrides" in result["config"]
        assert (
            result["config"]["overrides"]["verification"]["method"] == "digest"
        )
        assert result["config"]["overrides"]["icon"]["filename"] == "myapp.png"

    def test_create_app_config_save_failure(
        self, mock_config_manager, mock_release
    ):
        """Test handling of save failure."""
        mock_config_manager.save_app_config.side_effect = ValueError(
            "Save failed"
        )

        result = create_app_config_v2(
            app_name="myapp",
            app_path=Path("/apps/myapp.AppImage"),
            app_config={},
            release=mock_release,
            verify_result=None,
            icon_result={},
            source="catalog",
            config_manager=mock_config_manager,
        )

        assert result["success"] is False
        assert "error" in result


class TestUpdateAppConfig:
    """Test update_app_config function."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create mock config manager."""
        config_mgr = Mock()
        config_mgr.load_raw_app_config = Mock(
            return_value={
                "config_version": "2.0.0",
                "source": "catalog",
                "state": {
                    "version": "1.0.0",
                    "installed_path": "/old/path",
                    "icon": {},
                },
            }
        )
        config_mgr.save_app_config = Mock()
        return config_mgr

    def test_update_app_config_success(self, mock_config_manager):
        """Test successful app config update."""
        verify_result = {
            "passed": True,
            "methods": {"digest": {"passed": True, "hash": "abc123"}},
        }
        icon_config = {
            "installed": True,
            "source": "extraction",
            "path": "/icons/app.png",
        }

        update_app_config(
            app_name="myapp",
            latest_version="2.0.0",
            appimage_path=Path("/apps/myapp.AppImage"),
            icon_path=Path("/icons/app.png"),
            verify_result=verify_result,
            updated_icon_config=icon_config,
            config_manager=mock_config_manager,
        )

        mock_config_manager.save_app_config.assert_called_once()
        saved_config = mock_config_manager.save_app_config.call_args[0][1]

        assert saved_config["state"]["version"] == "2.0.0"
        assert (
            saved_config["state"]["installed_path"] == "/apps/myapp.AppImage"
        )
        assert saved_config["state"]["icon"]["installed"] is True
        assert saved_config["state"]["icon"]["method"] == "extraction"

    def test_update_app_config_not_found(self, mock_config_manager):
        """Test update when app config not found."""
        mock_config_manager.load_raw_app_config.return_value = None

        with pytest.raises(ValueError, match="app state not found"):
            update_app_config(
                app_name="missing",
                latest_version="2.0.0",
                appimage_path=Path("/apps/app.AppImage"),
                icon_path=None,
                verify_result={},
                updated_icon_config=None,
                config_manager=mock_config_manager,
            )

    def test_update_app_config_without_icon(self, mock_config_manager):
        """Test update without icon config."""
        update_app_config(
            app_name="myapp",
            latest_version="2.0.0",
            appimage_path=Path("/apps/myapp.AppImage"),
            icon_path=None,
            verify_result={},
            updated_icon_config=None,
            config_manager=mock_config_manager,
        )

        saved_config = mock_config_manager.save_app_config.call_args[0][1]
        # Icon should remain from original config
        assert "icon" in saved_config["state"]


class TestGetStoredHash:
    """Test get_stored_hash function."""

    def test_get_hash_from_digest_verification(self):
        """Test getting hash from digest verification."""
        verification_results = {
            "digest": {"passed": True, "hash": "abc123digest"}
        }
        asset = Mock(spec=Asset)
        asset.digest = "asset_digest"

        hash_val = get_stored_hash(verification_results, asset)

        assert hash_val == "abc123digest"

    def test_get_hash_from_checksum_file(self):
        """Test getting hash from checksum file verification."""
        verification_results = {
            "digest": {"passed": False},
            "checksum_file": {"passed": True, "hash": "xyz789checksum"},
        }
        asset = Mock(spec=Asset)
        asset.digest = "asset_digest"

        hash_val = get_stored_hash(verification_results, asset)

        assert hash_val == "xyz789checksum"

    def test_get_hash_from_asset_digest(self):
        """Test getting hash from asset digest when verification failed."""
        verification_results = {
            "digest": {"passed": False},
            "checksum_file": {"passed": False},
        }
        asset = Mock(spec=Asset)
        asset.digest = "fallback_asset_digest"

        hash_val = get_stored_hash(verification_results, asset)

        assert hash_val == "fallback_asset_digest"

    def test_get_hash_returns_empty_when_no_hash_available(self):
        """Test getting hash returns empty string when no hash available."""
        verification_results = {}
        asset = Mock(spec=Asset)
        asset.digest = ""

        hash_val = get_stored_hash(verification_results, asset)

        assert hash_val == ""

    def test_get_hash_priority_order(self):
        """Test hash retrieval follows priority: digest > checksum > asset."""
        # All three available
        verification_results = {
            "digest": {"passed": True, "hash": "from_digest"},
            "checksum_file": {"passed": True, "hash": "from_checksum"},
        }
        asset = Mock(spec=Asset)
        asset.digest = "from_asset"

        hash_val = get_stored_hash(verification_results, asset)

        assert hash_val == "from_digest"  # Highest priority
