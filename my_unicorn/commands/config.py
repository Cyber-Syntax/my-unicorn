"""Config command handler for my-unicorn CLI.

This module handles configuration management operations, including
displaying current configuration and resetting to default values.
"""

from argparse import Namespace

from ..logger import get_logger
from .base import BaseCommandHandler

logger = get_logger(__name__)


class ConfigHandler(BaseCommandHandler):
    """Handler for config command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the config command."""
        if args.show:
            await self._show_config()
        elif args.reset:
            await self._reset_config()

    async def _show_config(self) -> None:
        """Display current configuration."""
        print("📋 Current Configuration:")
        print(f"  Config Version: {self.global_config['config_version']}")
        print(
            f"  Max Downloads: {self.global_config['max_concurrent_downloads']}"
        )
        print(f"  Log Level: {self.global_config['log_level']}")
        print(f"  Storage Dir: {self.global_config['directory']['storage']}")
        print(f"  Download Dir: {self.global_config['directory']['download']}")
        print(f"  Icon Dir: {self.global_config['directory']['icon']}")
        print(f"  Backup Dir: {self.global_config['directory']['backup']}")

    async def _reset_config(self) -> None:
        """Reset configuration to default values."""
        # Reset to defaults by removing the settings file and loading fresh config
        if self.config_manager.directory_manager.settings_file.exists():
            self.config_manager.directory_manager.settings_file.unlink()

        # Load fresh config (which will create defaults)
        self.config_manager.load_global_config()
        print("✅ Configuration reset to defaults")
