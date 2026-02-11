"""Tests for PostDownloadContext and PostDownloadResult dataclasses.

Tests cover dataclass creation, field validation, and enum values.
"""

from pathlib import Path
from typing import Any

from my_unicorn.core.post_download import (
    OperationType,
    PostDownloadContext,
    PostDownloadResult,
)


class TestOperationType:
    """Test OperationType enum."""

    def test_operation_type_enum_values(self) -> None:
        """Verify INSTALL and UPDATE enum values.

        Tests that:
        - INSTALL enum value is 'install'
        - UPDATE enum value is 'update'
        - Enum can be created from string values

        """
        assert OperationType.INSTALL.value == "install"
        assert OperationType.UPDATE.value == "update"

        # Verify enum creation from value
        assert OperationType("install") == OperationType.INSTALL
        assert OperationType("update") == OperationType.UPDATE


class TestPostDownloadContext:
    """Test PostDownloadContext dataclass."""

    def test_post_download_context_install_creation(
        self, install_context: PostDownloadContext
    ) -> None:
        """Verify INSTALL context dataclass creation.

        Args:
            install_context: Fixture providing INSTALL context.

        """
        assert install_context.app_name == "test-app"
        assert install_context.operation_type == OperationType.INSTALL
        assert install_context.verify_downloads is True
        assert install_context.source == "catalog"
        assert install_context.owner == "test-owner"
        assert install_context.repo == "test-repo"
        assert install_context.catalog_entry is not None
        assert install_context.app_config is not None

    def test_post_download_context_update_creation(
        self, update_context: PostDownloadContext
    ) -> None:
        """Verify UPDATE context dataclass creation.

        Args:
            update_context: Fixture providing UPDATE context.

        """
        assert update_context.app_name == "test-app"
        assert update_context.operation_type == OperationType.UPDATE
        assert update_context.verify_downloads is True
        assert update_context.source == "catalog"
        assert update_context.owner == "test-owner"
        assert update_context.repo == "test-repo"
        assert update_context.catalog_entry is not None
        assert update_context.app_config is not None

    def test_post_download_context_required_fields(
        self,
        sample_asset_post: Any,
        sample_release_post: Any,
        tmp_path: Path,
    ) -> None:
        """Verify required field validation for PostDownloadContext.

        Args:
            sample_asset_post: Sample asset for context.
            sample_release_post: Sample release for context.
            tmp_path: Temporary directory from pytest.

        """
        context = PostDownloadContext(
            app_name="test-app",
            downloaded_path=tmp_path / "test-app.AppImage",
            asset=sample_asset_post,
            release=sample_release_post,
            app_config={"test": "config"},
            catalog_entry=None,
            operation_type=OperationType.INSTALL,
            owner="owner",
            repo="repo",
        )

        assert context.app_name == "test-app"
        assert context.downloaded_path == tmp_path / "test-app.AppImage"
        assert context.asset == sample_asset_post
        assert context.release == sample_release_post
        assert context.app_config == {"test": "config"}
        assert context.catalog_entry is None
        assert context.operation_type == OperationType.INSTALL
        assert context.owner == "owner"
        assert context.repo == "repo"


class TestPostDownloadResult:
    """Test PostDownloadResult dataclass."""

    def test_post_download_result_creation(
        self, sample_post_download_result: PostDownloadResult
    ) -> None:
        """Verify result dataclass creation.

        Args:
            sample_post_download_result: Fixture providing result instance.

        """
        assert sample_post_download_result is not None
        assert isinstance(sample_post_download_result, PostDownloadResult)
        assert sample_post_download_result.success is True

    def test_post_download_result_success_case(
        self,
    ) -> None:
        """Verify success=True case with all fields populated.

        Tests that:
        - success is True
        - install_path is set
        - All result dictionaries are populated
        - error is None

        """
        result = PostDownloadResult(
            success=True,
            install_path=Path("/opt/appimages/test-app.AppImage"),
            verification_result={
                "passed": True,
                "methods": {"digest": {"passed": True}},
            },
            icon_result={"success": True, "path": "/opt/icons/test-app.png"},
            config_result={"success": True},
            desktop_result={"success": True},
        )

        assert result.success is True
        assert result.install_path == Path("/opt/appimages/test-app.AppImage")
        assert result.verification_result is not None
        assert result.icon_result is not None
        assert result.config_result is not None
        assert result.desktop_result is not None
        assert result.error is None

    def test_post_download_result_failure_case(self) -> None:
        """Verify success=False case with error message.

        Tests that:
        - success is False
        - install_path is None
        - All result dictionaries are None
        - error contains error message

        """
        result = PostDownloadResult(
            success=False,
            install_path=None,
            verification_result=None,
            icon_result=None,
            config_result=None,
            desktop_result=None,
            error="Installation failed: permission denied",
        )

        assert result.success is False
        assert result.install_path is None
        assert result.verification_result is None
        assert result.icon_result is None
        assert result.config_result is None
        assert result.desktop_result is None
        assert result.error == "Installation failed: permission denied"
