"""Tests for configuration builder utilities."""

from pathlib import Path
from unittest.mock import Mock

import pytest

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
        verification_results = {"digest": {"passed": True, "hash": "abc123"}}
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
            verification_results=verification_results,
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
                verification_results={},
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
            verification_results={},
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
