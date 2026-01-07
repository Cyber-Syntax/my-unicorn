"""Workflows layer - Application services that orchestrate business operations.

This module provides the main workflow orchestrators:
- InstallHandler: Orchestrates AppImage installations
- UpdateManager: Orchestrates AppImage updates
- RemoveService: Orchestrates AppImage removal
- BackupService: Orchestrates backup operations
- SelfUpdater: Orchestrates my-unicorn self-upgrades

Each workflow provides a `create_default()` factory method for simplified instantiation.
"""

from my_unicorn.workflows.backup import BackupService
from my_unicorn.workflows.install import InstallHandler
from my_unicorn.workflows.remove import RemoveService
from my_unicorn.workflows.update import UpdateManager
from my_unicorn.workflows.upgrade import SelfUpdater

__all__ = [
    "BackupService",
    "InstallHandler",
    "RemoveService",
    "SelfUpdater",
    "UpdateManager",
]
