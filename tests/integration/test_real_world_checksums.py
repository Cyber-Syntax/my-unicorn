"""Integration tests with real-world checksum files.

Tests the checksum parsing and hash normalization using actual checksum file
formats from popular AppImage distributions.

These tests verify that:
1. Hex hashes are correctly detected and preserved
2. Base64 hashes are correctly detected and converted to hex
3. Traditional SHA256SUMS format parses correctly
4. YAML format with files array parses correctly
5. The "dangerous hex" pattern (hex-looking base64) is NOT corrupted
"""

from pathlib import Path

import pytest

from my_unicorn.core.verification.checksum_parser import find_checksum_entry

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "checksums"


@pytest.mark.integration
class TestRealWorldChecksumFiles:
    """Test parsing of real-world checksum files from GitHub."""

    def test_parse_heroic_yaml_hex_sha512(self) -> None:
        """Test Heroic YAML with pure hex SHA512.

        Heroic Games Launcher uses hex-encoded SHA512 hashes in YAML format.
        The hash should be returned unchanged (only lowercased).
        """
        content = (FIXTURES_DIR / "heroic_latest-linux.yml").read_text()
        entry = find_checksum_entry(
            content, "Heroic-2.15.2.AppImage", "sha512"
        )

        expected_hex = (
            "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
            "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f"
        )

        assert entry is not None, "Failed to find Heroic checksum entry"
        assert entry.algorithm == "sha512"
        assert len(entry.hash_value) == 128, "SHA512 hex should be 128 chars"
        assert entry.hash_value == expected_hex
        assert all(c in "0123456789abcdef" for c in entry.hash_value)

    def test_parse_legcord_yaml_base64_sha512(self) -> None:
        """Test Legcord YAML with base64 SHA512.

        Legcord uses base64-encoded SHA512 hashes in YAML format.
        The hash should be converted from base64 to hex.
        """
        content = (FIXTURES_DIR / "legcord_latest-linux.yml").read_text()
        entry = find_checksum_entry(
            content, "Legcord-1.0.5.AppImage", "sha512"
        )

        # Base64 input converts to hex
        expected_hex = (
            "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f"
            "0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"
        )

        assert entry is not None, "Failed to find Legcord checksum entry"
        assert entry.hash_value == expected_hex
        assert entry.algorithm == "sha512"
        assert len(entry.hash_value) == 128, (
            "Converted SHA512 should be 128 hex chars"
        )

    def test_parse_qownnotes_sha256sums_hex(self) -> None:
        """Test QOwnNotes traditional SHA256SUMS with hex.

        QOwnNotes uses the traditional "hash  filename" format.
        """
        content = (FIXTURES_DIR / "qownnotes_SHA256SUMS.txt").read_text()
        entry = find_checksum_entry(
            content, "QOwnNotes-24.1.5-x86_64.AppImage", "sha256"
        )

        expected_hex = (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

        assert entry is not None, "Failed to find QOwnNotes checksum entry"
        assert entry.algorithm == "sha256"
        assert len(entry.hash_value) == 64, "SHA256 hex should be 64 chars"
        assert entry.hash_value == expected_hex

    def test_parse_siyuan_sha256sums_hex(self) -> None:
        """Test SiYuan traditional SHA256SUMS with hex.

        SiYuan uses the traditional "hash  filename" format.
        """
        content = (FIXTURES_DIR / "siyuan_SHA256SUMS.txt").read_text()
        entry = find_checksum_entry(
            content, "siyuan-3.5.4-linux.AppImage", "sha256"
        )

        expected_hex = (
            "72987a45605886b81c99cd28f48c294228cb6bf67000f223cf9051ed7f5e6281"
        )

        assert entry is not None, "Failed to find SiYuan checksum entry"
        assert entry.hash_value == expected_hex
        assert entry.algorithm == "sha256"
        assert len(entry.hash_value) == 64, "SHA256 hex should be 64 chars"

    def test_parse_superproductivity_yaml_base64_sha512(self) -> None:
        """Test Super Productivity YAML with base64 SHA512.

        Super Productivity uses base64-encoded SHA512 hashes in YAML format.
        """
        content = (
            FIXTURES_DIR / "superproductivity_latest-linux.yml"
        ).read_text()
        entry = find_checksum_entry(
            content, "superProductivity-x86_64.AppImage", "sha512"
        )

        assert entry is not None, (
            "Failed to find Super Productivity checksum entry"
        )
        assert entry.algorithm == "sha512"
        assert len(entry.hash_value) == 128, (
            "Converted SHA512 should be 128 hex chars"
        )
        assert all(c in "0123456789abcdef" for c in entry.hash_value)

    def test_parse_dangerous_hex_pattern(self) -> None:
        """Test YAML with hex hash that looks like base64.

        CRITICAL TEST: This hash uses only hex digits (0-9, a-f) but those
        characters are also valid base64. The system MUST detect this as hex
        and NOT attempt base64 decoding, which would corrupt the hash.
        """
        content = (FIXTURES_DIR / "dangerous_hex.yml").read_text()
        entry = find_checksum_entry(
            content, "dangerous-app-1.0.0.AppImage", "sha512"
        )

        # This exact hex pattern must be preserved
        expected_hex = (
            "deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678"
            "deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678"
        )

        assert entry is not None, "Failed to find dangerous hex checksum entry"
        assert len(entry.hash_value) == 128, "SHA512 hex should be 128 chars"
        assert entry.hash_value == expected_hex, (
            "Hex hash was corrupted by base64 decode!"
        )
        assert entry.hash_value.startswith("deadbeef")

    @pytest.mark.parametrize(
        ("fixture_file", "filename", "algo", "expected_length"),
        [
            (
                "heroic_latest-linux.yml",
                "Heroic-2.15.2.AppImage",
                "sha512",
                128,
            ),
            (
                "legcord_latest-linux.yml",
                "Legcord-1.0.5.AppImage",
                "sha512",
                128,
            ),
            (
                "qownnotes_SHA256SUMS.txt",
                "QOwnNotes-24.1.5-x86_64.AppImage",
                "sha256",
                64,
            ),
            (
                "siyuan_SHA256SUMS.txt",
                "siyuan-3.0.12-linux-amd64.AppImage",
                "sha256",
                64,
            ),
            (
                "superproductivity_latest-linux.yml",
                "superProductivity-x86_64.AppImage",
                "sha512",
                128,
            ),
            (
                "beekeeper-studio_latest-linux.yml",
                "Beekeeper-Studio-5.5.6.AppImage",
                "sha512",
                128,
            ),
            (
                "affine_latest-linux.yml",
                "affine-0.25.7-stable-linux-x64.appimage",
                "sha512",
                128,
            ),
            (
                "drawio_latest-linux.yml",
                "drawio-x86_64-29.3.6.AppImage",
                "sha512",
                128,
            ),
            (
                "joplin_latest-linux.yml",
                "Joplin-3.5.12.AppImage",
                "sha512",
                128,
            ),
            (
                "dangerous_hex.yml",
                "dangerous-app-1.0.0.AppImage",
                "sha512",
                128,
            ),
        ],
    )
    def test_all_samples_parse_correctly(
        self, fixture_file: str, filename: str, algo: str, expected_length: int
    ) -> None:
        """Parameterized test for all real-world samples.

        Verifies that all 10 fixture files parse correctly and produce
        the expected hash length.
        """
        content = (FIXTURES_DIR / fixture_file).read_text()
        entry = find_checksum_entry(content, filename, algo)

        assert entry is not None, f"Failed to parse {fixture_file}"
        assert len(entry.hash_value) == expected_length
        assert entry.algorithm == algo

    def test_all_hex_results_are_valid_hex(self) -> None:
        """Verify all parsed hashes contain only hex characters.

        All results from find_checksum_entry should be hex strings,
        whether the input was hex or base64.
        """
        test_cases = [
            ("heroic_latest-linux.yml", "Heroic-2.15.2.AppImage", "sha512"),
            ("legcord_latest-linux.yml", "Legcord-1.0.5.AppImage", "sha512"),
            (
                "qownnotes_SHA256SUMS.txt",
                "QOwnNotes-24.1.5-x86_64.AppImage",
                "sha256",
            ),
            (
                "siyuan_SHA256SUMS.txt",
                "siyuan-3.0.12-linux-amd64.AppImage",
                "sha256",
            ),
            (
                "superproductivity_latest-linux.yml",
                "superProductivity-x86_64.AppImage",
                "sha512",
            ),
            (
                "beekeeper-studio_latest-linux.yml",
                "Beekeeper-Studio-5.5.6.AppImage",
                "sha512",
            ),
            (
                "affine_latest-linux.yml",
                "affine-0.25.7-stable-linux-x64.appimage",
                "sha512",
            ),
            (
                "drawio_latest-linux.yml",
                "drawio-x86_64-29.3.6.AppImage",
                "sha512",
            ),
            (
                "joplin_latest-linux.yml",
                "Joplin-3.5.12.AppImage",
                "sha512",
            ),
            ("dangerous_hex.yml", "dangerous-app-1.0.0.AppImage", "sha512"),
        ]

        for fixture_file, filename, algo in test_cases:
            content = (FIXTURES_DIR / fixture_file).read_text()
            entry = find_checksum_entry(content, filename, algo)

            assert entry is not None, f"Failed to parse {fixture_file}"
            is_valid_hex = all(
                c in "0123456789abcdef" for c in entry.hash_value
            )
            assert is_valid_hex, f"{fixture_file}: found non-hex chars"
