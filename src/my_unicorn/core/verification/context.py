"""Verification configuration and context types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from my_unicorn.core.github import Asset, ChecksumFileInfo
    from my_unicorn.core.verification.verifier import Verifier


@dataclass(slots=True, frozen=True)
class VerificationConfig:
    """Verification configuration data."""

    skip: bool = False
    checksum_file: str | None = None
    checksum_hash_type: str = "sha256"
    digest_enabled: bool = False

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> VerificationConfig:
        """Create VerificationConfig from a dictionary.

        Args:
            config: Dictionary with configuration values

        Returns:
            VerificationConfig instance

        """
        from my_unicorn.constants import VerificationMethod  # noqa: PLC0415

        return cls(
            skip=config.get("skip", False),
            checksum_file=config.get("checksum_file"),
            checksum_hash_type=config.get("checksum_hash_type", "sha256"),
            digest_enabled=config.get(VerificationMethod.DIGEST, False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility.

        Returns:
            Dictionary with configuration values

        """
        from my_unicorn.constants import VerificationMethod  # noqa: PLC0415

        return {
            "skip": self.skip,
            "checksum_file": self.checksum_file,
            "checksum_hash_type": self.checksum_hash_type,
            VerificationMethod.DIGEST: self.digest_enabled,
        }


@dataclass(slots=True)
class VerificationContext:
    """Internal context for verification state management.

    Holds mutable state during verification process to reduce
    parameter passing.
    """

    file_path: Path
    asset: Asset
    config: dict[str, Any]
    owner: str
    repo: str
    tag_name: str
    app_name: str
    assets: list[Asset] | None
    progress_task_id: Any | None
    # Computed during preparation
    has_digest: bool = False
    checksum_files: list[ChecksumFileInfo] | None = None
    verifier: Verifier | None = None
    updated_config: dict[str, Any] | None = None
    # Results
    verification_passed: bool = False
    verification_methods: dict[str, Any] = field(default_factory=dict)
    verification_warning: str | None = None

    def __post_init__(self) -> None:
        """Initialize mutable state after dataclass creation."""
        if self.updated_config is None:
            object.__setattr__(self, "updated_config", self.config.copy())
