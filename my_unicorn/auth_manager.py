#!/usr/bin/env python3
"""GitHub authentication manager module.

This module provides functionality for handling GitHub API authentication
with proper Bearer token formatting and reuse.
"""

import json
import logging
import os
import time
from datetime import datetime
from threading import Lock
from typing import Any, NotRequired, TypedDict, cast

import requests

from my_unicorn.secure_token import SecureTokenManager
from my_unicorn.utils.cache_utils import (
    ensure_directory_exists,
)
from my_unicorn.utils.datetime_utils import (
    format_timestamp,
    get_next_hour_timestamp,
    parse_timestamp,
)

logger = logging.getLogger(__name__)


# Simplified cache structure - only core rate limit data
class RateLimitCacheData(TypedDict):
    remaining: int
    limit: int
    reset: int
    reset_formatted: str
    is_authenticated: bool
    request_count: int
    full_hour_reset: int
    full_hour_reset_formatted: str
    timestamp: NotRequired[float]


# Type aliases
RateLimitTuple = tuple[int, int, str, bool]
RateLimitReturn = RateLimitTuple | RateLimitCacheData

# Constants
RATE_LIMIT_CACHE_TTL = 60 * 60  # 1 hour
RATE_LIMIT_HARD_REFRESH = 60 * 60 * 2  # 2 hours
CACHE_DIR = os.path.expanduser("~/.cache/myunicorn")
TOKEN_REFRESH_THRESHOLD_DAYS = 30  # Refresh token when it has fewer than this many days left
MAX_AUTH_RETRIES = 2  # Maximum number of retries for failed auth


