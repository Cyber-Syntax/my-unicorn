"""Config command handler for my-unicorn CLI.

This module handles configuration management operations, including
displaying current configuration and resetting to default values.
"""

from argparse import Namespace

from my_unicorn.logger import get_logger, temporary_console_level

from .base import BaseCommandHandler

logger = get_logger(__name__)


class ConfigHandler(BaseCommandHandler):
    """Handler for config command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the config command."""
        with temporary_console_level("INFO"):
            if args.show:
                await self._show_config()
            elif args.reset:
                await self._reset_config()

    async def _show_config(self) -> None:
        """Display current configuration."""
        logger.info("📋 Current Configuration:")
        logger.info(
            "  Config Version: %s", self.global_config["config_version"]
        )
        logger.info(
            "  Max Downloads: %s",
            self.global_config["max_concurrent_downloads"],
        )
        logger.info("  Log Level: %s", self.global_config["log_level"])
        logger.info(
            "  Storage Dir: %s", self.global_config["directory"]["storage"]
        )
        logger.info(
            "  Download Dir: %s", self.global_config["directory"]["download"]
        )
        logger.info("  Icon Dir: %s", self.global_config["directory"]["icon"])
        logger.info(
            "  Backup Dir: %s", self.global_config["directory"]["backup"]
        )

    async def _reset_config(self) -> None:
        """Reset configuration to default values."""
        # Reset to defaults by removing the settings file and loading fresh config
        if self.config_manager.settings_file.exists():
            self.config_manager.settings_file.unlink()

        # Load fresh config (which will create defaults)
        self.config_manager.load_global_config()
        logger.info("✅ Configuration reset to defaults")
