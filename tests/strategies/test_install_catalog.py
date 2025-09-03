"""Tests for CatalogInstallStrategy: validation and install logic."""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from my_unicorn.github_client import GitHubAsset
from my_unicorn.strategies.install import InstallationError, ValidationError
from my_unicorn.strategies.install_catalog import CatalogInstallStrategy, InstallationContext


@pytest.fixture
async def catalog_strategy():
    """Async fixture for CatalogInstallStrategy with mocked dependencies."""
    # Mocks for dependencies
    catalog_manager = MagicMock()
    config_manager = MagicMock()
    global_config = {"max_concurrent_downloads": 2}
    config_manager.load_global_config.return_value = global_config
    github_client = MagicMock()
    download_service = MagicMock()
    storage_service = MagicMock()
    # Use a real aiohttp session for interface compatibility
    async with aiohttp.ClientSession() as session:
        # Patch get_available_apps to return a controlled catalog
        catalog_manager.get_available_apps.return_value = {
            "app1": {"name": "app1"},
            "app2": {"name": "app2"},
        }
        # Patch get_app_config for install logic
        catalog_manager.get_app_config.side_effect = (
            lambda name: {"name": name} if name in ["app1", "app2"] else None
        )

        strategy = CatalogInstallStrategy(
            catalog_manager=catalog_manager,
            config_manager=config_manager,
            github_client=github_client,
            download_service=download_service,
            storage_service=storage_service,
            session=session,
        )
        yield strategy


def test_validate_targets_valid(catalog_strategy):
    """Test validate_targets with valid app names."""
    catalog_strategy.validate_targets(["app1"])
    catalog_strategy.validate_targets(["app1", "app2"])


def test_validate_targets_invalid(catalog_strategy):
    """Test validate_targets raises ValidationError for invalid app name."""
    with pytest.raises(ValidationError):
        catalog_strategy.validate_targets(["not_in_catalog"])


def test_validate_targets_partial_invalid(catalog_strategy):
    """Test validate_targets raises ValidationError if any target is invalid."""
    with pytest.raises(ValidationError):
        catalog_strategy.validate_targets(["app1", "not_in_catalog"])


@pytest.mark.asyncio
async def test_install_success(catalog_strategy):
    """Test install returns success for valid targets."""
    # Patch _install_single_app to simulate success
    with patch.object(
        catalog_strategy,
        "_install_single_app",
        side_effect=lambda sem, app_name, **kwargs: {
            "target": app_name,
            "success": True,
            "path": f"/fake/path/{app_name}.AppImage",
            "name": f"{app_name}.AppImage",
            "source": "catalog",
        },
    ):
        result = await catalog_strategy.install(["app1", "app2"])
        assert all(r["success"] for r in result)
        assert result[0]["target"] == "app1"
        assert result[1]["target"] == "app2"


@pytest.mark.asyncio
async def test_install_failure(catalog_strategy):
    """Test install returns error for failed install."""

    # Patch _install_single_app to simulate failure
    def fail_install(sem, app_name, **kwargs):
        raise Exception("Install failed")

    with patch.object(catalog_strategy, "_install_single_app", side_effect=fail_install):
        result = await catalog_strategy.install(["app1"])
        assert not result[0]["success"]
        assert "Install failed" in result[0]["error"]


@pytest.mark.asyncio
async def test_install_mixed_results(catalog_strategy):
    """Test install returns mixed success/error for multiple targets."""

    def mixed_install(sem, app_name, **kwargs):
        if app_name == "app1":
            return {
                "target": app_name,
                "success": True,
                "path": f"/fake/path/{app_name}.AppImage",
                "name": f"{app_name}.AppImage",
                "source": "catalog",
            }
        else:
            raise Exception("Install failed")

    with patch.object(catalog_strategy, "_install_single_app", side_effect=mixed_install):
        result = await catalog_strategy.install(["app1", "app2"])
        assert result[0]["success"]
        assert not result[1]["success"]
    assert "Install failed" in result[1]["error"]


