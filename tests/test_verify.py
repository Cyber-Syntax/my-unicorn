from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.verify import VerificationConfig, Verifier

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
LEGCORD_BASE64_HASH = (
    "JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw=="
)


@pytest.fixture
def patch_logger():
    """Patch get_logger to avoid real logging output."""
    with patch("my_unicorn.verify.get_logger") as mock_logger:
        yield mock_logger


def test_verify_digest_success(tmp_path: Path, patch_logger):
    """Test Verifier.verify_digest succeeds with correct digest."""
    file = tmp_path / "file.bin"
    data = b"abc123"
    file.write_bytes(data)
    verifier = Verifier(file)
    algo = "sha256"
    import hashlib

    expected_hash = hashlib.sha256(data).hexdigest()
    digest = f"{algo}:{expected_hash}"
    verifier.verify_digest(digest)  # Should not raise


def test_verify_digest_invalid_format(tmp_path: Path, patch_logger):
    """Test Verifier.verify_digest raises on invalid digest format."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    with pytest.raises(ValueError):
        verifier.verify_digest("sha256")  # Missing hash


def test_verify_digest_wrong_hash(tmp_path: Path, patch_logger):
    """Test Verifier.verify_digest raises on hash mismatch."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    digest = "sha256:deadbeef"
    with pytest.raises(ValueError):
        verifier.verify_digest(digest)


def test_verify_digest_unsupported_algo(tmp_path: Path, patch_logger):
    """Test Verifier.verify_digest raises on unsupported algorithm."""


def test_convert_base64_to_hex(tmp_path: Path, patch_logger):
    """Test Base64 to hex conversion with Legcord example."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    hex_hash = verifier._convert_base64_to_hex(LEGCORD_BASE64_HASH)

    assert hex_hash == LEGCORD_EXPECTED_HEX


def test_convert_base64_to_hex_invalid(tmp_path: Path, patch_logger):
    """Test Base64 to hex conversion with invalid Base64."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    with pytest.raises(ValueError, match="Invalid Base64 hash"):
        verifier._convert_base64_to_hex("not_valid_base64!")


def test_is_yaml_content(tmp_path: Path, patch_logger):
    """Test YAML content detection."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    # Should detect YAML content
    assert verifier._is_yaml_content(LEGCORD_YAML_CONTENT) is True

    # Should not detect traditional checksum content as YAML
    assert verifier._is_yaml_content(SIYUAN_SHA256SUMS_CONTENT) is False

    # Should not detect random text as YAML
    assert verifier._is_yaml_content("just some random text") is False


@patch("my_unicorn.verify._YAML_AVAILABLE", False)
def test_is_yaml_content_no_yaml_available(tmp_path: Path, patch_logger):
    """Test YAML detection when PyYAML is not available."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    assert verifier._is_yaml_content(LEGCORD_YAML_CONTENT) is False


def test_parse_yaml_checksum_file_root_level(tmp_path: Path, patch_logger):
    """Test parsing YAML with hash at root level."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    yaml_content = """path: Legcord-1.1.5-linux-x86_64.AppImage
sha512: JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw=="""

    hash_value = verifier._parse_yaml_checksum_file(
        yaml_content, "Legcord-1.1.5-linux-x86_64.AppImage"
    )

    assert hash_value == LEGCORD_EXPECTED_HEX


def test_parse_yaml_checksum_file_files_array(tmp_path: Path, patch_logger):
    """Test parsing YAML with hash in files array."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    hash_value = verifier._parse_yaml_checksum_file(
        LEGCORD_YAML_CONTENT, "Legcord-1.1.5-linux-x86_64.AppImage"
    )

    assert hash_value == LEGCORD_EXPECTED_HEX


def test_parse_yaml_checksum_file_different_file(tmp_path: Path, patch_logger):
    """Test parsing YAML for different file in files array."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    hash_value = verifier._parse_yaml_checksum_file(
        LEGCORD_YAML_CONTENT, "Legcord-1.1.5-linux-x86_64.rpm"
    )

    # Should return the hex conversion of the RPM's Base64 hash
    expected_rpm_hex = verifier._convert_base64_to_hex(
        "3j2/BdKHypZrIQ0qDzJk9WjyXJwCfPfbQ7la8i+YFSHZwzOBdWDrkLPh16ZhTa3zRbQ13/XyeN76HwrRzCJIRg=="
    )
    assert hash_value == expected_rpm_hex


def test_parse_yaml_checksum_file_not_found(tmp_path: Path, patch_logger):
    """Test parsing YAML when target file is not found."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    hash_value = verifier._parse_yaml_checksum_file(
        LEGCORD_YAML_CONTENT, "NonExistentFile.AppImage"
    )

    assert hash_value is None


