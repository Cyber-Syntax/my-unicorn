"""Cache command handler for my-unicorn CLI.

Handles cache management operations for the CLI, including clearing cache entries
and displaying cache statistics.
"""

import sys
from argparse import Namespace

from ..logger import get_logger
from ..services.cache import get_cache_manager
from .base import BaseCommandHandler

logger = get_logger(__name__)


class CacheHandler(BaseCommandHandler):
    """Handler for cache command operations.

    Provides cache management functionality:
    - Clearing cache entries
    - Displaying cache statistics

    Note:
        Cache refresh is handled by the update command (--refresh-cache flag).

    """

    async def execute(self, args: Namespace) -> None:
        """Execute the cache command based on subcommand.

        Args:
            args: Parsed command-line arguments containing cache parameters.

        Raises:
            SystemExit: On unknown action or error.

        """
        try:
            if args.cache_action == "clear":
                await self._handle_clear(args)
            elif args.cache_action == "stats":
                await self._handle_stats(args)
            else:
                logger.error("Unknown cache action: %s", args.cache_action)
                sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Cache operation interrupted by user")
            sys.exit(130)
        except Exception as e:
            logger.error("Cache operation failed: %s", e)
            sys.exit(1)

    async def _handle_clear(self, args: Namespace) -> None:
        """Clear cache entries based on arguments.

        Args:
            args: Parsed command-line arguments.

        Raises:
            SystemExit: If neither --all nor app name is specified.

        """
        cache_manager = get_cache_manager()
        if args.all:
            await cache_manager.clear_cache()
            logger.info("✅ Cleared all cache entries")
        elif args.app_name:
            # Parse owner/repo from app name
            owner, repo = self._parse_app_name(args.app_name)
            await cache_manager.clear_cache(owner, repo)
            logger.info("✅ Cleared cache for %s/%s", owner, repo)
        else:
            logger.error("Please specify either --all or an app name to clear")
            sys.exit(1)

    async def _handle_stats(self, args: Namespace) -> None:
        """Display cache statistics.

        Args:
            args: Parsed command-line arguments.

        Raises:
            SystemExit: On error.

        """
        cache_manager = get_cache_manager()
        try:
            stats = await cache_manager.get_cache_stats()
            logger.info("📁 Cache Directory: %s", stats["cache_directory"])
            logger.info("Total Entries: %d", stats["total_entries"])
            logger.info("TTL Hours: %d", stats["ttl_hours"])

            total_entries = stats["total_entries"]
            if isinstance(total_entries, int) and total_entries > 0:
                print(f"✅ Fresh Entries: {stats['fresh_entries']}")
                print(f"⏰ Expired Entries: {stats['expired_entries']}")
                corrupted = stats["corrupted_entries"]
                if isinstance(corrupted, int) and corrupted > 0:
                    print(f"❌ Corrupted Entries: {corrupted}")
            else:
                print("📭 No cache entries found")

            if "error" in stats:
                print(f"⚠️ Error getting stats: {stats['error']}")
        except Exception as e:
            print(f"❌ Failed to get cache stats: {e}")
            sys.exit(1)

    def _parse_app_name(self, app_name: str) -> tuple[str, str]:
        """Parse app name to (owner, repo).

        Args:
            app_name: App name, either 'owner/repo' or just 'appname'.

        Returns:
            Tuple[str, str]: (owner, repo).

        Raises:
            SystemExit: If app config not found.

        """
        if "/" in app_name:
            owner, repo = app_name.split("/", 1)
            return owner, repo

        # Lookup owner/repo from installed app config
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            logger.error("App %s not found", app_name)
            sys.exit(1)
        return app_config["owner"], app_config["repo"]
