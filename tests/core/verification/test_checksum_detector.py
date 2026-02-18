"""Tests for checksum file detection and parsing functions.

Functions tested:
- find_checksum_entry
- parse_checksum_file
- parse_all_checksums
- detect_hash_type_from_checksum_filename
"""

from unittest.mock import patch

from my_unicorn.core.verification.checksum_parser import (
    detect_hash_type_from_checksum_filename,
    find_checksum_entry,
    parse_all_checksums,
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


@patch(
    "my_unicorn.core.verification.checksum_parser.yaml_parser._YAML_AVAILABLE",
    False,
)
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


class TestParseAllChecksums:
    """Tests for parse_all_checksums function."""

    def test_parse_all_traditional_checksums(self) -> None:
        """Test parsing all hashes from traditional SHA256SUMS format."""
        content = """abc123def456abc123def456abc123def456abc123def456abc123def456abc12345 app-1.0-x86_64.AppImage
789abc012345789abc012345789abc012345789abc012345789abc012345789abc01 app-1.0.tar.gz
fedcba987654fedcba987654fedcba987654fedcba987654fedcba987654fedcba98 app-1.0.deb"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 3
        assert "app-1.0-x86_64.AppImage" in hashes
        assert "app-1.0.tar.gz" in hashes
        assert "app-1.0.deb" in hashes

    def test_parse_all_traditional_checksums_with_asterisk(self) -> None:
        """Test parsing traditional format with binary mode asterisk."""
        content = """abc123def456abc123def456abc123def456abc123def456abc123def456abc12345 *app-1.0.AppImage
789abc012345789abc012345789abc012345789abc012345789abc012345789abc01 *app-1.0.tar.gz"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 2
        assert "app-1.0.AppImage" in hashes
        assert "app-1.0.tar.gz" in hashes

    def test_parse_all_traditional_checksums_with_comments(self) -> None:
        """Test parsing traditional format with comment lines."""
        content = """# SHA256 checksums for release v1.0
abc123def456abc123def456abc123def456abc123def456abc123def456abc12345 app-1.0.AppImage
# End of file"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 1
        assert "app-1.0.AppImage" in hashes

    def test_parse_all_bsd_checksums(self) -> None:
        """Test parsing all hashes from BSD checksum format."""
        content = """SHA256 (app-1.0.AppImage) = abc123def456abc123def456abc123def456abc123def456abc123def456abc12345
SHA256 (app-1.0.tar.gz) = 789abc012345789abc012345789abc012345789abc012345789abc012345789abc01
SHA512 (app-1.0.deb) = fedcba987654fedcba987654fedcba987654fedcba987654"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 3
        assert "app-1.0.AppImage" in hashes
        assert "app-1.0.tar.gz" in hashes
        assert "app-1.0.deb" in hashes

    def test_parse_all_yaml_checksums_dict_format(self) -> None:
        """Test parsing all hashes from YAML checksum format with dict structure."""
        content = """app-1.0.AppImage:
  sha256: abc123def456abc123def456abc123def456abc123def456abc123def456abc12345
app-1.0.rpm:
  sha512: 789abc012345789abc012345789abc012345789abc012345789abc012345789abc01"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 2
        assert "app-1.0.AppImage" in hashes
        assert "app-1.0.rpm" in hashes

    def test_parse_all_empty_content(self) -> None:
        """Test parsing empty content returns empty dict."""
        hashes = parse_all_checksums("")

        assert hashes == {}

    def test_parse_all_invalid_hex_skipped(self) -> None:
        """Test that lines with invalid hex characters are skipped."""
        content = """abc123def456abc123def456abc123def456abc123def456abc123def456abc12345 valid.AppImage
xyz_not_hex_at_all another.AppImage"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 1
        assert "valid.AppImage" in hashes

    def test_parse_all_siyuan_sha256sums(self) -> None:
        """Test parsing Siyuan SHA256SUMS content."""
        hashes = parse_all_checksums(SIYUAN_SHA256SUMS_CONTENT)

        assert len(hashes) == 11
        expected_linux_hash = (
            "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
        )
        assert hashes["siyuan-3.2.1-linux.AppImage"] == expected_linux_hash