@patch("my_unicorn.verify._YAML_AVAILABLE", False)
def test_parse_yaml_checksum_file_no_yaml(tmp_path: Path, patch_logger):
    """Test YAML parsing when PyYAML is not available."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    hash_value = verifier._parse_yaml_checksum_file(
        LEGCORD_YAML_CONTENT, "Legcord-1.1.5-linux-x86_64.AppImage"
    )

    assert hash_value is None


def test_parse_yaml_checksum_file_invalid_yaml(tmp_path: Path, patch_logger):
    """Test parsing invalid YAML content."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    invalid_yaml = "{ invalid: yaml: content: ["

    hash_value = verifier._parse_yaml_checksum_file(invalid_yaml, "test.AppImage")

    assert hash_value is None


def test_parse_traditional_checksum_file(tmp_path: Path, patch_logger):
    """Test parsing traditional checksum file format."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    hash_value = verifier._parse_traditional_checksum_file(
        SIYUAN_SHA256SUMS_CONTENT, "siyuan-3.2.1-linux.AppImage", "sha256"
    )

    assert hash_value == "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"


def test_parse_traditional_checksum_file_with_asterisk(tmp_path: Path, patch_logger):
    """Test parsing traditional checksum file with asterisk prefix."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    checksum_content = "abc123def456 *test.AppImage\ndef789abc123 other.bin"

    hash_value = verifier._parse_traditional_checksum_file(
        checksum_content, "test.AppImage", "sha256"
    )

    assert hash_value == "abc123def456"


def test_parse_traditional_checksum_file_not_found(tmp_path: Path, patch_logger):
    """Test parsing traditional checksum file when target not found."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    hash_value = verifier._parse_traditional_checksum_file(
        SIYUAN_SHA256SUMS_CONTENT, "nonexistent.AppImage", "sha256"
    )

    assert hash_value is None


def test_parse_traditional_checksum_file_with_comments(tmp_path: Path, patch_logger):
    """Test parsing traditional checksum file with comments and empty lines."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    checksum_content = """# This is a comment

abc123def456 test.AppImage
# Another comment
def789abc123 other.bin

"""

    hash_value = verifier._parse_traditional_checksum_file(
        checksum_content, "test.AppImage", "sha256"
    )

    assert hash_value == "abc123def456"


def test_detect_hash_type_from_filename(tmp_path: Path, patch_logger):
    """Test hash type detection from filename."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    assert verifier._detect_hash_type_from_filename("SHA512SUMS") == "sha512"
    assert verifier._detect_hash_type_from_filename("SHA256SUMS.txt") == "sha256"
    assert verifier._detect_hash_type_from_filename("checksums.sha1") == "sha1"
    assert verifier._detect_hash_type_from_filename("hashes.md5") == "md5"
    assert verifier._detect_hash_type_from_filename("latest-linux.yml") == "sha256"  # Default


def test_parse_checksum_file_auto_detect_yaml(tmp_path: Path, patch_logger):
    """Test automatic detection and parsing of YAML checksum files."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    hash_value = verifier._parse_checksum_file(
        LEGCORD_YAML_CONTENT, "Legcord-1.1.5-linux-x86_64.AppImage", "sha512"
    )

    assert hash_value == LEGCORD_EXPECTED_HEX


def test_parse_checksum_file_auto_detect_traditional(tmp_path: Path, patch_logger):
    """Test automatic detection and parsing of traditional checksum files."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)

    hash_value = verifier._parse_checksum_file(
        SIYUAN_SHA256SUMS_CONTENT, "siyuan-3.2.1-linux.AppImage", "sha256"
    )

    assert hash_value == "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    digest = "sha999:abcd"
    with pytest.raises(ValueError):
        verifier.verify_digest(digest)


def test_verify_hash_success(tmp_path: Path, patch_logger):
    """Test Verifier.verify_hash succeeds with correct hash."""
    file = tmp_path / "file.bin"
    data = b"xyz"
    file.write_bytes(data)
    verifier = Verifier(file)
    import hashlib

    expected_hash = hashlib.sha1(data).hexdigest()
    verifier.verify_hash(expected_hash, "sha1")  # Should not raise


def test_verify_hash_mismatch(tmp_path: Path, patch_logger):
    """Test Verifier.verify_hash raises on hash mismatch."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"xyz")
    verifier = Verifier(file)
    with pytest.raises(ValueError):
        verifier.verify_hash("deadbeef", "sha1")


def test_compute_hash_all_types(tmp_path: Path, patch_logger):
    """Test Verifier.compute_hash for all supported types."""
    file = tmp_path / "file.bin"
    data = b"test"
    file.write_bytes(data)
    verifier = Verifier(file)
    import hashlib

    assert verifier.compute_hash("sha1") == hashlib.sha1(data).hexdigest()
    assert verifier.compute_hash("sha256") == hashlib.sha256(data).hexdigest()
    assert verifier.compute_hash("sha512") == hashlib.sha512(data).hexdigest()
    assert verifier.compute_hash("md5") == hashlib.md5(data).hexdigest()


def test_compute_hash_unsupported(tmp_path: Path, patch_logger):
    """Test Verifier.compute_hash raises on unsupported type."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"test")
    verifier = Verifier(file)
    with pytest.raises(ValueError):
        verifier.compute_hash("sha999")


def test_compute_hash_file_not_found(tmp_path: Path, patch_logger):
    """Test Verifier.compute_hash raises if file missing."""
    file = tmp_path / "nofile.bin"
    verifier = Verifier(file)
    with pytest.raises(FileNotFoundError):
        verifier.compute_hash("sha256")


@pytest.mark.asyncio
async def test_verify_from_checksum_file_success(tmp_path: Path, patch_logger):
    """Test Verifier.verify_from_checksum_file finds hash and verifies."""
    file = tmp_path / "file.bin"
    data = b"abc"
    file.write_bytes(data)
    verifier = Verifier(file)
    checksum_content = f"{verifier.compute_hash('sha256')} {file.name}\n"
    mock_download_service = MagicMock()
    mock_download_service.download_checksum_file = AsyncMock(return_value=checksum_content)
    await verifier.verify_from_checksum_file(
        checksum_url="http://example.com/checksum.txt",
        hash_type="sha256",
        download_service=mock_download_service,
        filename=file.name,
    )


@pytest.mark.asyncio
async def test_verify_from_checksum_file_not_found(tmp_path: Path, patch_logger):
    """Test Verifier.verify_from_checksum_file raises if hash not found."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    checksum_content = "deadbeef otherfile.bin\n"
    mock_download_service = MagicMock()
    mock_download_service.download_checksum_file = AsyncMock(return_value=checksum_content)
    with pytest.raises(ValueError):
        await verifier.verify_from_checksum_file(
            checksum_url="http://example.com/checksum.txt",
            hash_type="sha256",
            download_service=mock_download_service,
            filename=file.name,
        )


def test_parse_checksum_file_sha256(tmp_path: Path, patch_logger):
    """Test _parse_checksum_file parses SHA256SUMS format."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    hashval = verifier.compute_hash("sha256")
    content = f"{hashval} {file.name}\n"
    result = verifier._parse_checksum_file(content, file.name, "sha256")
    assert result == hashval


def test_parse_checksum_file_generic(tmp_path: Path, patch_logger):
    """Test _parse_checksum_file parses generic format."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    hashval = "deadbeef"
    content = f"{hashval} {file.name}\n"
    result = verifier._parse_checksum_file(content, file.name, "sha256")
    assert result == hashval


def test_get_file_size(tmp_path: Path, patch_logger):
    """Test Verifier.get_file_size returns correct size."""
    file = tmp_path / "file.bin"
    data = b"abcde"
    file.write_bytes(data)
    verifier = Verifier(file)
    assert verifier.get_file_size() == len(data)


def test_get_file_size_not_found(tmp_path: Path, patch_logger):
    """Test Verifier.get_file_size raises if file missing."""
    file = tmp_path / "nofile.bin"
    verifier = Verifier(file)
    with pytest.raises(FileNotFoundError):
        verifier.get_file_size()


def test_verify_size_success(tmp_path: Path, patch_logger):
    """Test Verifier.verify_size passes if size matches."""
    file = tmp_path / "file.bin"
    data = b"abc"
    file.write_bytes(data)
    verifier = Verifier(file)
    verifier.verify_size(len(data))  # Should not raise


def test_verify_size_mismatch(tmp_path: Path, patch_logger):
    """Test Verifier.verify_size raises if size mismatches."""
    file = tmp_path / "file.bin"
    file.write_bytes(b"abc")
    verifier = Verifier(file)
    with pytest.raises(ValueError):
        verifier.verify_size(10)


def test_verification_config_init_and_from_dict():
    """Test VerificationConfig construction and from_dict."""
    config = VerificationConfig(
        digest=True,
        skip=False,
        checksum_file="foo.txt",
        checksum_hash_type="sha256",
        verify_size=True,
    )
    assert config.digest is True
    assert config.skip is False
    assert config.checksum_file == "foo.txt"
    assert config.checksum_hash_type == "sha256"
    assert config.verify_size is True

    data = {
        "digest": False,
        "skip": True,
        "checksum_file": "bar.txt",
        "checksum_hash_type": "md5",
        "verify_size": False,
    }
    config2 = VerificationConfig.from_dict(data)
    assert config2.digest is False
    assert config2.skip is True
    assert config2.checksum_file == "bar.txt"
    assert config2.checksum_hash_type == "md5"
    assert config2.verify_size is False
