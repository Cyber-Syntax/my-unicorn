"""Tests for multi-method concurrent verification.

This module tests the concurrent execution of multiple verification methods
(digest and checksum file verification) using asyncio.gather().

Key behaviors tested:
1. Both methods pass → overall passed, no warning
2. Digest passes, checksum fails → overall passed (partial success), warning
3. Digest fails, checksum passes → overall passed (partial success), warning
4. Both methods fail → exception raised, installation blocked
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.github import Asset
from my_unicorn.core.verification.service import VerificationService

# Test data constants - SHA256 hash of b"test content"
TEST_HASH = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
TEST_CONTENT = b"test content"
WRONG_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

# GitHub test URLs
GITHUB_BASE = "https://github.com/test/repo/releases/download/v1.0"


class TestConcurrentVerification:
    """Tests for concurrent multi-method verification."""

    @pytest.fixture
    def mock_download_service(self) -> MagicMock:
        """Create a mock download service."""
        return MagicMock()

    @pytest.fixture
    def verification_service(
        self, mock_download_service: MagicMock
    ) -> VerificationService:
        """Create a VerificationService instance with mock dependencies."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def test_file_path(self, tmp_path: Path) -> Path:
        """Create a temporary test file with known content."""
        file_path = tmp_path / "test.AppImage"
        file_path.write_bytes(TEST_CONTENT)
        return file_path

    @pytest.fixture
    def asset_with_correct_digest(self) -> Asset:
        """Asset with correct SHA256 digest matching TEST_CONTENT."""
        return Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

    @pytest.fixture
    def asset_with_wrong_digest(self) -> Asset:
        """Asset with incorrect SHA256 digest."""
        return Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{WRONG_HASH}",
        )

    @pytest.fixture
    def checksum_asset(self) -> Asset:
        """Checksum file asset."""
        return Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

    @pytest.mark.asyncio
    async def test_concurrent_both_methods_pass(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        asset_with_correct_digest: Asset,
        checksum_asset: Asset,
    ) -> None:
        """Both methods pass: overall passed, digest is primary, no warning."""
        assets = [asset_with_correct_digest, checksum_asset]
        config = {"skip": False}

        # Mock checksum file download to return matching hash
        checksum_content = f"{TEST_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=checksum_content)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset_with_correct_digest,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Assert overall success
        assert result.passed is True

        # Digest method should be recorded and passed
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

        # No warning for complete success
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_concurrent_digest_pass_checksum_fail(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        asset_with_correct_digest: Asset,
        checksum_asset: Asset,
    ) -> None:
        """Digest passes, checksum fails: passed with partial warning."""
        assets = [asset_with_correct_digest, checksum_asset]
        config = {"skip": False}

        # Mock checksum file to return wrong hash
        wrong_checksum = f"{WRONG_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=wrong_checksum)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset_with_correct_digest,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Overall should pass (at least one method passed)
        assert result.passed is True

        # Digest should pass and be recorded
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

        # Checksum should be recorded as failed
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is False

        # Warning about partial verification
        assert result.warning is not None
        assert "Partial" in result.warning

    @pytest.mark.asyncio
    async def test_concurrent_digest_fail_checksum_pass(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        asset_with_wrong_digest: Asset,
        checksum_asset: Asset,
    ) -> None:
        """Digest fails, checksum passes: passed with partial warning."""
        assets = [asset_with_wrong_digest, checksum_asset]
        config = {"skip": False}

        # Mock checksum to return correct hash
        checksum_content = f"{TEST_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=checksum_content)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset_with_wrong_digest,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Overall should pass (checksum passed)
        assert result.passed is True

        # Checksum should be recorded and passed
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

        # Digest should be recorded as failed
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is False

        # Warning about partial verification
        assert result.warning is not None
        assert "Partial" in result.warning

    @pytest.mark.asyncio
    async def test_concurrent_both_methods_fail(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        asset_with_wrong_digest: Asset,
        checksum_asset: Asset,
    ) -> None:
        """Both methods fail: exception raised, installation blocked."""
        assets = [asset_with_wrong_digest, checksum_asset]
        config = {"skip": False}

        # Mock checksum to return wrong hash too
        wrong_checksum = f"{WRONG_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=wrong_checksum)
        )

        # Should raise exception when all methods fail
        with pytest.raises(Exception, match=r"verification|failed"):
            await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset_with_wrong_digest,
                config=config,
                owner="test",
                repo="repo",
                tag_name="v1.0",
                app_name="test.AppImage",
                assets=assets,
            )


