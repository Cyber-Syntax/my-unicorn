"""Tests for installation verification failure handling.

This test suite ensures that verification failures are properly handled
and prevent installation of corrupted or tampered AppImages.

These tests verify TASK-001 from Phase 1: Fix missing raise statement after
verification failure to prevent corrupted AppImages from being installed.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from my_unicorn.core.install import InstallHandler
from my_unicorn.exceptions import InstallError


class TestVerificationFailure:
    """Test cases for verification failure handling."""

    @pytest.mark.asyncio
    async def test_verify_appimage_download_failure_raises_exception(
        self,
    ) -> None:
        """Test that verification failure raises InstallationError.

        This is a critical security test ensuring that the raise statement
        added in Phase 1 (TASK-001) properly prevents corrupted or tampered
        AppImages from being installed.
        """
        from my_unicorn.core.post_download import PostDownloadResult

        download_service = Mock()
        storage_service = Mock()
        config_manager = Mock()
        github_client = Mock()

        # Create a mock PostDownloadProcessor that returns a failure result
        post_download_processor = AsyncMock()
        post_download_processor.process.return_value = PostDownloadResult(
            success=False,
            install_path=None,
            verification_result=None,
            icon_result=None,
            config_result=None,
            desktop_result=None,
            error="Verification failed: SHA256 checksum mismatch",
        )

        handler = InstallHandler(
            post_download_processor=post_download_processor,
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            github_client=github_client,
        )

        # Mock download to return a path
        download_service.download_appimage = AsyncMock(
            return_value=Path("/tmp/test.appimage")
        )

        # Mock release and asset
        from my_unicorn.core.github import Asset, Release

        asset = Asset(
            name="test.appimage",
            size=1024,
            digest="sha256:abc123",
            browser_download_url="https://example.com/test.appimage",
        )
        release = Release(
            owner="test-owner",
            repo="test-repo",
            version="1.0.0",
            prerelease=False,
            assets=[asset],
            original_tag_name="v1.0.0",
        )

        app_config = {
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
            },
            "appimage": {
                "naming": {
                    "target_name": "test-app",
                },
            },
        }

        # This should raise InstallError due to verification failure
        with pytest.raises(InstallError, match="Verification failed"):
            await handler._install_workflow(
                app_name="test-app",
                asset=asset,
                release=release,
                app_config=app_config,
                source="catalog",
            )

    @pytest.mark.asyncio
    async def test_verification_success_allows_installation(self) -> None:
        """Test that successful verification allows installation to continue.

        Ensures the happy path still works after the verification failure fix.
        """
        from my_unicorn.core.post_download import PostDownloadResult

        download_service = Mock()
        download_service.download_appimage = AsyncMock(
            return_value=Path("/tmp/test.appimage")
        )

        storage_service = Mock()
        config_manager = Mock()
        github_client = Mock()

        # Create a mock PostDownloadProcessor that returns successful result
        post_download_processor = AsyncMock()
        post_download_processor.process.return_value = PostDownloadResult(
            success=True,
            install_path=Path("/install/test.appimage"),
            verification_result={"passed": True, "method": "digest"},
            icon_result={"icon_path": "/tmp/icons/test.png"},
            config_result={"saved": True},
            desktop_result={"desktop_path": "/tmp/desktop/test.desktop"},
            error=None,
        )

        handler = InstallHandler(
            post_download_processor=post_download_processor,
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            github_client=github_client,
        )

        from my_unicorn.core.github import Asset, Release

        asset = Asset(
            name="test.appimage",
            size=1024,
            digest="sha256:abc123",
            browser_download_url="https://example.com/test.appimage",
        )
        release = Release(
            owner="test-owner",
            repo="test-repo",
            version="1.0.0",
            prerelease=False,
            assets=[asset],
            original_tag_name="v1.0.0",
        )

        app_config = {
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
            },
            "appimage": {
                "naming": {
                    "target_name": "test-app",
                },
            },
        }

        # Should complete successfully
        result = await handler._install_workflow(
            app_name="test-app",
            asset=asset,
            release=release,
            app_config=app_config,
            source="catalog",
        )

        # Verify successful result
        assert result["success"] is True
        assert result["name"] == "test-app"
