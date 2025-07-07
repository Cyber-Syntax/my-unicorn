#!/usr/bin/env python3
"""GitHub authentication manager module.

This module provides functionality for handling GitHub API authentication
with proper Bearer token formatting and reuse.
"""

import logging
import os
import time
from datetime import datetime
from threading import Lock
from typing import Any

import requests

from my_unicorn.secure_token import SecureTokenManager
from my_unicorn.utils.cache_utils import ensure_directory_exists, load_json_cache, save_json_cache
from my_unicorn.utils.datetime_utils import (
    format_timestamp,
    get_next_hour_timestamp,
    parse_timestamp,
)

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
TOKEN_REFRESH_THRESHOLD_DAYS = 30  # Refresh token when it has fewer than this many days left
MAX_AUTH_RETRIES = 2  # Maximum number of retries for failed auth
RATE_LIMIT_CACHE_TTL = 60 * 60  # 1 hour cache TTL for rate limits - matches GitHub's reset window
RATE_LIMIT_HARD_REFRESH = 60 * 60 * 2  # Force refresh after 2 hours (safety margin)
CACHE_DIR = os.path.expanduser("~/.cache/myunicorn")  # Cache directory
HTTP_OK = 200  # HTTP status code for successful requests
HTTP_UNAUTHORIZED = 401  # HTTP status code for unauthorized requests
HTTP_FORBIDDEN = 403  # HTTP status code for forbidden requests


