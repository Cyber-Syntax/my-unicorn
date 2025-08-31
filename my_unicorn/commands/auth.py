"""Auth command handler for my-unicorn CLI.

This module handles GitHub authentication management, including token saving,
removal, and status checking with rate limit information.
"""

import sys
from argparse import Namespace
from datetime import datetime

import aiohttp

from ..auth import GitHubAuthManager
from ..logger import get_logger
from .base import BaseCommandHandler

logger = get_logger(__name__)


class AuthHandler(BaseCommandHandler):
    """Handler for auth command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the auth command."""
        if args.save_token:
            await self._save_token()
        elif args.remove_token:
            await self._remove_token()
        elif args.status:
            await self._show_status()

    async def _save_token(self) -> None:
        """Save GitHub authentication token."""
        try:
            GitHubAuthManager.save_token()
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)

    async def _remove_token(self) -> None:
        """Remove GitHub authentication token."""
        GitHubAuthManager.remove_token()

    async def _show_status(self) -> None:
        """Show authentication status and rate limit information."""
        if not self.auth_manager.is_authenticated():
            print("❌ No GitHub token configured")
            print("Use 'my-unicorn auth --save-token' to configure authentication")
            return

        print("✅ GitHub token is configured")

        # Get fresh rate limit information
        rate_limit_data = await self._fetch_fresh_rate_limit()

        # Show rate limit information
        await self._display_rate_limit_info(rate_limit_data)

    async def _fetch_fresh_rate_limit(self) -> dict | None:
        """Fetch fresh rate limit information from GitHub API."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = GitHubAuthManager.apply_auth({})
                # Make a lightweight API call to get rate limit info
                async with session.get(
                    "https://api.github.com/rate_limit", headers=headers
                ) as response:
                    response.raise_for_status()
                    self.auth_manager.update_rate_limit_info(dict(response.headers))
                    return await response.json()
        except Exception as e:
            print(f"   ⚠️  Failed to fetch fresh rate limit info: {e}")
            return None

    async def _display_rate_limit_info(self, rate_limit_data: dict | None) -> None:
        """Display rate limit information."""
        rate_limit = self.auth_manager.get_rate_limit_status()
        remaining = rate_limit.get("remaining")
        reset_time = rate_limit.get("reset_time")
        reset_in = rate_limit.get("reset_in_seconds")

        print("\n📊 GitHub API Rate Limit Status:")

        if remaining is not None:
            print(f"   🔢 Remaining requests: {remaining}")

            if reset_time:
                reset_datetime = datetime.fromtimestamp(reset_time)
                print(f"   ⏰ Resets at: {reset_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

            if reset_in is not None and reset_in > 0:
                self._display_reset_time(reset_in)

            # Rate limit warnings
            self._display_rate_limit_warnings(remaining)

            # Show additional rate limit details if available
            self._display_additional_rate_limit_details(rate_limit_data, remaining)
        else:
            print("Unable to fetch rate limit information")

    def _display_reset_time(self, reset_in: int) -> None:
        """Display formatted reset time."""
        if reset_in < 60:
            print(f"   ⏳ Resets in: {reset_in} seconds")
        elif reset_in < 3600:
            minutes = reset_in // 60
            seconds = reset_in % 60
            print(f"   ⏳ Resets in: {minutes}m {seconds}s")
        else:
            hours = reset_in // 3600
            minutes = (reset_in % 3600) // 60
            print(f"   ⏳ Resets in: {hours}h {minutes}m")

    def _display_rate_limit_warnings(self, remaining: int) -> None:
        """Display rate limit warnings if applicable."""
        if remaining < 100:
            if remaining < 10:
                print("   ⚠️  WARNING: Very low rate limit remaining!")
            else:
                print("   ⚠️  Rate limit getting low")

    def _display_additional_rate_limit_details(
        self, rate_limit_data: dict | None, remaining: int
    ) -> None:
        """Display additional rate limit details if available."""
        if rate_limit_data and "resources" in rate_limit_data:
            core_info = rate_limit_data["resources"].get("core", {})
            if core_info:
                limit = core_info.get("limit", 0)
                print(f"   📋 Rate limit: {remaining}/{limit} requests")
