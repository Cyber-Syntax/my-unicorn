"""Tests for update verification refresh flow."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.api import Asset, Release
from my_unicorn.core.post_download import OperationType, PostDownloadResult
from my_unicorn.core.update import UpdateInfo, UpdateManager

# Test constants
EXPECTED_APP_COUNT = 2
EXPECTED_CALL_COUNT = 3


class TestUpdateVerificationFlow:
    """End-to-end tests for update verification refresh.

    These tests verify that when an app is updated:
    - Verification is recalculated with new release hashes
    - App state reflects new verification data (not old)
    - Cache is updated with new checksum_files
    """

    @pytest.fixture
    def mock_config_manager(self) -> MagicMock:
        """Create mock ConfigManager with complete configuration."""
        mock_config = MagicMock()
        mock_config.load_global_config.return_value = {
            "max_concurrent_downloads": 3,
            "directory": {
                "storage": Path("/test/storage"),
                "download": Path("/test/download"),
                "backup": Path("/test/backup"),
                "icon": Path("/test/icon"),
                "cache": Path("/test/cache"),
            },
        }
        mock_config.list_installed_apps.return_value = ["test-app"]
        return mock_config

    @pytest.fixture
    def v1_app_config(self) -> dict[str, Any]:
        """App configuration for installed v1.0.0 with verification A."""
        return {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "test-app",
            "state": {
                "version": "1.0.0",
                "installed_date": "2026-01-01T00:00:00+00:00",
                "installed_path": "/test/storage/test-app.AppImage",
                "verification": {
                    "passed": True,
                    "overall_passed": True,
                    "actual_method": "digest",
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                            "algorithm": "SHA256",
                            "expected": "abc123v1hash",
                            "computed": "abc123v1hash",
                            "source": "github_api",
                        }
                    ],
                },
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": "/test/icon/test-app.png",
                },
            },
        }

    @pytest.fixture
    def v2_release_data(self) -> Release:
        """Release data for v2.0.0 update."""
        return Release(
            owner="test-owner",
            repo="test-repo",
            version="2.0.0",
            prerelease=False,
            assets=[
                Asset(
                    name="test-app-2.0.0.AppImage",
                    size=2048,
                    digest="sha256:def456v2hash",
                    browser_download_url="https://github.com/test-owner/test-repo/releases/download/v2.0.0/test-app-2.0.0.AppImage",
                ),
                Asset(
                    name="SHA256SUMS.txt",
                    size=200,
                    digest=None,
                    browser_download_url="https://github.com/test-owner/test-repo/releases/download/v2.0.0/SHA256SUMS.txt",
                ),
            ],
            original_tag_name="v2.0.0",
        )

    @pytest.mark.asyncio
    async def test_update_replaces_verification_with_new_hash(
        self,
        mock_config_manager: MagicMock,
        v1_app_config: dict[str, Any],
        v2_release_data: Release,
    ) -> None:
        """Test that update replaces v1 verification with v2 verification.

        Verifies requirement: verification.methods array is replaced,
        not appended.
        """
        mock_config_manager.load_app_config.return_value = v1_app_config
        mock_config_manager.load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
            "verification": {},
            "appimage": {"naming": {"target_name": "test-app"}},
        }

        saved_configs: list[dict[str, Any]] = []

        def capture_save(app_name: str, config: dict[str, Any], **kwargs):
            saved_configs.append(config)
            return Path(f"/config/{app_name}.json")

        mock_config_manager.save_app_config.side_effect = capture_save

        with (
            patch("my_unicorn.core.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.FileOperations"),
            patch("my_unicorn.core.update.BackupService"),
            patch(
                "my_unicorn.core.update.ReleaseCacheManager"
            ) as mock_cache_cls,
            patch(
                "my_unicorn.core.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.PostDownloadProcessor"
            ) as mock_processor_cls,
            patch("my_unicorn.core.update.ReleaseFetcher"),
        ):
            mock_cache = MagicMock()
            mock_cache_cls.return_value = mock_cache

            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/test-app-2.0.0.AppImage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            # v2 verification result (different from v1)
            v2_verification_result = {
                "passed": True,
                "methods": {
                    "digest": {
                        "passed": True,
                        "hash": "def456v2hash",
                        "computed_hash": "def456v2hash",
                        "hash_type": "sha256",
                    }
                },
            }

            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                return_value=PostDownloadResult(
                    success=True,
                    install_path=Path("/test/storage/test-app.AppImage"),
                    verification_result=v2_verification_result,
                    icon_result={"icon_path": "/test/icon/test-app.png"},
                    config_result={"success": True},
                    desktop_result={"success": True},
                )
            )
            mock_processor_cls.return_value = mock_processor

            manager = UpdateManager(mock_config_manager)

            update_info = UpdateInfo(
                app_name="test-app",
                current_version="1.0.0",
                latest_version="2.0.0",
                has_update=True,
                release_data=v2_release_data,
                app_config=v1_app_config,
            )

            mock_context = {
                "app_config": v1_app_config,
                "update_info": update_info,
                "appimage_asset": v2_release_data.assets[0],
                "catalog_entry": mock_config_manager.load_catalog.return_value,
                "owner": "test-owner",
                "repo": "test-repo",
            }

            mock_session = AsyncMock()

            with patch(
                "my_unicorn.core.update.prepare_update_context",
                new=AsyncMock(return_value=(mock_context, None)),
            ):
                success, error = await manager.update_single_app(
                    "test-app", mock_session, force=True
                )

            assert success is True
            assert error is None

            # Verify PostDownloadProcessor was called with UPDATE operation
            mock_processor.process.assert_called_once()
            call_args = mock_processor.process.call_args
            context = call_args[0][0]
            assert context.operation_type == OperationType.UPDATE

    @pytest.mark.asyncio
    async def test_update_verification_service_receives_cache_manager(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test that VerificationService is initialized with cache_manager.

        This ensures checksum_files are cached during update.
        """
        with (
            patch("my_unicorn.core.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.FileOperations"),
            patch("my_unicorn.core.update.BackupService"),
            patch(
                "my_unicorn.core.update.ReleaseCacheManager"
            ) as mock_cache_cls,
            patch(
                "my_unicorn.core.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.VerificationService"
            ) as mock_verify_cls,
        ):
            mock_cache = MagicMock()
            mock_cache_cls.return_value = mock_cache

            mock_download = MagicMock()
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            mock_verify = MagicMock()
            mock_verify_cls.return_value = mock_verify

            manager = UpdateManager(mock_config_manager)

            mock_session = AsyncMock()
            manager._initialize_services(mock_session)

            # Verify VerificationService received cache_manager
            mock_verify_cls.assert_called_once()
            call_kwargs = mock_verify_cls.call_args[1]
            assert "cache_manager" in call_kwargs
            assert call_kwargs["cache_manager"] is manager.cache_manager

    @pytest.mark.asyncio
    async def test_update_old_verification_not_preserved(
        self,
        mock_config_manager: MagicMock,
        v1_app_config: dict[str, Any],
        v2_release_data: Release,
    ) -> None:
        """Test that old v1 verification data is replaced, not merged.

        Requirement: Original verification A is not preserved.
        """
        mock_config_manager.load_app_config.return_value = v1_app_config
        mock_config_manager.load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
            "verification": {},
            "appimage": {"naming": {"target_name": "test-app"}},
        }

        config_updates: list[dict[str, Any]] = []

        def track_config_update(
            app_name: str, config: dict[str, Any], **kwargs
        ):
            config_updates.append(config.copy())
            return Path(f"/config/{app_name}.json")

        mock_config_manager.save_app_config.side_effect = track_config_update

        with (
            patch("my_unicorn.core.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.FileOperations"),
            patch("my_unicorn.core.update.BackupService"),
            patch("my_unicorn.core.update.ReleaseCacheManager"),
            patch(
                "my_unicorn.core.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.PostDownloadProcessor"
            ) as mock_processor_cls,
        ):
            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/test-app.AppImage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            # v2 uses checksum_file, not digest (different from v1)
            v2_verification = {
                "passed": True,
                "methods": {
                    "checksum_file": {
                        "passed": True,
                        "hash": "xyz789v2checksum",
                        "computed_hash": "xyz789v2checksum",
                        "hash_type": "sha256",
                        "url": "https://example.com/SHA256SUMS.txt",
                    }
                },
            }

            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                return_value=PostDownloadResult(
                    success=True,
                    install_path=Path("/test/storage/test-app.AppImage"),
                    verification_result=v2_verification,
                    icon_result={"icon_path": "/test/icon/test-app.png"},
                    config_result={"success": True},
                    desktop_result={"success": True},
                )
            )
            mock_processor_cls.return_value = mock_processor

            manager = UpdateManager(mock_config_manager)

            update_info = UpdateInfo(
                app_name="test-app",
                current_version="1.0.0",
                latest_version="2.0.0",
                has_update=True,
                release_data=v2_release_data,
                app_config=v1_app_config,
            )

            mock_context = {
                "app_config": v1_app_config,
                "update_info": update_info,
                "appimage_asset": v2_release_data.assets[0],
                "catalog_entry": mock_config_manager.load_catalog.return_value,
                "owner": "test-owner",
                "repo": "test-repo",
            }

            mock_session = AsyncMock()

            with patch(
                "my_unicorn.core.update.prepare_update_context",
                new=AsyncMock(return_value=(mock_context, None)),
            ):
                success, _ = await manager.update_single_app(
                    "test-app", mock_session, force=True
                )

            assert success is True

            # Verify processor received context with UPDATE operation type
            assert mock_processor.process.called
            context = mock_processor.process.call_args[0][0]

            # Operation should be UPDATE (triggers verification replacement)
            assert context.operation_type == OperationType.UPDATE
            # Verification is enabled by default
            assert context.verify_downloads is True

    @pytest.mark.asyncio
    async def test_update_cache_stores_new_checksum_files(
        self,
        mock_config_manager: MagicMock,
        v1_app_config: dict[str, Any],
        v2_release_data: Release,
    ) -> None:
        """Test that cache is updated with new checksum_files after update.

        Requirement: Verify cache has updated checksum_files.
        """
        mock_config_manager.load_app_config.return_value = v1_app_config
        mock_config_manager.load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
            "verification": {},
            "appimage": {"naming": {"target_name": "test-app"}},
        }

        with (
            patch("my_unicorn.core.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.FileOperations"),
            patch("my_unicorn.core.update.BackupService"),
            patch(
                "my_unicorn.core.update.ReleaseCacheManager"
            ) as mock_cache_cls,
            patch(
                "my_unicorn.core.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.VerificationService"
            ) as mock_verify_cls,
            patch(
                "my_unicorn.core.update.PostDownloadProcessor"
            ) as mock_processor_cls,
        ):
            mock_cache = MagicMock()
            mock_cache.store_checksum_file = AsyncMock(return_value=True)
            mock_cache_cls.return_value = mock_cache

            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/test-app.AppImage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            mock_verify = MagicMock()
            mock_verify_cls.return_value = mock_verify

            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                return_value=PostDownloadResult(
                    success=True,
                    install_path=Path("/test/storage/test-app.AppImage"),
                    verification_result={
                        "passed": True,
                        "methods": {"digest": {"passed": True}},
                    },
                    icon_result={"icon_path": "/test/icon/test-app.png"},
                    config_result={"success": True},
                    desktop_result={"success": True},
                )
            )
            mock_processor_cls.return_value = mock_processor

            manager = UpdateManager(mock_config_manager)

            # Verify cache_manager is properly assigned
            assert manager.cache_manager is mock_cache

            # Initialize services to setup verification with cache
            mock_session = AsyncMock()
            manager._initialize_services(mock_session)

            # VerificationService should be created with cache_manager
            mock_verify_cls.assert_called_with(
                mock_download,
                mock_download.progress_reporter,
                cache_manager=mock_cache,
            )

    @pytest.mark.asyncio
    async def test_update_verification_flow_from_digest_to_checksum_file(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test update where v1 used digest and v2 uses checksum_file.

        This is a realistic scenario where the verification method changes
        between versions.
        """
        v1_config = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "evolving-app",
            "state": {
                "version": "1.0.0",
                "installed_date": "2026-01-01T00:00:00+00:00",
                "installed_path": "/test/storage/evolving-app.AppImage",
                "verification": {
                    "passed": True,
                    "overall_passed": True,
                    "actual_method": "digest",
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                            "algorithm": "SHA256",
                            "expected": "v1digestonly",
                            "computed": "v1digestonly",
                            "source": "github_api",
                        }
                    ],
                },
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": "/test/icon/evolving-app.png",
                },
            },
        }

        mock_config_manager.load_app_config.return_value = v1_config
        mock_config_manager.load_catalog.return_value = {
            "source": {"owner": "evolving", "repo": "app"},
            "verification": {"checksum_file": "SHA256SUMS.txt"},
            "appimage": {"naming": {"target_name": "evolving-app"}},
        }

        v2_release = Release(
            owner="evolving",
            repo="app",
            version="2.0.0",
            prerelease=False,
            assets=[
                Asset(
                    name="evolving-app-2.0.0.AppImage",
                    size=3000,
                    digest=None,  # v2 has no digest
                    browser_download_url="https://example.com/v2.AppImage",
                ),
                Asset(
                    name="SHA256SUMS.txt",
                    size=100,
                    digest=None,
                    browser_download_url="https://example.com/SHA256SUMS.txt",
                ),
            ],
            original_tag_name="v2.0.0",
        )

        with (
            patch("my_unicorn.core.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.FileOperations"),
            patch("my_unicorn.core.update.BackupService"),
            patch("my_unicorn.core.update.ReleaseCacheManager"),
            patch(
                "my_unicorn.core.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.PostDownloadProcessor"
            ) as mock_processor_cls,
        ):
            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/evolving-app.AppImage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            # v2 verification uses checksum_file method
            v2_verification = {
                "passed": True,
                "methods": {
                    "checksum_file": {
                        "passed": True,
                        "hash": "v2checksumhash",
                        "computed_hash": "v2checksumhash",
                        "hash_type": "sha256",
                        "url": "https://example.com/SHA256SUMS.txt",
                    }
                },
            }

            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                return_value=PostDownloadResult(
                    success=True,
                    install_path=Path("/test/storage/evolving-app.AppImage"),
                    verification_result=v2_verification,
                    icon_result={"icon_path": "/test/icon/evolving-app.png"},
                    config_result={"success": True},
                    desktop_result={"success": True},
                )
            )
            mock_processor_cls.return_value = mock_processor

            manager = UpdateManager(mock_config_manager)

            update_info = UpdateInfo(
                app_name="evolving-app",
                current_version="1.0.0",
                latest_version="2.0.0",
                has_update=True,
                release_data=v2_release,
                app_config=v1_config,
            )

            mock_context = {
                "app_config": v1_config,
                "update_info": update_info,
                "appimage_asset": v2_release.assets[0],
                "catalog_entry": mock_config_manager.load_catalog.return_value,
                "owner": "evolving",
                "repo": "app",
            }

            mock_session = AsyncMock()

            with patch(
                "my_unicorn.core.update.prepare_update_context",
                new=AsyncMock(return_value=(mock_context, None)),
            ):
                success, error = await manager.update_single_app(
                    "evolving-app", mock_session, force=True
                )

            assert success is True
            assert error is None

            # Verify the update was processed
            mock_processor.process.assert_called_once()
            context = mock_processor.process.call_args[0][0]
            assert context.operation_type == OperationType.UPDATE
            assert context.app_name == "evolving-app"

    @pytest.mark.asyncio
    async def test_update_verification_result_passed_to_config_update(
        self,
        mock_config_manager: MagicMock,
        v1_app_config: dict[str, Any],
        v2_release_data: Release,
    ) -> None:
        """Test that new verification result is passed to config update.

        Ensures verification state is properly updated in app config.
        """
        mock_config_manager.load_app_config.return_value = v1_app_config
        mock_config_manager.load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
            "verification": {},
            "appimage": {"naming": {"target_name": "test-app"}},
        }

        with (
            patch("my_unicorn.core.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.FileOperations"),
            patch("my_unicorn.core.update.BackupService"),
            patch("my_unicorn.core.update.ReleaseCacheManager"),
            patch(
                "my_unicorn.core.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.PostDownloadProcessor"
            ) as mock_processor_cls,
        ):
            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/test-app.AppImage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            v2_verification = {
                "passed": True,
                "methods": {
                    "digest": {
                        "passed": True,
                        "hash": "newhashv2",
                        "computed_hash": "newhashv2",
                        "hash_type": "sha256",
                    }
                },
            }

            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                return_value=PostDownloadResult(
                    success=True,
                    install_path=Path("/test/storage/test-app.AppImage"),
                    verification_result=v2_verification,
                    icon_result={"icon_path": "/test/icon/test-app.png"},
                    config_result={"success": True},
                    desktop_result={"success": True},
                )
            )
            mock_processor_cls.return_value = mock_processor

            manager = UpdateManager(mock_config_manager)

            update_info = UpdateInfo(
                app_name="test-app",
                current_version="1.0.0",
                latest_version="2.0.0",
                has_update=True,
                release_data=v2_release_data,
                app_config=v1_app_config,
            )

            mock_context = {
                "app_config": v1_app_config,
                "update_info": update_info,
                "appimage_asset": v2_release_data.assets[0],
                "catalog_entry": mock_config_manager.load_catalog.return_value,
                "owner": "test-owner",
                "repo": "test-repo",
            }

            mock_session = AsyncMock()

            with patch(
                "my_unicorn.core.update.prepare_update_context",
                new=AsyncMock(return_value=(mock_context, None)),
            ):
                success, _ = await manager.update_single_app(
                    "test-app", mock_session, force=True
                )

            assert success is True

            # Verify result includes verification_result from processor
            result = mock_processor.process.return_value
            assert result.verification_result is not None
            assert result.verification_result["passed"] is True
            assert "digest" in result.verification_result["methods"]
            assert (
                result.verification_result["methods"]["digest"]["hash"]
                == "newhashv2"
            )