class GitHubAuthManager:
    """Manages GitHub API authentication.

    This class provides methods to generate properly formatted authentication
    headers for GitHub API requests using securely stored tokens.

    All methods are static to allow easy usage across different modules.
    """

    _cached_headers: dict[str, str] | None = None
    _last_token: str | None = None
    _last_token_check: float = 0
    _token_check_interval: int = 300  # Check token validity every 5 minutes
    _cached_headers_expiration: float = 0  # Timestamp when cached headers expire

    _rate_limit_cache: dict[str, Any] = {}
    _rate_limit_cache_time: float = 0
    _request_count_since_cache: int = 0  # Counter for API requests since last cache refresh

    @classmethod
    def get_auth_headers(cls, force_refresh: bool = False) -> dict | None:
        """Get authentication headers for GitHub API requests.

        Returns properly formatted headers with Bearer authentication if a token
        is available, or basic headers if no token is found.

        Args:
            force_refresh: Force refresh of the token headers

        Returns:
            dict: Headers dictionary for API requests

        """
        # Prepare base headers that are always needed
        base_headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "my-unicorn-app/1.0",  # Best practice: always include a user agent
        }

        # Check if we need to validate token
        current_time = time.time()
        should_check = (
            force_refresh or current_time - cls._last_token_check > cls._token_check_interval
        )

        # If we should check token validity
        if should_check:
            cls._last_token_check = current_time

            # Check if token needs rotation
            if cls._should_rotate_token():
                logger.info("Token approaching expiration, rotating token")
                cls.clear_cached_headers()
                # Note: We don't actually get a new token here,
                # just clear cache so it will be prompted on next use

        # Get the current token from secure storage with validation
        token = SecureTokenManager.get_token(validate_expiration=True)

        # If no token, return base headers only
        if not token:
            logger.debug("No GitHub token found, using unauthenticated requests")
            return base_headers

        # Check if we can reuse the cached headers
        if (
            cls._cached_headers
            and token == cls._last_token
            and current_time < cls._cached_headers_expiration
        ):
            return cls._cached_headers

        # Create new headers with the token
        auth_headers = base_headers.copy()
        auth_headers["Authorization"] = f"Bearer {token}"

        # Cache the result for future calls
        cls._cached_headers = auth_headers
        cls._last_token = token

        # Update the cache expiration based on the token's remaining lifetime
        is_expired, expiration_str = SecureTokenManager.get_token_expiration_info()
        if expiration_str:
            try:
                # Use our datetime utility to parse the expiration string
                expiration_dt = parse_timestamp(expiration_str)
                if expiration_dt:
                    remaining = (expiration_dt - datetime.now()).total_seconds()
                    cache_validity = (
                        min(cls._token_check_interval, remaining / 2)
                        if remaining > 0
                        else cls._token_check_interval
                    )
                    cls._cached_headers_expiration = time.time() + cache_validity
            except Exception as e:
                logger.warning("Error parsing token expiration info: %s", e)
                cls._cached_headers_expiration = time.time() + cls._token_check_interval
        else:
            cls._cached_headers_expiration = time.time() + cls._token_check_interval

        logger.debug("Created GitHub API authentication headers with token")
        return auth_headers

    @classmethod
    def clear_cached_headers(cls) -> None:
        """Clear cached authentication headers.

        Call this method when the token changes to force regeneration of headers.
        """
        cls._cached_headers = None
        cls._last_token = None
        cls._last_token_check = 0
        logger.debug("Cleared cached GitHub API authentication headers")

    @classmethod
    def clear_rate_limit_cache(cls) -> None:
        """Clear the cached rate limit information.

        This should be called when the authentication status changes,
        especially when a token is removed to ensure the rate limits
        properly reflect the unauthenticated state (60 requests/hour).
        """
        cls._rate_limit_cache = {}
        cls._rate_limit_cache_time = 0
        cls._request_count_since_cache = 0

        # Calculate next hour boundary for unauthenticated limits
        next_hour_timestamp = get_next_hour_timestamp()
        next_hour = datetime.fromtimestamp(next_hour_timestamp)

        # set default unauthenticated rate limits
        cache_data = {
            "remaining": 50,  # Start a bit below max to be conservative
            "limit": 60,  # Unauthenticated limit is 60 per hour
            "reset_formatted": next_hour.strftime("%Y-%m-%d %H:%M:%S"),
            "is_authenticated": False,
            "request_count": 0,
            "full_hour_reset": next_hour_timestamp,
            "full_hour_reset_formatted": next_hour.strftime("%Y-%m-%d %H:%M:%S"),
            "resources": {
                "core": {
                    "limit": 60,
                    "remaining": 50,
                    "reset": next_hour_timestamp,
                }
            },
        }

        # Save to cache file
        cls._save_rate_limit_cache(cache_data)
        logger.info("Rate limit cache cleared and reset to unauthenticated limits (60/hour)")

    @staticmethod
    def has_valid_token() -> bool:
        """Check if a valid GitHub token is available.

        Returns:
            bool: True if a token exists and is not expired, False otherwise

        """
        # Get token and check that it's not expired
        token = SecureTokenManager.get_token(validate_expiration=True)
        return bool(token)

    @classmethod
    def _should_rotate_token(cls) -> bool:
        """Check if token should be rotated based on expiration.

        Returns:
            bool: True if token should be rotated, False otherwise

        """
        # Get token expiration info
        is_expired, expiration_str = SecureTokenManager.get_token_expiration_info()

        if is_expired:
            return True

        if not expiration_str:
            # If we can't determine expiration, don't rotate
            return False

        # Check if token is approaching expiration
        try:
            # Use datetime utility to parse expiration
            expiration_date = parse_timestamp(expiration_str)
            if not expiration_date:
                return False

            current_date = datetime.now()

            # Calculate days until expiration
            days_until_expiration = (expiration_date - current_date).days

            # If token expires in less than threshold days, rotate it
            return days_until_expiration <= TOKEN_REFRESH_THRESHOLD_DAYS
        except Exception as e:
            logger.warning("Error checking token rotation: %s", e)
            return False

    @classmethod
    def _get_cache_file_path(cls) -> str:
        """Get the path to the rate limit cache file.

        Returns:
            str: Path to the cache file

        """
        return os.path.join(ensure_directory_exists(CACHE_DIR), "rate_limit_cache.json")

    @classmethod
    def _load_rate_limit_cache(cls) -> dict[str, Any]:
        """Load rate limit information from cache.

        Returns:
            dict: Rate limit cache or empty dict if no cache

        """
        cache_data = load_json_cache(
            cls._get_cache_file_path(),
            ttl_seconds=RATE_LIMIT_CACHE_TTL,
            hard_refresh_seconds=RATE_LIMIT_HARD_REFRESH,  # type: ignore[arg-type]
        )
        # The cache utility returns a dict despite wrong type annotation
        return cache_data  # type: ignore[return-value]

    @classmethod
    def _save_rate_limit_cache(cls, data: dict[str, Any]) -> bool:
        """Save rate limit information to cache.

        Args:
            data: Rate limit data to cache

        Returns:
            bool: True if saved successfully, False otherwise

        """
        # Add request count to cache
        data["request_count"] = cls._request_count_since_cache
        data["cache_ttl"] = RATE_LIMIT_CACHE_TTL

        # The cache utility expects a dict despite wrong type annotation
        return save_json_cache(cls._get_cache_file_path(), data)  # type: ignore[arg-type]

    @classmethod
    def _update_cached_rate_limit(cls, decrement: int = 1) -> None:
        """Update the cached rate limit by decrementing the remaining count.

        GitHub API rate limits reset on an hourly basis (both for authenticated and
        unauthenticated requests). The limit counts will refresh at the top of each hour.

        Args:
            decrement: Number to decrement from remaining count (default: 1)

        """
        # Only update if we have cache
        if cls._rate_limit_cache:
            # Increment request counter
            cls._request_count_since_cache += decrement

            # Update the remaining count in the cache
            current_remaining = cls._rate_limit_cache.get("remaining", 0)
            new_remaining = max(0, current_remaining - decrement)
            cls._rate_limit_cache["remaining"] = new_remaining

            # Update the file cache periodically
            if cls._request_count_since_cache % 5 == 0:  # Update file every 5 requests
                cls._save_rate_limit_cache(cls._rate_limit_cache)

            logger.debug("Updated cached rate limit: %s (-%s) remaining", new_remaining, decrement)

    @classmethod
    def _extract_rate_limit_from_headers(cls, headers: dict[str, Any]) -> None:
        """Extract and cache rate limit information from response headers.

        Args:
            headers: Response headers from GitHub API request

        """
        try:
            # Check if rate limit headers exist
            if all(h in headers for h in ["X-RateLimit-Limit", "X-RateLimit-Remaining"]):
                # Extract rate limit info
                limit = int(headers["X-RateLimit-Limit"])
                remaining = int(headers["X-RateLimit-Remaining"])
                reset = int(headers["X-RateLimit-Reset"])

                # Calculate next reset time
                reset_datetime = datetime.fromtimestamp(reset)
                reset_formatted = reset_datetime.strftime("%Y-%m-%d %H:%M:%S")

                # Update cache
                cache_data = {
                    "remaining": remaining,
                    "limit": limit,
                    "reset": reset,
                    "reset_formatted": reset_formatted,
                    "is_authenticated": bool(cls._last_token),
                    "request_count": cls._request_count_since_cache,
                    "full_hour_reset": reset,
                    "full_hour_reset_formatted": reset_formatted,
                }

                # Update the cache
                cls._rate_limit_cache = cache_data
                cls._rate_limit_cache_time = time.time()

            logger.debug("Updated rate limits from headers: %s/%s", remaining, limit)
        except Exception as e:
            logger.debug("Failed to extract rate limits from headers: %s", e)

    @classmethod
    def _core_rate_limit_data(
        cls,
        use_cache: bool = True,
        custom_headers: dict[str, str] | None = None,
        return_dict: bool = False,
    ) -> tuple[int, int, str, bool] | dict[str, Any]:
        """Core implementation for rate limit data retrieval.

        This method handles both cached and live rate limit information.

        Args:
            use_cache: Whether to use cached data when available
            custom_headers: Optional custom headers for API request
            return_dict: If True, returns complete data dictionary

        Returns:
            tuple or tuple: Rate limit information

        """
        # Check memory cache if using cache
        current_time = time.time()
        if use_cache:
            cache_age = current_time - cls._rate_limit_cache_time

            # Force refresh if cache is too old
            if (cache_age > RATE_LIMIT_HARD_REFRESH) and cls._rate_limit_cache:
                logger.debug("Cache too old, forcing refresh of rate limit information")
                cls._rate_limit_cache = {}
            # Use memory cache if it's still valid
            elif (cache_age < RATE_LIMIT_CACHE_TTL) and cls._rate_limit_cache:
                logger.debug("Using cached rate limit information")
                # Include request count in debug info
                logger.debug("API requests since cache refresh: %s", cls._request_count_since_cache)

                # Return the appropriate format
                if return_dict and "resources" in cls._rate_limit_cache:
                    return cls._rate_limit_cache
                else:
                    return (
                        cls._rate_limit_cache.get("remaining", 0),
                        cls._rate_limit_cache.get("limit", 0),
                        cls._rate_limit_cache.get("reset_formatted", ""),
                        cls._rate_limit_cache.get("is_authenticated", False),
                    )

        # Try to load from file cache if memory cache is invalid and we're using cache
        if not cls._rate_limit_cache and use_cache:
            file_cache = cls._load_rate_limit_cache()
            if file_cache:
                logger.debug("Using file cached rate limit information")
                cls._rate_limit_cache = file_cache
                cls._rate_limit_cache_time = current_time

                # Return the appropriate format
                if return_dict and "resources" in file_cache:
                    return file_cache
                else:
                    return (
                        file_cache.get("remaining", 0),
                        file_cache.get("limit", 0),
                        file_cache.get("reset_formatted", ""),
                        file_cache.get("is_authenticated", False),
                    )

        # No valid cache or cache disabled, make API call
        token = SecureTokenManager.get_token(validate_expiration=True)
        is_authenticated = bool(token)

        # Prepare headers - use custom headers if provided
        headers = custom_headers if custom_headers else cls.get_auth_headers()

        try:
            # Make rate limit API request
            response = requests.get(
                "https://api.github.com/rate_limit",
                headers=headers,
                timeout=10 if not use_cache else 5,  # Longer timeout for explicit checks
            )

            if response.status_code == 200:
                data = response.json()
                rate = data.get("rate", {})
                remaining = rate.get("remaining", 0)
                limit = rate.get("limit", 0)
                reset_time = rate.get("reset", 0)

                # Format reset time
                reset_datetime = datetime.fromtimestamp(reset_time)
                reset_formatted = reset_datetime.strftime("%Y-%m-%d %H:%M:%S")

                # Add a full hour timestamp for the next reset
                next_full_hour_reset = get_next_hour_timestamp()
                full_hour_reset_formatted = datetime.fromtimestamp(next_full_hour_reset).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                # Create the result dictionary
                cache_data = {
                    "remaining": remaining,
                    "limit": limit,
                    "reset": reset_time,
                    "reset_formatted": reset_formatted,
                    "is_authenticated": is_authenticated,
                    "request_count": 0,  # Reset counter when we get fresh data
                    "resources": data.get("resources", {}),  # Store complete resources data
                    "full_hour_reset": next_full_hour_reset,
                    "full_hour_reset_formatted": full_hour_reset_formatted,
                }

                # Cache the result if caching is enabled
                if use_cache:
                    cls._rate_limit_cache = cache_data
                    cls._rate_limit_cache_time = current_time
                    cls._request_count_since_cache = 0  # Reset counter
                    cls._save_rate_limit_cache(cache_data)

                # Return the appropriate format
                if return_dict:
                    return cache_data
                else:
                    return remaining, limit, reset_formatted, is_authenticated

            # Handle error response
            logger.debug("Rate limit check failed, status code: %s", response.status_code)
            if response.status_code == 401:
                # Authentication failed - token may be invalid
                logger.warning("Rate limit check failed due to authentication error")
                # If token was invalid but exists, clear it from cache
                if token and cls._last_token:
                    cls.clear_cached_headers()

            # Create default values based on authentication status
            if is_authenticated:
                defaults = (4000, 5000, "", True)  # Default authenticated rate limit
            else:
                defaults = (50, 60, "", False)  # Default for unauthenticated users

            # Calculate next hour boundary for reset
            next_hour_timestamp = get_next_hour_timestamp()
            next_hour_formatted = datetime.fromtimestamp(next_hour_timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            # Create cache data dictionary
            cache_data = {
                "remaining": defaults[0],
                "limit": defaults[1],
                "reset_formatted": defaults[2],
                "is_authenticated": defaults[3],
                "request_count": 0,
                "full_hour_reset": next_hour_timestamp,
                "full_hour_reset_formatted": next_hour_formatted,
                "resources": {
                    "core": {
                        "limit": defaults[1],
                        "remaining": defaults[0],
                        "reset": next_hour_timestamp,  # Use hourly reset
                    }
                },
            }

            # Cache the result if caching is enabled
            if use_cache:
                cls._rate_limit_cache = cache_data
                cls._rate_limit_cache_time = current_time
                cls._request_count_since_cache = 0  # Reset counter
                cls._save_rate_limit_cache(cache_data)

            # Return the appropriate format
            if return_dict:
                return cache_data
            else:
                return defaults

        except Exception as e:
            logger.debug("Failed to check rate limits: %s", e)

            # Create default values based on authentication status
            if is_authenticated:
                defaults = (4500, 5000, "", True)  # Default authenticated limit
            else:
                defaults = (50, 60, "", False)  # Default unauthenticated limit

            # Calculate next hour boundary for reset
            next_hour_timestamp = get_next_hour_timestamp()
            next_hour_formatted = datetime.fromtimestamp(next_hour_timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            # Create cache data dictionary
            cache_data = {
                "remaining": defaults[0],
                "limit": defaults[1],
                "reset_formatted": defaults[2],
                "is_authenticated": defaults[3],
                "request_count": 0,
                "full_hour_reset": next_hour_timestamp,
                "full_hour_reset_formatted": next_hour_formatted,
                "resources": {
                    "core": {
                        "limit": defaults[1],
                        "remaining": defaults[0],
                        "reset": next_hour_timestamp,  # Use hourly reset
                    }
                },
            }

            # Cache the result if caching is enabled
            if use_cache:
                cls._rate_limit_cache = cache_data
                cls._rate_limit_cache_time = current_time
                cls._request_count_since_cache = 0  # Reset counter

            # Return the appropriate format
            if return_dict:
                return cache_data
            else:
                return defaults

    @classmethod
    def get_rate_limit_info(
        cls, custom_headers: dict[str, str] | None = None, return_dict: bool = False
    ) -> tuple[int, int, str, bool] | dict[str, Any]:
        """Get the current GitHub API rate limit information.

        Uses a local cache to avoid frequent API calls.

        Args:
            custom_headers: Optional custom headers for rate limit check
            return_dict: If True, returns the complete rate limit information as a dictionary

        Returns:
            tuple or dict: By default returns (remaining, limit, reset time, is_authenticated)
                          If return_dict=True, returns the complete rate limit information

        """
        return cls._core_rate_limit_data(
            use_cache=True, custom_headers=custom_headers, return_dict=return_dict
        )

    @classmethod
    def get_estimated_rate_limit_info(cls) -> tuple[int, int, str, bool] | tuple[str, Any]:
        """Get estimated GitHub API rate limit information based only on cached data.

        This method is optimized for startup performance and never makes API calls.
        Instead, it calculates an estimate based on the time elapsed since the last
        cache update and GitHub's hourly reset cycle.

        Returns:
            tuple: (estimated_remaining, limit, reset_time, is_authenticated)

        """
        logger.debug("Getting estimated rate limit information from cache only")

        # First try the in-memory cache
        current_time = time.time()
        if cls._rate_limit_cache:
            logger.debug("Using existing memory cache for rate limit estimation")
            cached_data = cls._rate_limit_cache
            cache_time = cls._rate_limit_cache_time
        else:
            # Try to load from file cache
            cached_data = cls._load_rate_limit_cache()
            if cached_data:
                logger.debug("Loaded rate limit data from file cache for estimation")
                cls._rate_limit_cache = cached_data
                cls._rate_limit_cache_time = current_time
                cache_time = current_time
            else:
                # No cache exists, provide default values based on authentication status
                token = SecureTokenManager.get_token(validate_expiration=True)
                is_authenticated = bool(token)

                # Calculate next hour boundary for reset
                next_hour_timestamp = get_next_hour_timestamp()
                next_hour_formatted = datetime.fromtimestamp(next_hour_timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                # set defaults based on authentication status
                if is_authenticated:
                    logger.debug("No cache found, using default authenticated values")
                    return (
                        5000,
                        5000,
                        next_hour_formatted,
                        True,
                    )  # Assume full limit if no cache exists
                else:
                    logger.debug("No cache found, using default unauthenticated values")
                    return 60, 60, next_hour_formatted, False  # Full unauthenticated limit

        # Extract key values from cache
        cached_remaining = cached_data.get("remaining", 0)
        cached_limit = cached_data.get("limit", 0)
        is_authenticated = cached_data.get("is_authenticated", False)
        request_count = cached_data.get("request_count", 0) + cls._request_count_since_cache

        # Get reset time from cache
        reset_time = None
        if "reset" in cached_data:
            reset_time = cached_data.get("reset", 0)

        reset_formatted = cached_data.get("reset_formatted", "")

        # Determine if we're past the reset time
        reset_passed = False

        if reset_time:
            # Check if current time is past or exactly at the reset time from GitHub API
            if current_time >= reset_time:
                reset_passed = True
                logger.debug(
                    "Rate limit reset detected: current=%s, reset=%s",
                    datetime.fromtimestamp(current_time).strftime("%H:%M:%S"),
                    datetime.fromtimestamp(reset_time).strftime("%H:%M:%S"),
                )
        else:
            # If no reset time available, check if we've crossed an hour boundary
            # GitHub resets at the top of each hour
            cache_datetime = datetime.fromtimestamp(cache_time)
            current_datetime = datetime.fromtimestamp(current_time)

            if (
                current_datetime.hour != cache_datetime.hour
                or current_datetime.day != cache_datetime.day
                or current_datetime.month != cache_datetime.month
                or current_datetime.year != cache_datetime.year
            ):
                reset_passed = True
                logger.debug(
                    "Hour boundary crossed since last cache update, assuming rate limit reset"
                )

        # Calculate the estimated remaining based on reset status
        if reset_passed:
            # If we're past the reset, rate limits would have been reset to full
            if is_authenticated:
                estimated_remaining = cached_limit  # Default to full limit (5000 for authenticated)
                logger.debug(
                    "Reset passed: setting estimated remaining to full limit (%s)",
                    cached_limit,
                )
            else:
                estimated_remaining = 60  # Default GitHub unauthenticated limit
                logger.debug(
                    "Reset passed: setting estimated remaining to unauthenticated limit (60)"
                )

            # Calculate next hour boundary for new reset time
            next_reset = get_next_hour_timestamp()
            reset_formatted = datetime.fromtimestamp(next_reset).strftime("%Y-%m-%d %H:%M:%S")
        else:
            # If reset hasn't occurred, adjust remaining based on tracked request count
            estimated_remaining = max(0, cached_remaining - request_count)
            logger.debug(
                "No reset detected: estimated remaining = %s - %s = %s",
                cached_remaining,
                request_count,
                estimated_remaining,
            )

        logger.debug(
            "Final estimated rate limit: %s/%s, reset at %s",
            estimated_remaining,
            cached_limit,
            reset_formatted,
        )
        return estimated_remaining, cached_limit, reset_formatted, is_authenticated

    @classmethod
    def make_authenticated_request(
        cls,
        method: str,
        url: str,
        retry_auth: bool = True,
        **kwargs,
    ) -> requests.Response:
        """Make an authenticated request to GitHub API with session reuse.

        Args:
            method: HTTP method (GET, POST, etc)
            url: URL to request
            retry_auth: Whether to retry on auth failures (with token refresh)

            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object from requests

        """
        # Get token for session key
        token = cls._last_token or SecureTokenManager.get_token(validate_expiration=False)
        # Create a string key for the session pool
        token_key = str(hash(token)) if token else "unauthenticated"

        # Get session from pool
        session = SessionPool.get_session(token_key)

        # Update headers if needed
        headers_copy = None
        if "headers" in kwargs:
            headers_copy = kwargs.pop("headers")  # Extract and remove from kwargs
            for k, v in headers_copy.items():
                session.headers[k] = v

        # Track retries
        retries = 0
        max_retries = MAX_AUTH_RETRIES if retry_auth else 0

        while True:
            try:
                # Make the request with session
                response = session.request(method, url, **kwargs)

                # Extract rate limit info from headers instead of separate API calls
                if response.status_code == 200 and url.startswith("https://api.github.com"):
                    cls._extract_rate_limit_from_headers(dict(response.headers))

                # Handle auth failures
                if response.status_code in (401, 403) and retries < max_retries:
                    # Clear session and headers to force refresh
                    SessionPool.clear_session(token_key)
                    cls.clear_cached_headers()

                    # Get new token and session
                    token = SecureTokenManager.get_token(validate_expiration=True)
                    # Create a string key for the session pool
                    token_key = str(hash(token)) if token else "unauthenticated"
                    session = SessionPool.get_session(token_key)

                    # Reapply the custom headers if they were provided
                    if headers_copy:
                        for k, v in headers_copy.items():
                            session.headers[k] = v

                    retries += 1
                    logger.warning("Authentication failed, retrying (%s/%s)", retries, max_retries)
                    continue

                return response

            except requests.RequestException as e:
                if retries < max_retries:
                    retries += 1
                    logger.warning("Request failed, retrying (%s/%s): %s", retries, max_retries, e)
                    continue
                raise

    @classmethod
    def get_token_info(cls) -> dict[str, Any]:
        """Get information about the current token.

        Retrieves metadata about the stored GitHub token including validity,
        expiration, scopes, and usage information.

        Returns:
            dict[str, Any]: Token information including:
                - token_exists: bool
                - token_valid: bool
                - is_expired: bool
                - expiration_date: str | None
                - days_until_rotation: int | None
                - created_at: str | None
                - last_used_at: str | None

        """
        logger.debug("Getting token information and status")
        token_metadata = SecureTokenManager.get_token_metadata()
        is_expired, expiration_date = SecureTokenManager.get_token_expiration_info()

        # Calculate when the token will be rotated
        days_until_rotation = None
        if expiration_date and not is_expired:
            try:
                # Use datetime utility to parse the expiration date
                expiration = parse_timestamp(expiration_date)
                if expiration:
                    current_date = datetime.now()
                    days_until_expiration = (expiration - current_date).days

                    if days_until_expiration <= TOKEN_REFRESH_THRESHOLD_DAYS:
                        days_until_rotation = 0  # Will be rotated on next use
                    else:
                        days_until_rotation = days_until_expiration - TOKEN_REFRESH_THRESHOLD_DAYS
            except Exception as e:
                logger.warning("Error calculating token rotation time: %s", e)

        # Use our own has_valid_token method
        result = {
            "token_exists": SecureTokenManager.token_exists(),
            "token_valid": cls.has_valid_token(),
            "is_expired": is_expired,
            "expiration_date": expiration_date,
            "days_until_rotation": days_until_rotation,
            "created_at": None,
            "last_used_at": None,
        }

        # Add metadata if available
        if token_metadata and isinstance(token_metadata, dict):
            if "created_at" in token_metadata:
                # Use our datetime utility to format the creation date
                created_at_str = format_timestamp(token_metadata["created_at"])  # type: ignore[arg-type]
                if created_at_str:
                    result["created_at"] = created_at_str

            if "last_used_at" in token_metadata:
                # Use our datetime utility to format the last used date
                last_used_str = format_timestamp(token_metadata["last_used_at"])  # type: ignore[arg-type]
                if last_used_str:
                    result["last_used_at"] = last_used_str

        logger.debug(
            "Token info result: valid=%s, expired=%s",
            result["token_valid"],
            result["is_expired"],
        )
        return result

    @classmethod
    def get_live_rate_limit_info(
        cls, custom_headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Get current GitHub API rate limit information directly from the API.

        Makes a real-time API call to GitHub to get rate limit status,
        bypassing any cached information.

        Args:
            custom_headers: Authentication headers to use, None to use default token

        Returns:
            tuple[str, Any]: Rate limit info containing:
                - remaining: Current remaining requests
                - limit: Total request limit
                - reset_formatted: Human readable reset time
                - is_authenticated: Whether request was authenticated

        """
        logger.info("Checking live rate limit information from GitHub API")

        # Log cache status before the check
        cache_age = time.time() - cls._rate_limit_cache_time
        logger.debug(
            "Cache status before live check: age=%ss, requests since refresh=%s",
            int(cache_age),
            cls._request_count_since_cache,
        )
        if cls._rate_limit_cache:
            logger.debug(
                f"Current cached remaining: {cls._rate_limit_cache.get('remaining', 'N/A')}/{cls._rate_limit_cache.get('limit', 'N/A')}"
            )

        # Use our core implementation with cache disabled
        result = cls._core_rate_limit_data(
            use_cache=False, custom_headers=custom_headers, return_dict=True
        )

        # Ensure result is a dict (should be since we passed return_dict=True)
        if isinstance(result, tuple):
            # Convert tuple to dict format for compatibility
            result = {
                "remaining": result[0],
                "limit": result[1],
                "reset_formatted": result[2],
                "is_authenticated": result[3],
                "error": "Failed to get dict format",
            }

        # Log the live check results if it was successful
        if "error" not in result:
            logger.info(
                "Live rate limit check results: %s/%s (reset at %s)",
                result.get("remaining", "N/A"),
                result.get("limit", "N/A"),
                result.get("reset_formatted", "N/A"),
            )

            # Also update the cache with the fresh data
            logger.debug("Updating rate limit cache with fresh data from API")
            cls._rate_limit_cache = result.copy()
            cls._rate_limit_cache["request_count"] = 0  # Reset counter
            cls._rate_limit_cache_time = time.time()
            cls._request_count_since_cache = 0
            cls._save_rate_limit_cache(cls._rate_limit_cache)

            # Log cache status after update
            logger.debug(
                "Cache updated with fresh data. New timestamp: %s",
                datetime.fromtimestamp(cls._rate_limit_cache_time).strftime("%Y-%m-%d %H:%M:%S"),
            )

        return result

    @classmethod
    def validate_token(
        cls, custom_headers: dict[str, str] | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """Validate a GitHub token by making a test request and analyzing the response.

        Args:
            custom_headers: Custom headers containing the token to validate

        Returns:
            tuple: (is_valid, token_info_dict)

        """
        logger.info("Validating GitHub token")

        # Prepare headers - use custom headers if provided
        headers = custom_headers if custom_headers else cls.get_auth_headers()

        # Initialize result
        token_info = {
            "is_valid": False,
            "scopes": [],
            "rate_limit": 0,
            "token_type": "Unknown",
            "is_fine_grained": False,
            "is_classic": False,
        }

        try:
            # Make a simple request to the user endpoint to validate the token
            response = requests.get("https://api.github.com/user", headers=headers, timeout=10)

            # Check if the request was successful
            if response.status_code == 200:
                logger.info("Token validation successful")
                token_info["is_valid"] = True

                # Get token type from response headers
                if "X-OAuth-Scopes" in response.headers:
                    scopes = response.headers.get("X-OAuth-Scopes", "")
                    token_info["scopes"] = [s.strip() for s in scopes.split(",")] if scopes else []

                if "X-GitHub-Enterprise-Version" in response.headers:
                    token_info["is_enterprise"] = True

                # Try to determine if it's a fine-grained token or classic token
                if "X-OAuth-Client-Id" in response.headers:
                    # Classic tokens typically have this header
                    token_info["is_classic"] = True
                    token_info["token_type"] = "Classic Token"
                else:
                    # Fine-grained tokens don't have client_id, but have limited scope
                    token_info["is_fine_grained"] = True
                    token_info["token_type"] = "Fine-Grained Token"

                # Get rate limit info
                try:
                    rate_response = requests.get(
                        "https://api.github.com/rate_limit", headers=headers, timeout=5
                    )
                    if rate_response.status_code == 200:
                        rate_data = rate_response.json()
                        if "rate" in rate_data and "limit" in rate_data["rate"]:
                            token_info["rate_limit"] = rate_data["rate"]["limit"]
                except Exception as e:
                    logger.warning("Failed to get rate limit info during token validation: %s", e)

                return True, token_info

            # Handle common error cases
            elif response.status_code == 401:
                logger.warning("Token validation failed: Unauthorized")
                token_info["error"] = "Token is invalid or expired"
                return False, token_info

            elif response.status_code == 403:
                logger.warning("Token validation failed: Forbidden")
                # Check if it's a rate limit issue
                if "rate limit exceeded" in response.text.lower():
                    token_info["error"] = (
                        "Rate limit exceeded. The token is valid but you've reached GitHub's API rate limit."
                    )
                    token_info["is_valid"] = True  # Still valid but rate-limited
                    return True, token_info
                else:
                    token_info["error"] = "Token has insufficient permissions"
                    return False, token_info

            else:
                logger.warning("Token validation failed with status code: %s", response.status_code)
                token_info["error"] = "GitHub API returned status code %s" % response.status_code
                return False, token_info

        except requests.exceptions.RequestException as e:
            logger.error("Network error during token validation: %s", e)
            token_info["error"] = "Network error: %s" % (e,)
            return False, token_info

        except Exception as e:
            logger.error("Unexpected error during token validation: %s", e)
            token_info["error"] = "Unexpected error: %s" % (e,)
            return False, token_info


class SessionPool:
    """Manages reusable HTTP sessions with authentication."""

    _sessions: dict[str, requests.Session] = {}
    _lock = Lock()
    _last_used: dict[str, float] = {}
    _max_idle_time: int = 300  # 5 minutes

    @classmethod
    def get_session(cls, token_key: str | None = None) -> requests.Session:
        """Get or create a session with the current auth token.

        Args:
            token_key: Optional unique identifier for the token

        Returns:
            requests.Session: Authenticated session

        """
        # Use token hash or "unauthenticated" as key
        key = str(token_key or "unauthenticated")

        with cls._lock:
            # Clean up idle sessions periodically
            cls._clean_idle_sessions()

            # If we have an existing session for this token
            if key in cls._sessions:
                cls._last_used[key] = time.time()
                logger.debug("Reusing existing session for token key: %s...", key[:8])
                return cls._sessions[key]

            # Create a new session with proper headers
            logger.debug("Creating new session for token key: %s...", key[:8])
            session = requests.Session()
            headers = GitHubAuthManager.get_auth_headers()
            if headers:
                session.headers.update(headers)

            # Set default timeout for all requests (use patching approach for session.request)
            original_request = session.request

            def patched_request(*args, **kwargs):
                # Set default timeout if not provided
                if "timeout" not in kwargs:
                    kwargs["timeout"] = (10, 30)  # (connect timeout, read timeout)
                return original_request(*args, **kwargs)

            session.request = patched_request

            # Store session in pool and return
            cls._sessions[key] = session
            cls._last_used[key] = time.time()
            return session

    @classmethod
    def _clean_idle_sessions(cls) -> None:
        """Clean up sessions that haven't been used recently."""
        now = time.time()
        to_remove = []

        for key, last_used in cls._last_used.items():
            if now - last_used > cls._max_idle_time:
                to_remove.append(key)

        for key in to_remove:
            if key in cls._sessions:
                try:
                    logger.debug("Closing idle session: %s...", key[:8])
                    cls._sessions[key].close()
                except Exception as e:
                    logger.debug("Error closing session: %s", e)
                del cls._sessions[key]
                del cls._last_used[key]

    @classmethod
    def clear_session(cls, token_key: str | None = None) -> None:
        """Close and remove a session when token changes.

        Properly closes and cleans up session resources for the specified token.
        If no token key is provided, clears the unauthenticated session.

        Args:
            token_key: Token identifier to clear session for, None for unauthenticated

        """
        key = str(token_key or "unauthenticated")

        with cls._lock:
            if key in cls._sessions:
                try:
                    cls._sessions[key].close()
                except Exception:
                    pass
                del cls._sessions[key]
                if key in cls._last_used:
                    del cls._last_used[key]
