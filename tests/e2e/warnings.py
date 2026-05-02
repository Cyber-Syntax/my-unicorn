"""Warning detection helpers for E2E CLI subprocess output."""

import re
import warnings
from dataclasses import dataclass

SUMMARY_PARTIAL_VERIFICATION_PATTERN = re.compile(
    r"Partial verification:\s*(\d+)\s*passed,\s*(\d+)\s*failed",
    re.IGNORECASE,
)
LOG_PARTIAL_VERIFICATION_PATTERN = re.compile(
    r"Partial verification success for\s+(?P<app>[\w.-]+):\s*"
    r"(?P<passed>[\w, _-]+)\s+passed,\s*"
    r"(?P<failed>[\w, _-]+)\s+failed",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PartialVerificationMatch:
    """Partial verification details detected in CLI output or logs."""

    app_name: str
    passed_count: int
    failed_count: int


class PartialVerificationWarning(UserWarning):
    """Raised when install succeeds but verification is only partial."""


def _count_methods(methods_text: str) -> int:
    """Count comma-separated verification method names."""
    return len(
        [method for method in methods_text.split(",") if method.strip()]
    )


def find_partial_verifications(
    text: str,
    default_app_name: str,
) -> list[PartialVerificationMatch]:
    """Find partial verification summaries in CLI output or log text."""
    matches: list[PartialVerificationMatch] = []

    for passed_str, failed_str in SUMMARY_PARTIAL_VERIFICATION_PATTERN.findall(
        text
    ):
        failed_count = int(failed_str)
        if failed_count > 0:
            matches.append(
                PartialVerificationMatch(
                    app_name=default_app_name,
                    passed_count=int(passed_str),
                    failed_count=failed_count,
                )
            )

    for log_match in LOG_PARTIAL_VERIFICATION_PATTERN.finditer(text):
        failed_count = _count_methods(log_match.group("failed"))
        if failed_count > 0:
            matches.append(
                PartialVerificationMatch(
                    app_name=log_match.group("app"),
                    passed_count=_count_methods(log_match.group("passed")),
                    failed_count=failed_count,
                )
            )

    return matches


def warn_on_partial_verification(text: str, app_name: str) -> int:
    """
    Emit pytest warning if CLI output or logs contain partial verification.

    Example CLI summary matched text:
        Partial verification: 1 passed, 1 failed

    Example log matched text:
        Partial verification success for joplin: digest passed,
        checksum_file failed

    Returns:
        Number of warnings emitted.
    """
    matches = find_partial_verifications(text, app_name)

    for match in matches:
        warnings.warn(
            (
                f"{match.app_name} partial verification: "
                f"{match.passed_count} passed, {match.failed_count} failed"
            ),
            PartialVerificationWarning,
            stacklevel=2,
        )

    return len(matches)
