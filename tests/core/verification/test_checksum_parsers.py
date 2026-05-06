"""Tests for checksum file detection and parsing functions.

Functions tested:
- find_checksum_entry
- parse_checksum_file
- parse_all_checksums
- detect_hash_type_from_checksum_filename
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from my_unicorn.core.checksum_parser import (
    ChecksumFileResult,
    _is_likely_base64,
    _is_likely_hex,
    _normalize_hash_value,
    convert_base64_to_hex,
    detect_hash_type_from_checksum_filename,
    find_checksum_entry,
    parse_all_checksums,
    parse_checksum_file,
)

CHECKSUM_FIXTURES_DIR = (
    Path(__file__).resolve().parents[2] / "fixtures" / "checksums"
)


@pytest.fixture
def load_checksum_fixture():
    def _load(filename: str) -> str:
        path = CHECKSUM_FIXTURES_DIR / filename
        return path.read_text(encoding="utf-8")

    return _load


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
    blockMapSize: 131387
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

LEGCORD_EXPECTED_HEX = (
    "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f"
    "0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"
)
LEGCORD_BASE64_HASH = "JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw=="
SIYUAN_EXPECTED_HEX = (
    "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
)


def test_convert_base64_to_hex_legcord() -> None:
    assert convert_base64_to_hex(LEGCORD_BASE64_HASH) == LEGCORD_EXPECTED_HEX


@pytest.mark.parametrize(
    "filename,expected_len,should_have_mapping",
    [
        ("siyuan_SHA256SUMS.txt", 64, True),
        ("Joplin-3.6.10.AppImage.sha512", 128, False),
        ("legcord_latest-linux.yml", 128, True),
    ],
)
def test_real_world_checksums(
    load_checksum_fixture, filename, expected_len, should_have_mapping
):
    content = load_checksum_fixture(filename)

    hashes = parse_all_checksums(content)

    if not should_have_mapping:
        assert hashes == {}
        return

    assert len(hashes) > 0

    for hash_value in hashes.values():
        assert len(hash_value) == expected_len


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


@patch("my_unicorn.core.checksum_parser._YAML_AVAILABLE", False)
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


def test_find_checksum_entry_bsd_format() -> None:
    content = (
        f"SHA256 (test.AppImage) = {SIYUAN_EXPECTED_HEX}\n"
        f"SHA512 (other.AppImage) = {LEGCORD_EXPECTED_HEX}"
    )

    entry = find_checksum_entry(content, "test.AppImage")

    assert entry is not None
    assert entry.filename == "test.AppImage"
    assert entry.algorithm == "sha256"
    assert entry.hash_value == SIYUAN_EXPECTED_HEX


@pytest.mark.parametrize(
    "content, filename, algorithm, expected",
    [
        (
            f"SHA256 (test.AppImage) = {SIYUAN_EXPECTED_HEX}",
            "test.AppImage",
            "sha256",
            ("test.AppImage", SIYUAN_EXPECTED_HEX, "sha256"),
        ),
        (
            f"SHA256 (other.AppImage) = {SIYUAN_EXPECTED_HEX}",
            "test.AppImage",
            "sha256",
            None,
        ),
        (
            f"""SHA256 (other.AppImage) = {SIYUAN_EXPECTED_HEX}
SHA256 (test.AppImage) = {SIYUAN_EXPECTED_HEX}
MD5 (another.AppImage) = d41d8cd98f00b204e9800998ecf8427e""",
            "test.AppImage",
            "sha256",
            ("test.AppImage", SIYUAN_EXPECTED_HEX, "sha256"),
        ),
    ],
)
def test_parse_bsd_checksum(content, filename, algorithm, expected):
    entry = find_checksum_entry(content, filename, algorithm)
    if expected is None:
        assert entry is None
    else:
        assert entry is not None
        exp_filename, exp_hash, exp_alg = expected
        assert entry.filename == exp_filename
        assert entry.hash_value == exp_hash
        assert entry.algorithm == exp_alg


def test_parse_traditional_checksum_file() -> None:
    hash_value = parse_checksum_file(
        SIYUAN_SHA256SUMS_CONTENT, "siyuan-3.2.1-linux.AppImage", "sha256"
    )

    assert hash_value == SIYUAN_EXPECTED_HEX


def test_parse_traditional_checksum_file_with_asterisk() -> None:
    checksum_content = (
        f"{SIYUAN_EXPECTED_HEX} *test.AppImage\nabc123def456 other.bin"
    )

    hash_value = parse_checksum_file(
        checksum_content, "test.AppImage", "sha256"
    )

    assert hash_value == SIYUAN_EXPECTED_HEX


def test_parse_traditional_checksum_file_with_comments() -> None:
    checksum_content = f"""# This is a comment

