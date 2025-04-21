#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub authentication manager module.

This module provides functionality for handling GitHub API authentication
with proper Bearer token formatting and reuse.
"""

import logging
import time
import os
import json
from typing import Dict, Optional, Tuple, List, Any, Union
from datetime import datetime

import requests

from src.secure_token import SecureTokenManager

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
TOKEN_REFRESH_THRESHOLD_DAYS = 30  # Refresh token when it has fewer than this many days left
MAX_AUTH_RETRIES = 2  # Maximum number of retries for failed auth
RATE_LIMIT_CACHE_TTL = 60 * 60  # 1 hour cache TTL for rate limits - matches GitHub's reset window
RATE_LIMIT_HARD_REFRESH = 60 * 60 * 2  # Force refresh after 2 hours (safety margin)
CACHE_DIR = os.path.expanduser("~/.cache/myunicorn")  # Cache directory


class GitHubAuthManager:
    """
    Manages GitHub API authentication.

    This class provides methods to generate properly formatted authentication
    headers for GitHub API requests using securely stored tokens.

    All methods are static to allow easy usage across different modules.
    """

    _cached_headers: Optional[Dict[str, str]] = None
    _last_token: Optional[str] = None
    _last_token_check: float = 0
    _token_check_interval: int = 300  # Check token validity every 5 minutes
    _cached_headers_expiration: float = 0  # Timestamp when cached headers expire
    _audit_enabled: bool = True  # Enable audit logging by default
    _rate_limit_cache: Dict[str, Any] = {}
    _rate_limit_cache_time: float = 0
    _request_count_since_cache: int = 0  # Counter for API requests since last cache refresh

    @classmethod
    def get_auth_headers(cls, force_refresh: bool = False) -> Dict[str, str]:
        """
        Get authentication headers for GitHub API requests.

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
                expiration_dt = datetime.strptime(expiration_str, "%Y-%m-%d %H:%M:%S")
                remaining = (expiration_dt - datetime.now()).total_seconds()
                cache_validity = (
                    min(cls._token_check_interval, remaining / 2)
                    if remaining > 0
                    else cls._token_check_interval
                )
                cls._cached_headers_expiration = time.time() + cache_validity
            except Exception as e:
                logger.warning(f"Error parsing token expiration info: {e}")
                cls._cached_headers_expiration = time.time() + cls._token_check_interval
        else:
            cls._cached_headers_expiration = time.time() + cls._token_check_interval

        # Log this action if audit is enabled (but don't expose token)
        if cls._audit_enabled:
            SecureTokenManager.audit_log_token_usage("generate_auth_headers")

        logger.debug("Created GitHub API authentication headers with token")
        return auth_headers

    @classmethod
    def clear_cached_headers(cls) -> None:
        """
        Clear cached authentication headers.

        Call this method when the token changes to force regeneration of headers.
        """
        cls._cached_headers = None
        cls._last_token = None
        cls._last_token_check = 0
        logger.debug("Cleared cached GitHub API authentication headers")

    @staticmethod
    def has_valid_token() -> bool:
        """
        Check if a valid GitHub token is available.

        Returns:
            bool: True if a token exists and is not expired, False otherwise
        """
        # Get token and check that it's not expired
        token = SecureTokenManager.get_token(validate_expiration=True)
        return bool(token)

    @classmethod
    def _should_rotate_token(cls) -> bool:
        """
        Check if token should be rotated based on expiration.

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
            expiration_date = datetime.strptime(expiration_str, "%Y-%m-%d %H:%M:%S")
            current_date = datetime.now()

            # Calculate days until expiration
            days_until_expiration = (expiration_date - current_date).days

            # If token expires in less than threshold days, rotate it
            return days_until_expiration <= TOKEN_REFRESH_THRESHOLD_DAYS
        except Exception as e:
            logger.warning(f"Error checking token rotation: {e}")
            return False

    @classmethod
    def _ensure_cache_dir(cls) -> str:
        """
        Ensure the cache directory exists.

        Returns:
            str: Path to the cache directory
        """
        os.makedirs(CACHE_DIR, exist_ok=True)
        return CACHE_DIR

    @classmethod
    def _get_cache_file_path(cls) -> str:
        """
        Get the path to the rate limit cache file.

        Returns:
            str: Path to the cache file
        """
        return os.path.join(cls._ensure_cache_dir(), "rate_limit_cache.json")

    @classmethod
    def _load_rate_limit_cache(cls) -> Dict[str, Any]:
        """
        Load rate limit information from cache.

        Returns:
            dict: Rate limit cache or empty dict if no cache
        """
        try:
            cache_file = cls._get_cache_file_path()
            if os.path.exists(cache_file):
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    # Check if cache is still valid
                    current_time = time.time()
                    cache_age = current_time - data.get("timestamp", 0)

                    # If cache is still valid and not forced to refresh
                    if cache_age < RATE_LIMIT_CACHE_TTL:
                        # Reset request counter if loading from file
                        if "request_count" in data:
                            cls._request_count_since_cache = data.get("request_count", 0)
                        return data
                    # If cache is old but within the hard refresh limit, we can still use it
                    # but reset the request counter to be safe
                    elif cache_age < RATE_LIMIT_HARD_REFRESH:
                        cls._request_count_since_cache = 0
                        data["request_count"] = 0
                        return data
            return {}
        except Exception as e:
            logger.debug(f"Error loading rate limit cache: {e}")
            return {}

    @classmethod
    def _save_rate_limit_cache(cls, data: Dict[str, Any]) -> bool:
        """
        Save rate limit information to cache.

        Args:
            data: Rate limit data to cache

        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            # Add timestamp and request count to cache
            data["timestamp"] = time.time()
            data["request_count"] = cls._request_count_since_cache
            data["cache_ttl"] = RATE_LIMIT_CACHE_TTL

            # Save to file
            cache_file = cls._get_cache_file_path()
            # Write to temp file first for atomic update
            temp_file = f"{cache_file}.tmp"
            with open(temp_file, "w") as f:
                json.dump(data, f)
            # Atomic replace
            os.replace(temp_file, cache_file)
            return True
        except Exception as e:
            logger.debug(f"Error saving rate limit cache: {e}")
            return False

    @classmethod
    def _update_cached_rate_limit(cls, decrement: int = 1) -> None:
        """
        Update the cached rate limit by decrementing the remaining count.

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

            logger.debug(f"Updated cached rate limit: {new_remaining} (-{decrement}) remaining")

    @classmethod
    def get_rate_limit_info(
        cls, custom_headers: Optional[Dict[str, str]] = None, return_dict: bool = False
    ) -> Union[Tuple[int, int, str, bool], Dict[str, Any]]:
        """
        Get the current GitHub API rate limit information.

        Uses a local cache to avoid frequent API calls.

        Args:
            custom_headers: Optional custom headers for rate limit check
            return_dict: If True, returns the complete rate limit information as a dictionary

        Returns:
            tuple or dict: By default returns (remaining, limit, reset time, is_authenticated)
                          If return_dict=True, returns the complete rate limit information
        """
        # Check if we have a recent cache first
        current_time = time.time()
        cache_age = current_time - cls._rate_limit_cache_time

        # Force refresh if cache is too old
        if (cache_age > RATE_LIMIT_HARD_REFRESH) and cls._rate_limit_cache:
            logger.debug("Cache too old, forcing refresh of rate limit information")
            cls._rate_limit_cache = {}
        # Use memory cache if it's still valid
        elif (cache_age < RATE_LIMIT_CACHE_TTL) and cls._rate_limit_cache:
            logger.debug("Using cached rate limit information")
            # Include request count in debug info
            logger.debug(f"API requests since cache refresh: {cls._request_count_since_cache}")

            # If a dictionary return is requested, return the full cache
            if return_dict and "resources" in cls._rate_limit_cache:
                return cls._rate_limit_cache

            return (
                cls._rate_limit_cache.get("remaining", 0),
                cls._rate_limit_cache.get("limit", 0),
                cls._rate_limit_cache.get("reset_formatted", ""),
                cls._rate_limit_cache.get("is_authenticated", False),
            )

        # Try to load from file cache if memory cache is invalid
        if not cls._rate_limit_cache:
            file_cache = cls._load_rate_limit_cache()
            if file_cache:
                logger.debug("Using file cached rate limit information")
                cls._rate_limit_cache = file_cache
                cls._rate_limit_cache_time = current_time

                # If a dictionary return is requested, return the full cache
                if return_dict and "resources" in file_cache:
                    return file_cache

                return (
                    file_cache.get("remaining", 0),
                    file_cache.get("limit", 0),
                    file_cache.get("reset_formatted", ""),
                    file_cache.get("is_authenticated", False),
                )

        # No valid cache, need to make API call
        token = SecureTokenManager.get_token(validate_expiration=True)
        is_authenticated = bool(token)

        # Prepare headers - use custom headers if provided
        headers = custom_headers if custom_headers else cls.get_auth_headers()

        try:
            # Make rate limit API request
            response = requests.get(
                "https://api.github.com/rate_limit",
                headers=headers,
                timeout=5,  # Short timeout to avoid blocking the main menu
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

                # Add a full hour timestamp to make it clear when the next reset will be (for display purposes)
                next_full_hour_reset = datetime.fromtimestamp(
                    (int(time.time() / 3600) + 1) * 3600  # Next hour boundary
                )
                full_hour_reset_formatted = next_full_hour_reset.strftime("%Y-%m-%d %H:%M:%S")

                # Log usage for audit
                if cls._audit_enabled and is_authenticated:
                    SecureTokenManager.audit_log_token_usage("check_rate_limit")

                # Cache the result - store the full API response
                cache_data = {
                    "remaining": remaining,
                    "limit": limit,
                    "reset": reset_time,
                    "reset_formatted": reset_formatted,
                    "is_authenticated": is_authenticated,
                    "request_count": 0,  # Reset counter when we get fresh data
                    "resources": data.get("resources", {}),  # Store complete resources data
                    "full_hour_reset": next_full_hour_reset.timestamp(),
                    "full_hour_reset_formatted": full_hour_reset_formatted,
                }
                cls._rate_limit_cache = cache_data
                cls._rate_limit_cache_time = current_time
                cls._request_count_since_cache = 0  # Reset counter
                cls._save_rate_limit_cache(cache_data)

                # Return the full dict if requested
                if return_dict:
                    return cache_data

                return remaining, limit, reset_formatted, is_authenticated

            # Return defaults if request failed
            logger.debug(f"Rate limit check failed, status code: {response.status_code}")
            if response.status_code == 401:
                # Authentication failed - token may be invalid
                logger.warning("Rate limit check failed due to authentication error")
                # If token was invalid but exists, clear it from cache
                if token and cls._last_token:
                    cls.clear_cached_headers()

            # For unauthenticated users, GitHub allows 60 requests per hour
            if is_authenticated:
                defaults = (4000, 5000, "", True)  # Default authenticated rate limit
            else:
                defaults = (50, 60, "", False)  # Default for unauthenticated users

            # Calculate next hour boundary for reset
            next_hour_timestamp = (int(time.time() / 3600) + 1) * 3600
            next_hour = datetime.fromtimestamp(next_hour_timestamp)
            next_hour_formatted = next_hour.strftime("%Y-%m-%d %H:%M:%S")

            # Cache these defaults too
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
            cls._rate_limit_cache = cache_data
            cls._rate_limit_cache_time = current_time
            cls._request_count_since_cache = 0  # Reset counter
            cls._save_rate_limit_cache(cache_data)

            # Return the full dict if requested
            if return_dict:
                return cache_data

            return defaults

        except Exception as e:
            logger.debug(f"Failed to check rate limits: {e}")
            # Return sensible defaults that won't cause alarm
            if is_authenticated:
                defaults = (4500, 5000, "", True)  # Default authenticated limit
            else:
                defaults = (50, 60, "", False)  # Default unauthenticated limit

            # Calculate next hour boundary for reset
            next_hour_timestamp = (int(time.time() / 3600) + 1) * 3600
            next_hour = datetime.fromtimestamp(next_hour_timestamp)
            next_hour_formatted = next_hour.strftime("%Y-%m-%d %H:%M:%S")

            # Cache these defaults too
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
            cls._rate_limit_cache = cache_data
            cls._rate_limit_cache_time = current_time
            cls._request_count_since_cache = 0  # Reset counter

            # Return the full dict if requested
            if return_dict:
                return cache_data

            return defaults

    @classmethod
    def make_authenticated_request(
        cls,
        method: str,
        url: str,
        retry_auth: bool = True,
        audit_action: Optional[str] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Make an authenticated request to GitHub API with automatic token handling.

        Args:
            method: HTTP method (GET, POST, etc)
            url: URL to request
            retry_auth: Whether to retry on auth failures (with token refresh)
            audit_action: Action name for audit logging
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object from requests

        Raises:
            requests.RequestException: If the request fails
        """
        # Use our authentication headers
        if "headers" not in kwargs:
            kwargs["headers"] = {}

        # Merge our auth headers with any provided headers
        auth_headers = cls.get_auth_headers()
        for key, value in auth_headers.items():
            if key not in kwargs["headers"]:
                kwargs["headers"][key] = value

        # Track retries
        retries = 0
        max_retries = MAX_AUTH_RETRIES if retry_auth else 0

        while True:
            try:
                # Make the request
                response = requests.request(method, url, **kwargs)

                # For audit logging
                if cls._audit_enabled and audit_action:
                    SecureTokenManager.audit_log_token_usage(audit_action)

                # Update rate limit cache based on response if it's a successful GitHub API call
                if response.status_code == 200 and url.startswith("https://api.github.com"):
                    # Decrement the rate limit only for successful requests
                    cls._update_cached_rate_limit(1)
                    
                # Check if auth failed
                if response.status_code in (401, 403) and retries < max_retries:
                    # Clear cached headers to force token refresh
                    cls.clear_cached_headers()

                    # Update headers for next attempt
                    auth_headers = cls.get_auth_headers(force_refresh=True)
                    for key, value in auth_headers.items():
                        kwargs["headers"][key] = value

                    retries += 1
                    logger.warning(f"Authentication failed, retrying ({retries}/{max_retries})")
                    continue

                # Return the response regardless of status code
                return response

            except requests.RequestException as e:
                if retries < max_retries:
                    retries += 1
                    logger.warning(f"Request failed, retrying ({retries}/{max_retries}): {e}")
                    continue
                raise

    @classmethod
    def set_audit_enabled(cls, enabled: bool) -> None:
        """
        Enable or disable audit logging for authentication activities.

        Args:
            enabled: Whether to enable audit logging
        """
        cls._audit_enabled = enabled
        logger.info(f"Authentication audit logging {'enabled' if enabled else 'disabled'}")

    @classmethod
    def get_token_info(cls) -> Dict[str, Any]:
        """
        Get information about the current token.
    
        Returns:
            Dict with token information including expiration status
        """
        logger.debug("Getting token information and status")
        token_metadata = SecureTokenManager.get_token_metadata()
        is_expired, expiration_date = SecureTokenManager.get_token_expiration_info()
    
        # Calculate when the token will be rotated
        days_until_rotation = None
        if expiration_date and not is_expired:
            try:
                expiration = datetime.strptime(expiration_date, "%Y-%m-%d %H:%M:%S")
                current_date = datetime.now()
                days_until_expiration = (expiration - current_date).days
    
                if days_until_expiration <= TOKEN_REFRESH_THRESHOLD_DAYS:
                    days_until_rotation = 0  # Will be rotated on next use
                else:
                    days_until_rotation = days_until_expiration - TOKEN_REFRESH_THRESHOLD_DAYS
            except Exception as e:
                logger.warning(f"Error calculating token rotation time: {e}")
                pass
    
        # Use our own has_valid_token method instead of trying to call it on SecureTokenManager
        result = {
            "token_exists": SecureTokenManager.token_exists(),
            "token_valid": cls.has_valid_token(),  # Fixed: using GitHubAuthManager's method
            "is_expired": is_expired,
            "expiration_date": expiration_date,
            "days_until_rotation": days_until_rotation,
            "created_at": None,
            "last_used_at": None,
        }
    
        # Add metadata if available
        if token_metadata:
            if "created_at" in token_metadata:
                try:
                    created_ts = token_metadata["created_at"]
                    # Handle both string and integer timestamp formats
                    if isinstance(created_ts, str):
                        try:
                            # Try parsing as ISO format date first
                            created_at_dt = datetime.fromisoformat(created_ts)
                        except ValueError:
                            # Try parsing as a float/int string directly
                            created_at_dt = datetime.fromtimestamp(float(created_ts))
                    else:
                        # Assume it's an integer timestamp
                        created_at_dt = datetime.fromtimestamp(created_ts)
                        
                    result["created_at"] = created_at_dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    logger.warning(f"Error processing token creation date: {e}")
                    pass
    
            if "last_used_at" in token_metadata:
                try:
                    used_ts = token_metadata["last_used_at"]
                    # Handle both string and integer timestamp formats
                    if isinstance(used_ts, str):
                        try:
                            # Try parsing as ISO format date first
                            used_at_dt = datetime.fromisoformat(used_ts)
                        except ValueError:
                            # Try parsing as a float/int string directly
                            used_at_dt = datetime.fromtimestamp(float(used_ts))
                    else:
                        # Assume it's an integer timestamp
                        used_at_dt = datetime.fromtimestamp(used_ts)
                        
                    result["last_used_at"] = used_at_dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    logger.warning(f"Error processing token last used date: {e}")
                    pass
    
        logger.debug(
            f"Token info result: valid={result['token_valid']}, expired={result['is_expired']}"
        )
        return result
 
     
    # @classmethod
    # def get_token_info(cls) -> Dict[str, Any]:
    #     """
    #     Get information about the current token.

    #     Returns:
    #         Dict with token information including expiration status
    #     """
    #     logger.debug("Getting token information and status")
    #     token_metadata = SecureTokenManager.get_token_metadata()
    #     is_expired, expiration_date = SecureTokenManager.get_token_expiration_info()

    #     # Calculate when the token will be rotated
    #     days_until_rotation = None
    #     if expiration_date and not is_expired:
    #         try:
    #             expiration = datetime.strptime(expiration_date, "%Y-%m-%d %H:%M:%S")
    #             current_date = datetime.now()
    #             days_until_expiration = (expiration - current_date).days

    #             if days_until_expiration <= TOKEN_REFRESH_THRESHOLD_DAYS:
    #                 days_until_rotation = 0  # Will be rotated on next use
    #             else:
    #                 days_until_rotation = days_until_expiration - TOKEN_REFRESH_THRESHOLD_DAYS
    #         except Exception as e:
    #             logger.warning(f"Error calculating token rotation time: {e}")
    #             pass

    #     # Use our own has_valid_token method instead of trying to call it on SecureTokenManager
    #     result = {
    #         "token_exists": SecureTokenManager.token_exists(),
    #         "token_valid": cls.has_valid_token(),  # Fixed: using GitHubAuthManager's method
    #         "is_expired": is_expired,
    #         "expiration_date": expiration_date,
    #         "days_until_rotation": days_until_rotation,
    #         "created_at": None,
    #         "last_used_at": None,
    #     }

    #     # Add metadata if available
    #     if token_metadata:
    #         if "created_at" in token_metadata:
    #             try:
    #                 created_ts = token_metadata["created_at"]
    #                 result["created_at"] = datetime.fromtimestamp(created_ts).strftime(
    #                     "%Y-%m-%d %H:%M:%S"
    #                 )
    #             except Exception as e:
    #                 logger.warning(f"Error processing token creation date: {e}")
    #                 pass

    #         if "last_used_at" in token_metadata:
    #             try:
    #                 used_ts = token_metadata["last_used_at"]
    #                 result["last_used_at"] = datetime.fromtimestamp(used_ts).strftime(
    #                     "%Y-%m-%d %H:%M:%S"
    #                 )
    #             except Exception as e:
    #                 logger.warning(f"Error processing token last used date: {e}")
    #                 pass

    #     logger.debug(
    #         f"Token info result: valid={result['token_valid']}, expired={result['is_expired']}"
    #     )
    #     return result

    @classmethod
    def get_live_rate_limit_info(
        cls, custom_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Get the current GitHub API rate limit information directly from the API without using cache.

        This method is used when the user explicitly wants to check the current rate limits.

        Args:
            custom_headers: Optional custom headers for rate limit check

        Returns:
            Dict[str, Any]: Complete rate limit information dictionary
        """
        logger.info("Checking live rate limit information from GitHub API")

        # Log cache status before the check
        cache_age = time.time() - cls._rate_limit_cache_time
        logger.debug(
            f"Cache status before live check: age={int(cache_age)}s, requests since refresh={cls._request_count_since_cache}"
        )
        if cls._rate_limit_cache:
            logger.debug(
                f"Current cached remaining: {cls._rate_limit_cache.get('remaining', 'N/A')}/{cls._rate_limit_cache.get('limit', 'N/A')}"
            )

        # Get authentication token
        token = SecureTokenManager.get_token(validate_expiration=True)
        is_authenticated = bool(token)

        # Prepare headers - use custom headers if provided
        headers = custom_headers if custom_headers else cls.get_auth_headers()

        try:
            # Make rate limit API request
            logger.debug("Making direct API call to get rate limits")
            response = requests.get(
                "https://api.github.com/rate_limit",
                headers=headers,
                timeout=10,  # Longer timeout for explicit checks
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

                # Add a full hour timestamp to make it clear when the next reset will be (for display purposes)
                next_full_hour_reset = datetime.fromtimestamp(
                    (int(time.time() / 3600) + 1) * 3600  # Next hour boundary
                )
                full_hour_reset_formatted = next_full_hour_reset.strftime("%Y-%m-%d %H:%M:%S")

                # Log usage for audit
                if cls._audit_enabled and is_authenticated:
                    SecureTokenManager.audit_log_token_usage("check_rate_limit")

                # Create result dictionary
                result = {
                    "remaining": remaining,
                    "limit": limit,
                    "reset": reset_time,
                    "reset_formatted": reset_formatted,
                    "is_authenticated": is_authenticated,
                    "resources": data.get("resources", {}),
                    "full_hour_reset": next_full_hour_reset.timestamp(),
                    "full_hour_reset_formatted": full_hour_reset_formatted,
                }

                # Log the live check results
                logger.info(
                    f"Live rate limit check results: {remaining}/{limit} (reset at {reset_formatted})"
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
                    f"Cache updated with fresh data. New timestamp: {datetime.fromtimestamp(cls._rate_limit_cache_time).strftime('%Y-%m-%d %H:%M:%S')}"
                )

                return result

            # Handle error cases
            logger.error(f"Rate limit check failed, status code: {response.status_code}")
            if response.status_code == 401:
                logger.warning("Rate limit check failed due to authentication error")
                if token and cls._last_token:
                    cls.clear_cached_headers()

            # Create error result dictionary
            error_result = {
                "error": f"API request failed with status code: {response.status_code}",
                "is_authenticated": is_authenticated,
                "resources": {"core": {"limit": 0, "remaining": 0, "reset": 0}},
            }
            return error_result

        except Exception as e:
            logger.error(f"Error checking rate limits: {str(e)}")

            # Create error result dictionary
            error_result = {
                "error": f"Request error: {str(e)}",
                "is_authenticated": is_authenticated,
                "resources": {"core": {"limit": 0, "remaining": 0, "reset": 0}},
            }
            return error_result

    @classmethod
    def validate_token(
        cls, custom_headers: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate a GitHub token by making a test request and analyzing the response.

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
                    logger.warning(f"Failed to get rate limit info during token validation: {e}")

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
                logger.warning(f"Token validation failed with status code: {response.status_code}")
                token_info["error"] = f"GitHub API returned status code {response.status_code}"
                return False, token_info

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during token validation: {e}")
            token_info["error"] = f"Network error: {str(e)}"
            return False, token_info

        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}")
            token_info["error"] = f"Unexpected error: {str(e)}"
            return False, token_info
