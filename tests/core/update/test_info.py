"""Tests for UpdateInfo dataclass.

This module tests the UpdateInfo dataclass that encapsulates update status
and metadata, including in-memory caching of release data and loaded config.
"""

from my_unicorn.constants import VERSION_UNKNOWN
from my_unicorn.core.github import Release
from my_unicorn.core.update.info import UpdateInfo


class TestUpdateInfoInitialization:
    """Tests for UpdateInfo initialization."""

    def test_update_info_initialization_minimal_fields(self) -> None:
        """Create UpdateInfo with only app_name and verify defaults.

        Verifies that when creating UpdateInfo with only the required
        app_name field, all other fields are set to their default values:
        empty strings for version fields, False for boolean fields, and
        None for optional caching fields. Note that __post_init__ auto-
        generates original_tag_name even for empty latest_version.
        """
        info = UpdateInfo(app_name="test-app")

        assert info.app_name == "test-app"
        assert info.current_version == ""
        assert info.latest_version == ""
        assert info.has_update is False
        assert info.release_url == ""
        assert info.prerelease is False
        assert info.original_tag_name == "v"  # Auto-generated "v" + ""
        assert info.release_data is None
        assert info.app_config is None
        assert info.error_reason is None

    def test_update_info_initialization_all_fields(self) -> None:
        """Create UpdateInfo with all fields specified.

        Verifies that when all fields are explicitly provided, they are
        stored correctly in the UpdateInfo instance.
        """
        app_config = {"owner": "test-owner", "repo": "test-repo"}
        info = UpdateInfo(
            app_name="firefox",
            current_version="1.0.0",
            latest_version="2.0.0",
            has_update=True,
            release_url="https://github.com/test/releases/v2.0.0",
            prerelease=False,
            original_tag_name="v2.0.0",
            release_data=None,
            app_config=app_config,
            error_reason=None,
        )

        assert info.app_name == "firefox"
        assert info.current_version == "1.0.0"
        assert info.latest_version == "2.0.0"
        assert info.has_update is True
        assert info.release_url == "https://github.com/test/releases/v2.0.0"
        assert info.prerelease is False
        assert info.original_tag_name == "v2.0.0"
        assert info.release_data is None
        assert info.app_config == app_config
        assert info.error_reason is None


class TestUpdateInfoPostInit:
    """Tests for UpdateInfo __post_init__ behavior."""

    def test_update_info_post_init_auto_tag_name(self) -> None:
        """Verify __post_init__ sets original_tag_name from latest_version.

        When UpdateInfo is created with latest_version but no
        original_tag_name, __post_init__ should automatically set
        original_tag_name to f"v{latest_version}".
        """
        info = UpdateInfo(
            app_name="test-app",
            latest_version="1.5.0",
        )

        assert info.original_tag_name == "v1.5.0"

    def test_update_info_post_init_preserves_existing_tag(self) -> None:
        """Verify __post_init__ preserves explicitly set original_tag_name.

        When UpdateInfo is created with both latest_version and
        original_tag_name, __post_init__ should not override the
        explicitly provided original_tag_name.
        """
        info = UpdateInfo(
            app_name="test-app",
            latest_version="1.5.0",
            original_tag_name="release-1.5.0",
        )

        assert info.original_tag_name == "release-1.5.0"

    def test_update_info_post_init_skips_version_unknown(self) -> None:
        """Verify __post_init__ doesn't auto-set tag when version is UNKNOWN.

        When latest_version is VERSION_UNKNOWN, __post_init__ should not
        set original_tag_name, as VERSION_UNKNOWN is a placeholder value
        that shouldn't be used in tag names.
        """
        info = UpdateInfo(
            app_name="test-app",
            latest_version=VERSION_UNKNOWN,
        )

        assert info.original_tag_name == ""


class TestUpdateInfoFactory:
    """Tests for UpdateInfo factory methods."""

    def test_update_info_create_error_factory(self) -> None:
        """Test UpdateInfo.create_error() factory method.

        Verifies that the create_error class method creates an UpdateInfo
        instance with app_name and error_reason set correctly, and
        is_success returns False.
        """
        info = UpdateInfo.create_error(
            app_name="firefox",
            reason="Failed to fetch release data: Network error",
        )

        assert info.app_name == "firefox"
        assert (
            info.error_reason == "Failed to fetch release data: Network error"
        )
        assert info.is_success is False


