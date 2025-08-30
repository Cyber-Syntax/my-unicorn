"""Tests for VerificationService with enhanced YAML and checksum file support."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.github_client import ChecksumFileInfo
from my_unicorn.services.verification_service import (
    VerificationConfig,
    VerificationResult,
    VerificationService,
)

# Test data constants
LEGCORD_YAML_CONTENT = """version: 1.1.5
files:
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
path: Legcord-1.1.5-linux-x86_64.AppImage
sha512: JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw==
releaseDate: '2025-05-26T17:26:48.710Z'"""

SIYUAN_SHA256SUMS_CONTENT = """81529d6af7327f3468e13fe3aa226f378029aeca832336ef69af05438ef9146e siyuan-3.2.1-linux-arm64.AppImage
d0f6e2b796c730f077335a4661e712363512b911adfdb5cc419b7e02c4075c0a siyuan-3.2.1-linux-arm64.deb
dda94a3cf4b3a91a0240d4cbb70c7583f7611da92f9ed33713bb86530f2010a9 siyuan-3.2.1-linux-arm64.tar.gz
3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef siyuan-3.2.1-linux.AppImage
b39f78905a55bab8f16b82e90d784e4838c05b1605166d9cb3824a612cf6fc71 siyuan-3.2.1-linux.deb
70964f1e981a2aec0d7334cf49ee536fb592e7d19b2fccdffb005fd25a55f092 siyuan-3.2.1-linux.tar.gz
6153d6189302135f39c836e160a4a036ff495df81c3af1492d219d0d7818cb04 siyuan-3.2.1-mac-arm64.dmg
fbe6115ef044d451623c8885078172d6adc1318db6baf88e6b1fe379630a2da9 siyuan-3.2.1-mac.dmg
b75303038e40c0fcee7942bb47e9c8f853e8801fa87d63e0ab54d559837ffb03 siyuan-3.2.1-win-arm64.exe
ecfd14da398507452307bdb7671b57715a44a02ac7fdfb47e8afbe4f3b20e45f siyuan-3.2.1-win.exe
d9ad0f257893f6f2d25b948422257a938b03e6362ab638ad1a74e9bab1c0e755 siyuan-3.2.1.apk"""

# Expected hex hash for Legcord AppImage (converted from Base64)
LEGCORD_EXPECTED_HEX = "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"


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
        result = VerificationResult(passed=True, methods=methods, updated_config=config)

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
            {
                "name": "Legcord-1.1.5-linux-x86_64.AppImage",
                "browser_download_url": "https://github.com/Legcord/Legcord/releases/download/v1.1.5/Legcord-1.1.5-linux-x86_64.AppImage",
                "size": 124457255,
                "digest": "",
            },
            {
                "name": "latest-linux.yml",
                "browser_download_url": "https://github.com/Legcord/Legcord/releases/download/v1.1.5/latest-linux.yml",
                "size": 1234,
                "digest": "",
            },
        ]

    @pytest.fixture
    def sample_assets_with_both(self):
        """Sample GitHub assets with both YAML and traditional checksum files."""
        return [
            {
                "name": "app.AppImage",
                "browser_download_url": "https://github.com/test/test/releases/download/v1.0.0/app.AppImage",
                "size": 12345,
                "digest": "",
            },
            {
                "name": "latest-linux.yml",
                "browser_download_url": "https://github.com/test/test/releases/download/v1.0.0/latest-linux.yml",
                "size": 1234,
                "digest": "",
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": "https://github.com/test/test/releases/download/v1.0.0/SHA256SUMS.txt",
                "size": 567,
                "digest": "",
            },
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
        asset = {"digest": "", "size": 124457255}
        config = {"checksum_file": ""}

        has_digest, checksum_files = verification_service._detect_available_methods(
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
        asset = {"digest": "sha256:abc123", "size": 12345}
        config = {"checksum_file": ""}

        has_digest, checksum_files = verification_service._detect_available_methods(
            asset, config, sample_assets_with_both, "test", "test", "v1.0.0"
        )

        assert has_digest is True
        assert len(checksum_files) == 2  # Both YAML and traditional

    def test_detect_available_methods_manual_checksum_file(self, verification_service):
        """Test detection with manually configured checksum file."""
        asset = {"digest": "", "size": 124457255}
        config = {"checksum_file": "manual-checksums.txt"}

        has_digest, checksum_files = verification_service._detect_available_methods(
            asset, config, None, "owner", "repo", "v1.0.0"
        )

        assert has_digest is False
        assert len(checksum_files) == 1
        assert checksum_files[0].filename == "manual-checksums.txt"
        assert checksum_files[0].format_type == "traditional"

    def test_detect_available_methods_backward_compatibility(self, verification_service):
        """Test backward compatibility when assets parameter is not provided."""
        asset = {"digest": "sha256:abc123", "size": 124457255}
        config = {"checksum_file": "checksums.txt"}

        # Without assets parameter (old behavior)
        has_digest, checksum_files = verification_service._detect_available_methods(
            asset, config
        )

        assert has_digest is True
        assert len(checksum_files) == 0  # Can't detect without assets

    def test_should_skip_verification_logic(self, verification_service):
        """Test skip verification decision logic."""
        # Skip with no strong methods available
        should_skip, updated_config = verification_service._should_skip_verification(
            {"skip": True}, has_digest=False, has_checksum_files=False
        )
        assert should_skip is True
        assert updated_config["skip"] is True

        # Override skip when strong methods available
        should_skip, updated_config = verification_service._should_skip_verification(
            {"skip": True}, has_digest=True, has_checksum_files=False
        )
        assert should_skip is False
        assert updated_config["skip"] is False

        # No skip when not configured
        should_skip, updated_config = verification_service._should_skip_verification(
            {"skip": False}, has_digest=False, has_checksum_files=True
        )
        assert should_skip is False

    @pytest.mark.asyncio
    async def test_verify_digest_success(self, verification_service):
        """Test successful digest verification."""
        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.verify_digest.return_value = None

            result = await verification_service._verify_digest(
                mock_verifier, "sha256:abc123", "testapp", False
            )

            assert result["passed"] is True
            assert result["hash"] == "sha256:abc123"
            assert "GitHub API digest verification" in result["details"]

    @pytest.mark.asyncio
    async def test_verify_digest_failure(self, verification_service):
        """Test failed digest verification."""
        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.verify_digest.side_effect = Exception("Hash mismatch")

            result = await verification_service._verify_digest(
                mock_verifier, "sha256:abc123", "testapp", False
            )

            assert result["passed"] is False
            assert result["hash"] == "sha256:abc123"
            assert "Hash mismatch" in result["details"]

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

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.parse_checksum_file.return_value = LEGCORD_EXPECTED_HEX
            mock_verifier.compute_hash.return_value = LEGCORD_EXPECTED_HEX

            result = await verification_service._verify_checksum_file(
                mock_verifier, checksum_file, "Legcord-1.1.5-linux-x86_64.AppImage", "testapp"
            )

            assert result["passed"] is True
            assert "sha512:" in result["hash"]
            assert "yaml checksum file" in result["details"]
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

        expected_hash = "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.detect_hash_type_from_filename.return_value = "sha256"
            mock_verifier.parse_checksum_file.return_value = expected_hash
            mock_verifier.compute_hash.return_value = expected_hash

            result = await verification_service._verify_checksum_file(
                mock_verifier, checksum_file, "siyuan-3.2.1-linux.AppImage", "testapp"
            )

            assert result["passed"] is True
            assert result["hash"] == f"sha256:{expected_hash}"
            assert "traditional checksum file" in result["details"]

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

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.parse_checksum_file.return_value = LEGCORD_EXPECTED_HEX
            mock_verifier.compute_hash.return_value = "different_hash"

            result = await verification_service._verify_checksum_file(
                mock_verifier, checksum_file, "Legcord-1.1.5-linux-x86_64.AppImage", "testapp"
            )

            assert result["passed"] is False
            assert result["details"]  # Just check it has details

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

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.parse_checksum_file.return_value = None  # Not found

            result = await verification_service._verify_checksum_file(
                mock_verifier, checksum_file, "NonExistentFile.AppImage", "testapp"
            )

            assert result["passed"] is False
            assert result["details"]  # Just check it has details

    def test_verify_file_size(self, verification_service):
        """Test file size verification."""
        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.get_file_size.return_value = 1024
            mock_verifier.verify_size.return_value = None

            result = verification_service._verify_file_size(mock_verifier, 1024)

            assert result["passed"] is True
            assert "1,024 bytes" in result["details"]

    def test_verify_file_size_failure(self, verification_service):
        """Test file size verification failure."""
        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.get_file_size.return_value = 1024
            mock_verifier.verify_size.side_effect = Exception("Size mismatch")

            result = verification_service._verify_file_size(mock_verifier, 2048)

            assert result["passed"] is False
            assert "Size mismatch" in result["details"]

    @pytest.mark.asyncio
    async def test_verify_file_digest_priority(
        self, verification_service, test_file_path, sample_assets
    ):
        """Test that digest verification is prioritized over checksum files."""
        asset = {"digest": "sha256:abc123", "size": 12}
        config = {"skip": False}

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.verify_digest.return_value = None  # Digest succeeds
            mock_verifier.get_file_size.return_value = 12
            mock_verifier.verify_size.return_value = None

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
        asset = {"digest": "", "size": 12}  # No digest
        config = {"skip": False}

        verification_service.download_service.download_checksum_file = AsyncMock(
            return_value=LEGCORD_YAML_CONTENT
        )

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.parse_checksum_file.return_value = LEGCORD_EXPECTED_HEX
            mock_verifier.compute_hash.return_value = LEGCORD_EXPECTED_HEX
            mock_verifier.get_file_size.return_value = 12
            mock_verifier.verify_size.return_value = None

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
        """Test that multiple checksum files are tried and YAML is prioritized."""
        asset = {"digest": "", "size": 12}
        config = {"skip": False}

        # Mock first checksum file (YAML) to fail
        async def mock_download_side_effect(url):
            if "latest-linux.yml" in url:
                return "invalid yaml content"
            elif "SHA256SUMS.txt" in url:
                return SIYUAN_SHA256SUMS_CONTENT
            return ""

        verification_service.download_service.download_checksum_file = AsyncMock(
            side_effect=mock_download_side_effect
        )

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier

            def parse_side_effect(content, filename, hash_type):
                if "invalid yaml" in content:
                    return None  # YAML parsing fails
                elif "3afc23ec" in content:
                    return "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
                return None

            mock_verifier.parse_checksum_file.side_effect = parse_side_effect
            mock_verifier.compute_hash.return_value = (
                "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
            )
            mock_verifier.get_file_size.return_value = 12
            mock_verifier.verify_size.return_value = None

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
            # Should have tried both checksum files
            assert verification_service.download_service.download_checksum_file.call_count == 2

    @pytest.mark.asyncio
    async def test_verify_file_skip_verification(self, verification_service, test_file_path):
        """Test skipping verification when configured and no strong methods available."""
        asset = {"digest": "", "size": 12}
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
        asset = {"digest": "sha256:wrong_hash", "size": 12}
        config = {"skip": False}

        verification_service.download_service.download_checksum_file = AsyncMock(
            return_value=LEGCORD_YAML_CONTENT
        )

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.verify_digest.side_effect = Exception("Digest failed")
            mock_verifier.parse_checksum_file.return_value = LEGCORD_EXPECTED_HEX
            mock_verifier.compute_hash.return_value = "different_hash"  # Checksum fails
            mock_verifier.get_file_size.return_value = 12
            mock_verifier.verify_size.return_value = None

            with pytest.raises(Exception, match="Available verification methods failed"):
                await verification_service.verify_file(
                    file_path=test_file_path,
                    asset=asset,
                    config=config,
                    owner="test",
                    repo="test",
                    tag_name="v1.0.0",
                    app_name="app.AppImage",
                    assets=sample_assets_with_both,
                )

    @pytest.mark.asyncio
    async def test_verify_file_size_only_fallback(self, verification_service, test_file_path):
        """Test fallback to size-only verification when no strong methods available."""
        asset = {"digest": "", "size": 12}
        config = {"skip": False}

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.get_file_size.return_value = 12
            mock_verifier.verify_size.return_value = None

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
            assert "size" in result.methods
            assert result.methods["size"]["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_file_backward_compatibility(
        self, verification_service, test_file_path
    ):
        """Test backward compatibility without assets parameter."""
        asset = {"digest": "sha256:abc123", "size": 12}
        config = {"skip": False, "checksum_file": "manual.txt"}

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.verify_digest.return_value = None
            mock_verifier.get_file_size.return_value = 12
            mock_verifier.verify_size.return_value = None

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
        """Test with empty assets list."""
        asset = {"digest": "", "size": 12}
        config = {"skip": False}
        empty_assets = []

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.get_file_size.return_value = 12
            mock_verifier.verify_size.return_value = None

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

            assert result.passed is True
            assert "size" in result.methods

    @pytest.mark.asyncio
    async def test_verify_file_config_update(
        self, verification_service, test_file_path, sample_assets_with_both
    ):
        """Test that configuration is properly updated based on verification results."""
        asset = {"digest": "", "size": 12}
        config = {"skip": True, "checksum_file": ""}  # Skip initially true

        verification_service.download_service.download_checksum_file = AsyncMock(
            return_value=LEGCORD_YAML_CONTENT
        )

        with patch("my_unicorn.services.verification_service.Verifier") as mock_verifier_class:
            mock_verifier = MagicMock()
            mock_verifier_class.return_value = mock_verifier
            mock_verifier.parse_checksum_file.return_value = LEGCORD_EXPECTED_HEX
            mock_verifier.compute_hash.return_value = LEGCORD_EXPECTED_HEX
            mock_verifier.get_file_size.return_value = 12
            mock_verifier.verify_size.return_value = None

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

    def test_build_checksum_url(self, verification_service):
        """Test checksum URL building."""
        url = verification_service._build_checksum_url(
            "owner", "repo", "v1.0.0", "checksums.txt"
        )
        expected = "https://github.com/owner/repo/releases/download/v1.0.0/checksums.txt"
        assert url == expected

    def test_build_checksum_url_special_characters(self, verification_service):
        """Test checksum URL building with special characters."""
        url = verification_service._build_checksum_url(
            "owner", "repo", "v1.0.0-beta", "SHA256SUMS.txt"
        )
        expected = "https://github.com/owner/repo/releases/download/v1.0.0-beta/SHA256SUMS.txt"
        assert url == expected
