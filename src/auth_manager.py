#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub authentication manager module.

This module provides functionality for handling GitHub API authentication
with proper Bearer token formatting and reuse.
"""

import logging
from typing import Dict, Optional

from src.secure_token import SecureTokenManager

# Configure module logger
logger = logging.getLogger(__name__)


class GitHubAuthManager:
    """
    Manages GitHub API authentication.

    This class provides methods to generate properly formatted authentication
    headers for GitHub API requests using securely stored tokens.

    All methods are static to allow easy usage across different modules.
    """

    _cached_headers: Optional[Dict[str, str]] = None
    _last_token: Optional[str] = None

    @classmethod
    def get_auth_headers(cls) -> Dict[str, str]:
        """
        Get authentication headers for GitHub API requests.

        Returns properly formatted headers with Bearer authentication if a token
        is available, or basic headers if no token is found.

        Returns:
            dict: Headers dictionary for API requests
        """
        # Prepare base headers that are always needed
        base_headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # Get the current token from secure storage
        token = SecureTokenManager.get_token()

        # If no token, return base headers only
        if not token:
            logger.debug("No GitHub token found, using unauthenticated requests")
            return base_headers

        # Check if we can reuse the cached headers
        if cls._cached_headers and token == cls._last_token:
            return cls._cached_headers

        # Create new headers with the token
        auth_headers = base_headers.copy()
        auth_headers["Authorization"] = f"Bearer {token}"

        # Cache the result for future calls
        cls._cached_headers = auth_headers
        cls._last_token = token

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
        logger.debug("Cleared cached GitHub API authentication headers")

    @staticmethod
    def has_valid_token() -> bool:
        """
        Check if a valid GitHub token is available.

        Returns:
            bool: True if a token exists, False otherwise
        """
        return bool(SecureTokenManager.get_token())
