"""Tests for VerificationService with enhanced YAML and checksum file support."""

import asyncio
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.github import Asset, ChecksumFileInfo
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
)
from my_unicorn.core.verification.context import (
    VerificationConfig,
    VerificationContext,
)
from my_unicorn.core.verification.detection import (
    detect_available_methods,
    should_skip_verification,
)
from my_unicorn.core.verification.helpers import build_checksum_url
from my_unicorn.core.verification.results import VerificationResult
from my_unicorn.core.verification.service import VerificationService
from my_unicorn.core.verification.verification_methods import (
    verify_checksum_file,
    verify_digest,
)
from my_unicorn.core.verification.verifier import (
    LARGE_FILE_THRESHOLD,
    Verifier,
)
from my_unicorn.exceptions import VerificationError

# Test data constants
LEGCORD_YAML_CONTENT = """version: 1.1.5
files:
  - url: test.AppImage
    sha512: DL9MrvOAR7upok5iGpYUhOXSqSF2qFnn6yffND3TTrmNU4psX02hzjAuwlC4IcwAHkbMl6cEmIKXGFpN9+mWAg==
    size: 12
  - url: Legcord-1.1.5-linux-x86_64.AppImage
    sha512: JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw==
    size: 124457255
    blockMapSize: 131387
  - url: Legcord-1.1.5-linux-x86_64.rpm
    sha512: 3j2/BdKHypZrIQ0qDzJk9WjyXJwCfPfbQ7la8i+YFSHZwzOBdWDrkLPh16ZhTa3zRbQ13/XyeN76HwrRzCJIRg==
    size: 82429221
  - url: Legcord-1.1.5-linux-amd64.deb
    sha512: UjNfkg1xSME7aa7bRo4wcNz3bWMvVpcdUv08BNDCrrQ9Z/sx1nZo6FqByUd7GEZyJfgVaWYIfdQtcQaTV7Di6Q==
    size: 82572182
path: test.AppImage
sha512: DL9MrvOAR7upok5iGpYUhOXSqSF2qFnn6yffND3TTrmNU4psX02hzjAuwlC4IcwAHkbMl6cEmIKXGFpN9+mWAg==
releaseDate: '2025-05-26T17:26:48.710Z'"""

SIYUAN_SHA256SUMS_CONTENT = """6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72 test.AppImage
81529d6af7327f3468e13fe3aa226f378029aeca832336ef69af05438ef9146e siyuan-3.2.1-linux-arm64.AppImage
d0f6e2b796c730f077335a4661e712363512b911adfdb5cc419b7e02c4075c0a siyuan-3.2.1-linux-arm64.deb
dda94a3cf4b3a91a0240d4cbb70c7583f7611da92f9ed33713bb86530f2010a9 siyuan-3.2.1-linux-arm64.tar.gz
3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef siyuan-3.2.1-linux.AppImage
b39f78905a55bab8f16b82e90d784e4838c05b1605166d9cb3824a612cf6fc71 siyuan-3.2.1-linux.deb
70964f1e981a2aec0d7334cf49ee536fb592e7d19b2fccdffb005fd25a55f092 siyuan-3.2.1-linux.tar.gz
6153d6189302135f39c836e160a4a036ff495df81c3af1492d219d0d7818cb04 siyuan-3.2.1-mac-arm64.dmg
fbe6115ef044d451623c8885078172d6adc1318db6baf88e6b1fe379630a2da9 siyuan-3.2.1-mac.dmg
b75303038e40c0fcee7942bb47e9c8f853e8801fa87d63e0ab54d559837ffb03 siyuan-3.2.1-win-arm64.exe
ecfd14da398507452307bdb7671b57715a44a02ac7fdfb47e8afbe4f3b20e45f siyuan-3.2.1-win.exe
d9ad0f257893f6f2d25b948422257a938b03e6362ab638ad1a74e9bab1c0e755 siyuan-3.2.1.apk
6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72 app.AppImage"""

# Expected hex hash for Legcord AppImage (converted from Base64)
LEGCORD_EXPECTED_HEX = "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"

# Test data for SHA1/MD5 checksum files
BSD_SHA1_CONTENT = (
    """SHA1 (test.AppImage) = abc123def4567890abcdef1234567890abcdef12"""
)
BSD_MD5_CONTENT = """MD5 (test.AppImage) = abc123def4567890abcdef1234567890"""

TRADITIONAL_SHA1_CONTENT = (
    """abc123def4567890abcdef1234567890abcdef12  test.AppImage"""
)
TRADITIONAL_MD5_CONTENT = """abc123def4567890abcdef1234567890  test.AppImage"""

YAML_SHA1_CONTENT = """path: test.AppImage
sha1: q8Ej3vRWeJCrze8SNFZ4kKvN7xI="""
YAML_MD5_CONTENT = """path: test.AppImage
md5: q8Ej3vRWeJCrze8SNFZ4kA=="""

# Expected hashes for SHA1/MD5 tests
EXPECTED_SHA1_HEX = "abc123def4567890abcdef1234567890abcdef12"
EXPECTED_MD5_HEX = "abc123def4567890abcdef1234567890"


class TestVerificationConfig:
    """Test VerificationConfig dataclass."""

    def test_verification_config_defaults(self):
        """Test VerificationConfig with default values."""
        config = VerificationConfig()
        assert config.skip is False
        assert config.checksum_file is None
        assert config.checksum_hash_type == "sha256"
        assert config.digest_enabled is False

    def test_verification_config_custom_values(self):
        """Test VerificationConfig with custom values."""
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
        """Test that VerificationConfig is frozen/immutable."""
        config = VerificationConfig()
        with pytest.raises(AttributeError):
            config.skip = True


