"""Tests for verification strategies module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.download import DownloadService
from my_unicorn.models.verification import ChecksumFileInfo
from my_unicorn.verification.strategies import (
    ChecksumFileVerificationStrategy,
    DigestVerificationStrategy,
    VerificationStrategy,
)
from my_unicorn.verification.verify import Verifier


class TestVerificationStrategy:
    """Tests for abstract VerificationStrategy."""

    def test_verification_strategy_is_abstract(self):
        """Test that VerificationStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            VerificationStrategy()


class TestDigestVerificationStrategy:
    """Tests for DigestVerificationStrategy."""

    @pytest.fixture
    def strategy(self):
        """Digest verification strategy instance."""
        return DigestVerificationStrategy()

    @pytest.fixture
    def mock_verifier(self):
        """Mock verifier instance."""
        mock = MagicMock(spec=Verifier)
        # Configure file_path attribute that strategies access
        mock.file_path = Path("/test/app.AppImage")
        return mock

    def test_can_verify_with_digest(self, strategy):
        """Test can_verify returns True when digest is provided."""
        assert strategy.can_verify("sha256:abc123", {}) is True

    def test_can_verify_without_digest(self, strategy):
        """Test can_verify returns False when no digest is provided."""
        assert strategy.can_verify("", {}) is False
        assert strategy.can_verify(None, {}) is False

    @pytest.mark.asyncio
    async def test_verify_success(self, strategy, mock_verifier):
        """Test successful digest verification."""
        digest = "sha256:abc123"
        context = {"app_name": "test.AppImage", "skip_configured": False}
        mock_verifier.verify_digest.return_value = None  # Success
        mock_verifier.compute_hash.return_value = "abc123"

        result = await strategy.verify(mock_verifier, digest, context)

        assert result is not None
        assert result["method"] == "digest"
        assert result["status"] == "success"
        assert result["expected_hash"] == "abc123"
        assert result["computed_hash"] == "abc123"
        mock_verifier.verify_digest.assert_called_once_with(digest)

    @pytest.mark.asyncio
    async def test_verify_failure(self, strategy, mock_verifier):
        """Test digest verification failure."""
        digest = "sha256:wrong_hash"
        context = {"app_name": "test.AppImage", "skip_configured": False}
        mock_verifier.verify_digest.side_effect = ValueError("Hash mismatch")

        result = await strategy.verify(mock_verifier, digest, context)

        assert result is None
        mock_verifier.verify_digest.assert_called_once_with(digest)


class TestChecksumFileVerificationStrategy:
    """Tests for ChecksumFileVerificationStrategy."""

    @pytest.fixture
    def download_service(self):
        """Mock download service."""
        return AsyncMock(spec=DownloadService)

    @pytest.fixture
    def strategy(self, download_service):
        """Checksum file verification strategy instance."""
        return ChecksumFileVerificationStrategy(download_service)

    @pytest.fixture
    def mock_verifier(self):
        """Mock verifier instance."""
        mock = MagicMock(spec=Verifier)
        # Configure file_path attribute that strategies access
        mock.file_path = Path("/test/app.AppImage")
        return mock

    @pytest.fixture
    def sample_checksum_file(self):
        """Sample checksum file info."""
        return ChecksumFileInfo(
            filename="SHA256SUMS",
            url="https://example.com/SHA256SUMS",
            format_type="traditional",
        )

    def test_can_verify_with_checksum_file(self, strategy):
        """Test can_verify returns True when checksum file is provided."""
        checksum_file = ChecksumFileInfo("test.sha256", "url", "traditional")
        assert strategy.can_verify(checksum_file, {}) is True

    def test_can_verify_without_checksum_file(self, strategy):
        """Test can_verify returns False when no checksum file is provided."""
        assert strategy.can_verify(None, {}) is False
        assert strategy.can_verify("", {}) is False

    @pytest.mark.asyncio
    async def test_verify_success_traditional_format(
        self, strategy, mock_verifier, sample_checksum_file
    ):
        """Test successful checksum file verification with traditional format."""
        context = {"target_filename": "test.AppImage", "app_name": "test.AppImage"}
        checksum_content = "abc123  test.AppImage"
        expected_hash = "abc123"
        computed_hash = "abc123"

        strategy.download_service.download_checksum_file.return_value = checksum_content
        mock_verifier.parse_checksum_file.return_value = expected_hash
        mock_verifier.compute_hash.return_value = computed_hash

        result = await strategy.verify(mock_verifier, sample_checksum_file, context)

        assert result is not None
        assert result["method"] == "checksum_file"
        assert result["status"] == "success"
        assert result["expected_hash"] == expected_hash
        assert result["computed_hash"] == computed_hash
        assert result["checksum_file"] == sample_checksum_file.filename

    @pytest.mark.asyncio
    async def test_verify_success_yaml_format(self, strategy, mock_verifier):
        """Test successful checksum file verification with YAML format."""
        yaml_checksum_file = ChecksumFileInfo(
            filename="latest-linux.yml",
            url="https://example.com/latest-linux.yml",
            format_type="yaml",
        )
        context = {"target_filename": "test.AppImage", "app_name": "test.AppImage"}
        checksum_content = "version: 1.0\nfiles:\n  - url: test.AppImage\n    sha512: abc123"
        expected_hash = "abc123"
        computed_hash = "abc123"

        strategy.download_service.download_checksum_file.return_value = checksum_content
        mock_verifier.parse_checksum_file.return_value = expected_hash
        mock_verifier.compute_hash.return_value = computed_hash

        result = await strategy.verify(mock_verifier, yaml_checksum_file, context)

        assert result is not None
        assert result["method"] == "checksum_file"
        assert result["status"] == "success"
        assert result["checksum_file"] == yaml_checksum_file.filename

    @pytest.mark.asyncio
    async def test_verify_hash_not_found(self, strategy, mock_verifier, sample_checksum_file):
        """Test checksum verification when hash is not found in file."""
        context = {"target_filename": "test.AppImage", "app_name": "test.AppImage"}
        checksum_content = "abc123  other-file.AppImage"

        strategy.download_service.download_checksum_file.return_value = checksum_content
        mock_verifier.parse_checksum_file.return_value = None  # Hash not found

        result = await strategy.verify(mock_verifier, sample_checksum_file, context)

        assert result is None

    @pytest.mark.asyncio
    async def test_verify_hash_mismatch(self, strategy, mock_verifier, sample_checksum_file):
        """Test checksum verification when hashes don't match."""
        context = {"target_filename": "test.AppImage", "app_name": "test.AppImage"}
        checksum_content = "abc123  test.AppImage"
        expected_hash = "abc123"
        computed_hash = "different_hash"

        strategy.download_service.download_checksum_file.return_value = checksum_content
        mock_verifier.parse_checksum_file.return_value = expected_hash
        mock_verifier.compute_hash.return_value = computed_hash

        result = await strategy.verify(mock_verifier, sample_checksum_file, context)

        assert result is None

    @pytest.mark.asyncio
    async def test_verify_download_failure(
        self, strategy, mock_verifier, sample_checksum_file
    ):
        """Test checksum verification when download fails."""
        context = {"target_filename": "test.AppImage", "app_name": "test.AppImage"}

        strategy.download_service.download_checksum_file.side_effect = Exception(
            "Download failed"
        )

        result = await strategy.verify(mock_verifier, sample_checksum_file, context)

        assert result is None
