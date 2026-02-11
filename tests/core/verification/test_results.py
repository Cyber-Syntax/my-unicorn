"""Tests for verification result types (MethodResult, VerificationResult)."""

from __future__ import annotations

import pytest

from my_unicorn.core.verification.results import (
    MethodResult,
    VerificationResult,
)


class TestMethodResult:
    """Test MethodResult dataclass."""

    def test_method_result_success(self) -> None:
        """Test MethodResult creation with passed=True."""
        result = MethodResult(
            passed=True,
            hash="abc123",
            details="Verification succeeded",
        )

        assert result.passed is True
        assert result.hash == "abc123"
        assert result.details == "Verification succeeded"
        assert result.computed_hash is None
        assert result.url is None
        assert result.hash_type is None

    def test_method_result_failure(self) -> None:
        """Test MethodResult creation with passed=False."""
        result = MethodResult(
            passed=False,
            hash="expected_hash",
            details="Hash mismatch detected",
        )

        assert result.passed is False
        assert result.hash == "expected_hash"
        assert result.details == "Hash mismatch detected"

    def test_method_result_with_optional_fields(self) -> None:
        """Test MethodResult with all optional fields populated."""
        result = MethodResult(
            passed=True,
            hash="abc123def456",
            details="SHA256 verification passed",
            computed_hash="abc123def456",
            url="https://example.com/app.AppImage",
            hash_type="sha256",
        )

        assert result.passed is True
        assert result.hash == "abc123def456"
        assert result.computed_hash == "abc123def456"
        assert result.url == "https://example.com/app.AppImage"
        assert result.hash_type == "sha256"

    def test_method_result_to_dict_minimal(self) -> None:
        """Test MethodResult.to_dict() with required fields only."""
        result = MethodResult(
            passed=True,
            hash="abc123",
            details="Verification passed",
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["passed"] is True
        assert result_dict["hash"] == "abc123"
        assert result_dict["details"] == "Verification passed"
        assert "computed_hash" not in result_dict
        assert "url" not in result_dict
        assert "hash_type" not in result_dict

    def test_method_result_to_dict_with_computed_hash(self) -> None:
        """Test MethodResult.to_dict() includes computed_hash when present."""
        result = MethodResult(
            passed=True,
            hash="expected",
            details="Passed",
            computed_hash="expected",
        )

        result_dict = result.to_dict()

        assert result_dict["computed_hash"] == "expected"

    def test_method_result_to_dict_excludes_none_computed_hash(self) -> None:
        """Test MethodResult.to_dict() excludes computed_hash when None."""
        result = MethodResult(
            passed=True,
            hash="abc123",
            details="Test",
            computed_hash=None,
        )

        result_dict = result.to_dict()

        assert "computed_hash" not in result_dict

    def test_method_result_to_dict_with_url(self) -> None:
        """Test MethodResult.to_dict() includes url when present."""
        result = MethodResult(
            passed=True,
            hash="abc123",
            details="Test",
            url="https://example.com/file.AppImage",
        )

        result_dict = result.to_dict()

        assert result_dict["url"] == "https://example.com/file.AppImage"

    def test_method_result_to_dict_excludes_none_url(self) -> None:
        """Test MethodResult.to_dict() excludes url when None."""
        result = MethodResult(
            passed=True,
            hash="abc123",
            details="Test",
            url=None,
        )

        result_dict = result.to_dict()

        assert "url" not in result_dict

    def test_method_result_to_dict_with_hash_type(self) -> None:
        """Test MethodResult.to_dict() includes hash_type when present."""
        result = MethodResult(
            passed=True,
            hash="abc123",
            details="Test",
            hash_type="sha256",
        )

        result_dict = result.to_dict()

        assert result_dict["hash_type"] == "sha256"

    def test_method_result_to_dict_excludes_none_hash_type(self) -> None:
        """Test MethodResult.to_dict() excludes hash_type when None."""
        result = MethodResult(
            passed=True,
            hash="abc123",
            details="Test",
            hash_type=None,
        )

        result_dict = result.to_dict()

        assert "hash_type" not in result_dict

    def test_method_result_to_dict_with_all_fields(self) -> None:
        """Test MethodResult.to_dict() with all fields populated."""
        result = MethodResult(
            passed=True,
            hash="expected_hash",
            details="Verification passed",
            computed_hash="expected_hash",
            url="https://example.com/app.AppImage",
            hash_type="sha256",
        )

        result_dict = result.to_dict()

        assert result_dict == {
            "passed": True,
            "hash": "expected_hash",
            "details": "Verification passed",
            "computed_hash": "expected_hash",
            "url": "https://example.com/app.AppImage",
            "hash_type": "sha256",
        }

    def test_method_result_immutable(self) -> None:
        """Test that MethodResult is frozen/immutable."""
        result = MethodResult(
            passed=True,
            hash="abc123",
            details="Test",
        )

        with pytest.raises(AttributeError):
            result.passed = False  # pragma: no cover

    def test_method_result_defaults(self) -> None:
        """Test MethodResult default values for optional fields."""
        result = MethodResult(
            passed=False,
            hash="test_hash",
            details="Test details",
        )

        assert result.computed_hash is None
        assert result.url is None
        assert result.hash_type is None


class TestVerificationResult:
    """Test VerificationResult dataclass."""

    def test_verification_result_initialization(self) -> None:
        """Test VerificationResult initialization with required fields."""
        methods = {"digest": {"passed": True, "hash": "abc123"}}
        updated_config = {"verified": True}

        result = VerificationResult(
            passed=True,
            methods=methods,
            updated_config=updated_config,
        )

        assert result.passed is True
        assert result.methods == methods
        assert result.updated_config == updated_config
        assert result.warning is None

    def test_verification_result_with_warning(self) -> None:
        """Test VerificationResult with optional warning message."""
        methods = {"digest": {"passed": True}}
        updated_config: dict[str, bool] = {}
        warning_msg = "Checksum file not found, using digest verification only"

        result = VerificationResult(
            passed=True,
            methods=methods,
            updated_config=updated_config,
            warning=warning_msg,
        )

        assert result.passed is True
        assert result.warning == warning_msg

    def test_verification_result_with_multiple_methods(self) -> None:
        """Test VerificationResult with multiple verification methods."""
        methods = {
            "sha256_digest": {"passed": True, "hash": "abc123"},
            "sha512_digest": {"passed": True, "hash": "def456"},
            "checksum_file": {"passed": True, "hash": "ghi789"},
        }
        updated_config = {"verified": True, "checksum_method": "sha256"}

        result = VerificationResult(
            passed=True,
            methods=methods,
            updated_config=updated_config,
        )

        assert len(result.methods) == 3
        assert "sha256_digest" in result.methods
        assert "sha512_digest" in result.methods
        assert "checksum_file" in result.methods
        assert updated_config["verified"] is True

    def test_verification_result_failed(self) -> None:
        """Test VerificationResult when verification failed."""
        methods = {
            "digest": {
                "passed": False,
                "hash": "expected",
                "error": "mismatch",
            }
        }
        updated_config = {"verified": False}

        result = VerificationResult(
            passed=False,
            methods=methods,
            updated_config=updated_config,
        )

        assert result.passed is False
        assert result.methods == methods

    def test_verification_result_immutable(self) -> None:
        """Test that VerificationResult is frozen/immutable."""
        result = VerificationResult(
            passed=True,
            methods={},
            updated_config={},
        )

        with pytest.raises(AttributeError):
            result.passed = False  # pragma: no cover

    def test_verification_result_default_warning(self) -> None:
        """Test VerificationResult default warning is None."""
        result = VerificationResult(
            passed=True,
            methods={},
            updated_config={},
        )

        assert result.warning is None

    def test_verification_result_with_method_results(self) -> None:
        """Test VerificationResult with MethodResult objects in methods."""
        method_result = MethodResult(
            passed=True,
            hash="abc123",
            details="SHA256 verification passed",
            computed_hash="abc123",
            hash_type="sha256",
        )

        # Convert MethodResult to dict for storage
        methods = {
            "sha256": method_result.to_dict(),
        }

        result = VerificationResult(
            passed=True,
            methods=methods,
            updated_config={"verified": True},
        )

        assert result.methods["sha256"]["passed"] is True
        assert result.methods["sha256"]["hash"] == "abc123"
        assert result.methods["sha256"]["hash_type"] == "sha256"

    def test_verification_result_multiple_method_results(self) -> None:
        """Test VerificationResult with multiple MethodResult objects."""
        method_results = {
            "sha256": MethodResult(
                passed=True,
                hash="abc123",
                details="SHA256 passed",
                hash_type="sha256",
            ).to_dict(),
            "sha512": MethodResult(
                passed=True,
                hash="def456",
                details="SHA512 passed",
                hash_type="sha512",
            ).to_dict(),
        }

        result = VerificationResult(
            passed=True,
            methods=method_results,
            updated_config={"verified": True},
        )

        assert len(result.methods) == 2
        assert result.methods["sha256"]["hash_type"] == "sha256"
        assert result.methods["sha512"]["hash_type"] == "sha512"

    def test_verification_result_with_empty_methods(self) -> None:
        """Test VerificationResult with empty methods dictionary."""
        result = VerificationResult(
            passed=False,
            methods={},
            updated_config={},
            warning="No verification methods available",
        )

        assert result.methods == {}
        assert result.passed is False
        assert result.warning == "No verification methods available"

    def test_verification_result_with_empty_config(self) -> None:
        """Test VerificationResult with empty updated_config."""
        result = VerificationResult(
            passed=True,
            methods={"digest": {"passed": True}},
            updated_config={},
        )

        assert result.updated_config == {}
        assert result.passed is True