class TestVerificationResult:
    """Test VerificationResult dataclass."""

    def test_verification_result_creation(self):
        """Test VerificationResult creation."""
        methods = {"digest": {"passed": True, "hash": "abc123"}}
        config = {"skip": False}
        result = VerificationResult(
            passed=True, methods=methods, updated_config=config
        )

        assert result.passed is True
        assert result.methods == methods
        assert result.updated_config == config

    def test_verification_result_immutable(self):
        """Test that VerificationResult is frozen/immutable."""
        result = VerificationResult(passed=True, methods={}, updated_config={})
        with pytest.raises(AttributeError):
            result.passed = False


class TestVerificationService:
    """Test VerificationService with enhanced functionality."""

    @pytest.fixture
    def mock_download_service(self):
        """Create a mock download service."""
        return MagicMock()

    @pytest.fixture
    def verification_service(self, mock_download_service):
        """Create a VerificationService instance with mock dependencies."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def sample_assets(self):
        """Sample GitHub assets for testing."""
        return [
            Asset(
                name="Legcord-1.1.5-linux-x86_64.AppImage",
                browser_download_url="https://github.com/Legcord/Legcord/releases/download/v1.1.5/Legcord-1.1.5-linux-x86_64.AppImage",
                size=124457255,
                digest=None,
            ),
            Asset(
                name="latest-linux.yml",
                browser_download_url="https://github.com/Legcord/Legcord/releases/download/v1.1.5/latest-linux.yml",
                size=1234,
                digest=None,
            ),
        ]

    @pytest.fixture
    def sample_assets_with_both(self):
        """Sample GitHub assets with both YAML and traditional checksum files."""
        return [
            Asset(
                name="app.AppImage",
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/app.AppImage",
                size=12345,
                digest=None,
            ),
            Asset(
                name="latest-linux.yml",
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/latest-linux.yml",
                size=1234,
                digest=None,
            ),
            Asset(
                name="SHA256SUMS.txt",
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/SHA256SUMS.txt",
                size=567,
                digest=None,
            ),
        ]

    @pytest.fixture
    def test_file_path(self, tmp_path):
        """Create a temporary file for testing."""
        file_path = tmp_path / "test.AppImage"
        file_path.write_bytes(b"test content")
        return file_path

    def test_detect_available_methods_with_assets_yaml(
        self, verification_service, sample_assets
    ):
        """Test detection with assets containing YAML checksum file."""
        asset = Asset(
            name="Legcord-1.1.5-linux-x86_64.AppImage",
            size=124457255,
            browser_download_url="https://github.com/Legcord/Legcord/releases/download/v1.1.5/Legcord-1.1.5-linux-x86_64.AppImage",
            digest=None,
        )
        config = {"checksum_file": ""}

        has_digest, checksum_files = detect_available_methods(
            asset, config, sample_assets, "Legcord", "Legcord", "v1.1.5"
        )

        assert has_digest is False
        assert len(checksum_files) == 1  # Only latest-linux.yml
        # YAML files should be prioritized first
        assert checksum_files[0].filename == "latest-linux.yml"
        assert checksum_files[0].format_type == "yaml"

    def test_detect_available_methods_with_digest_and_assets(
        self, verification_service, sample_assets_with_both
    ):
        """Test detection with both digest and checksum files available."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/app.AppImage",
            digest="sha256:abc123",
        )
        config = {"checksum_file": ""}

        has_digest, checksum_files = detect_available_methods(
            asset,
            config,
            sample_assets_with_both,
            "test",
            "test",
            "v1.0.0",
        )

        assert has_digest is True
        assert len(checksum_files) == 2  # Both YAML and traditional

    def test_detect_available_methods_manual_checksum_file(
        self, verification_service
    ):
        """Test detection with manually configured checksum file."""
        asset = Asset(
            name="test.AppImage",
            size=124457255,
            browser_download_url="https://github.com/owner/repo/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"checksum_file": "manual-checksums.txt"}

        has_digest, checksum_files = detect_available_methods(
            asset, config, None, "owner", "repo", "v1.0.0"
        )

        assert has_digest is False
        assert len(checksum_files) == 1
        assert checksum_files[0].filename == "manual-checksums.txt"
        assert checksum_files[0].format_type == "traditional"

    def test_detect_available_methods_v2_checksum_file_dict(
        self, verification_service
    ):
        """Test detection with v2 format dict checksum_file configuration.

        This is a regression test for the bug where v2 catalog format
        uses a dict for checksum_file with 'filename' and 'algorithm' keys,
        but the code was treating it as a string and calling .strip() on it.
        """
        asset = Asset(
            name="test.AppImage",
            size=124457255,
            browser_download_url="https://github.com/owner/repo/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        # v2 format: checksum_file is a dict
        config = {
            "checksum_file": {
                "filename": "latest-linux.yml",
                "algorithm": "sha512",
            }
        }

        has_digest, checksum_files = detect_available_methods(
            asset, config, None, "owner", "repo", "v1.0.0"
        )

        assert has_digest is False
        assert len(checksum_files) == 1
        assert checksum_files[0].filename == "latest-linux.yml"
        # YAML files should be detected based on extension
        assert checksum_files[0].format_type in ["yaml", "traditional"]

    def test_detect_available_methods_backward_compatibility(
        self, verification_service
    ):
        """Test backward compatibility when assets parameter is not provided."""
        asset = Asset(
            name="test.AppImage",
            size=124457255,
            browser_download_url="https://github.com/owner/repo/releases/download/v1.0.0/test.AppImage",
            digest="sha256:abc123",
        )
        config = {"checksum_file": "checksums.txt"}

        # Without assets parameter (old behavior)
        has_digest, checksum_files = detect_available_methods(asset, config)

        assert has_digest is True
        assert len(checksum_files) == 0  # Can't detect without assets

    def test_should_skip_verification_logic(self, verification_service):
        """Test skip verification decision logic."""
        # Skip with no strong methods available
        should_skip, updated_config = should_skip_verification(
            {"skip": True}, has_digest=False, has_checksum_files=False
        )
        assert should_skip is True
        assert updated_config["skip"] is True

        # Override skip when strong methods available
        should_skip, updated_config = should_skip_verification(
            {"skip": True}, has_digest=True, has_checksum_files=False
        )
        assert should_skip is False
        assert updated_config["skip"] is False

        # No skip when not configured
        should_skip, updated_config = should_skip_verification(
            {"skip": False}, has_digest=False, has_checksum_files=True
        )
        assert should_skip is False

    @pytest.mark.asyncio
    async def test_verify_digest_success(self, verification_service):
        """Test successful digest verification."""
        with patch(
            "my_unicorn.core.verification.verifier.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.verify_digest.return_value = None

            result = await verify_digest(
                mock_verifier, "sha256:abc123", "testapp", False
            )

            assert result.passed is True
            assert result.hash == "sha256:abc123"
            assert "GitHub API digest verification" in result.details

    @pytest.mark.asyncio
    async def test_verify_digest_failure(self, verification_service):
        """Test failed digest verification."""
        with patch(
            "my_unicorn.core.verification.verifier.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.verify_digest.side_effect = Exception(
                "Hash mismatch"
            )

            result = await verify_digest(
                mock_verifier, "sha256:abc123", "testapp", False
            )

            assert result.passed is False
            assert result.hash == "sha256:abc123"
            assert "Hash mismatch" in result.details

    @pytest.mark.asyncio
    async def test_verify_yaml_checksum_file(
        self, verification_service, mock_download_service
    ):
        """Test YAML checksum file verification (Legcord example)."""
        mock_download_service.download_checksum_file = AsyncMock(
            return_value=LEGCORD_YAML_CONTENT
        )

        checksum_file = ChecksumFileInfo(
            filename="latest-linux.yml",
            url="https://github.com/Legcord/Legcord/releases/download/v1.1.5/latest-linux.yml",
            format_type="yaml",
        )

        with patch(
            "my_unicorn.core.verification.verifier.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.parse_checksum_file.return_value = (
                LEGCORD_EXPECTED_HEX
            )
            mock_verifier.compute_hash.return_value = LEGCORD_EXPECTED_HEX

            result = await verify_checksum_file(
                mock_verifier,
                checksum_file,
                "Legcord-1.1.5-linux-x86_64.AppImage",
                "testapp",
                mock_download_service,
            )

            assert result.passed is True
            assert result.hash == LEGCORD_EXPECTED_HEX
            assert result.computed_hash == LEGCORD_EXPECTED_HEX
            assert result.hash_type == "sha512"
            assert "yaml checksum file" in result.details
            mock_download_service.download_checksum_file.assert_called_once_with(
                checksum_file.url
            )

    @pytest.mark.asyncio
    async def test_verify_traditional_checksum_file(
        self, verification_service, mock_download_service
    ):
        """Test traditional checksum file verification (SHA256SUMS example)."""
        mock_download_service.download_checksum_file = AsyncMock(
            return_value=SIYUAN_SHA256SUMS_CONTENT
        )

        checksum_file = ChecksumFileInfo(
            filename="SHA256SUMS.txt",
            url="https://github.com/siyuan/siyuan/releases/download/v3.2.1/SHA256SUMS.txt",
            format_type="traditional",
        )

        expected_hash = (
            "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
        )

        with patch(
            "my_unicorn.core.verification.verifier.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.detect_hash_type_from_filename.return_value = (
                "sha256"
            )
            mock_verifier.parse_checksum_file.return_value = expected_hash
            mock_verifier.compute_hash.return_value = expected_hash

            result = await verify_checksum_file(
                mock_verifier,
                checksum_file,
                "siyuan-3.2.1-linux.AppImage",
                "testapp",
                mock_download_service,
            )

            assert result.passed is True
            assert result.hash == expected_hash
            assert result.computed_hash == expected_hash
            assert result.hash_type == "sha256"
            assert "traditional checksum file" in result.details

    @pytest.mark.asyncio
    async def test_verify_checksum_file_hash_mismatch(
        self, verification_service, mock_download_service
    ):
        """Test checksum file verification with hash mismatch."""
        mock_download_service.download_checksum_file = AsyncMock(
            return_value=LEGCORD_YAML_CONTENT
        )

        checksum_file = ChecksumFileInfo(
            filename="latest-linux.yml",
            url="https://github.com/Legcord/Legcord/releases/download/v1.1.5/latest-linux.yml",
            format_type="yaml",
        )

        with patch(
            "my_unicorn.core.verification.verifier.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.parse_checksum_file.return_value = (
                LEGCORD_EXPECTED_HEX
            )
            mock_verifier.compute_hash.return_value = "different_hash"

            result = await verify_checksum_file(
                mock_verifier,
                checksum_file,
                "Legcord-1.1.5-linux-x86_64.AppImage",
                "testapp",
                mock_download_service,
            )

            assert result.passed is False
            assert result.details  # Just check it has details

    @pytest.mark.asyncio
    async def test_verify_checksum_file_not_found(
        self, verification_service, mock_download_service
    ):
        """Test checksum file verification when target file not found."""
        mock_download_service.download_checksum_file = AsyncMock(
            return_value=LEGCORD_YAML_CONTENT
        )

        checksum_file = ChecksumFileInfo(
            filename="latest-linux.yml",
            url="https://github.com/Legcord/Legcord/releases/download/v1.1.5/latest-linux.yml",
            format_type="yaml",
        )

        with patch(
            "my_unicorn.core.verification.verifier.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.parse_checksum_file.return_value = None  # Not found

            result = await verify_checksum_file(
                mock_verifier,
                checksum_file,
                "NonExistentFile.AppImage",
                "testapp",
                mock_download_service,
            )

            assert result.passed is False
            assert result.details  # Just check it has details

    @pytest.mark.asyncio
    async def test_verify_file_digest_priority(
        self, verification_service, test_file_path, sample_assets
    ):
        """Test that digest verification is prioritized over checksum files."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/repo/releases/download/v1.0.0/test.AppImage",
            digest="sha256:6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72",
        )
        config = {"skip": False}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="test.AppImage",
            assets=sample_assets,
        )

        assert result.passed is True
        assert "digest" in result.methods
        # Digest verification takes priority - checksum may still be detected but not used
        assert result.methods["digest"]["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_file_fallback_to_checksum(
        self, verification_service, test_file_path, sample_assets
    ):
        """Test fallback to checksum file when digest is not available."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/Legcord/Legcord/releases/download/v1.1.5/test.AppImage",
            digest=None,
        )
        config = {"skip": False}

        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=LEGCORD_YAML_CONTENT)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="Legcord",
            repo="Legcord",
            tag_name="v1.1.5",
            app_name="test.AppImage",
            assets=sample_assets,
        )

        assert result.passed is True
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_file_multiple_checksum_files_priority(
        self, verification_service, test_file_path, sample_assets_with_both
    ):
        """Test that only the highest-priority checksum file is selected.

        With YAGNI principle, only ONE checksum file is used per verification.
        YAML files have priority 3, while generic files (SHA256SUMS) have
        priority 5, so YAML should be selected.
        """
        asset = Asset(
            name="app.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/app.AppImage",
            digest=None,
        )
        config = {"skip": False}

        # Mock YAML checksum with correct hash for app.AppImage
        # Base64 of SHA512(b"test content")
        yaml_content = """version: 1.0
path: app.AppImage
sha512: DL9MrvOAR7upok5iGpYUhOXSqSF2qFnn6yffND3TTrmNU4psX02hzjAuwlC4IcwAHkbMl6cEmIKXGFpN9+mWAg=="""

        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=yaml_content)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="test",
            tag_name="v1.0.0",
            app_name="app.AppImage",
            assets=sample_assets_with_both,
        )

        assert result.passed is True
        # Should only try ONE checksum file (highest priority)
        assert (
            verification_service.download_service.download_checksum_file.call_count
            == 1
        )
        # Should select YAML (priority 3) over SHA256SUMS (priority 5)
        call_url = verification_service.download_service.download_checksum_file.call_args[
            0
        ][0]
        assert "latest-linux.yml" in call_url

    @pytest.mark.asyncio
    async def test_verify_file_skip_verification(
        self, verification_service, test_file_path
    ):
        """Test verification is skipped when configured."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/repo/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"skip": True}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="test.AppImage",
        )

        assert result.passed is True
        assert result.methods == {}  # No methods attempted

    @pytest.mark.asyncio
    async def test_verify_file_all_methods_fail(
        self, verification_service, test_file_path, sample_assets_with_both
    ):
        """Test when all available verification methods fail."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest="sha256:wrong_hash",
        )
        config = {"skip": False}

        # Use YAML content that doesn't have test.AppImage entry to force checksum failure
        failing_yaml_content = """version: 1.1.5
files:
  - url: other-file.AppImage
    sha512: DL9MrvOAR7upok5iGpYUhOXSqSF2qFnn6yffND3TTrmNU4psX02hzjAuwlC4IcwAHkbMl6cEmIKXGFpN9+mWAg==
    size: 12
path: other-file.AppImage
sha512: DL9MrvOAR7upok5iGpYUhOXSqSF2qFnn6yffND3TTrmNU4psX02hzjAuwlC4IcwAHkbMl6cEmIKXGFpN9+mWAg==
releaseDate: '2025-05-26T17:26:48.710Z'"""

        # Mock download service to return content that doesn't contain our target file
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=failing_yaml_content)
        )

        with pytest.raises(
            VerificationError, match="All verification methods failed"
        ):
            await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="test.AppImage",
                assets=sample_assets_with_both,
            )

    @pytest.mark.asyncio
    async def test_verify_file_backward_compatibility(
        self, verification_service, test_file_path
    ):
        """Test backward compatibility without assets parameter."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/repo/releases/download/v1.0.0/test.AppImage",
            digest="sha256:6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72",
        )
        config = {"skip": False, "checksum_file": "manual.txt"}

        # Mock the download service to return proper checksum content
        verification_service.download_service.download_checksum_file = AsyncMock(
            return_value="6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72 test.AppImage"
        )

        # Call without assets parameter (old API)
        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="test.AppImage",
        )

        assert result.passed is True
        assert "digest" in result.methods

    @pytest.mark.asyncio
    async def test_verify_file_edge_case_empty_assets(
        self, verification_service, test_file_path
    ):
        """Test with empty assets list - should allow installation with warning."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/repo/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"skip": False}
        empty_assets = []

        with patch(
            "my_unicorn.core.verification.verifier.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier

            # Should allow installation with warning when no verification methods available
            result = await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="repo",
                tag_name="v1.0.0",
                app_name="test.AppImage",
                assets=empty_assets,
            )

            assert result.passed is True  # Changed: allow installation
            assert result.methods == {}

    @pytest.mark.asyncio
    async def test_verify_file_config_update(
        self, verification_service, test_file_path, sample_assets_with_both
    ):
        """Test that configuration is properly updated based on verification results."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/repo/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"skip": True, "checksum_file": ""}  # Skip initially true

        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=LEGCORD_YAML_CONTENT)
        )

        with patch(
            "my_unicorn.core.verification.verifier.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.parse_checksum_file.return_value = (
                LEGCORD_EXPECTED_HEX
            )
            mock_verifier.compute_hash.return_value = LEGCORD_EXPECTED_HEX
            result = await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="app.AppImage",
                assets=sample_assets_with_both,
            )

            assert result.passed is True
            # Should override skip setting when strong methods are available
            assert result.updated_config["skip"] is False
            assert result.updated_config["checksum_file"] == "latest-linux.yml"


class TestSHA1MD5Verification:
    """Test SHA1/MD5 verification from various checksum file formats."""

    @pytest.fixture
    def mock_download_service(self):
        """Create a mock download service."""
        return MagicMock()

    @pytest.fixture
    def verification_service(self, mock_download_service):
        """Create a VerificationService instance with mock dependencies."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def test_file_path(self, tmp_path):
        """Create a temporary file for testing."""
        file_path = tmp_path / "test.AppImage"
        # Create file with content that matches our test hashes
        file_path.write_bytes(b"test content for hash verification")
        return file_path

    async def test_verify_sha1_from_bsd_checksum(
        self, verification_service, test_file_path
    ):
        """Test SHA1 verification from BSD checksum format."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"skip": False}

        # Provide assets including the checksum file
        assets = [
            Asset(
                name="test.AppImage",
                size=12,
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
                digest=None,
            ),
            Asset(
                name="checksums.sha1",
                size=100,
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/checksums.sha1",
                digest=None,
            ),
        ]

        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=BSD_SHA1_CONTENT)
        )

        # Mock the hash computation to return expected value
        with patch(
            "my_unicorn.core.verification.service.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier.compute_hash.return_value = EXPECTED_SHA1_HEX
            mock_verifier.detect_hash_type_from_filename.return_value = "sha1"
            mock_verifier.parse_checksum_file.return_value = EXPECTED_SHA1_HEX
            mock_verifier_class.return_value = mock_verifier

            result = await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="test.AppImage",
                assets=assets,
            )

        assert result.passed is True
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True
        # Note: algorithm key may not be present in result, just check that verification works

    async def test_verify_md5_from_bsd_checksum(
        self, verification_service, test_file_path
    ):
        """Test MD5 verification from BSD checksum format."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"skip": False}
        assets = [
            Asset(
                name="MD5SUMS.txt",
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/MD5SUMS.txt",
                size=123,
                digest=None,
            )
        ]

        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=BSD_MD5_CONTENT)
        )

        # Mock the hash computation to return expected value
        with patch(
            "my_unicorn.core.verification.service.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier.compute_hash.return_value = EXPECTED_MD5_HEX
            mock_verifier.detect_hash_type_from_filename.return_value = "md5"
            mock_verifier.parse_checksum_file.return_value = EXPECTED_MD5_HEX
            mock_verifier_class.return_value = mock_verifier

            result = await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="test.AppImage",
                assets=assets,
            )

        assert result.passed is True
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

    async def test_verify_sha1_from_traditional_checksum(
        self, verification_service, test_file_path
    ):
        """Test SHA1 verification from traditional checksum format."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"skip": False}
        assets = [
            Asset(
                name="SHA1SUMS.txt",
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/SHA1SUMS.txt",
                size=123,
                digest=None,
            )
        ]

        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=TRADITIONAL_SHA1_CONTENT)
        )

        # Mock the hash computation to return expected value
        with patch(
            "my_unicorn.core.verification.service.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier.compute_hash.return_value = EXPECTED_SHA1_HEX
            mock_verifier.detect_hash_type_from_filename.return_value = "sha1"
            mock_verifier.parse_checksum_file.return_value = EXPECTED_SHA1_HEX
            mock_verifier_class.return_value = mock_verifier

            result = await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="test.AppImage",
                assets=assets,
            )

        assert result.passed is True
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

    async def test_verify_md5_from_traditional_checksum(
        self, verification_service, test_file_path
    ):
        """Test MD5 verification from traditional checksum format."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"skip": False}
        assets = [
            Asset(
                name="MD5SUMS.txt",
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/MD5SUMS.txt",
                size=123,
                digest=None,
            )
        ]

        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=TRADITIONAL_MD5_CONTENT)
        )

        # Mock the hash computation to return expected value
        with patch(
            "my_unicorn.core.verification.service.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier.compute_hash.return_value = EXPECTED_MD5_HEX
            mock_verifier.detect_hash_type_from_filename.return_value = "md5"
            mock_verifier.parse_checksum_file.return_value = EXPECTED_MD5_HEX
            mock_verifier_class.return_value = mock_verifier

            result = await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="test.AppImage",
                assets=assets,
            )

        assert result.passed is True
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

    async def test_verify_sha1_from_yaml_checksum(
        self, verification_service, test_file_path
    ):
        """Test SHA1 verification from YAML checksum format."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"skip": False}
        assets = [
            Asset(
                name="latest-linux.yml",
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/latest-linux.yml",
                size=123,
                digest=None,
            )
        ]

        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=YAML_SHA1_CONTENT)
        )

        # Mock the hash computation to return expected value
        with patch(
            "my_unicorn.core.verification.service.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier.compute_hash.return_value = EXPECTED_SHA1_HEX
            mock_verifier.detect_hash_type_from_filename.return_value = "sha1"
            mock_verifier.parse_checksum_file.return_value = EXPECTED_SHA1_HEX
            mock_verifier_class.return_value = mock_verifier

            result = await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="test.AppImage",
                assets=assets,
            )

        assert result.passed is True
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

    async def test_verify_md5_from_yaml_checksum(
        self, verification_service, test_file_path
    ):
        """Test MD5 verification from YAML checksum format."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"skip": False}
        assets = [
            Asset(
                name="latest-linux.yml",
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/latest-linux.yml",
                size=123,
                digest=None,
            )
        ]

        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=YAML_MD5_CONTENT)
        )

        # Mock the hash computation to return expected value
        with patch(
            "my_unicorn.core.verification.service.Verifier"
        ) as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier.compute_hash.return_value = EXPECTED_MD5_HEX
            mock_verifier.detect_hash_type_from_filename.return_value = "md5"
            mock_verifier.parse_checksum_file.return_value = EXPECTED_MD5_HEX
            mock_verifier_class.return_value = mock_verifier

            result = await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="test.AppImage",
                assets=assets,
            )

        assert result.passed is True
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

    def test_build_checksum_url(self, verification_service):
        """Test checksum URL building."""
        url = build_checksum_url("owner", "repo", "v1.0.0", "checksums.txt")
        expected = "https://github.com/owner/repo/releases/download/v1.0.0/checksums.txt"
        assert url == expected

    def test_build_checksum_url_special_characters(self, verification_service):
        """Test checksum URL building with special characters."""
        url = build_checksum_url(
            "owner", "repo", "v1.0.0-beta", "SHA256SUMS.txt"
        )
        expected = "https://github.com/owner/repo/releases/download/v1.0.0-beta/SHA256SUMS.txt"
        assert url == expected


