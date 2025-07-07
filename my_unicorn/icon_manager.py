#!/usr/bin/env python3
"""Icon management module.

This module provides functionality for finding, fetching and storing
application icons from GitHub repositories or direct URLs using app definitions.
"""

import logging
import os
from pathlib import Path
from typing import Any

import requests

from my_unicorn.auth_manager import GitHubAuthManager
from my_unicorn.catalog import load_app_definition

logger = logging.getLogger(__name__)


class IconManager:
    """Manages finding and retrieving application icons."""

    def __init__(self) -> None:
        """Initialize the icon manager."""

    def find_icon(
        self, owner: str, repo: str, headers: dict[str, str] | None = None
    ) -> dict[str, Any] | None:
        """Find an icon for a given repository.

        First tries to use the repository path from app definition,
        then falls back to direct icon URL if specified.

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

        # Use GitHubAuthManager for authentication if no headers provided
        if headers is None:
            headers = GitHubAuthManager.get_auth_headers()
            logger.debug("Using GitHubAuthManager for icon search authentication")

        # Load app definition
        app_info = load_app_definition(repo.lower())
        if not app_info:
            logger.info("No app definition found for %s/%s", owner, repo)
            return None

        # First try to use repository path if specified
        icon_info = None
        if app_info.icon_repo_path:
            logger.info("Checking repository icon path: %s", app_info.icon_repo_path)
            icon_info = self._check_icon_path(owner, repo, app_info.icon_repo_path, headers)
            if icon_info and app_info.icon_file_name:
                preferred_filename = app_info.icon_file_name.lower()  # Ensure lowercase
                icon_info["preferred_filename"] = preferred_filename
                logger.info("Found icon at repository path: %s", app_info.icon_repo_path)

        # Fall back to direct icon URL if available and repo path didn't work
        if not icon_info and app_info.icon_info:
            logger.info("Repository path failed, trying direct icon URL: %s", app_info.icon_info)
            preferred_filename = (
                app_info.icon_file_name.lower()
                if app_info.icon_file_name
                else Path(app_info.icon_info).name.lower()
            )

            icon_info = {
                "download_url": app_info.icon_info,
                "content_type": self._get_content_type_from_url(app_info.icon_info),
                "size": 0,  # Size unknown for external URLs
                "name": preferred_filename,
                "path": app_info.icon_info,
                "preferred_filename": preferred_filename,
            }

        if icon_info:
            return icon_info

        logger.info(
            "No icon configuration found for %s/%s. "
            "Will use app name in desktop file; this may work with system icon themes like Papirus.",
            owner,
            repo,
        )
        return None

    def _get_content_type_from_url(self, url: str) -> str:
        """Determine content type based on URL extension.

        Args:
            url: Icon URL

        Returns:
            str: Content type (defaults to image/png if unknown)

        """
        url_lower = url.lower()
        if url_lower.endswith(".svg"):
            return "image/svg+xml"
        elif url_lower.endswith(".png"):
            return "image/png"
        elif url_lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        return "image/png"  # Default

    def _check_icon_path(
        self, owner: str, repo: str, path: str, headers: dict[str, str]
    ) -> dict[str, Any] | None:
        """Check if an icon exists at a specific path in the repository.

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
            logger.warning("Invalid icon path: '%s'", path)
            return None

        try:
            # Format the GitHub content API URL
            content_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
            logger.debug("Checking for icon at: %s", content_url)

            # Use GitHubAuthManager for authenticated requests with rate limit handling
            response = GitHubAuthManager.make_authenticated_request(
                "GET", content_url, headers=headers, timeout=10
            )

            if response.status_code == 200:
                content = response.json()
                if isinstance(content, dict) and content.get("type") == "file":
                    name = content.get("name", "").lower()
                    if any(name.endswith(ext) for ext in [".png", ".svg", ".jpg", ".jpeg"]):
                        logger.info("Found icon at %s", path)
                        return self._format_icon_info(content)

            elif response.status_code == 403 and "rate limit exceeded" in response.text.lower():
                logger.warning("GitHub API rate limit exceeded during icon search")
                GitHubAuthManager.clear_cached_headers()
            elif response.status_code == 404:
                logger.debug("Icon path not found: %s", path)
            else:
                logger.debug("Unexpected response (%s) for icon path: %s", response.status_code, path)

            return None

        except Exception as e:
            logger.debug("Error checking icon path %s: %s", path, e)
            return None

    def _format_icon_info(self, content: dict[str, Any]) -> dict[str, Any]:
        """Format icon file information.

        Args:
            content: GitHub API content information or URL info

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

    def download_icon(self, icon_info: dict[str, Any], destination_dir: str) -> tuple[bool, str]:
        """Download an icon file to the specified destination.

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
                base_name = icon_info["preferred_filename"].lower()  # Ensure lowercase
                if not base_name or base_name == "default":
                    # Fall back to original name if preferred_filename is invalid
                    base_name = icon_info["name"].lower()  # Ensure lowercase
                    logger.warning(
                        "Invalid preferred_filename '%s', using %s instead",
                        icon_info["preferred_filename"],
                        base_name,
                    )
            else:
                base_name = icon_info["name"].lower()  # Ensure lowercase

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

            # Download using appropriate method based on URL type
            download_url = icon_info["download_url"]
            if "api.github.com" in download_url:
                # Use GitHubAuthManager for GitHub API URLs
                response = GitHubAuthManager.make_authenticated_request(
                    "GET", download_url, stream=True, timeout=10
                )
            else:
                # Direct download for external URLs
                response = requests.get(download_url, stream=True, timeout=10)
            response.raise_for_status()

            with open(temp_icon_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Replace with atomic operation
            os.replace(temp_icon_path, icon_path)

            logger.info("Downloaded icon to %s", icon_path)
            return True, icon_path

        except Exception as e:
            logger.error("Failed to download icon: %s", e)
            # Clean up temp file if exists
            if "temp_icon_path" in locals() and os.path.exists(temp_icon_path):
                try:
                    os.remove(temp_icon_path)
                except Exception:
                    pass
            return False, f"Error: {e!s}"

    def ensure_app_icon(
        self,
        owner: str,
        repo: str,
        app_rename: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bool, str | None]:
        """Ensure an icon exists for the specified app, downloading if necessary.

        First checks if an icon already exists in expected locations.
        If not, downloads the icon from the configured URL or GitHub repository.

        Args:
            owner: Repository owner
            repo: Repository name (original case preserved)
            app_rename: Optional app identifier for naming (defaults to lookup or repo name)
            headers: Optional authentication headers

        Returns:
            tuple[bool, Optional[str]]: (Success status, Path to icon or status message)

        """
        try:
            # If app_rename not provided, try to load from app definition
            if app_rename is None:
                app_info = load_app_definition(repo.lower())
                if app_info and app_info.app_rename:
                    app_rename = app_info.app_rename
                    logger.debug("Using app_rename from JSON: %s", app_rename)
                else:
                    # Use repo name as fallback
                    app_rename = repo
                    logger.debug("Using repo name as app_rename: %s", app_rename)

            logger.info(
                "Using app_rename '%s' for icon folder (owner=%s, repo=%s)",
                app_rename,
                owner,
                repo,
            )

            # Check if icon already exists
            icon_base_dir = Path("~/.local/share/icons/myunicorn").expanduser()

            # Always use lowercase app name for consistency in storage
            app_name_lower = app_rename.lower()
            app_icon_dir = icon_base_dir / app_name_lower

            # For backward compatibility, also check the original case directory
            app_icon_dir_original = icon_base_dir / app_rename

            # Get the preferred filename from app definition
            app_info = load_app_definition(repo.lower())
            icon_filename = None
            if app_info and app_info.icon_file_name:
                icon_filename = app_info.icon_file_name.lower()  # Ensure lowercase
                # Check both case variants
                for directory in [app_icon_dir, app_icon_dir_original]:
                    icon_path = directory / icon_filename
                    if icon_path.exists() and icon_path.is_file():
                        logger.info("✓ Using existing icon: %s (skipping API request)", icon_path)
                        return True, str(icon_path)

            # Also check for any image file in the directories
            for directory in [app_icon_dir, app_icon_dir_original]:
                if directory.exists() and directory.is_dir():
                    for ext in [".png", ".svg", ".jpg", ".jpeg"]:
                        for icon_file in directory.glob(f"*{ext}"):
                            logger.info(
                                "✓ Using existing icon: %s (skipping API request)", icon_file
                            )
                            return True, str(icon_file)

            # No existing icon found, proceed with download
            logger.info(
                "✗ No existing icon found for %s, proceeding with API request to download icon",
                repo,
            )

            # Get authentication headers if not provided
            if not headers:
                headers = GitHubAuthManager.get_auth_headers()

            # Find icon in the repository or from URL
            logger.info("Making API request to find icon for %s", owner + "/" + repo)
            icon_info = self.find_icon(owner, repo, headers)

            if not icon_info:
                message = (
                    "No icon configuration found for %s/%s. "
                    "Desktop entry will use the app name ('%s') which may work with "
                    "system icon themes like Papirus or Adwaita."
                )
                logger.info(message, owner, repo, app_rename)
                return True, None

            # Create and download to the lowercase directory for consistency
            os.makedirs(app_icon_dir, exist_ok=True)
            logger.info("Icon found for %s, downloading to %s", repo, app_icon_dir)
            success, result_path = self.download_icon(icon_info, str(app_icon_dir))

            if success:
                logger.info("✓ Successfully downloaded icon to %s", result_path)
                return True, result_path
            else:
                logger.error("✗ Failed to download icon: %s", result_path)
                return False, result_path

        except Exception as e:
            logger.error("Failed to ensure app icon: %s", e)
            return False, f"Error: {e!s}"

    def get_icon_path(self, app_rename: str, repo: str | None = None) -> str | None:
        """Get the path to an existing icon for an app.

        Checks common locations for existing icons before attempting to download.

        Args:
            app_rename: The display name of the app
            repo: Optional repository name (lowercase) to load app definition

        Returns:
            Optional[str]: Path to existing icon if found, None otherwise

        """
        # Check standard icon locations
        icon_base_dir = Path("~/.local/share/icons/myunicorn").expanduser()

        # Try with lowercase app name for consistency
        app_name_lower = app_rename.lower()
        app_icon_dir_lower = icon_base_dir / app_name_lower

        # For backward compatibility, also check the original case directory
        app_icon_dir_original = icon_base_dir / app_rename

        # Check if we can get preferred filename from app definition
        preferred_filename = None
        if repo:
            app_info = load_app_definition(repo.lower())
            if app_info and app_info.icon_file_name:
                preferred_filename = app_info.icon_file_name.lower()  # Ensure lowercase

        # Places to look for icons
        locations_to_check = []

        # If we have a preferred filename, prioritize that
        if preferred_filename:
            locations_to_check.extend(
                [
                    app_icon_dir_lower / preferred_filename,
                    app_icon_dir_original / preferred_filename,
                ]
            )

        # Also check for any image files in the directories
        for directory in [app_icon_dir_lower, app_icon_dir_original]:
            if directory.exists() and directory.is_dir():
                for ext in [".png", ".svg", ".jpg", ".jpeg"]:
                    locations_to_check.extend(directory.glob(f"*{ext}"))

        # Return the first valid icon found
        for icon_path in locations_to_check:
            if icon_path.exists() and icon_path.is_file():
                logger.debug("Found existing icon at %s", icon_path)
                return str(icon_path)

        logger.debug("No existing icon found for %s", app_rename)
        return None
