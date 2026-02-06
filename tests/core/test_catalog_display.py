"""Tests for CatalogService display functions."""

from my_unicorn.core.catalog import CatalogService


class TestBuildMultiMethodVerificationDisplay:
    """Tests for _build_multi_method_verification_display."""

    def test_both_digest_and_checksum_file(self) -> None:
        """Test when both digest and checksum_file are configured."""
        verification = {
            "method": "digest",
            "digest": {"algorithm": "SHA256"},
            "checksum_file": {"name": "SHA256SUMS.txt", "algorithm": "SHA256"},
        }

        result = CatalogService._build_multi_method_verification_display(
            verification
        )

        assert result == "SHA256 digest + checksum file (concurrent)"

    def test_only_digest(self) -> None:
        """Test when only digest is configured."""
        verification = {
            "method": "digest",
            "digest": {"algorithm": "SHA256"},
        }

        result = CatalogService._build_multi_method_verification_display(
            verification
        )

        assert result == "SHA256 digest (embedded in GitHub release)"

    def test_only_checksum_file(self) -> None:
        """Test when only checksum_file is configured."""
        verification = {
            "method": "checksum_file",
            "checksum_file": {"name": "SHA512SUMS.txt", "algorithm": "SHA512"},
        }

        result = CatalogService._build_multi_method_verification_display(
            verification
        )

        assert result == "SHA512 checksum (SHA512SUMS.txt)"

    def test_method_only_digest(self) -> None:
        """Test legacy format with only method field."""
        verification = {"method": "digest"}

        result = CatalogService._build_multi_method_verification_display(
            verification
        )

        assert result == "SHA256 digest (embedded in GitHub release)"

    def test_method_skip(self) -> None:
        """Test when verification is set to skip."""
        verification = {"method": "skip"}

        result = CatalogService._build_multi_method_verification_display(
            verification
        )

        assert result == "No verification (developer provides no checksums)"

    def test_empty_verification(self) -> None:
        """Test when no verification is configured."""
        verification: dict[str, object] = {}

        result = CatalogService._build_multi_method_verification_display(
            verification
        )

        assert result == "No verification available"

    def test_none_values(self) -> None:
        """Test when digest and checksum_file are explicitly None."""
        verification = {"digest": None, "checksum_file": None}

        result = CatalogService._build_multi_method_verification_display(
            verification
        )

        assert result == "No verification available"