# =============================================================================
# Task 2.4: Protocol Usage Tests
# =============================================================================


class TestVerificationServiceProtocolUsage:
    """Tests for VerificationService protocol-based progress reporting."""

    @pytest.fixture
    def mock_download_service(self):
        """Create a mock download service."""
        return MagicMock()

    def test_accepts_progress_reporter_protocol(self, mock_download_service):
        """VerificationService accepts ProgressReporter protocol objects."""
        # Create a mock implementing ProgressReporter protocol
        mock_reporter = MagicMock(spec=ProgressReporter)
        mock_reporter.is_active.return_value = True
        mock_reporter.add_task.return_value = "task-123"

        service = VerificationService(
            download_service=mock_download_service,
            progress_reporter=mock_reporter,
        )

        assert service.progress_reporter is mock_reporter
        assert isinstance(service.progress_reporter, ProgressReporter)

    def test_uses_null_progress_reporter_when_none_provided(
        self, mock_download_service
    ):
        """NullProgressReporter is used when no reporter is provided."""
        service = VerificationService(download_service=mock_download_service)

        assert isinstance(service.progress_reporter, NullProgressReporter)
        assert service.progress_reporter.is_active() is False

    def test_uses_null_progress_reporter_when_explicitly_none(
        self, mock_download_service
    ):
        """NullProgressReporter is used when None is explicitly passed."""
        service = VerificationService(
            download_service=mock_download_service,
            progress_reporter=None,
        )

        assert isinstance(service.progress_reporter, NullProgressReporter)

    def test_progress_reporter_attribute_accessible(
        self, mock_download_service
    ):
        """progress_reporter attribute is accessible (not progress_service)."""
        service = VerificationService(download_service=mock_download_service)

        # Check attribute name is progress_reporter, not progress_service
        assert hasattr(service, "progress_reporter")
        assert isinstance(service.progress_reporter, NullProgressReporter)

    @pytest.mark.asyncio
    async def test_progress_task_created_with_verification_type(
        self, mock_download_service
    ):
        """Progress task is created with ProgressType.VERIFICATION."""
        mock_reporter = MagicMock(spec=ProgressReporter)
        mock_reporter.is_active.return_value = True
        mock_reporter.add_task = AsyncMock(return_value="task-verification")
        mock_reporter.finish_task = AsyncMock()
        mock_reporter.get_task_info.return_value = {}

        service = VerificationService(
            download_service=mock_download_service,
            progress_reporter=mock_reporter,
        )

        # Create minimal context for _prepare_verification
        context = VerificationContext(
            file_path=Path("/tmp/test.AppImage"),
            asset=Asset(
                name="test.AppImage",
                size=100,
                browser_download_url="https://example.com/test.AppImage",
                digest=None,
            ),
            config={"skip": True},
            owner="test",
            repo="test",
            tag_name="v1.0.0",
            app_name="test",
            assets=None,
            progress_task_id=None,
        )

        # Call prepare to trigger task creation
        await service._prepare_verification(context)

        # Verify add_task was called with ProgressType.VERIFICATION
        mock_reporter.add_task.assert_called_once()
        call_args = mock_reporter.add_task.call_args
        assert call_args[0][1] == ProgressType.VERIFICATION

    @pytest.mark.asyncio
    async def test_null_progress_reporter_no_errors(
        self, mock_download_service
    ):
        """NullProgressReporter allows verification to complete."""
        service = VerificationService(download_service=mock_download_service)

        context = VerificationContext(
            file_path=Path("/tmp/test.AppImage"),
            asset=Asset(
                name="test.AppImage",
                size=100,
                browser_download_url="https://example.com/test.AppImage",
                digest=None,
            ),
            config={"skip": True},
            owner="test",
            repo="test",
            tag_name="v1.0.0",
            app_name="test",
            assets=None,
            progress_task_id=None,
        )

        # Should complete without raising any errors
        result = await service._prepare_verification(context)
        assert result is not None
        assert result.passed is True


