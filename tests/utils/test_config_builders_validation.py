"""Tests for write-time validation of config save operations.

These tests verify that config save operations perform validation at write time
rather than deferring it to read time. This ensures invalid data is caught
immediately rather than being silently persisted.
"""

from pathlib import Path
from unittest.mock import MagicMock

from my_unicorn.core.github import Release
from my_unicorn.utils.config_builders import (
    create_app_config_v2,
    update_app_config,
)


class TestCreateAppConfigV2Validation:
    """Test that create_app_config_v2 validates on save."""

    def test_create_app_config_v2_validates_on_save(self) -> None:
        """Test save_app_config is called WITHOUT skip_validation=True.

        This ensures validation runs at write time rather than only at read
        time. The config_manager.save_app_config must be called with either:
        - No skip_validation keyword argument (default False)
        - Or explicitly skip_validation=False
        """
        # Create mock release and config_manager
        release = MagicMock(spec=Release)
        release.version = "1.0.0"

        config_manager = MagicMock()
        config_manager.save_app_config.return_value = None

        # Call create_app_config_v2
        result = create_app_config_v2(
            app_name="test_app",
            app_path=Path("/path/to/app.AppImage"),
            app_config={"source": {"owner": "test", "repo": "app"}},
            release=release,
            verify_result={
                "passed": True,
                "methods": {
                    "digest": {
                        "passed": True,
                        "hash_type": "sha256",
                        "hash": "abc123",
                        "computed_hash": "abc123",
                    }
                },
            },
            icon_result={
                "icon_path": "/path/to/icon.png",
                "source": "extraction",
            },
            source="catalog",
            config_manager=config_manager,
        )

        # Verify save_app_config was called
        assert config_manager.save_app_config.called
        call_args = config_manager.save_app_config.call_args

        # Verify skip_validation is NOT True
        # The call should either have no skip_validation kwarg, or have False
        if "skip_validation" in call_args.kwargs:
            assert call_args.kwargs["skip_validation"] is False, (
                "skip_validation must be False or omitted, not True"
            )

        # Verify result indicates success
        assert result["success"] is True


class TestUpdateAppConfigValidation:
    """Test that update_app_config validates on save."""

    def test_update_app_config_validates_on_save(self) -> None:
        """Test save_app_config is called WITHOUT skip_validation=True.

        This ensures validation runs at write time. The config_manager must
        be called with either:
        - No skip_validation keyword argument (default False)
        - Or explicitly skip_validation=False
        """
        config_manager = MagicMock()
        config_manager.save_app_config.return_value = None

        # Prepare test data: a valid app config
        app_config = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "test_app",
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-08-19T12:50:44.179839",
                "installed_path": "/path/to/test_app.AppImage",
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
                    "path": "/path/to/icon.png",
                },
            },
        }

        config_manager.load_raw_app_config.return_value = app_config

        # Call update_app_config
        update_app_config(
            app_name="test_app",
            latest_version="2.0.0",
            appimage_path=Path("/path/to/test_app.AppImage"),
            icon_path=Path("/path/to/icon.png"),
            verify_result={
                "passed": True,
                "methods": {
                    "digest": {
                        "passed": True,
                        "hash_type": "sha256",
                        "hash": "abc123",
                        "computed_hash": "abc123",
                    }
                },
            },
            updated_icon_config={
                "installed": True,
                "method": "extraction",
                "path": "/path/to/icon.png",
            },
            config_manager=config_manager,
        )

        # Verify save_app_config was called
        assert config_manager.save_app_config.called
        call_args = config_manager.save_app_config.call_args

        # Verify skip_validation is NOT True
        if "skip_validation" in call_args.kwargs:
            assert call_args.kwargs["skip_validation"] is False, (
                "skip_validation must be False or omitted, not True"
            )
