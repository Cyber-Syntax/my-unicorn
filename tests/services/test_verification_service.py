"""Comprehensive tests for VerificationService with high coverage and edge cases."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.download import DownloadService
from my_unicorn.services.verification_service import (
    VerificationConfig,
    VerificationResult,
    VerificationService,
)


class TestVerificationConfig:
    """Test cases for VerificationConfig dataclass."""

    def test_verification_config_defaults(self):
        """Test VerificationConfig creation with default values."""
        config = VerificationConfig()

        assert config.skip is False
        assert config.checksum_file is None
        assert config.checksum_hash_type == "sha256"
        assert config.digest_enabled is False

    def test_verification_config_custom_values(self):
        """Test VerificationConfig creation with custom values."""
        config = VerificationConfig(
            skip=True,
            checksum_file="checksums.txt",
            checksum_hash_type="sha512",
            digest_enabled=True,
        )

        assert config.skip is True
        assert config.checksum_file == "checksums.txt"
        assert config.checksum_hash_type == "sha512"
        assert config.digest_enabled is True

    def test_verification_config_immutable(self):
        """Test that VerificationConfig is immutable (frozen)."""
        config = VerificationConfig(skip=True)

        with pytest.raises(AttributeError):
            config.skip = False

    def test_verification_config_none_checksum_file(self):
        """Test VerificationConfig with None checksum file."""
        config = VerificationConfig(checksum_file=None)

        assert config.checksum_file is None


class TestVerificationResult:
    """Test cases for VerificationResult dataclass."""

    def test_verification_result_creation(self):
        """Test VerificationResult creation with all parameters."""
        methods = {"digest": {"passed": True, "hash": "abc123"}}
        config = {"skip": False, "digest": True}

        result = VerificationResult(
            passed=True,
            methods=methods,
            updated_config=config,
        )

        assert result.passed is True
        assert result.methods == methods
        assert result.updated_config == config

    def test_verification_result_failed(self):
        """Test VerificationResult for failed verification."""
        result = VerificationResult(
            passed=False,
            methods={"digest": {"passed": False, "details": "Hash mismatch"}},
            updated_config={"skip": False},
        )

        assert result.passed is False
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is False

    def test_verification_result_immutable(self):
        """Test that VerificationResult is immutable (frozen)."""
        result = VerificationResult(
            passed=True,
            methods={},
            updated_config={},
        )

        with pytest.raises(AttributeError):
            result.passed = False


class TestVerificationService:
    """Test cases for VerificationService."""

    @pytest.fixture
    def mock_download_service(self):
        """Create a mock DownloadService."""
        return MagicMock(spec=DownloadService)

    @pytest.fixture
    def verification_service(self, mock_download_service):
        """Create a VerificationService instance with mock dependencies."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def sample_asset(self):
        """Create a sample asset for testing."""
        return {
            "digest": "sha256:abc123def456",
            "size": 1024,
            "name": "test.AppImage",
        }

    @pytest.fixture
    def sample_config(self):
        """Create a sample verification config."""
        return {
            "skip": False,
            "checksum_file": "checksums.txt",
            "checksum_hash_type": "sha256",
        }

    @pytest.fixture
    def mock_verifier(self):
        """Create a mock Verifier instance."""
        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            yield mock_verifier

    @pytest.fixture
    def test_file_path(self, tmp_path):
        """Create a test file for verification."""
        file_path = tmp_path / "test.AppImage"
        file_path.write_bytes(b"test file content")
        return file_path

    def test_detect_available_methods_both_available(self, verification_service):
        """Test detection when both digest and checksum file are available."""
        asset = {"digest": "sha256:abc123"}
        config = {"checksum_file": "checksums.txt"}

        has_digest, has_checksum_file = verification_service._detect_available_methods(
            asset, config
        )

        assert has_digest is True
        assert has_checksum_file is True

    def test_detect_available_methods_digest_only(self, verification_service):
        """Test detection when only digest is available."""
        asset = {"digest": "sha256:abc123"}
        config = {}

        has_digest, has_checksum_file = verification_service._detect_available_methods(
            asset, config
        )

        assert has_digest is True
        assert has_checksum_file is False

    def test_detect_available_methods_checksum_only(self, verification_service):
        """Test detection when only checksum file is available."""
        asset = {}
        config = {"checksum_file": "checksums.txt"}

        has_digest, has_checksum_file = verification_service._detect_available_methods(
            asset, config
        )

        assert has_digest is False
        assert has_checksum_file is True

    def test_detect_available_methods_none_available(self, verification_service):
        """Test detection when no methods are available."""
        asset = {}
        config = {}

        has_digest, has_checksum_file = verification_service._detect_available_methods(
            asset, config
        )

        assert has_digest is False
        assert has_checksum_file is False

    def test_detect_available_methods_empty_digest(self, verification_service):
        """Test detection with empty digest."""
        asset = {"digest": ""}
        config = {"checksum_file": "checksums.txt"}

        has_digest, has_checksum_file = verification_service._detect_available_methods(
            asset, config
        )

        assert has_digest is False
        assert has_checksum_file is True

    def test_detect_available_methods_empty_checksum_file(self, verification_service):
        """Test detection with empty checksum file."""
        asset = {"digest": "sha256:abc123"}
        config = {"checksum_file": ""}

        has_digest, has_checksum_file = verification_service._detect_available_methods(
            asset, config
        )

        assert has_digest is True
        assert has_checksum_file is False

    def test_should_skip_verification_skip_and_no_methods(self, verification_service):
        """Test skip decision when skip is configured and no strong methods available."""
        config = {"skip": True}

        should_skip, updated_config = verification_service._should_skip_verification(
            config, has_digest=False, has_checksum_file=False
        )

        assert should_skip is True
        assert updated_config == {"skip": True}

    def test_should_skip_verification_skip_but_digest_available(self, verification_service):
        """Test skip decision when skip is configured but digest is available."""
        config = {"skip": True}

        should_skip, updated_config = verification_service._should_skip_verification(
            config, has_digest=True, has_checksum_file=False
        )

        assert should_skip is False
        assert updated_config["skip"] is False

    def test_should_skip_verification_skip_but_checksum_available(self, verification_service):
        """Test skip decision when skip is configured but checksum file is available."""
        config = {"skip": True}

        should_skip, updated_config = verification_service._should_skip_verification(
            config, has_digest=False, has_checksum_file=True
        )

        assert should_skip is False
        assert updated_config["skip"] is False

    def test_should_skip_verification_no_skip(self, verification_service):
        """Test skip decision when skip is not configured."""
        config = {"skip": False}

        should_skip, updated_config = verification_service._should_skip_verification(
            config, has_digest=False, has_checksum_file=False
        )

        assert should_skip is False
        assert updated_config == {"skip": False}

    def test_should_skip_verification_missing_skip_key(self, verification_service):
        """Test skip decision when skip key is missing."""
        config = {}

        should_skip, updated_config = verification_service._should_skip_verification(
            config, has_digest=True, has_checksum_file=False
        )

        assert should_skip is False
        assert updated_config == {}

    @pytest.mark.asyncio
    async def test_verify_digest_success(self, verification_service, mock_verifier):
        """Test successful digest verification."""
        digest = "sha256:abc123def456"
        mock_verifier.verify_digest.return_value = None  # Success

        result = await verification_service._verify_digest(
            mock_verifier, digest, "testapp", skip_configured=False
        )

        assert result["passed"] is True
        assert result["hash"] == digest
        assert result["details"] == "GitHub API digest verification"
        mock_verifier.verify_digest.assert_called_once_with(digest)

    @pytest.mark.asyncio
    async def test_verify_digest_failure(self, verification_service, mock_verifier):
        """Test failed digest verification."""
        digest = "sha256:abc123def456"
        mock_verifier.verify_digest.side_effect = Exception("Hash mismatch")

        result = await verification_service._verify_digest(
            mock_verifier, digest, "testapp", skip_configured=False
        )

        assert result["passed"] is False
        assert result["hash"] == digest
        assert result["details"] == "Hash mismatch"

    @pytest.mark.asyncio
    async def test_verify_digest_with_skip_configured(
        self, verification_service, mock_verifier
    ):
        """Test digest verification when skip was configured."""
        digest = "sha256:abc123def456"
        mock_verifier.verify_digest.return_value = None

        with patch("my_unicorn.services.verification_service.logger") as mock_logger:
            result = await verification_service._verify_digest(
                mock_verifier, digest, "testapp", skip_configured=True
            )

            assert result["passed"] is True
            # Should have debug logging calls
            mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_verify_checksum_file_success(self, verification_service, mock_verifier):
        """Test successful checksum file verification."""
        checksum_url = "https://example.com/checksums.txt"
        hash_type = "sha256"
        filename = "test.AppImage"
        computed_hash = "abc123def456"

        # Make verify_from_checksum_file async
        mock_verifier.verify_from_checksum_file = AsyncMock(return_value=None)
        mock_verifier.compute_hash.return_value = computed_hash

        result = await verification_service._verify_checksum_file(
            mock_verifier, checksum_url, hash_type, filename, "testapp"
        )

        assert result["passed"] is True
        assert result["hash"] == f"{hash_type}:{computed_hash}"
        assert result["details"] == "Verified against checksum file"
        assert result["url"] == checksum_url
        assert result["hash_type"] == hash_type

        mock_verifier.verify_from_checksum_file.assert_called_once_with(
            checksum_url, hash_type, verification_service.download_service, filename
        )

    @pytest.mark.asyncio
    async def test_verify_checksum_file_failure(self, verification_service, mock_verifier):
        """Test failed checksum file verification."""
        checksum_url = "https://example.com/checksums.txt"
        hash_type = "sha256"
        filename = "test.AppImage"

        mock_verifier.verify_from_checksum_file = AsyncMock(
            side_effect=Exception("Checksum mismatch")
        )

        result = await verification_service._verify_checksum_file(
            mock_verifier, checksum_url, hash_type, filename, "testapp"
        )

        assert result["passed"] is False
        assert result["hash"] == ""
        assert result["details"] == "Checksum mismatch"

    def test_verify_file_size_success(self, verification_service, mock_verifier):
        """Test successful file size verification."""
        expected_size = 1024
        file_size = 1024

        mock_verifier.get_file_size.return_value = file_size
        mock_verifier.verify_size.return_value = None

        result = verification_service._verify_file_size(mock_verifier, expected_size)

        assert result["passed"] is True
        assert result["details"] == f"File size: {file_size:,} bytes"

        mock_verifier.verify_size.assert_called_once_with(expected_size)

    def test_verify_file_size_failure(self, verification_service, mock_verifier):
        """Test failed file size verification."""
        expected_size = 1024

        mock_verifier.get_file_size.side_effect = Exception("File not found")

        result = verification_service._verify_file_size(mock_verifier, expected_size)

        assert result["passed"] is False
        assert result["details"] == "File not found"

    def test_verify_file_size_zero_expected(self, verification_service, mock_verifier):
        """Test file size verification with zero expected size."""
        expected_size = 0
        file_size = 1024

        mock_verifier.get_file_size.return_value = file_size

        result = verification_service._verify_file_size(mock_verifier, expected_size)

        assert result["passed"] is True
        # Should not call verify_size when expected_size is 0
        mock_verifier.verify_size.assert_not_called()

    def test_build_checksum_url(self, verification_service):
        """Test checksum URL building."""
        url = verification_service._build_checksum_url(
            "owner", "repo", "v1.0.0", "checksums.txt"
        )

        expected = "https://github.com/owner/repo/releases/download/v1.0.0/checksums.txt"
        assert url == expected

    def test_build_checksum_url_with_special_chars(self, verification_service):
        """Test checksum URL building with special characters."""
        url = verification_service._build_checksum_url(
            "owner-name", "repo.name", "v1.0.0-beta", "checksums-sha256.txt"
        )

        expected = "https://github.com/owner-name/repo.name/releases/download/v1.0.0-beta/checksums-sha256.txt"
        assert url == expected

    @pytest.mark.asyncio
    async def test_verify_file_skip_verification(
        self, verification_service, test_file_path, sample_asset
    ):
        """Test file verification when skip is configured and no strong methods."""
        config = {"skip": True}
        asset = {}  # No digest

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="testapp",
        )

        assert result.passed is True
        assert result.methods == {}
        assert result.updated_config == {"skip": True}

    @pytest.mark.asyncio
    async def test_verify_file_digest_success(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test file verification with successful digest verification."""
        asset = {"digest": "sha256:abc123def456", "size": 1024}
        config = {"skip": False}

        mock_verifier.verify_digest.return_value = None
        mock_verifier.get_file_size.return_value = 1024
        mock_verifier.verify_size.return_value = None

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="testapp",
        )

        assert result.passed is True
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True
        assert "size" in result.methods
        assert result.updated_config["digest"] is True

    @pytest.mark.asyncio
    async def test_verify_file_checksum_fallback(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test file verification falling back to checksum file."""
        asset = {"digest": "sha256:wronghash", "size": 1024}
        config = {"skip": False, "checksum_file": "checksums.txt"}

        # Digest verification fails
        mock_verifier.verify_digest.side_effect = Exception("Hash mismatch")
        # Checksum verification succeeds
        mock_verifier.verify_from_checksum_file = AsyncMock(return_value=None)
        mock_verifier.compute_hash.return_value = "correcthash"
        # Size verification succeeds
        mock_verifier.get_file_size.return_value = 1024
        mock_verifier.verify_size.return_value = None

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="testapp",
        )

        assert result.passed is True
        assert result.methods["digest"]["passed"] is False
        assert result.methods["checksum_file"]["passed"] is True
        assert result.methods["size"]["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_file_all_methods_fail(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test file verification when all methods fail."""
        asset = {"digest": "sha256:wronghash", "size": 1024}
        config = {"skip": False, "checksum_file": "checksums.txt"}

        # All verifications fail
        mock_verifier.verify_digest.side_effect = Exception("Digest mismatch")
        mock_verifier.verify_from_checksum_file = AsyncMock(
            side_effect=Exception("Checksum mismatch")
        )
        mock_verifier.get_file_size.return_value = 1024
        mock_verifier.verify_size.return_value = None  # Size check passes

        with pytest.raises(Exception, match="Available verification methods failed"):
            await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="repo",
                tag_name="v1.0.0",
                app_name="testapp",
            )

    @pytest.mark.asyncio
    async def test_verify_file_size_only(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test file verification with only size check available."""
        asset = {"size": 1024}
        config = {"skip": False}

        mock_verifier.get_file_size.return_value = 1024
        mock_verifier.verify_size.return_value = None

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="testapp",
        )

        assert result.passed is True
        assert "size" in result.methods
        assert result.methods["size"]["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_file_size_check_fails_no_strong_methods(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test file verification when size check fails and no strong methods available."""
        asset = {"size": 1024}
        config = {"skip": False}

        mock_verifier.get_file_size.side_effect = Exception("File corrupted")

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="testapp",
        )

        assert result.passed is False
        assert result.methods["size"]["passed"] is False

    @pytest.mark.asyncio
    async def test_verify_file_size_check_fails_with_strong_methods(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test file verification when size check fails but strong methods available."""
        asset = {"digest": "sha256:wronghash", "size": 1024}
        config = {"skip": False}

        # Digest fails, size fails
        mock_verifier.verify_digest.side_effect = Exception("Hash mismatch")
        mock_verifier.get_file_size.side_effect = Exception("File corrupted")

        with pytest.raises(Exception, match="File verification failed"):
            await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="repo",
                tag_name="v1.0.0",
                app_name="testapp",
            )

    @pytest.mark.asyncio
    async def test_verify_file_complex_scenario(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test complex verification scenario with multiple methods and edge cases."""
        asset = {"digest": "sha256:abc123", "size": 2048}
        config = {
            "skip": True,  # Skip is set but should be overridden
            "checksum_file": "checksums.sha256",
            "checksum_hash_type": "sha512",  # Different hash type
        }

        # Digest verification succeeds (overrides skip)
        mock_verifier.verify_digest.return_value = None
        # Size verification succeeds
        mock_verifier.get_file_size.return_value = 2048
        mock_verifier.verify_size.return_value = None

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test-owner",
            repo="test-repo",
            tag_name="v2.1.0",
            app_name="complex-app",
        )

        assert result.passed is True
        assert result.updated_config["skip"] is False  # Should be overridden
        assert result.updated_config["digest"] is True  # Should be enabled
        assert result.methods["digest"]["passed"] is True
        assert result.methods["size"]["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_file_logging_calls(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test that appropriate logging calls are made."""
        asset = {"digest": "sha256:abc123", "size": 1024}
        config = {"skip": False}

        mock_verifier.verify_digest.return_value = None
        mock_verifier.get_file_size.return_value = 1024
        mock_verifier.verify_size.return_value = None

        with patch("my_unicorn.services.verification_service.logger") as mock_logger:
            result = await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="repo",
                tag_name="v1.0.0",
                app_name="testapp",
            )

            # Check that debug logging was called
            mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_verify_file_edge_case_empty_asset(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test file verification with empty asset."""
        asset = {}
        config = {"skip": False}

        mock_verifier.get_file_size.return_value = 0
        mock_verifier.verify_size.return_value = None

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="testapp",
        )

        assert result.passed is True
        # Should not call verify_size when expected size is 0
        mock_verifier.verify_size.assert_not_called()

    def test_verification_service_initialization(self, mock_download_service):
        """Test that VerificationService initializes correctly."""
        service = VerificationService(mock_download_service)

        assert service.download_service is mock_download_service

    @pytest.mark.asyncio
    async def test_verify_file_with_none_values_in_asset(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test file verification with None values in asset."""
        asset = {"digest": None, "size": None}
        config = {"skip": False}

        mock_verifier.get_file_size.return_value = 1024

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="testapp",
        )

        # Should handle None values gracefully
        assert result.passed is True
        assert "size" in result.methods

    @pytest.mark.asyncio
    async def test_verify_file_preserves_original_config(
        self, verification_service, test_file_path, mock_verifier
    ):
        """Test that original config values are preserved when not modified."""
        asset = {"digest": "sha256:abc123", "size": 1024}
        config = {
            "skip": False,
            "custom_setting": "preserve_me",
            "another_setting": 42,
        }

        mock_verifier.verify_digest.return_value = None
        mock_verifier.get_file_size.return_value = 1024
        mock_verifier.verify_size.return_value = None

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="testapp",
        )

        assert result.updated_config["custom_setting"] == "preserve_me"
        assert result.updated_config["another_setting"] == 42