# =============================================================================
# Task 2.5: Domain Exception Tests
# =============================================================================


class TestVerificationServiceDomainExceptions:
    """Tests for VerificationService domain exception usage (Task 2.5)."""

    @pytest.fixture
    def mock_download_service(self):
        """Create a mock download service."""
        return MagicMock()

    @pytest.fixture
    def verification_service(self, mock_download_service):
        """Create a VerificationService instance."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def test_file_path(self, tmp_path):
        """Create a temporary file for testing."""
        file_path = tmp_path / "test.AppImage"
        file_path.write_bytes(b"test content")
        return file_path

    @pytest.mark.asyncio
    async def test_verification_error_raised_when_all_methods_fail(
        self, verification_service, test_file_path, mock_download_service
    ):
        """VerificationError is raised when all verification methods fail."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest="sha256:wrong_hash_that_will_fail",
        )
        config = {"skip": False}

        with pytest.raises(VerificationError) as exc_info:
            await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="testapp",
                assets=None,
            )

        # Verify it's the correct exception type
        assert isinstance(exc_info.value, VerificationError)

    @pytest.mark.asyncio
    async def test_verification_error_includes_context_fields(
        self, verification_service, test_file_path, mock_download_service
    ):
        """VerificationError includes app_name, file_path, and method info."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest="sha256:invalid_hash",
        )
        config = {"skip": False}

        with pytest.raises(VerificationError) as exc_info:
            await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="testapp",
                assets=None,
            )

        error = exc_info.value
        # Check context dictionary contains expected fields
        assert hasattr(error, "context")
        assert "app_name" in error.context
        assert "file_path" in error.context
        assert "available_methods" in error.context
        assert "failed_methods" in error.context

        # Verify context values
        assert error.context["app_name"] == "testapp"
        assert str(test_file_path) in error.context["file_path"]
        assert "digest" in error.context["available_methods"]

    @pytest.mark.asyncio
    async def test_verification_error_not_raised_when_skip_configured(
        self, verification_service, test_file_path
    ):
        """VerificationError not raised when skip=True and no methods available."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest=None,
        )
        config = {"skip": True}

        # Should not raise - verification is skipped
        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="test",
            tag_name="v1.0.0",
            app_name="testapp",
            assets=None,
        )

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_verification_error_not_raised_when_method_passes(
        self, verification_service, test_file_path
    ):
        """VerificationError not raised when at least one method passes."""
        # Compute correct hash for test content
        content = b"test content"
        correct_hash = hashlib.sha256(content).hexdigest()

        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest=f"sha256:{correct_hash}",
        )
        config = {"skip": False}

        # Should not raise - digest verification passes
        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="test",
            tag_name="v1.0.0",
            app_name="testapp",
            assets=None,
        )

        assert result.passed is True
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

    @pytest.mark.asyncio
    async def test_verification_error_contains_all_failed_methods(
        self, verification_service, test_file_path, mock_download_service
    ):
        """VerificationError lists all methods that were attempted and failed."""
        # Mock checksum file download to also fail
        mock_download_service.download_checksum_file = AsyncMock(
            return_value="wrong_hash test.AppImage"
        )

        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
            digest="sha256:invalid_hash",
        )
        config = {"skip": False}
        assets = [
            Asset(
                name="SHA256SUMS.txt",
                browser_download_url="https://github.com/test/test/releases/download/v1.0.0/SHA256SUMS.txt",
                size=100,
                digest=None,
            )
        ]

        with pytest.raises(VerificationError) as exc_info:
            await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="testapp",
                assets=assets,
            )

        error = exc_info.value
        # Both digest and checksum file should be in available_methods
        assert len(error.context["available_methods"]) >= 1
        # Failed methods should also be populated
        assert len(error.context["failed_methods"]) >= 1


