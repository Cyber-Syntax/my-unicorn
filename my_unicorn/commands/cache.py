"""Cache command handler for my-unicorn CLI.

This module handles cache management operations including r            logger                   stats = await cache_manager.get_cache_stats()
            
            print("📊 Cache Statistics")
            print(f"📁 Cache Directory: {stats['cache_directory']}")
            print(f"📊 Total Entries: {stats['total_entries']}")
            print(f"🕐 TTL Hours: {stats['ttl_hours']}")
            
            total_entries = stats["total_entries"]          stats = await cache_manager.get_cache_stats()
            
            print("📊 Cache Statistics")
            print(f"📁 Cache Directory: {stats['cache_directory']}")
            print(f"📊 Total Entries: {stats['total_entries']}")
            print(f"🕐 TTL Hours: {stats['ttl_hours']}")� Cache Statistics")
            
            try:
            stats = await cache_manager.get_cache_stats()
            
            print("📊 Cache Statistics")
            print(f"�📁 Cache Directory: {stats['cache_directory']}")
            print(f"📊 Total Entries: {stats['total_entries']}")
            print(f"🕐 TTL Hours: {stats['ttl_hours']}")
            
            # Also print to ensure visibility
            print(f"📁 Cache Directory: {stats['cache_directory']}")
            print(f"📊 Total Entries: {stats['total_entries']}")
            print(f"🕐 TTL Hours: {stats['ttl_hours']}")
            
            total_entries = stats["total_entries"]
            if isinstance(total_entries, int) and total_entries > 0:
                logger.info("✅ Fresh Entries: %d", stats["fresh_entries"])
                logger.info("⏰ Expired Entries: %d", stats["expired_entries"])
                print(f"✅ Fresh Entries: {stats['fresh_entries']}")
                print(f"⏰ Expired Entries: {stats['expired_entries']}")
                corrupted = stats["corrupted_entries"]
                if isinstance(corrupted, int) and corrupted > 0:
                    logger.info("❌ Corrupted Entries: %d", corrupted)
                    print(f"❌ Corrupted Entries: {corrupted}")
            else:
                logger.info("📭 No cache entries found")
                print("📭 No cache entries found")        # Get installed apps
        installed_apps = self.config_manager.list_installed_apps() data,
clearing cache entries, and displaying cache statistics.
"""

import sys
from argparse import Namespace

from ..logger import get_logger
from ..services.cache import get_cache_manager
from .base import BaseCommandHandler

logger = get_logger(__name__)


class CacheHandler(BaseCommandHandler):
    """Handler for cache command operations.

    Provides cache management functionality including:
    - Clearing cache entries
    - Displaying cache statistics
    
    Note: Cache refresh functionality has been moved to the update command
    with the --refresh-cache flag for better integration with update workflows.
    """

    async def execute(self, args: Namespace) -> None:
        """Execute the cache command based on subcommand.

        Args:
            args: Parsed command-line arguments containing cache parameters

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
            sys.exit(130)  # Standard exit code for SIGINT
        except Exception as e:
            logger.error("Cache operation failed: %s", e)
            sys.exit(1)

    async def _handle_clear(self, args: Namespace) -> None:
        """Handle cache clear operations.

        Args:
            args: Parsed command-line arguments

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
        """Handle stats command."""
        cache_manager = get_cache_manager()
        
        try:
            stats = await cache_manager.get_cache_stats()
            
            logger.info("📁 Cache Directory: %s", stats["cache_directory"])
            logger.info("� Total Entries: %d", stats["total_entries"])
            logger.info("� TTL Hours: %d", stats["ttl_hours"])
            
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
        """Parse app name into owner/repo format.

        Args:
            app_name: App name (could be 'appname' or 'owner/repo')

        Returns:
            Tuple of (owner, repo)

        """
        if "/" in app_name:
            owner, repo = app_name.split("/", 1)
            return owner, repo
        
        # Try to look up from installed apps
        app_config = self.config_manager.load_app_config(app_name)
        
        if not app_config:
            logger.error("App %s not found", app_name)
            sys.exit(1)
        
        return app_config["owner"], app_config["repo"]