class TestUpdateInfoProperties:
    """Tests for UpdateInfo properties."""

    def test_update_info_is_success_property_true(self) -> None:
        """Test is_success property returns True when no error.

        When error_reason is None, the is_success property should
        return True, indicating the update check was successful.
        """
        info = UpdateInfo(
            app_name="test-app",
            error_reason=None,
        )

        assert info.is_success is True

    def test_update_info_is_success_property_false(self) -> None:
        """Test is_success property returns False when error exists.

        When error_reason contains a string value, the is_success
        property should return False, indicating the update check failed.
        """
        info = UpdateInfo(
            app_name="test-app",
            error_reason="Network connection failed",
        )

        assert info.is_success is False


class TestUpdateInfoCaching:
    """Tests for UpdateInfo caching functionality."""

    def test_update_info_caches_release_data(
        self,
        sample_release_data: Release,
    ) -> None:
        """Test that release_data parameter caches Release object.

        Verifies that when UpdateInfo is created with a release_data
        parameter, the Release object is stored and can be retrieved
        without needing to reload cache files.
        """
        info = UpdateInfo(
            app_name="test-app",
            release_data=sample_release_data,
        )

        assert info.release_data is sample_release_data
        assert info.release_data.version == "1.0.0"
        assert info.release_data.owner == "test-owner"

    def test_update_info_caches_app_config(self) -> None:
        """Test that app_config parameter caches configuration dict.

        Verifies that when UpdateInfo is created with an app_config
        parameter, the configuration dict is stored and can be retrieved
        without needing to reload config files.
        """
        config = {
            "owner": "test-owner",
            "repo": "test-repo",
            "appimage": {"name": "test.AppImage", "version": "1.0.0"},
        }
        info = UpdateInfo(
            app_name="test-app",
            app_config=config,
        )

        assert info.app_config == config
        assert info.app_config["owner"] == "test-owner"


class TestUpdateInfoVersionUnknown:
    """Tests for VERSION_UNKNOWN constant usage."""

    def test_update_info_version_unknown_constant(self) -> None:
        """Verify VERSION_UNKNOWN constant and its behavior.

        Tests that VERSION_UNKNOWN is defined and has the expected value.
        When used as latest_version, it should not trigger automatic
        original_tag_name generation.
        """
        assert VERSION_UNKNOWN == "unknown"

        info = UpdateInfo(
            app_name="test-app",
            latest_version=VERSION_UNKNOWN,
        )

        # Should not auto-generate tag name for VERSION_UNKNOWN
        assert info.original_tag_name == ""
        assert info.latest_version == "unknown"


class TestUpdateInfoRepr:
    """Tests for UpdateInfo string representation."""

    def test_update_info_repr_with_update_available(self) -> None:
        """Test __repr__ when update is available.

        Verifies that the string representation displays current and latest
        versions with "Available" status when has_update is True.
        """
        info = UpdateInfo(
            app_name="firefox",
            current_version="1.0.0",
            latest_version="2.0.0",
            has_update=True,
        )

        repr_str = repr(info)
        assert "firefox" in repr_str
        assert "1.0.0" in repr_str
        assert "2.0.0" in repr_str
        assert "Available" in repr_str

    def test_update_info_repr_up_to_date(self) -> None:
        """Test __repr__ when application is up to date.

        Verifies that the string representation displays current and latest
        versions with "Up to date" status when has_update is False.
        """
        info = UpdateInfo(
            app_name="firefox",
            current_version="1.0.0",
            latest_version="1.0.0",
            has_update=False,
        )

        repr_str = repr(info)
        assert "firefox" in repr_str
        assert "1.0.0" in repr_str
        assert "Up to date" in repr_str

    def test_update_info_repr_with_error(self) -> None:
        """Test __repr__ when error occurred.

        Verifies that the string representation displays error status and
        message when error_reason is set.
        """
        info = UpdateInfo(
            app_name="firefox",
            error_reason="Network connection failed",
        )

        repr_str = repr(info)
        assert "firefox" in repr_str
        assert "Error" in repr_str
        assert "Network connection failed" in repr_str
