#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Icon manager module for handling app icon discovery and download.

This module provides functionality to find and download icons from GitHub repositories
using a combination of known paths and minimal API requests to avoid rate limiting.
"""

import base64
import logging
import os
import time
from typing import Dict, Optional, Tuple

import requests
import yaml
from src.global_config import GlobalConfigManager

# Configure module logger
logger = logging.getLogger(__name__)

# Constants for API request settings
DEFAULT_TIMEOUT = 5  # Default timeout for API requests in seconds
MAX_API_ATTEMPTS = 3  # Maximum attempts for API requests
API_CALL_DELAY = 1.0  # Minimum delay between API calls in seconds


class IconManager:
    """Manages icon discovery and downloading for AppImages."""

    def __init__(self):
        self.global_config = GlobalConfigManager()
        self._headers = self._get_request_headers()
        self.known_paths = self._load_known_paths()

    def _get_request_headers(self) -> dict:
        """Get headers for GitHub API requests including authentication if available."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.global_config.github_token:
            headers["Authorization"] = f"token {self.global_config.github_token}"
            logger.info("Using GitHub token for icon requests")
        return headers

    def _load_known_paths(self) -> Dict:
        """Load known icon paths from YAML configuration."""
        try:
            yaml_path = os.path.join(os.path.dirname(__file__), "..", "icon_paths.yaml")
            if os.path.exists(yaml_path):
                with open(yaml_path, "r") as f:
                    return yaml.safe_load(f) or {}
            return {}
        except Exception as e:
            logger.error(f"Failed to load icon paths: {e}")
            return {}

    def find_icon(self, owner: str, repo: str, api_limit: int = 3) -> Optional[Dict]:
        """
        Find the best suitable icon for an application.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            api_limit: Maximum number of API calls to make (default: 3)

        Returns:
            Optional[Dict]: Icon information or None if no suitable icon found
        """
        # First check known paths
        if repo.lower() in self.known_paths:
            for path in self.known_paths[repo.lower()]:
                icon_info = self._check_known_path(owner, repo, path)
                if icon_info:
                    return icon_info

        # Then try common locations with limited API calls
        tried = 0
        common_paths = [
            "icon.png",
            "icon.svg",
            "logo.png",
            "logo.svg",
            "assets/icon.png",
            "assets/icon.svg",
            "src/assets/icon.png",
            "src/assets/icons/icon.png",
            "resources/icon.png",
            "static/icon.png",
            "public/icon.png",
            "icons/icon.png",
        ]

        for path in common_paths:
            if tried >= api_limit:
                logger.info(f"Reached API call limit ({api_limit})")
                break

            try:
                url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
                response = requests.get(url, headers=self._headers)
                tried += 1

                if response.status_code == 200:
                    content = response.json()
                    if content.get("type") == "file" and self._is_valid_icon(content):
                        return content

            except Exception as e:
                logger.error(f"Error checking path {path}: {e}")

        return None

    def _check_known_path(self, owner: str, repo: str, path: str) -> Optional[Dict]:
        """Check a known icon path from configuration."""
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
            response = requests.get(url, headers=self._headers)

            if response.status_code == 200:
                content = response.json()
                if content.get("type") == "file" and self._is_valid_icon(content):
                    return content
            return None
        except Exception as e:
            logger.error(f"Error checking known path {path}: {e}")
            return None

    def _is_valid_icon(self, file_info: Dict) -> bool:
        """Check if file is a valid icon."""
        name = file_info.get("name", "").lower()
        return name.endswith((".png", ".svg", ".ico")) and file_info.get("size", 0) < 1024 * 1024

    def download_icon(self, icon_info: Dict, repo_name: str) -> Tuple[bool, str]:
        """
        Download and save an icon to the appropriate XDG directory.

        Args:
            icon_info: Icon information from GitHub API
            repo_name: Repository name for the app

        Returns:
            Tuple[bool, str]: Success status and path to saved icon or error message
        """
        try:
            # Determine icon format and setup paths
            icon_format = os.path.splitext(icon_info["name"])[1].lower()
            is_svg = icon_format == ".svg"

            # Set up XDG paths
            if is_svg:
                icon_dir = os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps")
            else:
                icon_dir = os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps")

            os.makedirs(icon_dir, exist_ok=True)
            icon_path = os.path.join(icon_dir, f"{repo_name.lower()}{icon_format}")

            # Download and save icon
            response = requests.get(icon_info["download_url"], headers=self._headers)
            response.raise_for_status()

            with open(icon_path, "wb") as f:
                f.write(response.content)

            logger.info(f"Icon saved to {icon_path}")
            return True, icon_path

        except Exception as e:
            error_msg = f"Failed to download icon: {e}"
            logger.error(error_msg)
            return False, error_msg