class GitHubAuthManager:
    """Manages GitHub API authentication and rate limiting."""

    _cached_headers: dict[str, str] | None = None
    _last_token: str | None = None
    _last_token_check: float = 0
    _token_check_interval: int = 300  # Check token validity every 5 minutes
    _cached_headers_expiration: float = 0  # Timestamp when cached headers expire

    _rate_limit_cache: RateLimitCacheData | None = None
    _rate_limit_cache_time: float = 0
    _request_count_since_cache: int = 0

    @classmethod
    def _core_rate_limit_data(
        cls,
        use_cache: bool = True,
        custom_headers: dict[str, str] | None = None,
        return_dict: bool = False,
    ) -> RateLimitReturn:
        """Core implementation for rate limit data retrieval."""
        current_time = time.time()
        is_authenticated = bool(SecureTokenManager.get_token(validate_expiration=True))

        # Try to get data from cache if enabled
        if use_cache:
            cached_data = cls._get_cached_rate_limit(current_time, return_dict)
            if cached_data is not None:
                return cached_data

        # Fetch live data if cache not available/disabled
        try:
            return cls._fetch_live_rate_limit(
                custom_headers, use_cache, return_dict, is_authenticated
            )
        except Exception as e:
            logger.debug("Failed to check rate limits: %s", e)
            return cls._handle_rate_limit_failure(use_cache, return_dict, is_authenticated)

    @classmethod
    def _get_cached_rate_limit(
        cls, current_time: float, return_dict: bool
    ) -> RateLimitReturn | None:
        """Retrieve rate limit data from cache if valid."""
        # Check memory cache first
        if cls._rate_limit_cache is not None:
            cache_age = current_time - cls._rate_limit_cache_time

            if cache_age > RATE_LIMIT_HARD_REFRESH:
                logger.debug("Cache too old, forcing refresh")
                cls._rate_limit_cache = None
            elif cache_age < RATE_LIMIT_CACHE_TTL:
                logger.debug("Using cached rate limit info")
                return cls._format_cache_output(cls._rate_limit_cache, return_dict)

        # Check file cache if memory cache invalid
        file_cache = cls._load_rate_limit_cache()
        if file_cache is not None:
            logger.debug("Using file cached rate limit info")
            cls._rate_limit_cache = file_cache
            cls._rate_limit_cache_time = current_time
            return cls._format_cache_output(file_cache, return_dict)

        return None

    @classmethod
    def _format_cache_output(
        cls, cache_data: RateLimitCacheData, return_dict: bool
    ) -> RateLimitReturn:
        """Format cached data for output based on return_dict flag."""
        if return_dict:
            return cache_data
        return (
            cache_data["remaining"],
            cache_data["limit"],
            cache_data["reset_formatted"],
            cache_data["is_authenticated"],
        )

    @classmethod
    def _fetch_live_rate_limit(
        cls,
        custom_headers: dict[str, str] | None,
        use_cache: bool,
        return_dict: bool,
        is_authenticated: bool,
    ) -> RateLimitReturn:
        """Fetch live rate limit data from API."""
        headers = custom_headers or cls.get_auth_headers()
        timeout = 5 if use_cache else 10

        try:
            response = requests.get(
                "https://api.github.com/rate_limit",
                headers=headers,
                timeout=timeout,
            )

            if response.status_code == 200:
                data = response.json()
                # Focus only on core rate limits
                rate = data.get("rate", {})
                return cls._process_successful_response(
                    rate, use_cache, return_dict, is_authenticated
                )

            # Handle API errors
            logger.debug("Rate limit check failed, status code: %s", response.status_code)
            if response.status_code == 401:
                logger.warning("Rate limit check failed due to authentication error")
                if SecureTokenManager.get_token() and cls._last_token:
                    cls.clear_cached_headers()
        except requests.exceptions.RequestException as e:
            logger.debug("Request failed during rate limit check: %s", e)

        # Fallback for API errors
        return cls._handle_rate_limit_failure(use_cache, return_dict, is_authenticated)

    @classmethod
    def _process_successful_response(
        cls,
        rate_data: dict[str, Any],
        use_cache: bool,
        return_dict: bool,
        is_authenticated: bool,
    ) -> RateLimitReturn:
        """Process successful API response and update cache."""
        # Extract core rate limit information
        reset_time = rate_data.get("reset", 0)
        reset_datetime = datetime.fromtimestamp(reset_time)
        next_hour = get_next_hour_timestamp()

        # Create simplified cache data
        cache_data: RateLimitCacheData = {
            "remaining": rate_data.get("remaining", 0),
            "limit": rate_data.get("limit", 0),
            "reset": reset_time,
            "reset_formatted": reset_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "is_authenticated": is_authenticated,
            "request_count": 0,
            "full_hour_reset": next_hour,
            "full_hour_reset_formatted": datetime.fromtimestamp(next_hour).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

        if use_cache:
            cls._update_rate_limit_cache(cache_data)

        if return_dict:
            return cache_data
        return (
            cache_data["remaining"],
            cache_data["limit"],
            cache_data["reset_formatted"],
            cache_data["is_authenticated"],
        )

    @classmethod
    def _update_rate_limit_cache(cls, cache_data: RateLimitCacheData) -> None:
        """Update cache with new rate limit data."""
        current_time = time.time()
        cls._rate_limit_cache = cache_data
        cls._rate_limit_cache_time = current_time
        cls._request_count_since_cache = 0
        cls._save_rate_limit_cache(cache_data)

    @classmethod
    def _handle_rate_limit_failure(
        cls, use_cache: bool, return_dict: bool, is_authenticated: bool
    ) -> RateLimitReturn:
        """Handle failure cases by generating fallback data."""
        # Default values based on authentication status
        defaults: RateLimitTuple = (
            (5000, 5000, "", True) if is_authenticated else (60, 60, "", False)
        )
        next_hour = get_next_hour_timestamp()
        next_hour_str = datetime.fromtimestamp(next_hour).strftime("%Y-%m-%d %H:%M:%S")

        # Create simplified fallback data
        fallback: RateLimitCacheData = {
            "remaining": defaults[0],
            "limit": defaults[1],
            "reset": next_hour,
            "reset_formatted": next_hour_str,
            "is_authenticated": defaults[3],
            "request_count": 0,
            "full_hour_reset": next_hour,
            "full_hour_reset_formatted": next_hour_str,
        }

        if use_cache:
            cls._update_rate_limit_cache(fallback)

        return fallback if return_dict else defaults

    @classmethod
    def _get_cache_file_path(cls) -> str:
        """Get the path to the rate limit cache file."""
        return os.path.join(ensure_directory_exists(CACHE_DIR), "rate_limit_cache.json")

    @classmethod
    def _load_rate_limit_cache(cls) -> RateLimitCacheData | None:
        """Load rate limit information from cache."""
        try:
            cache_file = cls._get_cache_file_path()
            if not os.path.exists(cache_file):
                return None

            with open(cache_file) as f:
                data = json.load(f)

            # Check if cache is still valid
            current_time = time.time()
            if "timestamp" in data:
                cache_age = current_time - data["timestamp"]
                if cache_age > RATE_LIMIT_HARD_REFRESH:
                    return None
                if cache_age > RATE_LIMIT_CACHE_TTL:
                    return None

            # Return only the fields we actually use
            return {
                "remaining": data["remaining"],
                "limit": data["limit"],
                "reset": data["reset"],
                "reset_formatted": data["reset_formatted"],
                "is_authenticated": data["is_authenticated"],
                "request_count": data["request_count"],
                "full_hour_reset": data["full_hour_reset"],
                "full_hour_reset_formatted": data["full_hour_reset_formatted"],
            }
        except Exception as e:
            logger.debug("Failed to load rate limit cache: %s", e)
            return None

    @classmethod
    def _save_rate_limit_cache(cls, data: RateLimitCacheData) -> bool:
        """Save rate limit information to cache."""
        try:
            cache_file = cls._get_cache_file_path()
            # Add timestamp for cache validation
            data_to_save = {**data, "timestamp": time.time()}

            with open(cache_file, "w") as f:
                json.dump(data_to_save, f)
            return True
        except Exception as e:
            logger.debug("Failed to save rate limit cache: %s", e)
            return False

    @classmethod
    def _update_cached_rate_limit(cls, decrement: int = 1) -> None:
        """Update the cached rate limit by decrementing the remaining count."""
        if cls._rate_limit_cache is None:
            return

        # Update the remaining count
        new_remaining = max(0, cls._rate_limit_cache["remaining"] - decrement)
        cls._rate_limit_cache["remaining"] = new_remaining
        cls._request_count_since_cache += decrement

        # Update file cache periodically
        if cls._request_count_since_cache % 5 == 0:
            cls._save_rate_limit_cache(cls._rate_limit_cache)

        logger.debug("Updated cached rate limit: %s (-%s) remaining", new_remaining, decrement)

    @classmethod
    def _extract_rate_limit_from_headers(cls, headers: dict[str, Any]) -> None:
        """Extract and cache rate limit information from response headers."""
        try:
            # Only extract core rate limits
            if all(
                h in headers
                for h in ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
            ):
                # Extract rate limit info
                limit = int(headers["X-RateLimit-Limit"])
                remaining = int(headers["X-RateLimit-Remaining"])
                reset = int(headers["X-RateLimit-Reset"])

                # Format reset time
                reset_datetime = datetime.fromtimestamp(reset)
                reset_formatted = reset_datetime.strftime("%Y-%m-%d %H:%M:%S")

                # Create cache data
                cache_data: RateLimitCacheData = {
                    "remaining": remaining,
                    "limit": limit,
                    "reset": reset,
                    "reset_formatted": reset_formatted,
                    "is_authenticated": bool(cls._last_token),
                    "request_count": cls._request_count_since_cache,
                    "full_hour_reset": reset,
                    "full_hour_reset_formatted": reset_formatted,
                }

                # Update cache
                cls._rate_limit_cache = cache_data
                cls._rate_limit_cache_time = time.time()

                logger.debug("Updated rate limits from headers: %s/%s", remaining, limit)
        except Exception as e:
            logger.debug("Failed to extract rate limits from headers: %s", e)

    @classmethod
    def get_auth_headers(cls, force_refresh: bool = False) -> dict[str, str]:
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

        This should be called when authentication status changes, especially
        when a token is removed to ensure rate limits reflect unauthenticated state.
        """
        # Clear in-memory cache
        cls._rate_limit_cache = None
        cls._rate_limit_cache_time = 0
        cls._request_count_since_cache = 0

        # Calculate next hour boundary
        next_hour = get_next_hour_timestamp()
        next_hour_str = datetime.fromtimestamp(next_hour).strftime("%Y-%m-%d %H:%M:%S")

        # Create properly typed cache data
        cache_data: RateLimitCacheData = {
            "remaining": 50,  # Start conservative
            "limit": 60,  # Unauthenticated limit
            "reset": next_hour,
            "reset_formatted": next_hour_str,
            "is_authenticated": False,
            "request_count": 0,
            "full_hour_reset": next_hour,
            "full_hour_reset_formatted": next_hour_str,
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
    def get_rate_limit_info(
        cls, custom_headers: dict[str, str] | None = None, return_dict: bool = False
    ) -> tuple[int, int, str, bool] | RateLimitCacheData:
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
    def get_estimated_rate_limit_info(cls) -> tuple[int, int, str, bool]:
        """Get estimated GitHub API rate limit information using only cached data.

        Optimized for startup performance - never makes API calls. Estimates are based on:
        - Time elapsed since last cache update
        - GitHub's hourly reset cycle
        - Tracked request count since last cache refresh

        Returns:
            tuple: (estimated_remaining, limit, reset_time, is_authenticated)

        """
        logger.debug("Getting estimated rate limit from cache")
        current_time = time.time()

        # Try to get cached data (memory or file)
        cached_data = cls._rate_limit_cache or cls._load_rate_limit_cache()
        if cached_data:
            if not cls._rate_limit_cache:  # If loaded from file
                cls._rate_limit_cache = cached_data
                cls._rate_limit_cache_time = current_time

        # Handle no cache scenario
        if not cached_data:
            is_authenticated = bool(SecureTokenManager.get_token(validate_expiration=True))
            next_hour = get_next_hour_timestamp()
            reset_formatted = datetime.fromtimestamp(next_hour).strftime("%Y-%m-%d %H:%M:%S")
            default_limit = 5000 if is_authenticated else 60
            logger.debug(
                f"No cache found, using default {'authenticated' if is_authenticated else 'unauthenticated'} values"
            )
            return (default_limit, default_limit, reset_formatted, is_authenticated)

        # Extract values from cache
        cache_time = cls._rate_limit_cache_time
        cached_remaining = cached_data["remaining"]
        cached_limit = cached_data["limit"]
        is_authenticated = cached_data["is_authenticated"]
        request_count = cached_data.get("request_count", 0) + cls._request_count_since_cache

        # Use the most relevant reset time
        reset_time = cached_data.get("reset", cached_data["full_hour_reset"])
        reset_formatted = cached_data.get(
            "reset_formatted", cached_data["full_hour_reset_formatted"]
        )

        # Determine if reset has occurred
        reset_passed = current_time >= reset_time
        if reset_passed:
            logger.debug("Rate limit reset detected")
            estimated_remaining = cached_limit  # Reset to full limit
            # Update reset time to next full hour
            next_reset = get_next_hour_timestamp()
            reset_formatted = datetime.fromtimestamp(next_reset).strftime("%Y-%m-%d %H:%M:%S")
        else:
            estimated_remaining = max(0, cached_remaining - request_count)
            logger.debug(
                f"Estimated remaining: {cached_remaining} - {request_count} = {estimated_remaining}"
            )

        logger.debug(
            f"Final estimate: {estimated_remaining}/{cached_limit}, reset at {reset_formatted}"
        )
        return (estimated_remaining, cached_limit, reset_formatted, is_authenticated)

    @classmethod
    def make_authenticated_request(
        cls,
        method: str,
        url: str,
        retry_auth: bool = True,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an authenticated request to the GitHub API with session reuse.

        Args:
            method (str): HTTP method ('GET', 'POST', etc.).
            url (str): The full URL to call.
            retry_auth (bool): If True, retry once on 401/403.
            headers (dict[str, str] | None): Extra headers to merge into session.headers.
            **kwargs: Passed directly to requests (e.g. params, json, timeout).

        Returns:
            requests.Response: The raw response object.

        """
        # Step 1: Fetch the last token or get a fresh one (but don't force expiration check).
        token = cls._last_token or SecureTokenManager.get_token(validate_expiration=False)
        token_key = str(hash(token)) if token else "unauthenticated"

        # Step 2: Acquire (or create) a Session for this token.
        session = SessionPool.get_session(token_key)

        retries = 0
        max_retries = MAX_AUTH_RETRIES if retry_auth else 0

        # Prepare any extra headers the caller passed in
        custom_headers: dict[str, str] = headers or {}

        while True:
            # Build a new dict[str, str] by decoding any bytes values
            request_headers: dict[str, str] = {
                key: value.decode() if isinstance(value, (bytes, bytearray)) else value
                for key, value in session.headers.items()
            }
            request_headers.update(custom_headers)


            # Step 4: Insert or remove the Authorization header
            if token:
                request_headers["Authorization"] = f"Bearer {token}"
            else:
                # In case the session had a stale Authorization header.
                request_headers.pop("Authorization", None)

            try:
                # Step 5: Perform the HTTP request
                response = session.request(method, url, headers=request_headers, **kwargs)

                # Step 6: On success, extract rate‐limit info if we hit GitHub.
                if response.status_code == 200 and url.startswith("https://api.github.com"):
                    cls._extract_rate_limit_from_headers(dict(response.headers))

                # Step 7: If we got a 401/403, clear session and retry once
                if response.status_code in (401, 403) and retries < max_retries:
                    SessionPool.clear_session(token_key)
                    cls.clear_cached_headers()

                    # Force a fresh token (this time validating expiration)
                    token = SecureTokenManager.get_token(validate_expiration=True)
                    token_key = str(hash(token)) if token else "unauthenticated"
                    session = SessionPool.get_session(token_key)

                    retries += 1
                    logger.warning(
                        "Authentication failed, retrying (%s/%s)", retries, max_retries
                    )
                    continue

                # Step 8: Return the response (successful or non‐retryable failure)
                return response

            except requests.RequestException as e:
                # Network‐level errors: retry if we still can, otherwise bubble up
                if retries < max_retries:
                    retries += 1
                    logger.warning(
                        "Request failed, retrying (%s/%s): %s", retries, max_retries, e
                    )
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
                        days_until_rotation = (
                            days_until_expiration - TOKEN_REFRESH_THRESHOLD_DAYS
                        )
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
    ) -> RateLimitCacheData:
        """Get current GitHub API rate limit information directly from the API.

        Makes a real-time API call to GitHub to get rate limit status,
        bypassing any cached information. Updates cache with fresh data.

        Args:
            custom_headers: Authentication headers to use, None for default token

        Returns:
            RateLimitCacheData: Current rate limit information

        """
        logger.info("Fetching live rate limit information from GitHub API")

        # Log current cache status
        if cls._rate_limit_cache:
            cache_age = time.time() - cls._rate_limit_cache_time
            logger.debug(
                "Cache status: age=%ss, requests since refresh=%s, remaining=%s/%s",
                int(cache_age),
                cls._request_count_since_cache,
                cls._rate_limit_cache["remaining"],
                cls._rate_limit_cache["limit"],
            )

        # Get fresh rate limit data (bypass cache) and cast to proper type
        rate_data = cast(
            RateLimitCacheData,
            cls._core_rate_limit_data(
                use_cache=False, custom_headers=custom_headers, return_dict=True
            ),
        )

        # Update cache with fresh data
        logger.debug("Updating cache with live rate limit data")
        cls._rate_limit_cache = rate_data
        cls._rate_limit_cache_time = time.time()
        cls._request_count_since_cache = 0
        cls._save_rate_limit_cache(rate_data)

        logger.info(
            "Live rate limits: %s/%s (reset at %s)",
            rate_data["remaining"],
            rate_data["limit"],
            rate_data["reset_formatted"],
        )

        return rate_data

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
                    token_info["scopes"] = (
                        [s.strip() for s in scopes.split(",")] if scopes else []
                    )

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
                    logger.warning(
                        "Failed to get rate limit info during token validation: %s", e
                    )

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
                logger.warning(
                    "Token validation failed with status code: %s", response.status_code
                )
                token_info["error"] = (
                    "GitHub API returned status code %s" % response.status_code
                )
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
