"""Tests for verification execution functions.

This module tests execution functions:
- execute_digest_verification()
- execute_checksum_file_verification()
- execute_all_verification_methods()

Tests cover success cases, failure cases, edge cases, and concurrent execution.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.constants import VerificationMethod
from my_unicorn.core.github import Asset, ChecksumFileInfo
from my_unicorn.core.verification.context import VerificationContext
from my_unicorn.core.verification.execution import (
    execute_all_verification_methods,
    execute_checksum_file_verification,
    execute_digest_verification,
)
from my_unicorn.core.verification.results import MethodResult


@pytest.fixture
def mock_verifier() -> MagicMock:
    """Create a mock verifier."""
    verifier = MagicMock()
    verifier.compute_hash = MagicMock(return_value="computed_hash_123")
    verifier.verify_digest = MagicMock()
    verifier.file_path = Path("/tmp/test.AppImage")
    return verifier


@pytest.fixture
def mock_download_service() -> MagicMock:
    """Create a mock download service."""
    service = MagicMock()
    service.download_checksum_file = AsyncMock(return_value="hash1234")
    return service


@pytest.fixture
def asset_with_digest(test_file_path: Path) -> Asset:
    """Create test asset with digest."""
    return Asset(
        name="test.AppImage",
        browser_download_url="https://example.com/test.AppImage",
        size=1024,
        digest="abc123def456",
    )


@pytest.fixture
def context_with_digest(
    asset_with_digest: Asset,
    test_file_path: Path,
    mock_verifier: MagicMock,
) -> VerificationContext:
    """Create test context with digest."""
    return VerificationContext(
        file_path=test_file_path,
        asset=asset_with_digest,
        config={"skip": False},
        owner="test-owner",
        repo="test-repo",
        tag_name="v1.0.0",
        app_name="test-app",
        assets=[asset_with_digest],
        progress_task_id=None,
        has_digest=True,
        verifier=mock_verifier,
    )


@pytest.fixture
def context_without_digest(
    test_file_path: Path,
    mock_verifier: MagicMock,
) -> VerificationContext:
    """Create test context without digest."""
    asset = Asset(
        name="test.AppImage",
        browser_download_url="https://example.com/test.AppImage",
        size=1024,
        digest=None,
    )
    return VerificationContext(
        file_path=test_file_path,
        asset=asset,
        config={"skip": False},
        owner="test-owner",
        repo="test-repo",
        tag_name="v1.0.0",
        app_name="test-app",
        assets=[asset],
        progress_task_id=None,
        has_digest=False,
        verifier=mock_verifier,
    )


class TestExecuteDigestVerification:
    """Tests for execute_digest_verification()."""

    @pytest.mark.asyncio
    async def test_success(
        self, context_with_digest: VerificationContext
    ) -> None:
        """Test successful digest verification."""
        with patch(
            "my_unicorn.core.verification.execution.verify_digest",
            new_callable=AsyncMock,
            return_value=MethodResult(
                passed=True,
                hash="abc123def456",
                computed_hash="abc123def456",
                details="Digest passed",
            ),
        ):
            result = await execute_digest_verification(context_with_digest)
            assert result is not None
            assert result.passed is True

    @pytest.mark.asyncio
    async def test_failure(
        self, context_with_digest: VerificationContext
    ) -> None:
        """Test failed digest verification."""
        with patch(
            "my_unicorn.core.verification.execution.verify_digest",
            new_callable=AsyncMock,
            return_value=MethodResult(
                passed=False, hash="expected_hash", details="Hash mismatch"
            ),
        ):
            result = await execute_digest_verification(context_with_digest)
            assert result is not None
            assert result.passed is False

    @pytest.mark.asyncio
    async def test_none_when_no_digest(
        self, context_without_digest: VerificationContext
    ) -> None:
        """Test that None is returned when digest not available."""
        result = await execute_digest_verification(context_without_digest)
        assert result is None

    @pytest.mark.asyncio
    async def test_none_when_verifier_missing(
        self, context_with_digest: VerificationContext
    ) -> None:
        """Test that None is returned when verifier missing."""
        object.__setattr__(context_with_digest, "verifier", None)
        result = await execute_digest_verification(context_with_digest)
        assert result is None


class TestExecuteChecksumFileVerification:
    """Tests for execute_checksum_file_verification()."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("format_type", "passed"),
        [("traditional", True), ("yaml", True), ("traditional", False)],
    )
    async def test_verification(
        self,
        context_with_digest: VerificationContext,
        mock_download_service: MagicMock,
        format_type: str,
        passed: bool,
    ) -> None:
        """Test checksum verification with different formats."""
        checksum_file = ChecksumFileInfo(
            filename="SHA256SUMS",
            url="https://example.com/SHA256SUMS",
            format_type=format_type,
        )
        with patch(
            "my_unicorn.core.verification.execution.verify_checksum_file",
            new_callable=AsyncMock,
            return_value=MethodResult(
                passed=passed,
                hash="hash_value",
                details="Checksum verified" if passed else "Hash mismatch",
            ),
        ):
            result = await execute_checksum_file_verification(
                context_with_digest, checksum_file, mock_download_service, None
            )
            assert result is not None
            assert result.passed is passed

    @pytest.mark.asyncio
    async def test_none_when_verifier_missing(
        self,
        context_with_digest: VerificationContext,
        mock_download_service: MagicMock,
    ) -> None:
        """Test None returned when verifier missing."""
        checksum_file = ChecksumFileInfo(
            filename="SHA256SUMS",
            url="https://example.com/SHA256SUMS",
            format_type="traditional",
        )
        object.__setattr__(context_with_digest, "verifier", None)
        result = await execute_checksum_file_verification(
            context_with_digest, checksum_file, mock_download_service, None
        )
        assert result is None


