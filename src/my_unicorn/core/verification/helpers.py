"""Helper functions for verification.

This module provides utility functions for URL building and template
expansion used in the verification process.
"""

from __future__ import annotations

from my_unicorn.core.github import Asset, ChecksumFileInfo
from my_unicorn.logger import get_logger

logger = get_logger(__name__, enable_file_logging=True)


def build_checksum_url(
    owner: str,
    repo: str,
    tag_name: str,
    checksum_file: str,
) -> str:
    """Build URL for checksum file download.

    Args:
        owner: Repository owner
        repo: Repository name
        tag_name: Release tag name
        checksum_file: Checksum filename

    Returns:
        Complete checksum file URL

    """
    return (
        f"https://github.com/{owner}/{repo}/releases/download/"
        f"{tag_name}/{checksum_file}"
    )


def resolve_manual_checksum_file(
    manual_checksum_file: str,
    asset: Asset,
    owner: str | None,
    repo: str | None,
    tag_name: str | None,
) -> list[ChecksumFileInfo]:
    """Resolve manually configured checksum file with template support.

    Args:
        manual_checksum_file: Configured checksum filename
            (may have templates)
        asset: GitHub asset information
        owner: Repository owner
        repo: Repository name
        tag_name: Release tag name

    Returns:
        List with single checksum file info, or empty list

    """
    resolved_name = manual_checksum_file
    try:
        if "{" in manual_checksum_file and tag_name:
            resolved_name = manual_checksum_file.replace(
                "{version}", tag_name
            ).replace("{tag}", tag_name)
        if (
            "{asset_name}" in resolved_name
            and asset
            and hasattr(asset, "name")
        ):
            resolved_name = resolved_name.replace("{asset_name}", asset.name)
    except Exception:
        resolved_name = manual_checksum_file

    if not (owner and repo and tag_name):
        return []

    url = build_checksum_url(owner, repo, tag_name, resolved_name)
    format_type = (
        "yaml"
        if resolved_name.lower().endswith((".yml", ".yaml"))
        else "traditional"
    )
    return [
        ChecksumFileInfo(
            filename=resolved_name,
            url=url,
            format_type=format_type,
        )
    ]
