"""Workflows layer - Application services that orchestrate business operations.

This module provides the main workflow orchestrators:
- InstallHandler: Orchestrates AppImage installations
- UpdateManager: Orchestrates AppImage updates
- RemoveService: Orchestrates AppImage removal
- BackupService: Orchestrates backup operations
- SelfUpdater: Orchestrates my-unicorn self-upgrades

Each workflow provides a `create_default()` factory method for simplified instantiation.
"""

from my_unicorn.core.workflows.backup import BackupService
from my_unicorn.core.workflows.install import InstallHandler
from my_unicorn.core.workflows.remove import RemoveService
from my_unicorn.core.workflows.update import UpdateManager

__all__ = [
    "BackupService",
    "InstallHandler",
    "RemoveService",
    "UpdateManager",
]