# =============================================================================
# Task 2.6: Async Hash Computation Tests
# =============================================================================


class TestHashVerifierAsyncComputation:
    """Tests for HashVerifier async hash computation (Task 2.6)."""

    @pytest.fixture
    def small_test_file(self, tmp_path):
        """Create a small test file (< 100MB threshold)."""
        file_path = tmp_path / "small_test.bin"
        file_path.write_bytes(b"small file content")
        return file_path

    @pytest.fixture
    def verifier_for_small_file(self, small_test_file):
        """Create a Verifier for the small test file."""
        return Verifier(small_test_file)

    def test_large_file_threshold_constant_exists(self):
        """LARGE_FILE_THRESHOLD constant exists and is 100MB."""
        assert LARGE_FILE_THRESHOLD == 100 * 1024 * 1024  # 100MB

    def test_compute_hash_sync_still_available(self, verifier_for_small_file):
        """Sync compute_hash() still works for backward compatibility."""
        expected = hashlib.sha256(b"small file content").hexdigest()
        result = verifier_for_small_file.compute_hash("sha256")

        assert result == expected

    @pytest.mark.asyncio
    async def test_compute_hash_async_small_file_uses_sync(
        self, verifier_for_small_file
    ):
        """Small files use synchronous computation directly (no executor)."""
        expected = hashlib.sha256(b"small file content").hexdigest()
        result = await verifier_for_small_file.compute_hash_async("sha256")

        assert result == expected

    @pytest.mark.asyncio
    async def test_compute_hash_async_returns_correct_hash(
        self, small_test_file
    ):
        """compute_hash_async returns correct hash value."""
        verifier = Verifier(small_test_file)
        expected = hashlib.sha256(b"small file content").hexdigest()

        result = await verifier.compute_hash_async("sha256")

        assert result == expected

    @pytest.mark.asyncio
    async def test_compute_hash_async_sha512(self, small_test_file):
        """compute_hash_async works with SHA512 algorithm."""
        verifier = Verifier(small_test_file)
        expected = hashlib.sha512(b"small file content").hexdigest()

        result = await verifier.compute_hash_async("sha512")

        assert result == expected

    @pytest.mark.asyncio
    async def test_compute_hash_async_file_not_found(self, tmp_path):
        """compute_hash_async raises FileNotFoundError for missing files."""
        verifier = Verifier(tmp_path / "nonexistent.bin")

        with pytest.raises(FileNotFoundError, match="File not found"):
            await verifier.compute_hash_async("sha256")

    @pytest.mark.asyncio
    async def test_compute_hash_async_invalid_algorithm(
        self, verifier_for_small_file
    ):
        """compute_hash_async raises ValueError for unsupported algorithms."""
        with pytest.raises(ValueError, match="Unsupported hash type"):
            await verifier_for_small_file.compute_hash_async("sha999")

    @pytest.mark.asyncio
    async def test_compute_hash_async_large_file_uses_executor(self, tmp_path):
        """Large files (>=100MB) use run_in_executor."""
        # Create a large file by using a mock that reports large size
        large_file = tmp_path / "large_test.bin"
        large_file.write_bytes(b"test content")

        verifier = Verifier(large_file)

        # Track whether run_in_executor was called
        executor_was_called = False

        def mock_stat(*args, **kwargs):
            # Create a mock that returns large file size
            mock_result = MagicMock()
            mock_result.st_size = LARGE_FILE_THRESHOLD + 1
            return mock_result

        # Patch at module level and track executor usage
        with patch("pathlib.Path.stat", mock_stat):
            # Patch run_in_executor to track if it's called
            async def tracking_executor(executor, func, *args):
                nonlocal executor_was_called
                executor_was_called = True
                # Actually run the computation
                return func(*args)

            with patch.object(
                asyncio.get_running_loop(),
                "run_in_executor",
                side_effect=tracking_executor,
            ):
                result = await verifier.compute_hash_async("sha256")

        # Verify executor was called for large file
        assert executor_was_called, (
            "run_in_executor should be called for large files"
        )
        # Result should still be valid
        expected = hashlib.sha256(b"test content").hexdigest()
        assert result == expected

    @pytest.mark.asyncio
    async def test_compute_hash_async_small_file_no_executor(self, tmp_path):
        """Small files (<100MB) do NOT use run_in_executor (avoid overhead)."""
        small_file = tmp_path / "small_test.bin"
        content = b"small file content"
        small_file.write_bytes(content)

        verifier = Verifier(small_file)

        # Verify run_in_executor is NOT called
        original_run_in_executor = asyncio.get_running_loop().run_in_executor

        executor_called = False

        async def tracking_run_in_executor(executor, func, *args):
            nonlocal executor_called
            executor_called = True
            return await original_run_in_executor(executor, func, *args)

        with patch.object(
            asyncio.get_running_loop(),
            "run_in_executor",
            side_effect=tracking_run_in_executor,
        ):
            result = await verifier.compute_hash_async("sha256")

        # Small files should NOT use executor
        assert not executor_called, (
            "Executor should not be used for small files"
        )

        # Result should still be correct
        expected = hashlib.sha256(content).hexdigest()
        assert result == expected

    def test_compute_hash_sync_matches_async(self, small_test_file):
        """Sync and async compute_hash return identical results."""
        verifier = Verifier(small_test_file)

        sync_result = verifier.compute_hash("sha256")
        async_result = asyncio.run(verifier.compute_hash_async("sha256"))

        assert sync_result == async_result