class TestCatalogInstallVerification:
    """Test suite for the refactored verification logic in CatalogInstallStrategy."""

    @pytest.fixture
    def mock_verifier(self):
        """Mock Verifier with configurable responses."""
        verifier = MagicMock()
        verifier.verify_digest = MagicMock()
        verifier.verify_from_checksum_file = AsyncMock()
        verifier.get_file_size.return_value = 1024
        verifier.verify_size = MagicMock()
        return verifier

    @pytest.fixture
    def mock_download_service(self):
        """Mock DownloadService."""
        service = MagicMock()
        service.verify_file_size.return_value = True
        return service

    @pytest.fixture
    def catalog_strategy_with_mocks(self):
        """CatalogInstallStrategy with comprehensive mocks."""
        catalog_manager = MagicMock()
        config_manager = MagicMock()
        github_client = MagicMock()
        download_service = MagicMock()

        # Mock progress service with async methods - set to None to avoid async calls
        download_service.progress_service = None

        storage_service = MagicMock()
        session = MagicMock()

        strategy = CatalogInstallStrategy(
            catalog_manager=catalog_manager,
            config_manager=config_manager,
            github_client=github_client,
            download_service=download_service,
            storage_service=storage_service,
            session=session,
        )

        return strategy

    def _create_installation_context(
        self,
        app_name: str = "test-app",
        download_path: Path | None = None,
        app_config: dict[str, Any] | None = None,
        release_data: dict[str, Any] | None = None,
        appimage_asset: dict[str, Any] | None = None,
    ) -> InstallationContext:
        """Create InstallationContext for tests."""
        if download_path is None:
            download_path = Path("/tmp/test.AppImage")

        if app_config is None:
            app_config = {
                "owner": "test-owner",
                "repo": "test-repo",
                "verification": {
                    "digest": False,
                    "skip": True,
                    "checksum_file": "",
                    "checksum_hash_type": "sha256",
                },
            }

        if release_data is None:
            release_data = {"tag_name": "v1.0.0", "original_tag_name": "v1.0.0"}

        if appimage_asset is None:
            appimage_asset = {
                "name": "test.AppImage",
                "digest": "sha256:good_digest",
                "size": 1024,
                "browser_download_url": "https://example.com/test.AppImage",
            }

        # Cast the dict to GitHubAsset since it matches the required fields
        typed_asset: GitHubAsset = appimage_asset  # type: ignore

        return InstallationContext(
            app_name=app_name,
            app_config=app_config,
            release_data=release_data,
            appimage_asset=typed_asset,
            download_path=download_path,
            post_processing_task_id=None,
        )

    @pytest.mark.asyncio
    async def test_perform_verification_skip_true_with_digest_available(
        self, catalog_strategy_with_mocks, mock_verifier, mock_download_service
    ):
        """Test skip=true with digest available should use digest and update config."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            # Write some content to avoid zero-size file issues
            tmp_file.write(b"test content for verification")
            tmp_file.flush()
            download_path = Path(tmp_file.name)

            # Setup context with specific verification config and asset
            app_config = {
                "owner": "test-owner",
                "repo": "test-repo",
                "verification": {
                    "digest": False,  # Catalog says don't use digest
                    "skip": True,  # Catalog says skip
                    "checksum_file": "",
                    "checksum_hash_type": "sha256",
                },
            }

            appimage_asset = {
                "name": "test.AppImage",
                "digest": "sha256:good_digest",
                "size": 1024,
                "browser_download_url": "https://example.com/test.AppImage",
            }

            context = self._create_installation_context(
                download_path=download_path,
                app_config=app_config,
                appimage_asset=appimage_asset,
            )

            with patch(
                "my_unicorn.services.verification_service.Verifier", return_value=mock_verifier
            ):
                # Test
                result = await catalog_strategy_with_mocks._perform_verification(context)

                # Verify digest verification was called
                mock_verifier.verify_digest.assert_called_once_with("sha256:good_digest")

                # Verify config was updated
                assert result["updated_config"]["skip"] is False
                assert result["updated_config"]["digest"] is True
                assert "digest" in result["successful_methods"]

    @pytest.mark.asyncio
    async def test_perform_verification_skip_true_with_checksum_available(
        self, catalog_strategy_with_mocks, mock_verifier, mock_download_service
    ):
        """Test skip=true with checksum file available should use checksum and update config."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            # Write some content to avoid zero-size file issues
            tmp_file.write(b"test content for verification")
            tmp_file.flush()
            download_path = Path(tmp_file.name)

            # Setup context
            app_config = {
                "owner": "test",
                "repo": "test",
                "verification": {
                    "digest": False,
                    "skip": True,
                    "checksum_file": "SHA256SUMS",
                    "checksum_hash_type": "sha256",
                },
            }

            appimage_asset = {
                "name": "test.AppImage",
                "digest": "",  # No digest
                "size": 1024,
                "browser_download_url": "https://example.com/test.AppImage",
            }

            context = self._create_installation_context(
                download_path=download_path,
                app_config=app_config,
                appimage_asset=appimage_asset,
            )

            # Mock the verification service's verify_file method
            from my_unicorn.services.verification_service import VerificationResult

            mock_result = VerificationResult(
                passed=True,
                methods={"checksum_file": {"passed": True, "method": "sha256"}},
                updated_config={"skip": False, "checksum_file": "SHA256SUMS"},
            )

            with patch.object(
                catalog_strategy_with_mocks.verification_service,
                "verify_file",
                new_callable=AsyncMock,
                return_value=mock_result,
            ):
                catalog_strategy_with_mocks.download_service = mock_download_service

                # Test
                result = await catalog_strategy_with_mocks._perform_verification(context)

                # Verify config was updated
                assert result["updated_config"]["skip"] is False
                assert "checksum_file" in result["successful_methods"]

    @pytest.mark.asyncio
    async def test_perform_verification_skip_true_no_strong_methods(
        self, catalog_strategy_with_mocks, mock_verifier
    ):
        """Test skip=true with no strong verification methods should actually skip."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            # Write some content to avoid zero-size file issues
            tmp_file.write(b"test content for verification")
            tmp_file.flush()
            download_path = Path(tmp_file.name)

            # Setup context
            app_config = {
                "owner": "test",
                "repo": "test",
                "verification": {
                    "digest": False,
                    "skip": True,
                    "checksum_file": "",
                    "checksum_hash_type": "sha256",
                },
            }

            appimage_asset = {
                "name": "test.AppImage",
                "digest": "",  # No digest
                "size": 1024,
                "browser_download_url": "https://example.com/test.AppImage",
            }

            context = self._create_installation_context(
                download_path=download_path,
                app_config=app_config,
                appimage_asset=appimage_asset,
            )

            with patch(
                "my_unicorn.services.verification_service.Verifier", return_value=mock_verifier
            ):
                # Test
                result = await catalog_strategy_with_mocks._perform_verification(context)

                # Verify no verification methods were called
                mock_verifier.verify_digest.assert_not_called()
                mock_verifier.verify_from_checksum_file.assert_not_called()

                # Verify config was not changed (skip still true)
                assert result["updated_config"]["skip"] is True
                assert not result["successful_methods"]

    @pytest.mark.asyncio
    async def test_perform_verification_skip_false_with_digest(
        self, catalog_strategy_with_mocks, mock_verifier, mock_download_service
    ):
        """Test skip=false with digest available should use digest."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            # Write some content to avoid zero-size file issues
            tmp_file.write(b"test content for verification")
            tmp_file.flush()
            download_path = Path(tmp_file.name)

            # Setup context
            app_config = {
                "owner": "test",
                "repo": "test",
                "verification": {
                    "digest": True,
                    "skip": False,
                    "checksum_file": "",
                    "checksum_hash_type": "sha256",
                },
            }

            appimage_asset = {
                "name": "test.AppImage",
                "digest": "sha256:good_digest",
                "size": 1024,
                "browser_download_url": "https://example.com/test.AppImage",
            }

            context = self._create_installation_context(
                download_path=download_path,
                app_config=app_config,
                appimage_asset=appimage_asset,
            )

            with patch(
                "my_unicorn.services.verification_service.Verifier", return_value=mock_verifier
            ):
                # Test
                result = await catalog_strategy_with_mocks._perform_verification(context)

                # Verify digest verification was called
                mock_verifier.verify_digest.assert_called_once_with("sha256:good_digest")

                # Verify successful methods
                assert "digest" in result["successful_methods"]

    @pytest.mark.asyncio
    async def test_perform_verification_digest_fails_checksum_succeeds(
        self, catalog_strategy_with_mocks, mock_verifier, mock_download_service
    ):
        """Test digest failure falls back to checksum file verification."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            # Write some content to avoid zero-size file issues
            tmp_file.write(b"test content for verification")
            tmp_file.flush()
            download_path = Path(tmp_file.name)

            # Setup context
            app_config = {
                "owner": "test",
                "repo": "test",
                "verification": {
                    "digest": True,
                    "skip": False,
                    "checksum_file": "SHA256SUMS",
                    "checksum_hash_type": "sha256",
                },
            }

            appimage_asset = {
                "name": "test.AppImage",
                "digest": "sha256:bad_digest",
                "size": 1024,
                "browser_download_url": "https://example.com/test.AppImage",
            }

            context = self._create_installation_context(
                download_path=download_path,
                app_config=app_config,
                appimage_asset=appimage_asset,
            )

            # Mock verification service to simulate digest failure but checksum success
            from my_unicorn.services.verification_service import VerificationResult

            mock_result = VerificationResult(
                passed=True,
                methods={"checksum_file": {"passed": True, "method": "sha256"}},
                updated_config={"checksum_file": "SHA256SUMS"},
            )

            with patch.object(
                catalog_strategy_with_mocks.verification_service,
                "verify_file",
                new_callable=AsyncMock,
                return_value=mock_result,
            ):
                catalog_strategy_with_mocks.download_service = mock_download_service

                # Test
                result = await catalog_strategy_with_mocks._perform_verification(context)

                # Verify fallback worked
                assert "checksum_file" in result["successful_methods"]

    @pytest.mark.asyncio
    async def test_perform_verification_all_methods_fail(
        self, catalog_strategy_with_mocks, mock_verifier, mock_download_service
    ):
        """Test all verification methods failing raises InstallationError."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            # Write some content to avoid zero-size file issues
            tmp_file.write(b"test content for verification")
            tmp_file.flush()
            download_path = Path(tmp_file.name)

            # Setup context
            app_config = {
                "owner": "test",
                "repo": "test",
                "verification": {
                    "digest": True,
                    "skip": False,
                    "checksum_file": "SHA256SUMS",
                    "checksum_hash_type": "sha256",
                },
            }

            appimage_asset = {
                "name": "test.AppImage",
                "digest": "sha256:bad_digest",
                "size": 1024,
                "browser_download_url": "https://example.com/test.AppImage",
            }

            context = self._create_installation_context(
                download_path=download_path,
                app_config=app_config,
                appimage_asset=appimage_asset,
            )

            # Make all verifications fail
            mock_verifier.verify_digest.side_effect = ValueError("Digest failed")
            mock_verifier.verify_from_checksum_file.side_effect = ValueError("Checksum failed")

            with patch(
                "my_unicorn.services.verification_service.Verifier", return_value=mock_verifier
            ):
                catalog_strategy_with_mocks.download_service = mock_download_service

                # Test - should raise InstallationError
                with pytest.raises(
                    InstallationError, match="Available verification methods failed"
                ):
                    await catalog_strategy_with_mocks._perform_verification(context)

    def test_get_updated_verification_config_with_successful_methods(
        self, catalog_strategy_with_mocks
    ):
        """Test _get_updated_verification_config updates config based on successful verification."""
        # Setup
        catalog_config = {
            "verification": {
                "digest": False,
                "skip": True,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            }
        }
        verification_result = {
            "successful_methods": {"digest": "sha256:test_hash"},
            "updated_config": {
                "digest": True,
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            },
        }

        # Test
        updated_config = catalog_strategy_with_mocks._get_updated_verification_config(
            catalog_config, verification_result
        )

        # Verify updates
        assert updated_config["digest"] is True
        assert updated_config["skip"] is False
        assert updated_config["checksum_file"] == ""
        assert updated_config["checksum_hash_type"] == "sha256"

    def test_get_updated_verification_config_no_verification_result(
        self, catalog_strategy_with_mocks
    ):
        """Test _get_updated_verification_config with no verification result uses catalog defaults."""
        # Setup
        catalog_config = {
            "verification": {
                "digest": False,
                "skip": True,
                "checksum_file": "test.sha256",
                "checksum_hash_type": "sha256",
            }
        }

        # Test
        updated_config = catalog_strategy_with_mocks._get_updated_verification_config(
            catalog_config, None
        )

        # Verify original config is preserved
        assert updated_config["digest"] is False
        assert updated_config["skip"] is True
        assert updated_config["checksum_file"] == "test.sha256"
        assert updated_config["checksum_hash_type"] == "sha256"

    def test_get_updated_verification_config_fallback_defaults(
        self, catalog_strategy_with_mocks
    ):
        """Test _get_updated_verification_config with missing verification section uses fallback."""
        # Setup - catalog config without verification section
        catalog_config = {"owner": "test", "repo": "test"}

        # Test
        updated_config = catalog_strategy_with_mocks._get_updated_verification_config(
            catalog_config, None
        )

        # Verify fallback defaults
        assert updated_config["digest"] is True
        assert updated_config["skip"] is False
        assert updated_config["checksum_file"] == ""
        assert updated_config["checksum_hash_type"] == "sha256"

    @pytest.mark.asyncio
    async def test_end_to_end_verification_with_config_update(
        self, catalog_strategy_with_mocks, mock_verifier, mock_download_service
    ):
        """Integration test: End-to-end verification with config update behavior."""
        # Setup - simulate outdated catalog with skip=true but digest available
        app_config = {
            "owner": "test_owner",
            "repo": "test_repo",
            "verification": {
                "digest": False,  # Outdated catalog setting
                "skip": True,  # Outdated catalog setting
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            },
        }

        appimage_asset = {
            "name": "test.AppImage",
            "digest": "sha256:discovered_digest",  # New digest from GitHub API
            "size": 2048,
            "browser_download_url": "https://example.com/test.AppImage",
        }

        release_data = {"tag_name": "v2.0.0", "original_tag_name": "v2.0.0"}

        # Mock the catalog manager to simulate saving updated config
        saved_configs = {}
        catalog_strategy_with_mocks.catalog_manager.save_app_config.side_effect = (
            lambda app_name, config: saved_configs.update({app_name: config})
        )

        with tempfile.NamedTemporaryFile() as tmp_file:
            # Write some content to avoid zero-size file issues
            tmp_file.write(b"test content for verification")
            tmp_file.flush()
            download_path = Path(tmp_file.name)

            context = self._create_installation_context(
                download_path=download_path,
                app_config=app_config,
                appimage_asset=appimage_asset,
                release_data=release_data,
            )

            with patch(
                "my_unicorn.services.verification_service.Verifier", return_value=mock_verifier
            ):
                # Test verification method
                verification_result = await catalog_strategy_with_mocks._perform_verification(
                    context
                )

                # Test config creation with verification updates
                from my_unicorn.strategies.install_catalog import AppConfigData

                # Cast the dict to GitHubAsset since it matches the required fields
                typed_appimage_asset: GitHubAsset = appimage_asset  # type: ignore

                config_data = AppConfigData(
                    app_name="test_app",
                    app_path=download_path,
                    catalog_config=app_config,
                    release_data=release_data,
                    icon_dir=Path("/fake/icons"),
                    appimage_asset=typed_appimage_asset,
                    verification_result=verification_result,
                )

                catalog_strategy_with_mocks._create_app_config(config_data)

                # Verify the complete flow worked correctly
                assert mock_verifier.verify_digest.called
                assert verification_result["updated_config"]["skip"] is False
                assert verification_result["updated_config"]["digest"] is True
                assert "digest" in verification_result["successful_methods"]

                # Verify the saved config was updated
                assert "test_app" in saved_configs
                saved_config = saved_configs["test_app"]
                assert saved_config["verification"]["skip"] is False
                assert saved_config["verification"]["digest"] is True
                assert saved_config["appimage"]["digest"] == "sha256:discovered_digest"

    @pytest.mark.asyncio
    async def test_verification_fallback_chain_integration(
        self, catalog_strategy_with_mocks, mock_verifier, mock_download_service
    ):
        """Integration test: Complete verification fallback chain."""
        # Setup - digest fails, checksum succeeds
        app_config = {
            "owner": "test_owner",
            "repo": "test_repo",
            "verification": {
                "digest": True,
                "skip": False,
                "checksum_file": "SHA256SUMS",
                "checksum_hash_type": "sha256",
            },
        }

        appimage_asset = {
            "name": "test.AppImage",
            "digest": "sha256:bad_digest",  # Will fail verification
            "size": 2048,
            "browser_download_url": "https://example.com/test.AppImage",
        }

        release_data = {"tag_name": "v2.0.0", "original_tag_name": "v2.0.0"}

        with tempfile.NamedTemporaryFile() as tmp_file:
            # Write some content to avoid zero-size file issues
            tmp_file.write(b"test content for verification")
            tmp_file.flush()
            download_path = Path(tmp_file.name)

            context = self._create_installation_context(
                download_path=download_path,
                app_config=app_config,
                appimage_asset=appimage_asset,
                release_data=release_data,
            )

            # Mock verification service to return successful checksum verification
            from my_unicorn.services.verification_service import VerificationResult

            mock_result = VerificationResult(
                passed=True,
                methods={"checksum_file": {"passed": True, "method": "sha256"}},
                updated_config={"checksum_file": "SHA256SUMS"},
            )

            with patch.object(
                catalog_strategy_with_mocks.verification_service,
                "verify_file",
                new_callable=AsyncMock,
                return_value=mock_result,
            ):
                catalog_strategy_with_mocks.download_service = mock_download_service

                # Test complete fallback chain
                verification_result = await catalog_strategy_with_mocks._perform_verification(
                    context
                )

                # Verify results show checksum success
                assert "checksum_file" in verification_result["successful_methods"]

    def test_verification_config_priority_matrix(self, catalog_strategy_with_mocks):
        """Test matrix of different catalog config combinations and expected behavior."""
        test_cases = [
            # (catalog_digest, catalog_skip, has_api_digest, has_checksum, expected_digest, expected_skip)
            (False, True, True, False, True, False),  # Skip override with digest
            (False, True, False, True, False, False),  # Skip override with checksum
            (False, True, False, False, False, True),  # Actually skip (no strong methods)
            (True, False, True, False, True, False),  # Normal digest usage
            (False, False, True, False, True, False),  # Digest discovery
            (True, True, True, False, True, False),  # Skip override with digest
        ]

        for (
            catalog_digest,
            catalog_skip,
            has_api_digest,
            has_checksum,
            expected_digest,
            expected_skip,
        ) in test_cases:
            catalog_config = {
                "verification": {
                    "digest": catalog_digest,
                    "skip": catalog_skip,
                    "checksum_file": "SHA256SUMS" if has_checksum else "",
                    "checksum_hash_type": "sha256",
                }
            }

            verification_result = {
                "successful_methods": {},
                "updated_config": {
                    "digest": catalog_digest,
                    "skip": catalog_skip,
                    "checksum_file": catalog_config["verification"]["checksum_file"],
                    "checksum_hash_type": "sha256",
                },
            }

            # Simulate successful verification discovery
            if has_api_digest:
                verification_result["successful_methods"]["digest"] = "sha256:test"
                verification_result["updated_config"]["digest"] = True
                verification_result["updated_config"]["skip"] = False

            if has_checksum and not has_api_digest:
                verification_result["successful_methods"]["checksum_file"] = {}
                verification_result["updated_config"]["skip"] = False

            # Test config update logic
            result = catalog_strategy_with_mocks._get_updated_verification_config(
                catalog_config,
                verification_result if verification_result["successful_methods"] else None,
            )

            # Verify expected outcomes
            assert result["digest"] == expected_digest, (
                f"Case: digest={catalog_digest}, skip={catalog_skip}, api_digest={has_api_digest}, checksum={has_checksum}"
            )
            assert result["skip"] == expected_skip, (
                f"Case: digest={catalog_digest}, skip={catalog_skip}, api_digest={has_api_digest}, checksum={has_checksum}"
            )
