"""Tests for verification methods (verify_digest and verify_checksum_file).

This module provides integration tests for the high-level verification
functions that coordinate between verifier, detection, execution, and cache.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.github import Asset, ChecksumFileInfo
from my_unicorn.core.verification.context import VerificationContext
from my_unicorn.core.verification.verification_methods import (
    cache_checksum_file_data,
    verify_checksum_file,
    verify_digest,
)
from tests.core.verification.conftest import (
    EXPECTED_MD5_HEX,
    EXPECTED_SHA1_HEX,
    LEGCORD_EXPECTED_HEX,
    LEGCORD_YAML_CONTENT,
    SIYUAN_SHA256SUMS_CONTENT,
)


class TestVerifyDigest:
    """Test verify_digest function."""

    @pytest.mark.asyncio
    async def test_verify_digest_success(self) -> None:
        """Test successful digest verification from GitHub API."""
        mock_verifier = MagicMock()
        mock_verifier.file_path = MagicMock()
        mock_verifier.file_path.name = "test.AppImage"
        mock_verifier.compute_hash.return_value = "abc123def456"
        mock_verifier.verify_digest.return_value = None

        result = await verify_digest(
            mock_verifier, "sha256:abc123def456", "testapp", False
        )

        assert result is not None
        assert result.passed is True
        assert result.hash == "sha256:abc123def456"
        assert result.computed_hash == "abc123def456"
        assert "GitHub API digest verification" in result.details
        mock_verifier.verify_digest.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_digest_failures(self) -> None:
        """Test digest verification failure cases."""
        # Case 1: Hash mismatch
        mock_verifier = MagicMock()
        mock_verifier.file_path = MagicMock()
        mock_verifier.file_path.name = "test.AppImage"
        mock_verifier.compute_hash.return_value = "wrong_hash"
        mock_verifier.verify_digest.side_effect = Exception(
            "Hash mismatch: expected abc123 but got wrong_hash"
        )

        result = await verify_digest(
            mock_verifier, "sha256:abc123", "testapp", False
        )

        assert result is not None
        assert result.passed is False
        assert "Hash mismatch" in result.details

        # Case 2: Unsupported algorithm
        mock_verifier.verify_digest.side_effect = Exception(
            "Unsupported hash algorithm: blake3"
        )

        result = await verify_digest(
            mock_verifier, "blake3:abcdef123456", "testapp", False
        )

        assert result is not None
        assert result.passed is False
        assert "Unsupported" in result.details

    @pytest.mark.asyncio
    async def test_verify_digest_skip_configured_and_exceptions(
        self,
    ) -> None:
        """Test digest verification with skip configured and exception."""
        # Case 1: Skip configured but digest used anyway
        mock_verifier = MagicMock()
        mock_verifier.file_path = MagicMock()
        mock_verifier.file_path.name = "test.AppImage"
        mock_verifier.compute_hash.return_value = "correct_hash"
        mock_verifier.verify_digest.return_value = None

        result = await verify_digest(
            mock_verifier, "sha256:correct_hash", "testapp", True
        )

        assert result is not None
        assert result.passed is True
        assert result.details

        # Case 2: Unexpected runtime error
        mock_verifier.verify_digest.side_effect = RuntimeError(
            "Unexpected error"
        )

        result = await verify_digest(
            mock_verifier, "sha256:abc123", "testapp", False
        )

        assert result is not None
        assert result.passed is False
        assert "Unexpected error" in result.details


class TestVerifyChecksumFile:
    """Test verify_checksum_file function."""

    @pytest.mark.parametrize(
        (
            "format_type",
            "content",
            "filename",
            "target",
            "expected_hash",
            "hash_type",
        ),
        [
            (
                "yaml",
                LEGCORD_YAML_CONTENT,
                "latest-linux.yml",
                "Legcord-1.1.5-linux-x86_64.AppImage",
                LEGCORD_EXPECTED_HEX,
                "sha512",
            ),
            (
                "traditional",
                SIYUAN_SHA256SUMS_CONTENT,
                "SHA256SUMS.txt",
                "siyuan-3.2.1-linux.AppImage",
                "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef",
                "sha256",
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_verify_checksum_file_success(  # noqa: PLR0913
        self,
        mock_download_service: MagicMock,
        format_type: str,
        content: str,
        filename: str,
        target: str,
        expected_hash: str,
        hash_type: str,
    ) -> None:
        """Test successful checksum file verification.

        Tests YAML and traditional format checksums.
        """
        mock_download_service.download_checksum_file = AsyncMock(
            return_value=content
        )

        checksum_file = ChecksumFileInfo(
            filename=filename,
            url="https://example.com/" + filename,
            format_type=format_type,
        )

        mock_verifier = MagicMock()
        if format_type != "yaml":
            mock_verifier.detect_hash_type_from_filename.return_value = (
                hash_type
            )
        mock_verifier.parse_checksum_file.return_value = expected_hash
        mock_verifier.compute_hash.return_value = expected_hash

        result = await verify_checksum_file(
            mock_verifier,
            checksum_file,
            target,
            "testapp",
            mock_download_service,
        )

        assert result is not None
        assert result.passed is True
        assert result.hash == expected_hash
        assert result.computed_hash == expected_hash
        assert result.hash_type == hash_type
        assert format_type in result.details
        mock_download_service.download_checksum_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_checksum_file_bsd_format_success(
        self, mock_download_service: MagicMock
    ) -> None:
        """Test successful BSD format checksum file verification."""
        bsd_sha1_content = (
            "SHA1 (test.AppImage) = abc123def4567890abcdef1234567890abcdef12"
        )
        mock_download_service.download_checksum_file = AsyncMock(
            return_value=bsd_sha1_content
        )

        checksum_file = ChecksumFileInfo(
            filename="SHA1SUMS",
            url="https://example.com/SHA1SUMS",
            format_type="bsd",
        )

        mock_verifier = MagicMock()
        mock_verifier.detect_hash_type_from_filename.return_value = "sha1"
        mock_verifier.parse_checksum_file.return_value = EXPECTED_SHA1_HEX
        mock_verifier.compute_hash.return_value = EXPECTED_SHA1_HEX

        result = await verify_checksum_file(
            mock_verifier,
            checksum_file,
            "test.AppImage",
            "testapp",
            mock_download_service,
        )

        assert result is not None
        assert result.passed is True
        assert result.hash == EXPECTED_SHA1_HEX
        assert result.hash_type == "sha1"

    @pytest.mark.asyncio
    async def test_verify_checksum_file_failure_cases(
        self, mock_download_service: MagicMock
    ) -> None:
        """Test checksum file verification handles hash mismatch.

        Tests cases: hash mismatch and missing file.
        """
        # Case 1: Hash mismatch
        mock_download_service.download_checksum_file = AsyncMock(
            return_value=LEGCORD_YAML_CONTENT
        )

        checksum_file = ChecksumFileInfo(
            filename="latest-linux.yml",
            url="https://example.com/latest-linux.yml",
            format_type="yaml",
        )

        mock_verifier = MagicMock()
        mock_verifier.parse_checksum_file.return_value = LEGCORD_EXPECTED_HEX
        mock_verifier.compute_hash.return_value = "different_wrong_hash"

        result = await verify_checksum_file(
            mock_verifier,
            checksum_file,
            "Legcord-1.1.5-linux-x86_64.AppImage",
            "legcord",
            mock_download_service,
        )

        assert result is not None
        assert result.passed is False
        assert "mismatch" in result.details.lower()

        # Case 2: File not found in checksum file
        mock_verifier.parse_checksum_file.return_value = None

        result = await verify_checksum_file(
            mock_verifier,
            checksum_file,
            "NonExistentFile.AppImage",
            "legcord",
            mock_download_service,
        )

        assert result is not None
        assert result.passed is False
        assert "not found" in result.details.lower()

    @pytest.mark.asyncio
    async def test_verify_checksum_file_download_and_parse_errors(
        self, mock_download_service: MagicMock
    ) -> None:
        """Test checksum file verification handles download/parse failures."""
        checksum_file = ChecksumFileInfo(
            filename="latest-linux.yml",
            url="https://example.com/latest.yml",
            format_type="yaml",
        )

        mock_verifier = MagicMock()

        # Download failure
        mock_download_service.download_checksum_file = AsyncMock(
            side_effect=Exception("Network error: connection timeout")
        )

        result = await verify_checksum_file(
            mock_verifier,
            checksum_file,
            "test.AppImage",
            "legcord",
            mock_download_service,
        )

        assert result is not None
        assert result.passed is False
        assert "timeout" in result.details.lower()

        # Parse failure
        mock_download_service.download_checksum_file = AsyncMock(
            return_value="invalid yaml content {{{"
        )
        mock_verifier.parse_checksum_file.side_effect = Exception(
            "YAML parse error"
        )

        result = await verify_checksum_file(
            mock_verifier,
            checksum_file,
            "test.AppImage",
            "testapp",
            mock_download_service,
        )

        assert result is not None
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_verify_checksum_file_with_bad_hash_detection(
        self, mock_download_service: MagicMock
    ) -> None:
        """Test checksum file verification handles unsupported hash types."""
        mock_download_service.download_checksum_file = AsyncMock(
            return_value="ab123  test.AppImage"
        )

        checksum_file = ChecksumFileInfo(
            filename="BLAKE3SUMS",
            url="https://example.com/BLAKE3SUMS",
            format_type="traditional",
        )

        mock_verifier = MagicMock()
        mock_verifier.detect_hash_type_from_filename.return_value = "blake3"
        mock_verifier.parse_checksum_file.return_value = EXPECTED_MD5_HEX
        mock_verifier.compute_hash.return_value = EXPECTED_MD5_HEX

        result = await verify_checksum_file(
            mock_verifier,
            checksum_file,
            "test.AppImage",
            "testapp",
            mock_download_service,
        )

        assert result is not None
        assert result.hash == EXPECTED_MD5_HEX


class TestCacheChecksumFileData:
    """Test cache_checksum_file_data function."""

    @pytest.mark.asyncio
    async def test_cache_checksum_file_scenarios(self, tmp_path: Path) -> None:
        """Test caching checksum file with various scenarios."""
        test_file = tmp_path / "test.AppImage"
        test_file.write_bytes(b"test content")

        asset = Asset(
            name="test.AppImage",
            browser_download_url="https://example.com/test.AppImage",
            size=12,
            digest="",
        )

        context = VerificationContext(
            file_path=test_file,
            asset=asset,
            config={},
            owner="test",
            repo="test-repo",
            tag_name="v1.0.0",
            app_name="testapp",
            assets=[],
            progress_task_id=None,
        )

        checksum_file = ChecksumFileInfo(
            filename="SHA256SUMS",
            url="https://example.com/SHA256SUMS",
            format_type="traditional",
        )

        # Scenario 1: Successful caching
        mock_cache_manager = MagicMock()
        mock_cache_manager.store_checksum_file = AsyncMock(return_value=True)

        with patch(
            "my_unicorn.core.verification.verification_methods.parse_all_checksums"
        ) as mock_parse:
            mock_parse.return_value = {"test.AppImage": "abc123def456"}

            await cache_checksum_file_data(
                "abc123def456  test.AppImage",
                checksum_file,
                "sha256",
                mock_cache_manager,
                context,
            )

            mock_cache_manager.store_checksum_file.assert_called_once()

        # Scenario 2: No cache manager (should skip silently)
        await cache_checksum_file_data(
            "abc123  test.AppImage",
            checksum_file,
            "sha256",
            None,
            context,
        )

        # Scenario 3: No context (should skip silently)
        mock_cache_manager.reset_mock()

        await cache_checksum_file_data(
            "abc123  test.AppImage",
            checksum_file,
            "sha256",
            mock_cache_manager,
            None,
        )

        mock_cache_manager.store_checksum_file.assert_not_called()

        # Scenario 4: No hashes found (should skip caching)
        mock_cache_manager.reset_mock()

        with patch(
            "my_unicorn.core.verification.verification_methods.parse_all_checksums"
        ) as mock_parse:
            mock_parse.return_value = {}

            await cache_checksum_file_data(
                "invalid content",
                checksum_file,
                "sha256",
                mock_cache_manager,
                context,
            )

            mock_cache_manager.store_checksum_file.assert_not_called()

        # Scenario 5: Cache error is handled gracefully
        mock_cache_manager.store_checksum_file = AsyncMock(
            side_effect=Exception("Cache write error")
        )

        with patch(
            "my_unicorn.core.verification.verification_methods.parse_all_checksums"
        ) as mock_parse:
            mock_parse.return_value = {"test.AppImage": "abc123"}

            # Should not raise exception despite cache error
            await cache_checksum_file_data(
                "abc123  test.AppImage",
                checksum_file,
                "sha256",
                mock_cache_manager,
                context,
            )
