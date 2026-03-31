"""Tests for Phase 1 bug fixes: passed=False for skipped verification.

Tests that verify the two bugs are fixed:
1. _prepare_verification returns passed=False when verification is skipped
2. _finalize_verification returns passed=False when no strong methods available
"""

from pathlib import Path

import pytest

from my_unicorn.core.github import Asset
from my_unicorn.core.verification.service import VerificationService


class TestSkipVerificationBug:
    """Tests for the skip verification bug fix."""

    @pytest.mark.asyncio
    async def test_skip_verification_returns_passed_false(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
    ) -> None:
        """When skip path is triggered, VerificationResult.passed should be.

        False.

        Bug: _prepare_verification was returning passed=True for skipped
        verification, which caused config to persist "passed": true and
        suppressed the "⚠️ Not verified" warning.

        Fix: Return passed=False when verification is skipped.
        """
        # Arrange: Mock config with skip=True to trigger the skip path
        config = {"skip": True}
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/repo/releases/download/v1.0.0/test.AppImage",
            digest="",
        )

        # Act: Call verify_file with skip=True
        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="test-app",
            assets=[asset],
        )

        # Assert: passed should be False, not True
        assert result.passed is False, (
            "VerificationResult.passed should be False for skipped "
            "verification, not True"
        )
        assert result.methods["skip"]["passed"] is False
        assert result.methods["skip"]["status"] == "skipped"


class TestFinalizeNoStrongMethodsBug:
    """Tests for the finalize no strong methods bug fix."""

    @pytest.mark.asyncio
    async def test_finalize_no_strong_methods_returns_passed_false(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
    ) -> None:
        """When no strong methods available, overall_passed should be False.

        Bug: _finalize_verification was using:
            overall_passed = not strong_methods_available or has_passing_method

        This caused passed=True even when no verification methods were
        available. The logic should be:
            overall_passed = strong_methods_available and has_passing_method

        Fix: Change the logic so that if no strong methods are available,
        overall_passed is False (not True).
        """
        # Arrange: Config with skip=False to reach _finalize_verification
        # Asset has no digest, and no checksum files in assets list
        # This ensures strong_methods_available=False in _finalize_verification
        config = {"skip": False}
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/repo/releases/download/v1.0.0/test.AppImage",
            digest="",
        )

        # Act: Call verify_file with skip=False and no checksums
        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="test-app",
            assets=[asset],  # No checksum files
        )

        # Assert: When no strong methods are available (skipped case),
        # passed should be False
        assert result.passed is False, (
            "VerificationResult.passed should be False when no strong "
            "methods are available (i.e., verification is skipped)"
        )
        assert "skip" in result.methods
        assert result.methods["skip"]["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_skip_verification_returns_warning_message(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
    ) -> None:
        """When skip path is triggered, warning message should be set.

        When verification is skipped (config has skip=True or method=skip,
        no digest, no checksum files), the returned VerificationResult.warning
        should be "Not verified - developer did not provide checksums".

        This ensures the install summary displays the warning to the user.
        """
        # Arrange: Mock config with skip=True to trigger the early skip path
        config = {"skip": True}
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url="https://github.com/test/repo/releases/download/v1.0.0/test.AppImage",
            digest="",
        )

        # Act: Call verify_file with skip=True
        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="test-app",
            assets=[asset],
        )

        # Assert: warning should be set to the expected message
        expected = "Not verified - developer did not provide checksums"
        assert result.warning == expected
