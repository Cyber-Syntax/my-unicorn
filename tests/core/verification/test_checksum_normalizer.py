"""Tests for hash normalization functions in checksum_parser.normalizer."""

from unittest.mock import patch

from my_unicorn.core.verification.checksum_parser.normalizer import (
    _is_likely_base64,
    _is_likely_hex,
    _normalize_hash_value,
)


class TestIsLikelyHex:
    """Tests for _is_likely_hex() encoding detection."""

    def test_is_likely_hex_md5(self) -> None:
        """Test hex detection for MD5 (32 chars)."""
        assert _is_likely_hex("abc123def4567890abcdef1234567890") is True

    def test_is_likely_hex_sha1(self) -> None:
        """Test hex detection for SHA1 (40 chars)."""
        assert (
            _is_likely_hex("abc123def4567890abcdef1234567890abcdef12") is True
        )

    def test_is_likely_hex_sha256(self) -> None:
        """Test hex detection for SHA256 (64 chars)."""
        hash_value = (
            "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
        )
        assert _is_likely_hex(hash_value) is True

    def test_is_likely_hex_sha512(self) -> None:
        """Test hex detection for SHA512 (128 chars)."""
        hash_value = (
            "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f"
            "0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"
        )
        assert _is_likely_hex(hash_value) is True

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
        hash_value = "  3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef  "
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
        assert _is_likely_base64("JNmY") is True  # 4 chars, no padding needed
        assert _is_likely_base64("aa==") is True  # 4 chars with == padding

    def test_is_likely_base64_no_padding(self) -> None:
        """Test base64 detection without padding."""
        assert _is_likely_base64("JNmYBTG9") is True

    def test_is_likely_base64_long_string(self) -> None:
        """Test base64 detection with SHA512 base64 (88 chars)."""
        base64_hash = (
            "JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8M"
            "SWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw=="
        )
        assert _is_likely_base64(base64_hash) is True

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
        # 16 chars (4*4) - valid base64 length, all chars in base64 charset
        assert _is_likely_base64("deadbeef12345678") is True
        # 64 chars (4*16) - valid base64 length, all chars in base64 charset
        sha256_hex = (
            "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
        )
        assert _is_likely_base64(sha256_hex) is True

    def test_is_likely_base64_with_whitespace(self) -> None:
        """Test base64 detection with leading/trailing whitespace."""
        assert _is_likely_base64("  JNmYBTG9lqXt  ") is True


class TestNormalizeHashValue:
    """Tests for _normalize_hash_value() with encoding detection."""

    def test_normalize_pure_hex_sha256(self) -> None:
        """Test that hex SHA256 hash is returned unchanged."""
        hex_hash = (
            "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
        )
        result = _normalize_hash_value(hex_hash)
        assert result == hex_hash.lower()
        assert len(result) == 64

    def test_normalize_pure_hex_sha512(self) -> None:
        """Test that hex SHA512 hash is returned unchanged."""
        hex_hash = (
            "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f"
            "0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"
        )
        result = _normalize_hash_value(hex_hash)
        assert result == hex_hash.lower()
        assert len(result) == 128

    def test_normalize_dangerous_hex_pattern(self) -> None:
        """Test that hex with base64-like chars is not corrupted."""
        # This pattern could be mistaken for base64
        hex_hash = "deadbeef" * 8  # 64 chars
        result = _normalize_hash_value(hex_hash)
        assert result == hex_hash.lower()
        assert len(result) == 64

    def test_normalize_pure_base64_sha512(self) -> None:
        """Test that base64 SHA512 is converted to hex."""
        base64_hash = (
            "JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8M"
            "SWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw=="
        )
        expected_hex = (
            "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f"
            "0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"
        )
        result = _normalize_hash_value(base64_hash)
        assert result == expected_hex
        assert len(result) == 128

    def test_normalize_with_algorithm_prefix_hex(self) -> None:
        """Test prefix stripping for hex hash."""
        prefixed = "sha256:3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
        expected = (
            "3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef"
        )
        assert _normalize_hash_value(prefixed) == expected

    def test_normalize_with_algorithm_prefix_base64(self) -> None:
        """Test prefix stripping for base64 hash."""
        base64_hash = (
            "JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8M"
            "SWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw=="
        )
        prefixed = f"sha512:{base64_hash}"
        # Should strip prefix, detect base64, convert to hex
        result = _normalize_hash_value(prefixed)
        assert ":" not in result
        assert len(result) == 128  # SHA512 hex length
        # Verify the conversion is correct
        expected_hex = (
            "24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f"
            "0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb"
        )
        assert result == expected_hex

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

        # Normalize the hash (this would corrupt it before the fix)
        result = _normalize_hash_value(dangerous_hex)

        # Proof 1: Result matches input (lowercased)
        assert result == dangerous_hex.lower()

        # Proof 2: Length is preserved
        assert len(result) == 64

        # Proof 3: Result is NOT the corrupted base64 decode
        corrupted = base64.b64decode(dangerous_hex.encode()).hex()
        assert result != corrupted, "Hash was corrupted by base64 decode!"

    def test_base64_decode_not_called_on_hex(self) -> None:
        """Verify base64 decode is never called for hex hashes."""
        with patch(
            "my_unicorn.core.verification.checksum_parser.convert_base64_to_hex"
        ) as mock_convert:
            hex_hash = (
                "abc123def4567890abcdef1234567890"
                "abcdef1234567890abcdef1234567890"
            )
            result = _normalize_hash_value(hex_hash)

            # Critical assertion: convert_base64_to_hex was never called
            mock_convert.assert_not_called()
            assert result == hex_hash.lower()

    def test_various_dangerous_patterns(self) -> None:
        """Test hex hashes with high base64 character overlap."""
        dangerous_patterns = [
            "deadbeef" * 8,  # Common pattern
            "cafebabe" * 8,  # Another common pattern
            "facade12" * 8,  # More base64-like chars
            "abcdef01" * 8,  # Sequential
        ]

        for pattern in dangerous_patterns:
            result = _normalize_hash_value(pattern)
            assert result == pattern.lower(), (
                f"Pattern {pattern} was corrupted"
            )
            assert len(result) == 64
