from unittest.mock import patch

import pytest

from my_unicorn.domain.verification.checksum_parser import (
    convert_base64_to_hex,
    detect_hash_type_from_checksum_filename,
    find_checksum_entry,
    parse_checksum_file,
)

LEGCORD_YAML_CONTENT = """version: 1.1.5
files:
  - url: Legcord-1.1.5-linux-x86_64.AppImage
    sha512: JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw==
    size: 124457255
    blockMapSize: 131387
  - url: Legcord-1.1.5-linux-x86_64.rpm
    sha512: 3j2/BdKHypZrIQ0qDzJk9WjyXJwCfPfbQ7la8i+YFSHZwzOBdWDrkLPh16ZhTa3zRbQ13/XyeN76HwrRzCJIRg==
    size: 82429221
    blockMapSize: 131387
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

LEGCORD_EXPECTED_HEX = "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"
LEGCORD_BASE64_HASH = "JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw=="


def test_convert_base64_to_hex() -> None:
    hex_hash = convert_base64_to_hex(LEGCORD_BASE64_HASH)

    assert hex_hash == LEGCORD_EXPECTED_HEX


def test_convert_base64_to_hex_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid base64 hash"):
        convert_base64_to_hex("not_valid_base64!")


def test_find_checksum_entry_yaml_root_level() -> None:
    entry = find_checksum_entry(
        """path: Legcord-1.1.5-linux-x86_64.AppImage
sha512: JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw==""",
        "Legcord-1.1.5-linux-x86_64.AppImage",
        "sha512",
    )

    assert entry
    assert entry.hash_value == LEGCORD_EXPECTED_HEX
    assert entry.algorithm == "sha512"


def test_find_checksum_entry_yaml_files_array() -> None:
    entry = find_checksum_entry(
        LEGCORD_YAML_CONTENT,
        "Legcord-1.1.5-linux-x86_64.AppImage",
        "sha512",
    )

    assert entry
    assert entry.hash_value == LEGCORD_EXPECTED_HEX
    assert entry.algorithm == "sha512"


def test_find_checksum_entry_yaml_other_file() -> None:
    entry = find_checksum_entry(
        LEGCORD_YAML_CONTENT,
        "Legcord-1.1.5-linux-x86_64.rpm",
        "sha512",
    )

    assert entry
    assert entry.algorithm == "sha512"


def test_find_checksum_entry_yaml_not_found() -> None:
    entry = find_checksum_entry(
        LEGCORD_YAML_CONTENT,
        "NonExistentFile.AppImage",
        "sha512",
    )

    assert entry is None


@patch("my_unicorn.domain.verification.checksum_parser._YAML_AVAILABLE", False)
def test_find_checksum_entry_yaml_not_available() -> None:
    entry = find_checksum_entry(
        LEGCORD_YAML_CONTENT,
        "Legcord-1.1.5-linux-x86_64.AppImage",
        "sha512",
    )

    assert entry is None


def test_find_checksum_entry_invalid_yaml() -> None:
    entry = find_checksum_entry(
        "{ invalid: yaml: content: [", "test.AppImage", "sha256"
    )

    assert entry is None


def test_parse_traditional_checksum_file() -> None:
    hash_value = parse_checksum_file(
        SIYUAN_SHA256SUMS_CONTENT, "siyuan-3.2.1-linux.AppImage", "sha256"
    )

    assert (
        hash_value
        == "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
    )


def test_parse_traditional_checksum_file_with_asterisk() -> None:
    checksum_content = "abc123def456 *test.AppImage\ndef789abc123 other.bin"

    hash_value = parse_checksum_file(
        checksum_content, "test.AppImage", "sha256"
    )

    assert hash_value == "abc123def456"


def test_parse_traditional_checksum_file_not_found() -> None:
    hash_value = parse_checksum_file(
        SIYUAN_SHA256SUMS_CONTENT, "nonexistent.AppImage", "sha256"
    )

    assert hash_value is None


def test_parse_traditional_checksum_file_with_comments() -> None:
    checksum_content = """# This is a comment

abc123def456 test.AppImage
# Another comment
def789abc123 other.bin

"""

    hash_value = parse_checksum_file(
        checksum_content, "test.AppImage", "sha256"
    )

    assert hash_value == "abc123def456"


def test_parse_checksum_file_auto_detect_yaml() -> None:
    hash_value = parse_checksum_file(
        LEGCORD_YAML_CONTENT,
        "Legcord-1.1.5-linux-x86_64.AppImage",
        "sha512",
    )

    assert hash_value == LEGCORD_EXPECTED_HEX


def test_parse_checksum_file_auto_detect_traditional() -> None:
    hash_value = parse_checksum_file(
        SIYUAN_SHA256SUMS_CONTENT, "siyuan-3.2.1-linux.AppImage", "sha256"
    )

    assert (
        hash_value
        == "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
    )


def test_detect_hash_type_from_filename() -> None:
    assert detect_hash_type_from_checksum_filename("SHA512SUMS") == "sha512"
    assert (
        detect_hash_type_from_checksum_filename("SHA256SUMS.txt") == "sha256"
    )
    assert detect_hash_type_from_checksum_filename("checksums.sha1") == "sha1"
    assert detect_hash_type_from_checksum_filename("hashes.md5") == "md5"
    assert (
        detect_hash_type_from_checksum_filename("latest-linux.yml") == "sha256"
    )


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
