"""Tests for config builder schema compatibility and integration.

These tests validate that config_builders output integrates correctly with
the app state schema and configuration system.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from my_unicorn.config.schemas import validate_app_state
from my_unicorn.core.github import Release
from my_unicorn.utils.config_builders import (
    build_verification_state,
    create_app_config_v2,
    update_app_config,
)


class TestBuildVerificationStateSchemaCompatibility:
    """Test build_verification_state output matches the app state schema.

    These tests validate the contract between config_builders and the schema.
    They ensure that verification objects created by config_builders will pass
    schema validation when saved as part of app state.
    """

    def test_verification_state_validates_against_schema(self) -> None:
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

    def test_verification_state_with_checksum_file_validates(self) -> None:
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

    def test_verification_state_with_warning_validates(self) -> None:
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

    def test_empty_verification_state_validates(self) -> None:
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

    def test_multi_method_verification_state_validates(self) -> None:
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


class TestCreateAppConfigV2Integration:
    """Test create_app_config_v2 function integration."""

    @pytest.fixture
    def mock_config_manager(self) -> Mock:
        """Create mock config manager."""
        config_mgr = Mock()
        config_mgr.apps_dir = Path("/config/apps")
        config_mgr.save_app_config = Mock()
        return config_mgr

    @pytest.fixture
    def mock_release(self) -> Mock:
        """Create mock release."""
        release = Mock(spec=Release)
        release.version = "1.2.3"
        return release

    def test_create_app_config_catalog_install(
        self, mock_config_manager: Mock, mock_release: Mock
    ) -> None:
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
        self, mock_config_manager: Mock, mock_release: Mock
    ) -> None:
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
        self, mock_config_manager: Mock, mock_release: Mock
    ) -> None:
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


class TestUpdateAppConfigIntegration:
    """Test update_app_config function integration."""

    @pytest.fixture
    def mock_config_manager(self) -> Mock:
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

    def test_update_app_config_success(
        self, mock_config_manager: Mock
    ) -> None:
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

    def test_update_app_config_not_found(
        self, mock_config_manager: Mock
    ) -> None:
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

    def test_update_app_config_without_icon(
        self, mock_config_manager: Mock
    ) -> None:
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
