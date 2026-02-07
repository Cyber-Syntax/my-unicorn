"""Tests for UI formatters module."""

from my_unicorn.core.progress.formatters import (
    _format_verification_legacy,
    format_verification_info,
)


class TestFormatVerificationInfo:
    """Tests for format_verification_info function."""

    def test_multi_method_all_passed(self) -> None:
        """Test formatting when all methods pass."""
        verification = {
            "passed": True,
            "methods": [
                {
                    "type": "digest",
                    "status": "passed",
                    "algorithm": "SHA256",
                    "source": "github_api",
                    "primary": True,
                },
                {
                    "type": "checksum_file",
                    "status": "passed",
                    "algorithm": "SHA256",
                    "source": "SHA256SUMS.txt",
                    "primary": False,
                },
            ],
        }

        result = format_verification_info(verification)

        assert "✓ SHA256 digest (github_api)" in result
        assert "✓ SHA256 checksum_file (SHA256SUMS.txt)" in result

    def test_multi_method_partial_failure(self) -> None:
        """Test formatting when some methods fail."""
        verification = {
            "passed": True,
            "methods": [
                {
                    "type": "digest",
                    "status": "passed",
                    "algorithm": "SHA256",
                    "source": "github_api",
                    "primary": True,
                },
                {
                    "type": "checksum_file",
                    "status": "failed",
                    "algorithm": "SHA256",
                    "source": "https://github.com/owner/repo/SHA256SUMS.txt",
                    "primary": False,
                },
            ],
            "warning": "Partial verification: 1 passed, 1 failed",
        }

        result = format_verification_info(verification)

        assert "✓ SHA256 digest (github_api)" in result
        assert "✗ SHA256 checksum_file (SHA256SUMS.txt)" in result
        assert "⚠ Partial verification: 1 passed, 1 failed" in result

    def test_multi_method_url_source_shortened(self) -> None:
        """Test that URL sources are shortened to filename."""
        verification = {
            "passed": True,
            "methods": [
                {
                    "type": "checksum_file",
                    "status": "passed",
                    "algorithm": "SHA512",
                    "source": "https://github.com/owner/repo/releases/SHA512SUMS",
                    "primary": True,
                },
            ],
        }

        result = format_verification_info(verification)

        assert "SHA512SUMS" in result
        assert "https://" not in result

    def test_empty_methods_falls_back_to_legacy(self) -> None:
        """Test fallback to legacy format when methods list is empty."""
        verification = {
            "passed": True,
            "methods": [],
            "digest": {"passed": True, "hash_type": "sha256"},
        }

        result = format_verification_info(verification)

        assert "SHA256 digest" in result

    def test_no_methods_key_falls_back_to_legacy(self) -> None:
        """Test fallback to legacy format when no methods key exists."""
        verification = {
            "passed": True,
            "digest": {"passed": True, "hash_type": "sha256"},
        }

        result = format_verification_info(verification)

        assert "SHA256 digest" in result

    def test_single_method_primary_marker(self) -> None:
        """Test primary marker shows correctly for single method."""
        verification = {
            "passed": True,
            "methods": [
                {
                    "type": "digest",
                    "status": "passed",
                    "algorithm": "SHA256",
                    "source": "github_api",
                    "primary": True,
                },
            ],
        }

        result = format_verification_info(verification)

        assert result.startswith("✓")
        assert "○" not in result


class TestFormatVerificationLegacy:
    """Tests for _format_verification_legacy function."""

    def test_digest_passed(self) -> None:
        """Test legacy digest format when passed."""
        verification = {
            "passed": True,
            "digest": {
                "passed": True,
                "hash": "abc123",
                "hash_type": "sha256",
            },
        }

        result = _format_verification_legacy(verification)

        assert "● ✓ SHA256 digest" in result

    def test_digest_failed(self) -> None:
        """Test legacy digest format when failed."""
        verification = {
            "passed": False,
            "digest": {"passed": False, "hash_type": "sha512"},
        }

        result = _format_verification_legacy(verification)

        assert "● ✗ SHA512 digest" in result

    def test_checksum_file_passed(self) -> None:
        """Test legacy checksum file format when passed."""
        verification = {
            "passed": True,
            "checksum_file": {"passed": True, "hash_type": "sha256"},
        }

        result = _format_verification_legacy(verification)

        assert "● ✓ SHA256 checksum file" in result

    def test_checksum_file_failed(self) -> None:
        """Test legacy checksum file format when failed."""
        verification = {
            "passed": False,
            "checksum_file": {"passed": False, "hash_type": "sha512"},
        }

        result = _format_verification_legacy(verification)

        assert "● ✗ SHA512 checksum file" in result

    def test_no_verification_data(self) -> None:
        """Test when no verification data exists."""
        verification = {"passed": False}

        result = _format_verification_legacy(verification)

        assert result == "Not verified"

    def test_empty_dict(self) -> None:
        """Test with empty verification dict."""
        result = _format_verification_legacy({})

        assert result == "Not verified"
