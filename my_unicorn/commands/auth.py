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

# Constants for rate limit display thresholds and time units
RESET_SECONDS = 60
HOUR_SECONDS = 3600
WARN_THRESHOLD = 100
WARN_CRITICAL = 10


class AuthHandler(BaseCommandHandler):
    """Handler for auth command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the auth command."""
        if args.save_token:
            logger.info("Saving GitHub token...")
            await self._save_token()
        elif args.remove_token:
            logger.info("Removing GitHub token...")
            await self._remove_token()
        elif args.status:
            logger.debug("Checking GitHub authentication status...")
            await self._show_status()

    async def _save_token(self) -> None:
        """Save GitHub authentication token."""
        try:
            GitHubAuthManager.save_token()
            logger.info("GitHub token saved successfully.")
        except ValueError as e:
            logger.error(f"Failed to save token: {e}")
            print(f"❌ {e}")
            sys.exit(1)

    async def _remove_token(self) -> None:
        """Remove GitHub authentication token."""
        try:
            GitHubAuthManager.remove_token()
            logger.info("GitHub token removed from keyring.")
        except Exception as e:
            logger.error(f"Error removing token: {e}")

    async def _show_status(self) -> None:
        """Show authentication status and rate limit information.

        Always attempt to fetch and display GitHub rate limit information even
        when no personal access token is configured. The API will return the
        public (unauthenticated) rate limits in that case.
        """
        configured = self.auth_manager.is_authenticated()
        if configured:
            print("✅ GitHub token is configured")
            logger.debug(
                "GitHub token is configured. Fetching rate limit info..."
            )
        else:
            logger.info("No GitHub token configured.")
            print("❌ No GitHub token configured")
            print("Use 'my-unicorn auth --save-token' to set a token")
            logger.debug(
                "No token configured. Fetching public GitHub rate limit info."
            )

        # Get fresh rate limit information (works with or without token)
        rate_limit_data = await self._fetch_fresh_rate_limit()

        # Show rate limit information
        await self._display_rate_limit_info(rate_limit_data)

    async def _fetch_fresh_rate_limit(self) -> dict[str, object] | None:
        """Fetch fresh rate limit information from GitHub API."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = GitHubAuthManager.apply_auth({})
                # Make a lightweight API call to get rate limit info
                async with session.get(
                    "https://api.github.com/rate_limit", headers=headers
                ) as response:
                    response.raise_for_status()
                    self.auth_manager.update_rate_limit_info(
                        dict(response.headers)
                    )
                    logger.debug(
                        "Fetched fresh rate limit info from GitHub API."
                    )
                    return await response.json()
        except Exception as e:
            logger.warning("Failed to fetch fresh rate limit info: %s", e)
            print(f"   ⚠️  Failed to fetch fresh rate limit info: {e}")
            return None

    def _extract_core_rate_limit_info(
        self, rate_limit_data: dict[str, object] | None
    ) -> dict[str, object] | None:
        """Extract core rate limit info from API response.

        Returns:
            Core rate limit dict or None if not found

        """
        if not isinstance(rate_limit_data, dict):
            return None
        resources = rate_limit_data.get("resources")
        if not isinstance(resources, dict):
            return None
        core_info = resources.get("core")
        if isinstance(core_info, dict):
            return core_info
        return None

    async def _display_rate_limit_info(
        self, rate_limit_data: dict[str, object] | None
    ) -> None:
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
                reset_str = reset_datetime.strftime("%Y-%m-%d %H:%M:%S")
                print(f"   ⏰ Resets at: {reset_str}")

            if reset_in is not None and reset_in > 0:
                self._display_reset_time(reset_in)

            # Rate limit warnings
            self._display_rate_limit_warnings(remaining)

            # Show additional rate limit details if available
            self._display_additional_rate_limit_details(
                rate_limit_data, remaining
            )
        else:
            # No cached/available rate limit info. Try to extract from the
            # fetched JSON payload (if available) as a fallback.
            core_info = self._extract_core_rate_limit_info(rate_limit_data)
            if core_info:
                limit = core_info.get("limit")
                remaining_from_payload = core_info.get("remaining")
                reset_ts = core_info.get("reset")

                if remaining_from_payload is not None:
                    print(
                        "   🔢 Remaining requests: "
                        + f"{remaining_from_payload}"
                    )
                    if reset_ts and isinstance(reset_ts, (int, float)):
                        reset_datetime = datetime.fromtimestamp(reset_ts)
                        reset_str = reset_datetime.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        print(f"   ⏰ Resets at: {reset_str}")
                    if limit is not None:
                        print(
                            "   📋 Rate limit: "
                            + f"{remaining_from_payload}/{limit}"
                            + " requests"
                        )
                    # Warnings based on payload value
                    if isinstance(remaining_from_payload, int):
                        self._display_rate_limit_warnings(
                            remaining_from_payload
                        )
                    return

            print("Unable to fetch rate limit information")

    def _display_reset_time(self, reset_in: int) -> None:
        """Display formatted reset time."""
        if reset_in < RESET_SECONDS:
            print(f"   ⏳ Resets in: {reset_in} seconds")
        elif reset_in < HOUR_SECONDS:
            minutes = reset_in // RESET_SECONDS
            seconds = reset_in % RESET_SECONDS
            print(f"   ⏳ Resets in: {minutes}m {seconds}s")
        else:
            hours = reset_in // HOUR_SECONDS
            minutes = (reset_in % HOUR_SECONDS) // RESET_SECONDS
            print(f"   ⏳ Resets in: {hours}h {minutes}m")

    def _display_rate_limit_warnings(self, remaining: int) -> None:
        """Display rate limit warnings if applicable."""
        if remaining < WARN_THRESHOLD:
            if remaining < WARN_CRITICAL:
                print("   ⚠️  WARNING: Very low rate limit remaining!")
            else:
                print("   ⚠️  Rate limit getting low")

    def _display_additional_rate_limit_details(
        self, rate_limit_data: dict[str, object] | None, remaining: int
    ) -> None:
        """Display additional rate limit details if available."""
        core_info = self._extract_core_rate_limit_info(rate_limit_data)
        if core_info:
            limit = core_info.get("limit", 0)
            print(f"   📋 Rate limit: {remaining}/{limit} requests")
