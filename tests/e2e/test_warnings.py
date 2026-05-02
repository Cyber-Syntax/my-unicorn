"""Tests for E2E warning detection helpers."""

import warnings

from tests.e2e.warnings import (
    PartialVerificationWarning,
    find_partial_verifications,
    warn_on_partial_verification,
)


def test_find_partial_verifications_from_cli_summary() -> None:
    """Detect partial verification from user-facing install summary."""
    text = "⚠️  Partial verification: 2 passed, 1 failed"

    matches = find_partial_verifications(text, "legcord")

    assert len(matches) == 1
    assert matches[0].app_name == "legcord"
    assert matches[0].passed_count == 2
    assert matches[0].failed_count == 1


def test_find_partial_verifications_from_log_message() -> None:
    """Detect partial verification from detailed application logs."""
    text = (
        "Partial verification success for joplin: "
        "digest passed, checksum_file failed"
    )

    matches = find_partial_verifications(text, "install")

    assert len(matches) == 1
    assert matches[0].app_name == "joplin"
    assert matches[0].passed_count == 1
    assert matches[0].failed_count == 1


def test_warn_on_partial_verification_emits_warning() -> None:
    """Emit pytest-visible warnings when partial verification is detected."""
    text = (
        "Partial verification success for joplin: "
        "digest passed, checksum_file failed"
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        warning_count = warn_on_partial_verification(text, "install")

    assert warning_count == 1
    assert len(captured) == 1
    assert issubclass(captured[0].category, PartialVerificationWarning)
    assert "joplin partial verification: 1 passed, 1 failed" in str(
        captured[0].message
    )


def test_warn_on_partial_verification_ignores_complete_success() -> None:
    """Do not emit warnings when no failed methods are present."""
    text = "Partial verification: 2 passed, 0 failed"

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        warning_count = warn_on_partial_verification(text, "legcord")

    assert warning_count == 0
    assert captured == []