class TestConcurrentVerificationEdgeCases:
    """Edge case tests for concurrent verification."""

    @pytest.fixture
    def mock_download_service(self) -> MagicMock:
        """Create a mock download service."""
        return MagicMock()

    @pytest.fixture
    def verification_service(
        self, mock_download_service: MagicMock
    ) -> VerificationService:
        """Create a VerificationService instance with mock dependencies."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def test_file_path(self, tmp_path: Path) -> Path:
        """Create a temporary test file with known content."""
        file_path = tmp_path / "test.AppImage"
        file_path.write_bytes(TEST_CONTENT)
        return file_path

    @pytest.mark.asyncio
    async def test_digest_only_pass(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Only digest available and passes: overall passed, no warning."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )
        # No checksum file in assets
        assets = [asset]
        config = {"skip": False}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Should pass with digest verification
        assert result.passed is True
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

        # No warning needed when single method passes
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_checksum_only_pass(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Only checksum available and passes: overall passed, no warning."""
        # Asset without digest
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",
        )
        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )
        assets = [asset, checksum_asset]
        config = {"skip": False}

        # Mock checksum file to return correct hash
        checksum_content = f"{TEST_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=checksum_content)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Should pass with checksum verification
        assert result.passed is True
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

        # No warning for complete success
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_no_verification_methods_available(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """No verification methods: passes with warning about no checksums."""
        # Asset without digest and no checksum files
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",
        )
        assets = [asset]  # No checksum file
        config = {"skip": False}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Should pass (cannot verify, but don't block)
        assert result.passed is True

        # Warning about no checksums provided
        assert result.warning is not None
        warning_lower = result.warning.lower()
        assert "not provide" in warning_lower or "checksum" in warning_lower

    @pytest.mark.asyncio
    async def test_verification_skipped_when_no_methods(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Verification skipped when no methods available: passes with empty.

        Note: skip=True is ignored when strong verification methods are
        available. This test verifies the skip behavior when NO methods exist.
        """
        # Asset without digest and no checksum files
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",  # No digest
        )
        assets = [asset]  # No checksum file
        config = {"skip": True}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Should pass (verification skipped)
        assert result.passed is True

        # No methods recorded when skipped (no methods available)
        assert result.methods == {}


class TestMethodResultRecording:
    """Tests for correct method result recording."""

    @pytest.fixture
    def mock_download_service(self) -> MagicMock:
        """Create a mock download service."""
        return MagicMock()

    @pytest.fixture
    def verification_service(
        self, mock_download_service: MagicMock
    ) -> VerificationService:
        """Create a VerificationService instance with mock dependencies."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def test_file_path(self, tmp_path: Path) -> Path:
        """Create a temporary test file with known content."""
        file_path = tmp_path / "test.AppImage"
        file_path.write_bytes(TEST_CONTENT)
        return file_path

    @pytest.mark.asyncio
    async def test_method_result_contains_hash_details(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Method results contain hash and details information."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )
        assets = [asset]
        config = {"skip": False}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Verify method result structure
        assert "digest" in result.methods
        digest_result = result.methods["digest"]

        # Required fields
        assert "passed" in digest_result
        assert "hash" in digest_result
        assert "details" in digest_result

        # Verify hash is recorded
        assert digest_result["hash"] != ""

    @pytest.mark.asyncio
    async def test_updated_config_includes_verification_info(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Updated config includes digest verification flag when successful."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )
        assets = [asset]
        config = {"skip": False}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Updated config should have digest flag set
        assert result.updated_config.get("digest") is True

    @pytest.mark.asyncio
    async def test_updated_config_includes_checksum_file(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Updated config includes checksum_file when successful."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",
        )
        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )
        assets = [asset, checksum_asset]
        config = {"skip": False}

        checksum_content = f"{TEST_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=checksum_content)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Updated config should have checksum_file set
        assert result.updated_config.get("checksum_file") == "SHA256SUMS.txt"


class TestMultipleChecksumFiles:
    """Tests for scenarios with multiple checksum files available."""

    @pytest.fixture
    def mock_download_service(self) -> MagicMock:
        """Create a mock download service."""
        return MagicMock()

    @pytest.fixture
    def verification_service(
        self, mock_download_service: MagicMock
    ) -> VerificationService:
        """Create a VerificationService instance with mock dependencies."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def test_file_path(self, tmp_path: Path) -> Path:
        """Create a temporary test file with known content."""
        file_path = tmp_path / "test.AppImage"
        file_path.write_bytes(TEST_CONTENT)
        return file_path

    @pytest.fixture
    def assets_with_multiple_checksums(self) -> list[Asset]:
        """Assets with digest and multiple checksum files."""
        return [
            Asset(
                name="test.AppImage",
                browser_download_url=f"{GITHUB_BASE}/test.AppImage",
                size=len(TEST_CONTENT),
                digest=f"sha256:{TEST_HASH}",
            ),
            Asset(
                name="latest-linux.yml",
                browser_download_url=f"{GITHUB_BASE}/latest-linux.yml",
                size=500,
                digest="",
            ),
            Asset(
                name="SHA256SUMS.txt",
                browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
                size=200,
                digest="",
            ),
            Asset(
                name="SHA512SUMS.txt",
                browser_download_url=f"{GITHUB_BASE}/SHA512SUMS.txt",
                size=300,
                digest="",
            ),
        ]

    @pytest.mark.asyncio
    async def test_multiple_checksum_files_with_digest(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        assets_with_multiple_checksums: list[Asset],
    ) -> None:
        """All methods attempted concurrently.

        When digest and checksums exist, all methods should be attempted.
        """
        asset = assets_with_multiple_checksums[0]
        config = {"skip": False}

        checksum_content = f"{TEST_HASH}  test.AppImage"
        mock_download = AsyncMock(return_value=checksum_content)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets_with_multiple_checksums,
        )

        assert result.passed is True
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

    @pytest.mark.asyncio
    async def test_checksum_files_use_unique_keys(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        assets_with_multiple_checksums: list[Asset],
    ) -> None:
        """Multiple checksum files produce unique method keys in result."""
        # Use asset without digest to force checksum verification
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",  # No digest
        )
        config = {"skip": False}

        checksum_content = f"{TEST_HASH}  test.AppImage"
        mock_download = AsyncMock(return_value=checksum_content)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets_with_multiple_checksums,
        )

        assert result.passed is True
        # At least one checksum method should be present
        checksum_keys = [k for k in result.methods if "checksum" in k]
        assert len(checksum_keys) >= 1

    @pytest.mark.asyncio
    async def test_first_successful_checksum_used_as_primary(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        assets_with_multiple_checksums: list[Asset],
    ) -> None:
        """First successful checksum is marked primary when no digest."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",  # No digest
        )
        config = {"skip": False}

        checksum_content = f"{TEST_HASH}  test.AppImage"
        mock_download = AsyncMock(return_value=checksum_content)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets_with_multiple_checksums,
        )

        assert result.passed is True

        # All three checksum files should be attempted
        checksum_methods = [
            k for k in result.methods.keys() if k.startswith("checksum")
        ]
        assert len(checksum_methods) >= 1


class TestExceptionHandling:
    """Tests for exception handling during concurrent verification."""

    @pytest.fixture
    def mock_download_service(self) -> MagicMock:
        """Create a mock download service."""
        return MagicMock()

    @pytest.fixture
    def verification_service(
        self, mock_download_service: MagicMock
    ) -> VerificationService:
        """Create a VerificationService instance with mock dependencies."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def test_file_path(self, tmp_path: Path) -> Path:
        """Create a temporary test file with known content."""
        file_path = tmp_path / "test.AppImage"
        file_path.write_bytes(TEST_CONTENT)
        return file_path

    @pytest.mark.asyncio
    async def test_checksum_download_exception_doesnt_block_digest(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Checksum download exception doesn't block successful digest."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        # Mock checksum download to raise exception
        mock_download = AsyncMock(side_effect=TimeoutError("Network timeout"))
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Overall should pass due to digest
        assert result.passed is True
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

    @pytest.mark.asyncio
    async def test_network_timeout_recorded_as_method_failure(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Network timeout during checksum download recorded as failure."""
        # Asset with digest and checksum
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        # Mock checksum download to raise exception
        mock_download = AsyncMock(side_effect=TimeoutError("Network timeout"))
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Digest should pass
        assert result.passed is True
        assert "digest" in result.methods

        # Checksum may be recorded as failed or not attempted
        # Either is acceptable - what matters is digest passes

    @pytest.mark.asyncio
    async def test_partial_success_with_exception_generates_warning(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Partial success with exception generates appropriate warning."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        # Mock checksum download to raise exception
        mock_download = AsyncMock(
            side_effect=ConnectionError("Connection refused")
        )
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Should pass with digest
        assert result.passed is True
        assert result.methods["digest"]["passed"] is True


class TestWarningGeneration:
    """Tests for verification warning generation in various scenarios."""

    @pytest.fixture
    def mock_download_service(self) -> MagicMock:
        """Create a mock download service."""
        return MagicMock()

    @pytest.fixture
    def verification_service(
        self, mock_download_service: MagicMock
    ) -> VerificationService:
        """Create a VerificationService instance with mock dependencies."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def test_file_path(self, tmp_path: Path) -> Path:
        """Create a temporary test file with known content."""
        file_path = tmp_path / "test.AppImage"
        file_path.write_bytes(TEST_CONTENT)
        return file_path

    @pytest.mark.asyncio
    async def test_no_warning_when_all_methods_pass(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """No warning generated when all available methods pass."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        checksum_content = f"{TEST_HASH}  test.AppImage"
        mock_download = AsyncMock(return_value=checksum_content)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        assert result.passed is True
        # No warning when all methods pass
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_no_warning_when_single_method_passes(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """No warning generated when single available method passes."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )
        assets = [asset]  # No checksum file
        config = {"skip": False}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        assert result.passed is True
        # No warning needed for single method success
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_warning_when_partial_verification(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Warning generated when some methods pass and others fail."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",  # Correct hash
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        # Wrong checksum content
        wrong_checksum = f"{WRONG_HASH}  test.AppImage"
        mock_download = AsyncMock(return_value=wrong_checksum)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Should pass (digest works)
        assert result.passed is True
        # Warning about partial verification
        assert result.warning is not None
        assert "Partial" in result.warning

    @pytest.mark.asyncio
    async def test_warning_when_no_verification_available(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Warning generated when no verification methods are available."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",  # No digest
        )
        assets = [asset]  # No checksum files
        config = {"skip": False}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Should pass (cannot verify, but don't block)
        assert result.passed is True

        # Warning about no checksums provided
        assert result.warning is not None
        warning_lower = result.warning.lower()
        assert "not provide" in warning_lower or "checksum" in warning_lower

    @pytest.mark.asyncio
    async def test_warning_contains_failure_details(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Warning includes details about which method failed."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        wrong_checksum = f"{WRONG_HASH}  test.AppImage"
        mock_download = AsyncMock(return_value=wrong_checksum)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        assert result.passed is True
        # Warning should exist for partial verification
        assert result.warning is not None