class TestExecuteAllVerificationMethods:
    """Tests for execute_all_verification_methods()."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("digest_passed", "checksum_passed"),
        [(True, True), (True, False), (False, True), (False, False)],
    )
    async def test_both_methods(
        self,
        context_with_digest: VerificationContext,
        mock_download_service: MagicMock,
        digest_passed: bool,
        checksum_passed: bool,
    ) -> None:
        """Test concurrent execution with different pass/fail combinations."""
        checksum_file = ChecksumFileInfo(
            filename="SHA256SUMS",
            url="https://example.com/SHA256SUMS",
            format_type="traditional",
        )
        object.__setattr__(
            context_with_digest, "checksum_files", [checksum_file]
        )

        with (
            patch(
                "my_unicorn.core.verification.execution.verify_digest",
                new_callable=AsyncMock,
                return_value=MethodResult(
                    passed=digest_passed, hash="abc123", details="Digest"
                ),
            ),
            patch(
                "my_unicorn.core.verification.execution.verify_checksum_file",
                new_callable=AsyncMock,
                return_value=MethodResult(
                    passed=checksum_passed, hash="xyz789", details="Checksum"
                ),
            ),
            patch(
                "my_unicorn.core.verification.detection.prioritize_checksum_files",
                return_value=[checksum_file],
            ),
        ):
            await execute_all_verification_methods(
                context_with_digest, mock_download_service, None
            )
            assert len(context_with_digest.verification_methods) == 2
            assert (
                context_with_digest.verification_methods[
                    VerificationMethod.DIGEST
                ]["passed"]
                is digest_passed
            )
            assert (
                context_with_digest.verification_methods["checksum_file"][
                    "passed"
                ]
                is checksum_passed
            )

    @pytest.mark.asyncio
    async def test_only_digest_available(
        self,
        context_with_digest: VerificationContext,
        mock_download_service: MagicMock,
    ) -> None:
        """Test when only digest available."""
        object.__setattr__(context_with_digest, "checksum_files", None)

        with patch(
            "my_unicorn.core.verification.execution.verify_digest",
            new_callable=AsyncMock,
            return_value=MethodResult(
                passed=True, hash="abc123", details="Digest"
            ),
        ):
            await execute_all_verification_methods(
                context_with_digest, mock_download_service, None
            )
            assert len(context_with_digest.verification_methods) == 1
            assert VerificationMethod.DIGEST in (
                context_with_digest.verification_methods
            )

    @pytest.mark.asyncio
    async def test_only_checksum_available(
        self,
        context_without_digest: VerificationContext,
        mock_download_service: MagicMock,
    ) -> None:
        """Test when only checksum available."""
        checksum_file = ChecksumFileInfo(
            filename="SHA256SUMS",
            url="https://example.com/SHA256SUMS",
            format_type="traditional",
        )
        object.__setattr__(
            context_without_digest, "checksum_files", [checksum_file]
        )

        with (
            patch(
                "my_unicorn.core.verification.execution.verify_checksum_file",
                new_callable=AsyncMock,
                return_value=MethodResult(
                    passed=True, hash="xyz789", details="Checksum"
                ),
            ),
            patch(
                "my_unicorn.core.verification.detection.prioritize_checksum_files",
                return_value=[checksum_file],
            ),
        ):
            await execute_all_verification_methods(
                context_without_digest, mock_download_service, None
            )
            assert len(context_without_digest.verification_methods) == 1
            assert "checksum_file" in (
                context_without_digest.verification_methods
            )

    @pytest.mark.asyncio
    async def test_neither_available(
        self,
        context_without_digest: VerificationContext,
        mock_download_service: MagicMock,
    ) -> None:
        """Test when neither method available."""
        object.__setattr__(context_without_digest, "checksum_files", None)

        await execute_all_verification_methods(
            context_without_digest, mock_download_service, None
        )
        assert len(context_without_digest.verification_methods) == 0

    @pytest.mark.asyncio
    async def test_concurrent_execution(
        self,
        context_with_digest: VerificationContext,
        mock_download_service: MagicMock,
    ) -> None:
        """Test concurrent execution of both methods."""
        checksum_file = ChecksumFileInfo(
            filename="SHA256SUMS",
            url="https://example.com/SHA256SUMS",
            format_type="traditional",
        )
        object.__setattr__(
            context_with_digest, "checksum_files", [checksum_file]
        )
        call_order: list[str] = []

        async def digest_impl(*args, **kwargs) -> MethodResult:
            call_order.append("digest")
            return MethodResult(passed=True, hash="abc123", details="Digest")

        async def checksum_impl(*args, **kwargs) -> MethodResult:
            call_order.append("checksum")
            return MethodResult(passed=True, hash="xyz789", details="Checksum")

        with (
            patch(
                "my_unicorn.core.verification.execution.verify_digest",
                new_callable=AsyncMock,
                side_effect=digest_impl,
            ),
            patch(
                "my_unicorn.core.verification.execution.verify_checksum_file",
                new_callable=AsyncMock,
                side_effect=checksum_impl,
            ),
            patch(
                "my_unicorn.core.verification.detection.prioritize_checksum_files",
                return_value=[checksum_file],
            ),
        ):
            await execute_all_verification_methods(
                context_with_digest, mock_download_service, None
            )
            assert "digest" in call_order
            assert "checksum" in call_order
            assert len(context_with_digest.verification_methods) == 2

    @pytest.mark.asyncio
    async def test_exception_handling(
        self,
        context_with_digest: VerificationContext,
        mock_download_service: MagicMock,
    ) -> None:
        """Test exception handling in concurrent execution."""
        checksum_file = ChecksumFileInfo(
            filename="SHA256SUMS",
            url="https://example.com/SHA256SUMS",
            format_type="traditional",
        )
        object.__setattr__(
            context_with_digest, "checksum_files", [checksum_file]
        )

        with (
            patch(
                "my_unicorn.core.verification.execution.verify_digest",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Test error"),
            ),
            patch(
                "my_unicorn.core.verification.execution.verify_checksum_file",
                new_callable=AsyncMock,
                return_value=MethodResult(
                    passed=True, hash="xyz789", details="Checksum"
                ),
            ),
            patch(
                "my_unicorn.core.verification.detection.prioritize_checksum_files",
                return_value=[checksum_file],
            ),
        ):
            await execute_all_verification_methods(
                context_with_digest, mock_download_service, None
            )
            assert (
                context_with_digest.verification_methods[
                    VerificationMethod.DIGEST
                ]["passed"]
                is False
            )
            assert (
                "Exception:"
                in context_with_digest.verification_methods[
                    VerificationMethod.DIGEST
                ]["details"]
            )

    @pytest.mark.asyncio
    async def test_config_updated_on_success(
        self,
        context_with_digest: VerificationContext,
        mock_download_service: MagicMock,
    ) -> None:
        """Test config updated when verification succeeds."""
        checksum_file = ChecksumFileInfo(
            filename="SHA256SUMS",
            url="https://example.com/SHA256SUMS",
            format_type="traditional",
        )
        object.__setattr__(
            context_with_digest, "checksum_files", [checksum_file]
        )
        object.__setattr__(context_with_digest, "updated_config", {})

        with (
            patch(
                "my_unicorn.core.verification.execution.verify_digest",
                new_callable=AsyncMock,
                return_value=MethodResult(
                    passed=True, hash="abc123", details="Digest"
                ),
            ),
            patch(
                "my_unicorn.core.verification.execution.verify_checksum_file",
                new_callable=AsyncMock,
                return_value=MethodResult(
                    passed=True, hash="xyz789", details="Checksum"
                ),
            ),
            patch(
                "my_unicorn.core.verification.detection.prioritize_checksum_files",
                return_value=[checksum_file],
            ),
        ):
            await execute_all_verification_methods(
                context_with_digest, mock_download_service, None
            )
            assert context_with_digest.updated_config is not None
            assert (
                context_with_digest.updated_config[VerificationMethod.DIGEST]
                is True
            )
            assert (
                context_with_digest.updated_config["checksum_file"]
                == "SHA256SUMS"
            )
