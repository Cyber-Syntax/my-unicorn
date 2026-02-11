"""Tests for checksum parser implementations (traditional, BSD, YAML formats)."""

import pytest

from my_unicorn.core.verification.checksum_parser import (
    ChecksumFileResult,
    convert_base64_to_hex,
    find_checksum_entry,
)

LEGCORD_EXPECTED_HEX = "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"
LEGCORD_BASE64_HASH = "JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw=="


def test_convert_base64_to_hex() -> None:
    hex_hash = convert_base64_to_hex(LEGCORD_BASE64_HASH)

    assert hex_hash == LEGCORD_EXPECTED_HEX


def test_convert_base64_to_hex_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid base64 hash"):
        convert_base64_to_hex("not_valid_base64!")


def test_parse_bsd_checksum_sha256() -> None:
    """Test BSD checksum format parsing for SHA256."""
    content = "SHA256 (test.AppImage) = abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890"
    entry = find_checksum_entry(content, "test.AppImage", "sha256")
    assert entry is not None
    assert entry.filename == "test.AppImage"
    assert (
        entry.hash_value
        == "abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890"
    )
    assert entry.algorithm == "sha256"


def test_parse_bsd_checksum_sha1() -> None:
    """Test BSD checksum format parsing for SHA1."""
    content = "SHA1 (test.AppImage) = abc123def4567890abcdef1234567890abcdef12"
    entry = find_checksum_entry(content, "test.AppImage", "sha1")
    assert entry is not None
    assert entry.filename == "test.AppImage"
    assert entry.hash_value == "abc123def4567890abcdef1234567890abcdef12"
    assert entry.algorithm == "sha1"


def test_parse_bsd_checksum_md5() -> None:
    """Test BSD checksum format parsing for MD5."""
    content = "MD5 (test.AppImage) = abc123def4567890abcdef1234567890"
    entry = find_checksum_entry(content, "test.AppImage", "md5")
    assert entry is not None
    assert entry.filename == "test.AppImage"
    assert entry.hash_value == "abc123def4567890abcdef1234567890"
    assert entry.algorithm == "md5"


def test_parse_bsd_checksum_wrong_filename() -> None:
    """Test BSD checksum format with wrong filename returns None."""
    content = "SHA256 (other.AppImage) = abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890"
    entry = find_checksum_entry(content, "test.AppImage", "sha256")
    assert entry is None


def test_parse_bsd_checksum_multiple_lines() -> None:
    """Test BSD checksum format with multiple lines."""
    content = """SHA256 (other.AppImage) = def4567890abcdef1234567890abcdef1234567890abcdef1234567890abc123
SHA256 (test.AppImage) = abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890
MD5 (another.AppImage) = 1234567890abcdef1234567890abcdef"""
    entry = find_checksum_entry(content, "test.AppImage", "sha256")
    assert entry is not None
    assert entry.filename == "test.AppImage"
    assert (
        entry.hash_value
        == "abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890"
    )
    assert entry.algorithm == "sha256"


def test_find_checksum_entry_yaml_sha1() -> None:
    """Test YAML checksum parsing with SHA1 hash."""
    content = """path: test.AppImage
sha1: q8Ej3vRWeJCrze8SNFZ4kKvN7xI="""
    entry = find_checksum_entry(content, "test.AppImage", "sha1")
    assert entry is not None
    assert entry.filename == "test.AppImage"
    assert entry.hash_value == "abc123def4567890abcdef1234567890abcdef12"
    assert entry.algorithm == "sha1"


def test_find_checksum_entry_yaml_md5() -> None:
    """Test YAML checksum parsing with MD5 hash."""
    content = """path: test.AppImage
md5: q8Ej3vRWeJCrze8SNFZ4kA=="""
    entry = find_checksum_entry(content, "test.AppImage", "md5")
    assert entry is not None
    assert entry.filename == "test.AppImage"
    assert entry.hash_value == "abc123def4567890abcdef1234567890"
    assert entry.algorithm == "md5"


def test_find_checksum_entry_yaml_sha1_files_array() -> None:
    """Test YAML checksum parsing with SHA1 hash in files array."""
    content = """files:
  - url: test.AppImage
    sha1: q8Ej3vRWeJCrze8SNFZ4kKvN7xI=
  - url: other.AppImage
    sha256: def4567890abcdef1234567890abcdef1234567890abcdef1234567890abc123"""
    entry = find_checksum_entry(content, "test.AppImage", "sha1")
    assert entry is not None
    assert entry.filename == "test.AppImage"
    assert entry.hash_value == "abc123def4567890abcdef1234567890abcdef12"
    assert entry.algorithm == "sha1"


def test_find_checksum_entry_yaml_md5_files_dict() -> None:
    """Test YAML checksum parsing with MD5 hash in files dict."""
    content = """files:
  test.AppImage:
    md5: q8Ej3vRWeJCrze8SNFZ4kA==
  other.AppImage:
    sha256: def4567890abcdef1234567890abcdef1234567890abcdef1234567890abc123"""
    entry = find_checksum_entry(content, "test.AppImage", "md5")
    assert entry is not None
    assert entry.filename == "test.AppImage"
    assert entry.hash_value == "abc123def4567890abcdef1234567890"
    assert entry.algorithm == "md5"


class TestChecksumFileResult:
    """Tests for ChecksumFileResult dataclass."""

    def test_to_cache_dict(self) -> None:
        """Test conversion to cache dictionary format."""
        result = ChecksumFileResult(
            source="https://github.com/owner/repo/releases/download/v1.0/SHA256SUMS.txt",
            filename="SHA256SUMS.txt",
            algorithm="SHA256",
            hashes={
                "app-1.0.AppImage": "abc123def456",
                "app-1.0.tar.gz": "789xyz012345",
            },
        )

        cache_dict = result.to_cache_dict()

        assert cache_dict["source"] == result.source
        assert cache_dict["filename"] == result.filename
        assert cache_dict["algorithm"] == result.algorithm
        assert cache_dict["hashes"] == result.hashes

    def test_frozen_dataclass(self) -> None:
        """Test that ChecksumFileResult is immutable."""
        result = ChecksumFileResult(
            source="https://example.com/SHA256SUMS.txt",
            filename="SHA256SUMS.txt",
            algorithm="SHA256",
            hashes={"file.AppImage": "hash123"},
        )

        with pytest.raises(AttributeError):
            result.source = "modified"
