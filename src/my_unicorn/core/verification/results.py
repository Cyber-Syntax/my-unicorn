"""Verification result types for AppImage integrity checking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class MethodResult:
    """Result of a single verification method attempt."""

    passed: bool
    hash: str
    details: str
    computed_hash: str | None = None
    url: str | None = None
    hash_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility.

        Returns:
            Dictionary representation

        """
        result: dict[str, Any] = {
            "passed": self.passed,
            "hash": self.hash,
            "details": self.details,
        }
        if self.computed_hash:
            result["computed_hash"] = self.computed_hash
        if self.url:
            result["url"] = self.url
        if self.hash_type:
            result["hash_type"] = self.hash_type
        return result


@dataclass(slots=True, frozen=True)
class VerificationResult:
    """Result of verification attempt.

    Attributes:
        passed: Overall verification success status
        methods: Dictionary of all verification method results
        updated_config: Configuration with verification results
        warning: Optional warning message for partial verification success

    """

    passed: bool
    methods: dict[str, Any]
    updated_config: dict[str, Any]
    warning: str | None = None
