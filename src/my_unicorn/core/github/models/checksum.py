"""GitHub checksum file info model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ChecksumFileInfo:
    """Information about detected checksum file."""

    filename: str
    url: str
    format_type: str  # 'yaml' or 'traditional'
