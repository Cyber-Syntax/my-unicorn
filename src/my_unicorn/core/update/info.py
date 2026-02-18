"""Update information types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from my_unicorn.core.github import Release


@dataclass
class UpdateInfo:
    r"""Information about an available update for an installed application.

    This class encapsulates update status and metadata, including in-memory
    caching of release data and loaded config to eliminate redundant cache
    file reads during a single update operation.

    Attributes:
        app_name: Name of the application.
        current_version: Currently installed version string.
        latest_version: Latest available version from GitHub.
        has_update: True if latest_version is newer than current_version.
        release_url: URL to the GitHub release page.
        prerelease: True if the latest release is a prerelease.
        original_tag_name: Original Git tag name for the release.
        release_data: Cached Release object from GitHub API.
        app_config: Cached loaded application configuration.
        error_reason: Error message if update check failed, None on success.

    Example:
        >>> info = await manager.check_single_update("firefox", session)
        >>> if info.is_success and info.has_update:
        ...     print(
        ...         f"Update: {info.current_version} -> {info.latest_version}"
        ...     )
        >>> elif info.error_reason:
        ...     print(f"Check failed: {info.error_reason}")

    """

    app_name: str
    current_version: str = ""
    latest_version: str = ""
    has_update: bool = False
    release_url: str = ""
    prerelease: bool = False
    original_tag_name: str = ""
    release_data: Release | None = None
    app_config: dict[str, Any] | None = None  # Cached loaded config
    error_reason: str | None = None

    def __post_init__(self) -> None:
        """Post-initialization processing."""
        from my_unicorn.constants import VERSION_UNKNOWN  # noqa: PLC0415

        # Set default original_tag_name if not provided
        if (
            not self.original_tag_name
            and self.latest_version != VERSION_UNKNOWN
        ):
            self.original_tag_name = f"v{self.latest_version}"

    @classmethod
    def create_error(cls, app_name: str, reason: str) -> UpdateInfo:
        """Create an UpdateInfo representing an error condition.

        Args:
            app_name: Name of the application
            reason: Error reason/message

        Returns:
            UpdateInfo with error_reason set

        """
        return cls(app_name=app_name, error_reason=reason)

    @property
    def is_success(self) -> bool:
        """Check if update info represents a successful operation.

        Returns:
            True if no error occurred, False otherwise

        """
        return self.error_reason is None

    def __repr__(self) -> str:
        """String representation of update info."""
        if self.error_reason:
            return f"UpdateInfo({self.app_name}: Error - {self.error_reason})"
        status = "Available" if self.has_update else "Up to date"
        return (
            f"UpdateInfo({self.app_name}: {self.current_version} -> "
            f"{self.latest_version}, {status})"
        )