{SIYUAN_EXPECTED_HEX} test.AppImage
# Another comment
abc123def456 other.bin

"""

    hash_value = parse_checksum_file(
        checksum_content, "test.AppImage", "sha256"
    )

    assert hash_value == SIYUAN_EXPECTED_HEX


def test_parse_traditional_hash_only_sha512_checksum_file() -> None:
    """Test parsing checksum files that contain only a SHA512 hash."""
    hash_value = parse_checksum_file(
        LEGCORD_EXPECTED_HEX, "Joplin-3.5.13.AppImage", "sha512"
    )

    assert hash_value == LEGCORD_EXPECTED_HEX


def test_parse_traditional_hash_only_rejects_wrong_hash_type() -> None:
    """Test hash-only checksums must match the expected algorithm length."""
    hash_value = parse_checksum_file(
        LEGCORD_EXPECTED_HEX, "Joplin-3.5.13.AppImage", "sha256"
    )

    assert hash_value is None


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

    assert hash_value == SIYUAN_EXPECTED_HEX


def test_detect_hash_type_unknown_filename() -> None:
    assert detect_hash_type_from_checksum_filename("checksums.txt") is None


def test_detect_hash_type_from_filename() -> None:
    assert detect_hash_type_from_checksum_filename("SHA512SUMS") == "sha512"
    assert (
        detect_hash_type_from_checksum_filename("SHA256SUMS.txt") == "sha256"
    )
    assert (
        detect_hash_type_from_checksum_filename("latest-linux.yml") == "sha512"
    )


def test_detect_hash_type_from_hyphenated_filename() -> None:
    assert detect_hash_type_from_checksum_filename("SHA-256SUMS") == "sha256"
    assert detect_hash_type_from_checksum_filename("SHA-512SUMS") == "sha512"
    assert (
        detect_hash_type_from_checksum_filename("SHA-256SUMS.txt") == "sha256"
    )


def test_hash_only_multiple_lines_rejected() -> None:
    """Verifies that hash-only parsing is disabled when the content contains more than one non-empty line."""
    assert (
        parse_checksum_file(
            f"{LEGCORD_EXPECTED_HEX}\n{LEGCORD_EXPECTED_HEX}",
            "file.AppImage",
            "sha512",
        )
        is None
    )


def test_hash_only_invalid_hex_rejected() -> None:
    """Verifies that non-hex content is rejected in hash-only checksum files."""
    assert (
        parse_checksum_file("zzzzzz_not_hex_at_all", "file.AppImage", "sha512")
        is None
    )


def test_hash_only_wrong_length_rejected() -> None:
    """Verifies that a hash-only file is rejected when its length does not match the expected algorithm."""
    assert parse_checksum_file("a" * 64, "file.AppImage", "sha512") is None


def test_hash_only_empty_content_rejected() -> None:
    """Verifies that empty checksum content does not produce a hash value."""
    assert parse_checksum_file("", "file.AppImage", "sha512") is None


class TestParseAllChecksums:
    """Tests for parse_all_checksums function."""

    def test_parse_all_traditional_checksums(self) -> None:
        """Test parsing all hashes from traditional SHA256SUMS format."""
        content = f"""{SIYUAN_EXPECTED_HEX} app-1.0-x86_64.AppImage
{SIYUAN_SHA256SUMS_CONTENT.splitlines()[1].split()[0]} app-1.0.tar.gz
{SIYUAN_SHA256SUMS_CONTENT.splitlines()[2].split()[0]} app-1.0.deb"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 3
        assert "app-1.0-x86_64.AppImage" in hashes
        assert "app-1.0.tar.gz" in hashes
        assert "app-1.0.deb" in hashes

    def test_parse_all_traditional_checksums_with_asterisk(self) -> None:
        """Test parsing traditional format with binary mode asterisk."""
        content = f"""{SIYUAN_EXPECTED_HEX} *app-1.0.AppImage
{LEGCORD_EXPECTED_HEX} *app-1.0.tar.gz"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 2
        assert "app-1.0.AppImage" in hashes
        assert "app-1.0.tar.gz" in hashes

    def test_parse_all_traditional_checksums_with_comments(self) -> None:
        """Test parsing traditional format with comment lines."""
        content = f"""# SHA256 checksums for release v1.0
{SIYUAN_EXPECTED_HEX} app-1.0.AppImage
# End of file"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 1
        assert "app-1.0.AppImage" in hashes

    def test_parse_all_bsd_checksums(self) -> None:
        """Test parsing all hashes from BSD checksum format."""
        content = f"""SHA256 (app-1.0.AppImage) = {SIYUAN_EXPECTED_HEX}
SHA256 (app-1.0.tar.gz) = 789abc012345789abc012345789abc012345789abc012345789abc012345789abc01
SHA512 (app-1.0.deb) = {LEGCORD_EXPECTED_HEX}"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 3
        assert "app-1.0.AppImage" in hashes
        assert "app-1.0.tar.gz" in hashes
        assert "app-1.0.deb" in hashes

    def test_parse_all_yaml_checksums_dict_format(self) -> None:
        """Test parsing all hashes from YAML checksum format with dict structure."""
        content = f"""app-1.0.AppImage:
  sha256: {SIYUAN_EXPECTED_HEX}
