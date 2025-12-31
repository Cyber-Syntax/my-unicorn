"""Auth command handler for my-unicorn CLI.

This module handles GitHub authentication management, including token saving,
removal, and status checking with rate limit information.
"""

import sys
from argparse import Namespace
from datetime import UTC, datetime

import aiohttp

from my_unicorn.auth import GitHubAuthManager
from my_unicorn.logger import get_logger, temporary_console_level

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
        except ValueError:
            logger.exception("Failed to save token")
            sys.exit(1)

    async def _remove_token(self) -> None:
        """Remove GitHub authentication token."""
        try:
            GitHubAuthManager.remove_token()
            logger.info("GitHub token removed from keyring.")
        except (ValueError, OSError):
            logger.exception("Error removing token")

    async def _show_status(self) -> None:
        """Show authentication status and rate limit information.

        Always attempt to fetch and display GitHub rate limit information even
        when no personal access token is configured. The API will return the
        public (unauthenticated) rate limits in that case.
        """
        with temporary_console_level("INFO"):
            configured = self.auth_manager.is_authenticated()
            if configured:
                logger.info("✅ GitHub token is configured")
                logger.debug(
                    "GitHub token is configured. Fetching rate limit info..."
                )
            else:
                logger.info("No GitHub token configured.")
                logger.info("❌ No GitHub token configured")
                logger.info(
                    "Use 'my-unicorn auth --save-token' to set a token"
                )
                logger.debug(
                    "No token configured. "
                    "Fetching public GitHub rate limit info."
                )

            # Get fresh rate limit information (works with or without token)
            rate_limit_data = await self._fetch_fresh_rate_limit()

            # Show rate limit information
            await self._display_rate_limit_info(rate_limit_data)

    async def _fetch_fresh_rate_limit(self) -> dict[str, object] | None:
        """Fetch fresh rate limit information from GitHub API.

        Security features:
        - Request timeout (30 seconds) to prevent hanging
        - Proper exception handling to avoid information disclosure

        Returns:
            dict | None: Rate limit data from API or None on error.

        """
        try:
            # Security: Add timeout to prevent indefinite hanging
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = self.auth_manager.apply_auth({})
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
                    result: dict[str, object] = await response.json()
                    return result
        except (aiohttp.ClientError, OSError):
            # Security: Sanitize error messages to avoid information disclosure
            logger.warning("Failed to fetch fresh rate limit info")
            logger.info("   ⚠️  Failed to connect to GitHub API")
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

        logger.info("")
        logger.info("📊 GitHub API Rate Limit Status:")

        if remaining is not None:
            logger.info("   🔢 Remaining requests: %s", remaining)

            if reset_time:
                reset_datetime = datetime.fromtimestamp(reset_time, tz=UTC)
                reset_str = reset_datetime.strftime("%Y-%m-%d %H:%M:%S UTC")
                logger.info("   ⏰ Resets at: %s", reset_str)

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
                    logger.info(
                        "   🔢 Remaining requests: %s", remaining_from_payload
                    )
                    if reset_ts and isinstance(reset_ts, (int, float)):
                        reset_datetime = datetime.fromtimestamp(
                            reset_ts, tz=UTC
                        )
                        reset_str = reset_datetime.strftime(
                            "%Y-%m-%d %H:%M:%S UTC"
                        )
                        logger.info("   ⏰ Resets at: %s", reset_str)
                    if limit is not None:
                        logger.info(
                            "   📋 Rate limit: %s/%s requests",
                            remaining_from_payload,
                            limit,
                        )
                    # Warnings based on payload value
                    if isinstance(remaining_from_payload, int):
                        self._display_rate_limit_warnings(
                            remaining_from_payload
                        )
                    return

            logger.info("Unable to fetch rate limit information")

    def _display_reset_time(self, reset_in: int) -> None:
        """Display formatted reset time."""
        if reset_in < RESET_SECONDS:
            logger.info("   ⏳ Resets in: %s seconds", reset_in)
        elif reset_in < HOUR_SECONDS:
            minutes = reset_in // RESET_SECONDS
            seconds = reset_in % RESET_SECONDS
            logger.info("   ⏳ Resets in: %sm %ss", minutes, seconds)
        else:
            hours = reset_in // HOUR_SECONDS
            minutes = (reset_in % HOUR_SECONDS) // RESET_SECONDS
            logger.info("   ⏳ Resets in: %sh %sm", hours, minutes)

    def _display_rate_limit_warnings(self, remaining: int) -> None:
        """Display rate limit warnings if applicable."""
        if remaining < WARN_THRESHOLD:
            if remaining < WARN_CRITICAL:
                logger.info("   ⚠️  WARNING: Very low rate limit remaining!")
            else:
                logger.info("   ⚠️  Rate limit getting low")

    def _display_additional_rate_limit_details(
        self, rate_limit_data: dict[str, object] | None, remaining: int
    ) -> None:
        """Display additional rate limit details if available."""
        core_info = self._extract_core_rate_limit_info(rate_limit_data)
        if core_info:
            limit = core_info.get("limit", 0)
            logger.info("   📋 Rate limit: %s/%s requests", remaining, limit)
