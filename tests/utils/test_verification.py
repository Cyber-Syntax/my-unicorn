"""Tests for verification utility module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
class TestVerifyAppimageDownload:
    """Tests for verify_appimage_download function."""

    async def test_verify_appimage_download_from_catalog(self):
        """Test verify_appimage_download using catalog config."""
        from my_unicorn.utils.verification import verify_appimage_download

        file_path = Path("/tmp/test.AppImage")
        asset = MagicMock(digest="sha256:abc123")
        release = MagicMock(original_tag_name="v1.0.0", assets=[])
        verification_service = MagicMock()
        verification_service.verify_file = AsyncMock(
            return_value={"passed": True, "methods": {}, "updated_config": {}}
        )

        catalog_entry = {
            "verification": {"enabled": True},
            "source": {"owner": "test-owner", "repo": "test-repo"},
        }

        result = await verify_appimage_download(
            file_path=file_path,
            asset=asset,
            release=release,
            app_name="testapp",
            verification_service=verification_service,
            catalog_entry=catalog_entry,
        )

        assert result["passed"] is True
        verification_service.verify_file.assert_called_once()

    async def test_verify_appimage_download_from_config(self):
        """Test verify_appimage_download using app config."""
        from my_unicorn.utils.verification import verify_appimage_download

        file_path = Path("/tmp/test.AppImage")
        asset = MagicMock(digest=None)
        release = MagicMock(original_tag_name="v1.0.0", assets=[])
        verification_service = MagicMock()
        verification_service.verify_file = AsyncMock(
            return_value={"passed": True, "methods": {}, "updated_config": {}}
        )

        verification_config = {"enabled": True}

        result = await verify_appimage_download(
            file_path=file_path,
            asset=asset,
            release=release,
            app_name="testapp",
            verification_service=verification_service,
            verification_config=verification_config,
            owner="config-owner",
            repo="config-repo",
        )

        assert result["passed"] is True
        verification_service.verify_file.assert_called_once()

    async def test_verify_appimage_download_extraction_from_catalog(self):
        """Test that owner/repo are extracted from catalog when not provided."""
        from my_unicorn.utils.verification import verify_appimage_download

        file_path = Path("/tmp/test.AppImage")
        asset = MagicMock(digest=None)
        release = MagicMock(original_tag_name="v1.0.0", assets=[])
        verification_service = MagicMock()
        verification_service.verify_file = AsyncMock(
            return_value={"passed": True, "methods": {}, "updated_config": {}}
        )

        catalog_entry = {
            "verification": {"enabled": True},
            "source": {"owner": "catalog-owner", "repo": "catalog-repo"},
        }

        result = await verify_appimage_download(
            file_path=file_path,
            asset=asset,
            release=release,
            app_name="testapp",
            verification_service=verification_service,
            catalog_entry=catalog_entry,
        )

        # Verify that the service was called with catalog owner/repo
        call_kwargs = verification_service.verify_file.call_args.kwargs
        assert call_kwargs["owner"] == "catalog-owner"
        assert call_kwargs["repo"] == "catalog-repo"

    async def test_verify_appimage_download_error_handling(self):
        """Test verify_appimage_download error handling."""
        from my_unicorn.utils.verification import verify_appimage_download

        file_path = Path("/tmp/test.AppImage")
        asset = MagicMock(digest=None)
        release = MagicMock(original_tag_name="v1.0.0", assets=[])
        verification_service = MagicMock()
        verification_service.verify_file = AsyncMock(
            side_effect=Exception("Verification error")
        )

        result = await verify_appimage_download(
            file_path=file_path,
            asset=asset,
            release=release,
            app_name="testapp",
            verification_service=verification_service,
            owner="test-owner",
            repo="test-repo",
        )

        assert result["passed"] is False
        assert "error" in result
        assert result["error"] == "Verification error"

    async def test_verify_appimage_download_with_progress_task(self):
        """Test verify_appimage_download with progress task ID."""
        from my_unicorn.utils.verification import verify_appimage_download

        file_path = Path("/tmp/test.AppImage")
        asset = MagicMock(digest="sha256:abc")
        release = MagicMock(original_tag_name="v1.0.0", assets=[asset])
        verification_service = MagicMock()
        verification_service.verify_file = AsyncMock(
            return_value={"passed": True, "methods": {}, "updated_config": {}}
        )

        result = await verify_appimage_download(
            file_path=file_path,
            asset=asset,
            release=release,
            app_name="testapp",
            verification_service=verification_service,
            owner="test-owner",
            repo="test-repo",
            progress_task_id="task-123",
        )

        # Verify that progress_task_id was passed to the service
        call_kwargs = verification_service.verify_file.call_args.kwargs
        assert call_kwargs["progress_task_id"] == "task-123"

    async def test_verify_appimage_download_no_config(self):
        """Test verify_appimage_download with no verification config."""
        from my_unicorn.utils.verification import verify_appimage_download

        file_path = Path("/tmp/test.AppImage")
        asset = MagicMock(digest=None)
        release = MagicMock(original_tag_name="v1.0.0", assets=[])
        verification_service = MagicMock()
        verification_service.verify_file = AsyncMock(
            return_value={"passed": True, "methods": {}, "updated_config": {}}
        )

        result = await verify_appimage_download(
            file_path=file_path,
            asset=asset,
            release=release,
            app_name="testapp",
            verification_service=verification_service,
            owner="test-owner",
            repo="test-repo",
        )

        # Should still call verify_file with empty config
        assert result["passed"] is True
        call_kwargs = verification_service.verify_file.call_args.kwargs
        assert call_kwargs["config"] == {}

    async def test_verify_appimage_download_tag_name_handling(self):
        """Test that tag_name is extracted correctly from release."""
        from my_unicorn.utils.verification import verify_appimage_download

        file_path = Path("/tmp/test.AppImage")
        asset = MagicMock(digest=None)
        release = MagicMock(original_tag_name="v2.5.0", assets=[])
        verification_service = MagicMock()
        verification_service.verify_file = AsyncMock(
            return_value={"passed": True, "methods": {}, "updated_config": {}}
        )

        result = await verify_appimage_download(
            file_path=file_path,
            asset=asset,
            release=release,
            app_name="testapp",
            verification_service=verification_service,
            owner="test-owner",
            repo="test-repo",
        )

        call_kwargs = verification_service.verify_file.call_args.kwargs
        assert call_kwargs["tag_name"] == "v2.5.0"

    async def test_verify_appimage_download_unknown_tag(self):
        """Test handling of None tag_name in release."""
        from my_unicorn.utils.verification import verify_appimage_download

        file_path = Path("/tmp/test.AppImage")
        asset = MagicMock(digest=None)
        release = MagicMock(original_tag_name=None, assets=[])
        verification_service = MagicMock()
        verification_service.verify_file = AsyncMock(
            return_value={"passed": True, "methods": {}, "updated_config": {}}
        )

        result = await verify_appimage_download(
            file_path=file_path,
            asset=asset,
            release=release,
            app_name="testapp",
            verification_service=verification_service,
            owner="test-owner",
            repo="test-repo",
        )

        call_kwargs = verification_service.verify_file.call_args.kwargs
        assert call_kwargs["tag_name"] == "unknown"