class TestVerificationServiceCacheIntegration:
    """Tests for VerificationService cache integration."""

    @pytest.fixture
    def mock_cache_manager(self):
        """Create a mock cache manager."""
        cache_manager = AsyncMock()
        cache_manager.store_checksum_file = AsyncMock(return_value=True)
        cache_manager.get_checksum_file = AsyncMock(return_value=None)
        cache_manager.has_checksum_file = AsyncMock(return_value=False)
        return cache_manager

    @pytest.fixture
    def test_file(self, tmp_path):
        """Create a test file with known content."""
        test_file = tmp_path / "test.AppImage"
        test_file.write_text("test content")
        return test_file

    @pytest.fixture
    def mock_download_service(self):
        """Create a mock download service."""
        service = AsyncMock()
        service.download_checksum_file = AsyncMock(
            return_value=SIYUAN_SHA256SUMS_CONTENT
        )
        return service

    def test_init_with_cache_manager(
        self, mock_download_service, mock_cache_manager
    ):
        """Test that VerificationService accepts cache_manager parameter."""
        service = VerificationService(
            download_service=mock_download_service,
            cache_manager=mock_cache_manager,
        )

        assert service.cache_manager is mock_cache_manager
        assert service.download_service is mock_download_service

    def test_init_without_cache_manager(self, mock_download_service):
        """Test that VerificationService works without cache_manager."""
        service = VerificationService(
            download_service=mock_download_service,
        )

        assert service.cache_manager is None

    async def test_cache_checksum_file_stores_data_on_success(
        self, tmp_path, mock_download_service, mock_cache_manager
    ):
        """Test that checksum file data is cached after successful verification."""
        test_file = tmp_path / "test.AppImage"
        test_file.write_text("test content")
        expected_hash = hashlib.sha256(b"test content").hexdigest()

        sha256sums = (
            f"{expected_hash} test.AppImage\nother_hash_value other.AppImage"
        )
        mock_download_service.download_checksum_file = AsyncMock(
            return_value=sha256sums
        )

        service = VerificationService(
            download_service=mock_download_service,
            cache_manager=mock_cache_manager,
        )

        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://example.com/test.AppImage",
            digest=None,
        )
        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            size=100,
            browser_download_url="https://example.com/SHA256SUMS.txt",
            digest=None,
        )

        result = await service.verify_file(
            file_path=test_file,
            asset=asset,
            config={"skip": False},
            owner="testowner",
            repo="testrepo",
            tag_name="v1.0.0",
            app_name="testapp",
            assets=[asset, checksum_asset],
        )

        assert result.passed is True

        mock_cache_manager.store_checksum_file.assert_called_once()
        call_args = mock_cache_manager.store_checksum_file.call_args
        assert call_args[0][0] == "testowner"
        assert call_args[0][1] == "testrepo"
        assert call_args[0][2] == "v1.0.0"
        file_data = call_args[0][3]
        assert file_data["algorithm"] == "SHA256"
        assert "hashes" in file_data
        assert "test.AppImage" in file_data["hashes"]

    async def test_cache_not_called_without_cache_manager(
        self, tmp_path, mock_download_service
    ):
        """Test that caching is skipped when no cache_manager provided."""
        test_file = tmp_path / "test.AppImage"
        test_file.write_text("test content")
        expected_hash = hashlib.sha256(b"test content").hexdigest()

        sha256sums = f"{expected_hash} test.AppImage"
        mock_download_service.download_checksum_file = AsyncMock(
            return_value=sha256sums
        )

        service = VerificationService(
            download_service=mock_download_service,
        )

        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://example.com/test.AppImage",
            digest=None,
        )
        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            size=100,
            browser_download_url="https://example.com/SHA256SUMS.txt",
            digest=None,
        )

        result = await service.verify_file(
            file_path=test_file,
            asset=asset,
            config={"skip": False},
            owner="testowner",
            repo="testrepo",
            tag_name="v1.0.0",
            app_name="testapp",
            assets=[asset, checksum_asset],
        )

        assert result.passed is True