app-1.0.rpm:
  sha512: {LEGCORD_EXPECTED_HEX}"""

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
        content = f"""{SIYUAN_EXPECTED_HEX} valid.AppImage
xyz_not_hex_at_all another.AppImage"""

        hashes = parse_all_checksums(content)

        assert len(hashes) == 1
        assert "valid.AppImage" in hashes

    def test_parse_all_siyuan_sha256sums(self) -> None:
        """Test parsing Siyuan SHA256SUMS content."""
        hashes = parse_all_checksums(SIYUAN_SHA256SUMS_CONTENT)

        assert len(hashes) == 11
        assert hashes["siyuan-3.2.1-linux.AppImage"] == SIYUAN_EXPECTED_HEX

    def test_parse_all_hash_only_content_is_rejected(self) -> None:
        """Hash-only inputs are not supported by parse_all_checksums."""
        hashes = parse_all_checksums(LEGCORD_EXPECTED_HEX)

        assert hashes == {}


class TestIsLikelyHex:
    """Tests for _is_likely_hex() encoding detection."""

    def test_is_likely_hex_md5(self, caplog) -> None:
        """Test hex detection for MD5 (32 chars)."""
        with caplog.at_level(logging.WARNING):
            assert _is_likely_hex("abc123def4567890abcdef1234567890") is False

        assert "MD5 hashes are no longer supported." in caplog.text

    def test_is_likely_hex_sha1(self, caplog) -> None:
        """Test hex detection for SHA1 (40 chars)."""
        with caplog.at_level(logging.WARNING):
            assert (
                _is_likely_hex("abc123def4567890abcdef1234567890abcdef12")
                is False
            )

        assert "SHA1 hashes are no longer supported." in caplog.text

    def test_is_likely_hex_sha256(self) -> None:
        """Test hex detection for SHA256 (64 chars)."""
        assert _is_likely_hex(SIYUAN_EXPECTED_HEX) is True

    def test_is_likely_hex_sha512(self) -> None:
        """Test hex detection for SHA512 (128 chars)."""
        assert _is_likely_hex(LEGCORD_EXPECTED_HEX) is True

    def test_is_likely_hex_uppercase(self) -> None:
        """Test hex detection with uppercase letters."""
        assert _is_likely_hex("DEADBEEF" * 8) is True

    def test_is_likely_hex_lowercase(self) -> None:
        """Test hex detection with lowercase letters."""
        assert _is_likely_hex("deadbeef" * 8) is True

    def test_is_likely_hex_mixed_case(self) -> None:
        """Test hex detection with mixed case."""
        assert _is_likely_hex("DeAdBeEf" * 8) is True

    def test_is_likely_hex_too_short(self) -> None:
        """Test rejection of too-short strings."""
        assert _is_likely_hex("abc123") is False

    def test_is_likely_hex_too_long(self) -> None:
        """Test rejection of non-standard lengths."""
        assert _is_likely_hex("a" * 100) is False

    def test_is_likely_hex_invalid_chars(self) -> None:
        """Test rejection of non-hex characters."""
        assert _is_likely_hex("ghijklmn" * 16) is False
        assert _is_likely_hex("abc123+a" * 16) is False
        assert _is_likely_hex("abc123 a" * 16) is False

    def test_is_likely_hex_empty_string(self) -> None:
        """Test rejection of empty string."""
        assert _is_likely_hex("") is False

    def test_is_likely_hex_whitespace_only(self) -> None:
        """Test rejection of whitespace-only string."""
        assert _is_likely_hex("   ") is False

    def test_is_likely_hex_with_leading_whitespace(self) -> None:
        """Test hex detection with leading/trailing whitespace (stripped)."""
        hash_value = f"  {SIYUAN_EXPECTED_HEX}  "
        assert _is_likely_hex(hash_value) is True

    def test_is_likely_hex_base64_string(self) -> None:
        """Test rejection of base64 strings."""
        assert (
            _is_likely_hex("JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8=")
            is False
        )


class TestIsLikelyBase64:
    """Tests for _is_likely_base64() encoding detection."""

    def test_is_likely_base64_valid_with_padding(self) -> None:
        """Test base64 detection with = padding."""
        assert (
            _is_likely_base64("JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8=")
            is True
        )

    def test_is_likely_base64_valid_double_padding(self) -> None:
        """Test base64 detection with == padding."""
        assert _is_likely_base64("JNmY") is True
        assert _is_likely_base64("aa==") is True

    def test_is_likely_base64_no_padding(self) -> None:
        """Test base64 detection without padding."""
        assert _is_likely_base64("JNmYBTG9") is True

    def test_is_likely_base64_long_string(self) -> None:
        """Test base64 detection with SHA512 base64 (88 chars)."""
        assert _is_likely_base64(LEGCORD_BASE64_HASH) is True

    def test_is_likely_base64_invalid_length(self) -> None:
        """Test rejection of non-multiple-of-4 length."""
        assert _is_likely_base64("JNm") is False
        assert _is_likely_base64("JNmYB") is False

    def test_is_likely_base64_padding_in_middle(self) -> None:
        """Test rejection of padding in middle."""
        assert _is_likely_base64("JN=mYBTG") is False
        assert _is_likely_base64("abc=defg") is False

    def test_is_likely_base64_invalid_chars(self) -> None:
        """Test rejection of invalid characters."""
        assert _is_likely_base64("JNmY#BTG") is False
        assert _is_likely_base64("JNmY BTG") is False
        assert _is_likely_base64("JNmY!BTG") is False

    def test_is_likely_base64_empty_string(self) -> None:
        """Test rejection of empty string."""
        assert _is_likely_base64("") is False

    def test_is_likely_base64_hex_string(self) -> None:
        """Test that hex strings can also match base64 criteria.

        Note: Pure hex strings like "deadbeef12345678" technically match base64
        charset and length rules. This is expected behavior - the _is_likely_hex()
        function should be checked FIRST in the normalization flow.
        """
        assert _is_likely_base64("deadbeef12345678") is True
        assert _is_likely_base64(SIYUAN_EXPECTED_HEX) is True

    def test_is_likely_base64_with_whitespace(self) -> None:
        """Test base64 detection with leading/trailing whitespace."""
        assert _is_likely_base64("  JNmYBTG9lqXt  ") is True


class TestNormalizeHashValue:
    """Tests for _normalize_hash_value() with encoding detection."""

    def test_normalize_pure_hex_sha256(self) -> None:
        """Test that hex SHA256 hash is returned unchanged."""
        result = _normalize_hash_value(SIYUAN_EXPECTED_HEX)
        assert result == SIYUAN_EXPECTED_HEX.lower()
        assert len(result) == 64

    def test_normalize_pure_hex_sha512(self) -> None:
        """Test that hex SHA512 hash is returned unchanged."""
        result = _normalize_hash_value(LEGCORD_EXPECTED_HEX)
        assert result == LEGCORD_EXPECTED_HEX.lower()
        assert len(result) == 128

    def test_normalize_dangerous_hex_pattern(self) -> None:
        """Test that hex with base64-like chars is not corrupted."""
        hex_hash = "deadbeef" * 8
        result = _normalize_hash_value(hex_hash)
        assert result == hex_hash.lower()
        assert len(result) == 64

    def test_normalize_pure_base64_sha512(self) -> None:
        """Test that base64 SHA512 is converted to hex."""
        expected_hex = LEGCORD_EXPECTED_HEX
        result = _normalize_hash_value(LEGCORD_BASE64_HASH)
        assert result == expected_hex
        assert len(result) == 128

    def test_normalize_with_algorithm_prefix_hex(self) -> None:
        """Test prefix stripping for hex hash."""
        prefixed = f"sha256:{SIYUAN_EXPECTED_HEX}"
        assert _normalize_hash_value(prefixed) == SIYUAN_EXPECTED_HEX

    def test_normalize_with_algorithm_prefix_base64(self) -> None:
        """Test prefix stripping for base64 hash."""
        prefixed = f"sha512:{LEGCORD_BASE64_HASH}"
        result = _normalize_hash_value(prefixed)
        assert ":" not in result
        assert len(result) == 128
        assert result == LEGCORD_EXPECTED_HEX

    def test_normalize_uppercase_hex(self) -> None:
        """Test hex normalization to lowercase."""
        hex_hash = "DEADBEEF" * 8
        result = _normalize_hash_value(hex_hash)
        assert result == hex_hash.lower()
        assert result.islower()

    def test_normalize_empty_string(self) -> None:
        """Test normalization of empty string."""
        assert _normalize_hash_value("") == ""

    def test_normalize_non_string_input(self) -> None:
        """Test normalization of stringified numeric input."""
        assert _normalize_hash_value(str(12345)) == "12345"

    def test_normalize_unknown_format(self) -> None:
        """Test fallback for unknown hash format."""
        unknown = "ghijklmn123456"
        assert _normalize_hash_value(unknown) == unknown


class TestCorruptionPrevention:
    """Regression tests proving hex hashes are not corrupted."""

    def test_hex_hash_not_corrupted_by_base64_decode(self) -> None:
        """REGRESSION TEST: Ensure hex hashes are never corrupted.

        This test proves the bug is fixed. Before the fix, this hex hash
        would be passed to base64.b64decode(), producing corrupted output.
        """
        import base64

        dangerous_hex = (
            "deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678"
        )

        result = _normalize_hash_value(dangerous_hex)

        assert result == dangerous_hex.lower()
        assert len(result) == 64

        corrupted = base64.b64decode(dangerous_hex.encode()).hex()
        assert result != corrupted, "Hash was corrupted by base64 decode!"

    def test_base64_decode_not_called_on_hex(self) -> None:
        """Verify base64 decode is never called for hex hashes."""
        with patch(
            "my_unicorn.core.checksum_parser.convert_base64_to_hex"
        ) as mock_convert:
            hex_hash = "abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890"
            result = _normalize_hash_value(hex_hash)

            mock_convert.assert_not_called()
            assert result == hex_hash.lower()

    def test_various_dangerous_patterns(self) -> None:
        """Test hex hashes with high base64 character overlap."""
        dangerous_patterns = [
            "deadbeef" * 8,
            "cafebabe" * 8,
            "facade12" * 8,
            "abcdef01" * 8,
        ]

        for pattern in dangerous_patterns:
            result = _normalize_hash_value(pattern)
            assert result == pattern.lower(), (
                f"Pattern {pattern} was corrupted"
            )
            assert len(result) == 64


def test_convert_base64_to_hex() -> None:
    hex_hash = convert_base64_to_hex(LEGCORD_BASE64_HASH)

    assert hex_hash == LEGCORD_EXPECTED_HEX


def test_convert_base64_to_hex_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid base64 hash"):
        convert_base64_to_hex("not_valid_base64!")


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
