#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Icon management module.

This module provides functionality for finding, fetching and storing
application icons from GitHub repositories.
"""

import logging
import os
import requests
from typing import Dict, Optional, List, Any, Tuple, Union

# Import the icon paths configuration module instead of using YAML
from src.utils.icon_paths import get_icon_paths
from src.auth_manager import GitHubAuthManager

# Configure module logger
logger = logging.getLogger(__name__)


class IconManager:
    """
    Manages finding and retrieving application icons from GitHub repositories.

    This class provides methods to find icons in GitHub repositories either
    through exact paths, common file patterns, or by searching repository files.
    """

    def __init__(self):
        """
        Initialize the icon manager.

        No longer loads YAML as we're using the Python module directly.
        """
        pass

    def find_icon(
        self, owner: str, repo: str, headers: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find the best icon for a given repository.

        Only checks paths from icon_paths.py configuration without falling back to
        searching other directories in the repository. This reduces API calls.

        Args:
            owner: Repository owner/organization
            repo: Repository name (original case preserved)
            headers: Optional request headers for authentication

        Returns:
            dict or None: Icon information dictionary or None if not found
        """
        if not owner or not repo:
            logger.warning("Missing owner or repo name")
            return None

        # Get repository-specific configuration
        repo_config = self._get_repo_config(owner, repo)

        # Check if repo_config is None or empty
        if not repo_config:
            logger.info(
                f"No icon configuration found for {owner}/{repo}. "
                f"Will use app name in desktop file; this may work with system icon themes like Papirus."
            )
            return None

        # Use GitHubAuthManager for authentication if no headers provided
        if headers is None:
            headers = GitHubAuthManager.get_auth_headers()
            logger.debug("Using GitHubAuthManager for icon search authentication")

        # Step 1: Try exact path if specified (highest priority)
        if isinstance(repo_config, dict) and "exact_path" in repo_config:
            exact_path = repo_config["exact_path"]
            if not exact_path or exact_path == "default":
                logger.warning(f"Invalid exact_path '{exact_path}' for {owner}/{repo}")
            else:
                logger.info(f"Trying exact icon path: {exact_path}")
                icon_info = self._check_icon_path(owner, repo, exact_path, headers)
                if icon_info:
                    # Add filename preference if specified
                    if "filename" in repo_config:
                        icon_info["preferred_filename"] = repo_config["filename"]
                    return icon_info

        # Step 2: Try paths from configuration
        paths_to_check = []
        if isinstance(repo_config, dict) and "paths" in repo_config:
            paths_to_check = repo_config["paths"]
        elif isinstance(repo_config, list):
            paths_to_check = repo_config

        # Filter out any invalid paths
        valid_paths = [p for p in paths_to_check if p and p != "default"]

        if len(valid_paths) < len(paths_to_check):
            logger.warning(
                f"Filtered out {len(paths_to_check) - len(valid_paths)} invalid paths for {owner}/{repo}"
            )

        # Check each repository-specific path
        for path in valid_paths:
            logger.debug(f"Checking repository-specific icon path: {path}")
            icon_info = self._check_icon_path(owner, repo, path, headers)
            if icon_info:
                # Add filename preference if specified
                if isinstance(repo_config, dict) and "filename" in repo_config:
                    icon_info["preferred_filename"] = repo_config["filename"]
                return icon_info

        # Skip default fallback paths to reduce API calls
        logger.info(f"No suitable icon found for {owner}/{repo}")
        return None

    def _get_repo_config(self, owner: str, repo: str) -> Union[Dict[str, Any], List[str], None]:
        """
        Get repository configuration for icon paths.

        Tries multiple formats to find a match:
        1. Full owner/repo format
        2. Just repo name

        Args:
            owner: Repository owner/organization
            repo: Repository name

        Returns:
            Union[Dict[str, Any], List[str], None]: Repository configuration or None if not found
        """
        # Try different formats to find a match
        full_name = f"{owner}/{repo}"
        config = get_icon_paths(full_name) or get_icon_paths(repo)

        if config:
            logger.debug(f"Using icon configuration for {repo}: {type(config)}")
        else:
            logger.debug(f"No icon configuration found for {repo}")

        return config

    def _check_icon_path(
        self, owner: str, repo: str, path: str, headers: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Check if an icon exists at a specific path in the repository.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            path: Path to check for the icon
            headers: Request headers for authentication

        Returns:
            dict or None: Icon information dictionary or None if not found
        """
        # Validate path before attempting to check
        if not path or path == "default":
            logger.warning(f"Invalid icon path: '{path}'")
            return None

        try:
            # Format the GitHub content API URL
            content_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
            logger.debug(f"Checking for icon at: {content_url}")

            # Use GitHubAuthManager for authenticated requests with rate limit handling
            response = GitHubAuthManager.make_authenticated_request(
                "GET", content_url, headers=headers, timeout=10, audit_action="icon_path_check"
            )

            # Handle directory responses by checking for icon files inside
            if response.status_code == 200:
                content = response.json()

                # Handle list response (directory)
                if isinstance(content, list):
                    logger.debug(f"Path {path} is a directory, searching for icon files...")
                    # Search for icon files in the directory
                    for item in content:
                        if item.get("type") == "file":
                            name = item.get("name", "").lower()
                            if any(name.endswith(ext) for ext in [".png", ".svg", ".jpg", ".jpeg"]):
                                # Found an icon file in the directory
                                logger.info(f"Found icon file in directory: {name}")
                                return self._format_icon_info(item)
                    return None

                # Handle file response
                elif isinstance(content, dict) and content.get("type") == "file":
                    name = content.get("name", "").lower()
                    if any(name.endswith(ext) for ext in [".png", ".svg", ".jpg", ".jpeg"]):
                        logger.info(f"Found icon at {path}")
                        return self._format_icon_info(content)

            # Handle rate limit exceeded
            elif response.status_code == 403 and "rate limit exceeded" in response.text.lower():
                logger.warning("GitHub API rate limit exceeded during icon search")
                # Try to refresh auth headers
                GitHubAuthManager.clear_cached_headers()
                # We don't retry here to avoid recursion, but the next request will use refreshed token
            elif response.status_code == 404:
                logger.debug(f"Icon path not found: {path}")
            else:
                logger.debug(f"Unexpected response ({response.status_code}) for icon path: {path}")

            return None

        except Exception as e:
            logger.debug(f"Error checking icon path {path}: {str(e)}")
            return None

    def _format_icon_info(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format icon file information from GitHub API response.

        Args:
            content: GitHub API content information

        Returns:
            dict: Formatted icon information
        """
        name = content.get("name", "").lower()
        # Determine content type based on file extension
        content_type = (
            "image/svg+xml"
            if name.endswith(".svg")
            else ("image/png" if name.endswith(".png") else "image/jpeg")
        )

        return {
            "path": content.get("path", ""),
            "name": content.get("name", ""),
            "download_url": content.get("download_url", ""),
            "content_type": content_type,
            "size": content.get("size", 0),
        }

    def download_icon(self, icon_info: Dict[str, Any], destination_dir: str) -> Tuple[bool, str]:
        """
        Download an icon file to the specified destination.

        Args:
            icon_info: Icon information from find_icon method
            destination_dir: Directory to save the icon

        Returns:
            tuple: (Success flag, path to downloaded icon or error message)
        """
        if not icon_info or "download_url" not in icon_info:
            return False, "Invalid icon information"

        try:
            # Create destination directory if it doesn't exist
            os.makedirs(destination_dir, exist_ok=True)

            # Determine filename (use preferred_filename if specified)
            if "preferred_filename" in icon_info:
                base_name = icon_info["preferred_filename"]
                if not base_name or base_name == "default":
                    # Fall back to original name if preferred_filename is invalid
                    base_name = icon_info["name"]
                    logger.warning(
                        f"Invalid preferred_filename '{icon_info['preferred_filename']}', using {base_name} instead"
                    )
            else:
                base_name = icon_info["name"]

            # Ensure proper file extension
            if not any(
                base_name.lower().endswith(ext) for ext in [".png", ".svg", ".jpg", ".jpeg"]
            ):
                content_type = icon_info.get("content_type", "")
                if "svg" in content_type:
                    base_name += ".svg"
                elif "png" in content_type:
                    base_name += ".png"
                else:
                    base_name += ".png"  # Default to PNG

            # Full path for download
            icon_path = os.path.join(destination_dir, base_name)

            # Use atomic download pattern with temporary file
            temp_icon_path = f"{icon_path}.tmp"

            # Use GitHubAuthManager for authenticated download
            download_url = icon_info["download_url"]
            response = GitHubAuthManager.make_authenticated_request(
                "GET", download_url, stream=True, timeout=10, audit_action="icon_download"
            )
            response.raise_for_status()

            with open(temp_icon_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Replace with atomic operation
            os.replace(temp_icon_path, icon_path)

            logger.info(f"Downloaded icon to {icon_path}")
            return True, icon_path

        except Exception as e:
            logger.error(f"Failed to download icon: {str(e)}")
            # Clean up temp file if exists
            if "temp_icon_path" in locals() and os.path.exists(temp_icon_path):
                try:
                    os.remove(temp_icon_path)
                except Exception:
                    pass
            return False, f"Error: {str(e)}"

    def get_icon_path(self, repo: str, app_name: Optional[str] = None) -> Optional[str]:
        """
        Find the path to an existing icon for an application.

        Searches for icons in various locations in the following order:
        1. Repository-specific directory with preferred filename
        2. Standard icon filenames in repository directory
        3. Legacy system locations

        Args:
            repo: Repository name (used for directory names)
            app_name: Optional alternative name (original case preserved)

        Returns:
            str or None: Path to icon file if found, None otherwise
        """
        if not app_name:
            app_name = repo

        # Base icon directory for myunicorn
        icon_base_dir = os.path.expanduser("~/.local/share/icons/myunicorn")

        # Primary and fallback directories
        app_icon_dir = os.path.join(icon_base_dir, repo)
        repo_icon_dir = os.path.join(icon_base_dir, app_name)

        # Build list of search directories in priority order
        icon_dirs = []
        if repo != app_name:
            icon_dirs.append(app_icon_dir)
        icon_dirs.append(repo_icon_dir)

        # Check standard icon filenames in each directory
        search_paths = []
        for icon_dir in icon_dirs:
            if os.path.exists(icon_dir) and os.path.isdir(icon_dir):
                # Add standard filenames
                search_paths.extend(
                    [
                        os.path.join(icon_dir, f"{name}{ext}")
                        for name in ["icon", "logo", repo.lower()]
                        for ext in [".svg", ".png", ".jpg", ".jpeg"]
                    ]
                )

                # Add any other image files in the directory
                search_paths.extend(
                    [
                        os.path.join(icon_dir, f)
                        for f in os.listdir(icon_dir)
                        if os.path.isfile(os.path.join(icon_dir, f))
                        and any(
                            f.lower().endswith(ext) for ext in [".svg", ".png", ".jpg", ".jpeg"]
                        )
                    ]
                )

        # Also check legacy locations
        search_paths.extend(
            [
                os.path.join(icon_base_dir, "scalable/apps", f"{name}.svg")
                for name in [app_name, repo]
            ]
        )
        search_paths.extend(
            [
                os.path.join(icon_base_dir, "256x256/apps", f"{name}.png")
                for name in [app_name, repo]
            ]
        )
        search_paths.extend(
            [
                os.path.expanduser(f"~/.local/share/icons/{name}{ext}")
                for name in [app_name, repo]
                for ext in [".svg", ".png"]
            ]
        )

        # Check each location for a valid icon file
        for icon_path in search_paths:
            try:
                if os.path.exists(icon_path) and os.path.isfile(icon_path):
                    logger.debug(f"Found icon at: {icon_path}")
                    return icon_path
            except Exception as e:
                # Skip paths with access errors
                logger.debug(f"Error checking icon path {icon_path}: {e}")
                continue

        logger.debug(f"No icon found for {app_name} or {repo}")
        return None

    def ensure_app_icon(
        self, owner: str, repo: str, headers: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str]:
        """
        Ensure an icon exists for the specified app, downloading if necessary.

        First checks if an icon already exists in expected locations.
        If not, downloads the icon from the GitHub repository.

        Args:
            owner: Repository owner
            repo: Repository name (original case preserved)
            headers: Optional authentication headers

        Returns:
            Tuple[bool, str]: (Success status, Path to icon or status message)
        """
        try:
            from src.app_config import AppConfigManager

            # Get app ID for consistent directory naming
            app_config = AppConfigManager(owner=owner, repo=repo)
            app_id = app_config.repo

            # Check if icon already exists
            existing_icon = self.get_icon_path(app_id, repo)
            if existing_icon:
                logger.info(f"Using existing icon: {existing_icon}")
                return True, existing_icon

            # No existing icon found, proceed with download
            logger.info(f"No existing icon found for {repo}, will download")

            # Prepare icon directory
            icon_base_dir = os.path.expanduser("~/.local/share/icons/myunicorn")
            target_icon_dir = os.path.join(icon_base_dir, app_id)
            os.makedirs(target_icon_dir, exist_ok=True)

            # Get authentication headers if not provided
            if not headers:
                from src.auth_manager import GitHubAuthManager

                headers = GitHubAuthManager.get_auth_headers()

            # Find icon in the repository
            icon_info = self.find_icon(owner, repo, headers)

            if not icon_info:
                message = (
                    f"No icon configuration found for {owner}/{repo}. "
                    f"Desktop entry will use the app name ('{repo}') which may work with "
                    f"system icon themes like Papirus or Adwaita."
                )
                logger.info(message)
                return True, message

            # Download the icon
            success, result_path = self.download_icon(icon_info, target_icon_dir)

            if success:
                logger.info(f"Successfully downloaded icon to {result_path}")
                return True, result_path
            else:
                logger.error(f"Failed to download icon: {result_path}")
                return False, result_path

        except Exception as e:
            logger.error(f"Failed to ensure app icon: {str(e)}")
            return False, f"Error: {str(e)}"
