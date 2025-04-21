#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub API handler module.

This module provides functionality for interacting with the GitHub API.
"""

import logging
import platform
import re
import os
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union

from src.icon_manager import IconManager
from src.auth_manager import GitHubAuthManager

# Configure module logger
logger = logging.getLogger(__name__)


class GitHubAPI:
    """Handler for GitHub API requests."""

    def __init__(
        self,
        owner: str,
        repo: str,
        sha_name: str = "sha256",
        hash_type: str = "sha256",
        arch_keyword: Optional[str] = None,
    ):
        """
        Initialize the GitHub API handler.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            sha_name: Name of the sha algorithm used in the release assets
            hash_type: Type of hash to use for file verification
            arch_keyword: Architecture keyword to filter releases
        """
        self.owner = owner
        self.repo = repo
        self.sha_name = sha_name
        self.hash_type = hash_type
        self.version = None
        self.sha_url = None
        self.appimage_url = None
        self.appimage_name = None
        self._arch_keyword = arch_keyword
        self.arch_keywords = self._get_arch_keywords()
        # Get authentication headers from GitHubAuthManager
        self._headers = GitHubAuthManager.get_auth_headers()
        self._icon_manager = IconManager()
        logger.debug(f"API initialized for {owner}/{repo} with auth headers")

    def _get_arch_keywords(self) -> List[str]:
        """
        Get architecture-specific keywords based on the current platform.

        Returns:
            list: List of architecture keywords
        """
        if self._arch_keyword:
            return [self._arch_keyword]

        system = platform.system().lower()
        machine = platform.machine().lower()

        # Simplified architecture mapping based on system and machine
        arch_map = {
            "linux": {
                "x86_64": ["x86_64", "amd64", "x64", "linux64"],
                "aarch64": ["aarch64", "arm64", "aarch", "arm"],
                "armv7l": ["armv7", "arm32", "armhf"],
                "armv6l": ["armv6", "arm"],
                "i686": ["i686", "x86", "i386", "linux32"],
            },
            "darwin": {
                "x86_64": ["x86_64", "amd64", "x64", "darwin64", "macos"],
                "arm64": ["arm64", "aarch64", "arm", "macos"],
            },
            "windows": {
                "AMD64": ["x86_64", "amd64", "x64", "win64"],
                "x86": ["x86", "i686", "i386", "win32"],
                "ARM64": ["arm64", "aarch64", "arm"],
            },
        }

        # Return default keywords for the current platform or empty list
        default_keywords = arch_map.get(system, {}).get(machine, [])
        if not default_keywords:
            logger.warning(
                f"No architecture keywords found for {system}/{machine}. "
                "Using system name as fallback."
            )
            return [system]
        return default_keywords

    def get_latest_release(self) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """
        Get the latest stable release from GitHub API.
        
        Returns:
            tuple: (Success flag, Release data or error message)
        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        
        try:
            logger.debug(f"Fetching latest release from {api_url}")
            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
                audit_action="fetch_latest_release"
            )
            
            if response.status_code == 200:
                release = response.json()
                self._process_release(release, release.get("prerelease", False))
                return True, release
            elif response.status_code == 404:
                logger.info(f"No stable release found for {self.owner}/{self.repo}, checking for beta releases")
                return self.get_beta_releases()
            elif response.status_code == 403 and "rate limit exceeded" in response.text.lower():
                logger.warning("GitHub API rate limit exceeded, refreshing authentication")
                self.refresh_auth()
                return False, "GitHub API rate limit exceeded. Please try again in a few minutes."
            else:
                error_msg = f"Failed to fetch latest release: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return False, error_msg
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching latest release: {str(e)}")
            return False, f"Network error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error fetching latest release: {str(e)}")
            return False, f"Error: {str(e)}"
    
    def get_beta_releases(self) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """
        Get all releases including pre-releases/betas.
        
        Returns:
            tuple: (Success flag, Latest release data or error message)
        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
        
        try:
            logger.debug(f"Fetching all releases from {api_url}")
            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
                audit_action="fetch_beta_releases"
            )
            
            if response.status_code == 200:
                releases = response.json()
                if not releases:
                    return False, "No releases found (including pre-releases)"
                    
                # Get the first (latest) release
                latest_release = releases[0]
                self._process_release(latest_release, latest_release.get("prerelease", False))
                return True, latest_release
            else:
                error_msg = f"Failed to fetch releases: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            logger.error(f"Error checking beta releases: {str(e)}")
            return False, f"Error checking beta releases: {str(e)}"
    
    def get_response(self, per_page: int = 100) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """
        Get the response from the GitHub API for releases.
        Simplified to use dedicated endpoints for latest and all releases.
        
        Returns:
            tuple: (Success flag, Response data or error message)
        """
        # First try to get the latest stable release
        success, response = self.get_latest_release()
        
        if success:
            return True, response
        
        # If no stable release is found, the get_latest_release method will already 
        # try to get beta releases through the get_beta_releases method
        return success, response
    
    def check_latest_version(self, current_version: Optional[str] = None) -> Tuple[bool, Dict[str, str]]:
        """
        Check if there's a newer version available.
        
        Args:
            current_version: Current version to compare against
            
        Returns:
            tuple: (Update available flag, Version information)
        """
        # Get latest release info (will try stable first, then fall back to beta if needed)
        success, response = self.get_response()
        
        if not success:
            return False, {"error": str(response)}
        
        try:
            # At this point, response should be a single release object, not a list
            latest_release = response
            latest_version = latest_release.get("tag_name", "")
            is_prerelease = latest_release.get("prerelease", False)
            
            # Normalize version strings for proper comparison
            current_version_clean = self._normalize_version_for_comparison(current_version)
            latest_version_clean = self._normalize_version_for_comparison(latest_version)
            
            logger.debug(
                f"Comparing versions: Current '{current_version_clean}' vs Latest '{latest_version_clean}'"
            )
            
            # Check if update is available
            update_available = False
            if current_version_clean and latest_version_clean != current_version_clean:
                # For repos that use beta versions, handle special comparison
                if self._repo_uses_beta():
                    # For FreeTube: if current is X.Y.Z and latest is vX.Y.Z-beta, consider it the same version
                    # Only consider it an update if the version numbers differ
                    current_base = self._extract_base_version(current_version_clean)
                    latest_base = self._extract_base_version(latest_version_clean)
                    
                    if current_base != latest_base:
                        update_available = True
                        logger.info(
                            f"Update available for beta app: {current_version} → {latest_version}"
                        )
                else:
                    # Standard comparison for non-beta apps
                    update_available = True
                    logger.info(f"Update available: {current_version} → {latest_version}")
                    
            # Get architecture keywords
            arch_keywords = self._get_arch_keywords()
            
            # Filter assets by architecture
            compatible_assets = []
            for asset in latest_release.get("assets", []):
                asset_name = asset.get("name", "").lower()
                if any(keyword.lower() in asset_name for keyword in arch_keywords):
                    compatible_assets.append(asset)
                    
            return update_available, {
                "current_version": current_version,
                "latest_version": latest_version,
                "release_notes": latest_release.get("body", ""),
                "release_url": latest_release.get("html_url", ""),
                "compatible_assets": compatible_assets,
                "is_prerelease": is_prerelease,
                "published_at": latest_release.get("published_at", ""),
            }
            
        except Exception as e:
            logger.error(f"Error parsing release information: {str(e)}")
            return False, {"error": f"Error parsing release information: {str(e)}"}

    def _process_latest_release(self, releases):
        """
        Process the latest release to set appimage_name, version, and other attributes.

        Args:
            releases: List of release data from GitHub API
        """
        try:
            # Filter out draft releases
            valid_releases = [r for r in releases if not r.get("draft", False)]

            if not valid_releases:
                logger.warning("No valid releases found after filtering drafts")
                return

            # Get the latest release (first in the list)
            latest_release = valid_releases[0]

            # Process with our existing method
            logger.info(f"Processing latest release: {latest_release.get('tag_name')}")
            result = self._process_release(latest_release, latest_release.get("prerelease", False))

            if not result:
                logger.warning("Failed to process release data")

            # Ensure we have the required data
            if not self.appimage_name or not self.appimage_url:
                logger.warning("Missing appimage_name or appimage_url after processing release")

        except Exception as e:
            logger.error(f"Error processing latest release: {e}")

    def _normalize_version_for_comparison(self, version: Optional[str]) -> str:
        """
        Normalize version string for consistent comparison.

        Args:
            version: Version string to normalize

        Returns:
            str: Normalized version string
        """
        if not version:
            return ""

        # Convert to lowercase for case-insensitive comparison
        normalized = version.lower()

        # Remove 'v' prefix if present
        if normalized.startswith("v"):
            normalized = normalized[1:]

        return normalized

    def _extract_base_version(self, version: str) -> str:
        """
        Extract the base version number without beta/alpha suffixes.

        Args:
            version: Version string to extract from

        Returns:
            str: Base version number (e.g., "0.23.3" from "0.23.3-beta")
        """
        # Split on common version separators
        for separator in ["-", "+", "_"]:
            if separator in version:
                return version.split(separator)[0]

        return version

    def _repo_uses_beta(self) -> bool:
        """
        Determine if this repository typically uses beta/pre-releases.

        Returns:
            bool: True if the repository typically uses beta releases
        """
        # List of repos that are known to use beta releases
        beta_repos = ["FreeTube"]

        # Check if the current repo is in the list
        if self.repo in beta_repos:
            logger.info(f"Repository {self.repo} is configured to use beta releases")
            return True

        return False

    def find_app_icon(self) -> Optional[Dict[str, Any]]:
        """
        Find application icon for the repository.

        Uses IconManager with the current authentication headers.

        Returns:
            dict or None: Icon information dictionary or None if not found
        """
        try:
            # Use the IconManager with current authentication headers
            icon_info = self._icon_manager.find_icon(self.owner, self.repo, headers=self._headers)

            if icon_info:
                logger.info(f"Found app icon: {icon_info.get('name')}")
                return icon_info

            return None
        except Exception as e:
            logger.error(f"Error finding app icon: {str(e)}")
            return None

    def refresh_auth(self) -> None:
        """
        Refresh authentication headers.

        This method should be called when encountering rate limits
        or authentication issues.
        """
        logger.debug("Refreshing authentication headers")
        # Clear cached headers in GitHubAuthManager
        GitHubAuthManager.clear_cached_headers()
        # Get fresh headers
        self._headers = GitHubAuthManager.get_auth_headers()
        logger.info("Authentication headers refreshed")

    def _process_release(self, release_data: dict, is_beta: bool):
        """Process release data with robust version parsing"""
        try:
            raw_tag = release_data["tag_name"]
            assets = release_data.get("assets", [])

            # First try to extract version from tag name
            version = self._extract_version(raw_tag, is_beta)

            # Find AppImage - THIS MUST SUCCEED
            self._find_appimage_asset(assets)
            if not self.appimage_name:
                raise ValueError("No AppImage found in release assets")

            if not version:
                version = self._extract_version_from_filename(self.appimage_name)

            if not version:
                raise ValueError(f"Could not determine version from tag: {raw_tag}")

            self.version = version
            self._find_sha_asset(assets)

            return {
                "owner": self.owner,
                "repo": self.repo,
                "version": self.version,
                "sha_name": self.sha_name,
                "hash_type": self.hash_type,
                "appimage_name": self.appimage_name,
                "arch_keyword": self._arch_keyword,
                "appimage_url": self.appimage_url,
                "sha_url": self.sha_url,
            }

        except KeyError as e:
            logging.error(f"Missing expected key in release data: {e}")
            return None

    def _extract_version(self, tag: str, is_beta: bool) -> str:
        """Extract semantic version from tag string"""
        # Clean common prefixes/suffixes
        clean_tag = tag.lstrip("vV").replace("-beta", "").replace("-stable", "")

        # Match semantic version pattern
        version_match = re.search(r"\d+\.\d+\.\d+(?:\.\d+)*", clean_tag)
        if version_match:
            return version_match.group(0)

        # Try alternative patterns if standard semantic version not found
        alt_match = re.search(r"(\d+[\w\.]+)", clean_tag)
        return alt_match.group(1) if alt_match else None

    def _extract_version_from_filename(self, filename: str) -> str:
        """Fallback version extraction from appimage filename"""
        if not filename:
            return None

        # Try to find version in filename segments
        for part in filename.split("-"):
            version = self._extract_version(part, False)
            if version:
                return version

        # Final fallback to regex search
        version_match = re.search(r"\d+\.\d+\.\d+", filename)

        return version_match.group(0) if version_match else None

    def _find_appimage_asset(self, assets: list):
        """
        Reliable AppImage selection with architecture keywords.

        Args:
            assets: List of release assets from GitHub API
        """
        # Current system architecture for logging
        current_arch = platform.machine().lower()
        logging.info(f"Current arch_keyword: {self._arch_keyword}")
        logging.info(f"Current system architecture: {current_arch}")

        # Get incompatible architectures to explicitly filter out
        incompatible_archs = self._get_incompatible_archs(current_arch)
        logging.info(f"Filtering out incompatible architectures: {incompatible_archs}")

        # Filter all AppImage files
        appimages = [a for a in assets if a["name"].lower().endswith(".appimage")]

        # First filter out incompatible architectures
        compatible_appimages = []
        for appimage in appimages:
            asset_name = appimage["name"].lower()
            # Skip assets with incompatible architecture markers
            if any(arch in asset_name for arch in incompatible_archs):
                logging.info(f"Skipping incompatible architecture: {asset_name}")
                continue
            compatible_appimages.append(appimage)

        # Use compatible AppImages for further processing, or fall back to all if none are compatible
        filtered_appimages = compatible_appimages if compatible_appimages else appimages

        if not filtered_appimages:
            raise ValueError("No AppImage files found in release")

        logging.info(f"Found {len(filtered_appimages)} potentially compatible AppImages")

        # 1. Try to match based on previously saved arch_keyword (exact ending)
        if self._arch_keyword:
            # Create a regex pattern that matches the arch_keyword at the end of the string.
            pattern = re.compile(re.escape(self._arch_keyword.strip().lower()) + r"\Z")
            logging.info(f"Trying to find match with arch keyword: {self._arch_keyword}")
            for asset in filtered_appimages:
                asset_name = asset["name"].strip().lower()
                logging.info(f"Checking asset: {asset_name}")
                if pattern.search(asset_name):
                    self._select_appimage(asset)
                    return

        # 2. Filter by current architecture keywords with stronger matching
        candidates = []
        exact_arch_match = None
        current_arch_keywords = self.arch_keywords

        for asset in filtered_appimages:
            name = asset["name"].lower()

            # Look for exact architecture match first (highest priority)
            if current_arch in name:
                exact_arch_match = asset
                break

            # Otherwise collect candidates based on architecture keywords
            if any(kw in name for kw in current_arch_keywords):
                candidates.append(asset)

        # If we found an exact architecture match, use it immediately
        if exact_arch_match:
            logging.info(f"Found exact architecture match: {exact_arch_match['name']}")
            self._select_appimage(exact_arch_match)
            return

        # 3. Handle candidate selection
        if len(candidates) == 1:
            self._select_appimage(candidates[0])
            return
        elif candidates:
            logging.info(f"Found {len(candidates)} architecture-matched AppImages")
            print(f"Found {len(candidates)} architecture-matched AppImages:")
            self._select_from_list(candidates)
            return

        # 4. For generic Linux builds without architecture in name, prefer those
        generic_linux_builds = [
            asset
            for asset in filtered_appimages
            if "linux" in asset["name"].lower()
            and not any(
                arch in asset["name"].lower()
                for arch in [
                    "arm",
                    "arm64",
                    "aarch64",
                    "armhf",
                    "arm32",
                    "x86_64",
                    "amd64",
                    "i686",
                    "i386",
                ]
            )
        ]

        if len(generic_linux_builds) == 1:
            logging.info(f"Found generic Linux build: {generic_linux_builds[0]['name']}")
            self._select_appimage(generic_linux_builds[0])
            return
        elif generic_linux_builds:
            logging.info(f"Found {len(generic_linux_builds)} generic Linux builds")
            print(f"Found {len(generic_linux_builds)} generic Linux builds:")
            self._select_from_list(generic_linux_builds)
            return

        # 5. Auto select if only one AppImage is left
        if len(filtered_appimages) == 1:
            self._select_appimage(filtered_appimages[0])
            return

        # 6. Fallback to asking user to choose from all compatible AppImages
        logging.info("No architecture-specific builds found, select from compatible AppImages")
        print("Please select the AppImage appropriate for your system:")
        self._select_from_list(filtered_appimages)

    def _get_incompatible_archs(self, current_arch: str) -> List[str]:
        """
        Get a list of architecture keywords that are incompatible with the current architecture.

        Args:
            current_arch: Current system architecture

        Returns:
            list: List of incompatible architecture keywords to filter out
        """
        # Define incompatible architectures based on current architecture
        incompatible_map = {
            # On x86_64, filter out ARM and 32-bit architectures
            "x86_64": [
                "arm64",
                "aarch64",
                "armhf",
                "arm32",
                "armv7",
                "armv6",
                "i686",
                "i386",
                "arm-",
                "-arm",
                "win",
                "windows",
                "darwin",
                "mac",
                "osx",
            ],
            # On ARM, filter out x86_64 and other incompatible architectures
            "aarch64": [
                "x86_64",
                "amd64",
                "i686",
                "i386",
                "win",
                "windows",
                "darwin",
                "mac",
                "osx",
            ],
            "arm64": ["x86_64", "amd64", "i686", "i386", "win", "windows", "darwin", "mac", "osx"],
            # On 32-bit x86, filter out 64-bit and ARM
            "i686": [
                "x86_64",
                "amd64",
                "arm64",
                "aarch64",
                "win",
                "windows",
                "darwin",
                "mac",
                "osx",
            ],
            "i386": [
                "x86_64",
                "amd64",
                "arm64",
                "aarch64",
                "win",
                "windows",
                "darwin",
                "mac",
                "osx",
            ],
        }

        # Return incompatible architectures or empty list if not defined
        return incompatible_map.get(current_arch, [])

    def _select_from_list(self, appimages):
        """User selection handler with persistence"""
        for idx, asset in enumerate(appimages, 1):
            print(f"{idx}. {asset['name']}")

        while True:
            choice = input(f"Select AppImage (1-{len(appimages)}): ")
            if choice.isdigit() and 1 <= int(choice) <= len(appimages):
                selected = appimages[int(choice) - 1]
                self._select_appimage(selected)
                return
            logging.warning("Invalid input, try again")
            print("Invalid input, try again")

    def _select_appimage(self, asset):
        """
        Select an AppImage asset and set instance attributes.

        Args:
            asset: GitHub API asset information dictionary
        """
        self.appimage_url = asset["browser_download_url"]
        self.appimage_name = asset["name"]
        logging.info(f"Selected: {self.appimage_name}")
        # Extract an arch keyword from the selected asset name.
        # Prioritize more specific identifiers.
        lower_name = self.appimage_name.lower()
        for key in ["arm64", "aarch64", "amd64", "x86_64"]:
            if key in lower_name:
                self._arch_keyword = f"-{key}.appimage"
                break
        else:
            # If no specific keyword is found, fallback to a default pattern.
            # For instance, extract the substring starting with "-linux"
            match = re.search(r"(-linux(?:64)?\.appimage)$", lower_name)
            if match:
                self._arch_keyword = match.group(1)
            else:
                # Last resort: use the file extension (this is less specific)
                self._arch_keyword = ".appimage"

    def _find_sha_asset(self, assets: list):
        """
        Find and select appropriate SHA file for verification.

        This method intelligently filters SHA files based on the selected AppImage architecture
        and prioritizes architecture-specific SHA files that match the selected AppImage.

        Args:
            assets: List of release assets from GitHub API
        """
        # Skip if SHA verification is disabled
        if self.sha_name == "no_sha_file":
            logging.info("Skipping SHA verification per configuration")
            return

        # Extract architecture from selected AppImage name for better SHA matching
        appimage_arch = self._extract_arch_from_filename(self.appimage_name)
        logging.info(f"Extracted architecture from AppImage: {appimage_arch}")

        # 1. Try exact match first if SHA name is provided
        if self.sha_name:
            for asset in assets:
                if asset["name"] == self.sha_name:
                    self._select_sha_asset(asset)
                    return

        # 2. Find architecture-specific SHA files that match the AppImage architecture
        sha_candidates = []
        generic_sha_candidates = []
        sha256sums = None
        linux_yml = None

        for asset in assets:
            name = asset["name"].lower()
            if not self._is_sha_file(name):
                continue

            # Special handling for common SHA files
            if name == "sha256sums":
                sha256sums = asset

            if name == "latest-linux.yml":
                linux_yml = asset

            # Match architecture-specific SHA files with the AppImage architecture
            asset_arch = self._extract_arch_from_filename(name)

            if asset_arch:
                # Only include architecture-specific files if they match the AppImage architecture
                if asset_arch == appimage_arch:
                    sha_candidates.append(asset)
                # Skip SHA files that are for other architectures
                continue

            # Include generic SHA files (no specific architecture in name)
            # Only include files that appear to be for Linux/generic platforms
            if "mac" not in name and "windows" not in name and "win" not in name:
                generic_sha_candidates.append(asset)

        # 3. Select SHA file based on intelligent prioritization

        # Use architecture-specific SHA files if available
        if len(sha_candidates) == 1:
            logging.info(f"Found architecture-specific SHA file: {sha_candidates[0]['name']}")
            self._select_sha_asset(sha_candidates[0])
            return
        elif len(sha_candidates) > 1:
            logging.info("Multiple architecture-specific SHA files found")
            print("Multiple architecture-specific SHA files found:")
            self._select_sha_from_list(sha_candidates)
            return

        # Set default SHA files based on common naming patterns
        if sha256sums:
            logging.info("Using SHA256SUMS file as default SHA256 checksums file")
            self._select_sha_asset(sha256sums)
            return

        if linux_yml and "linux" in self.appimage_name.lower():
            logging.info("Using latest-linux.yml file as default SHA for Linux")
            self._select_sha_asset(linux_yml)
            return

        # Use generic SHA candidates if available
        if len(generic_sha_candidates) == 1:
            logging.info(f"Using generic SHA file: {generic_sha_candidates[0]['name']}")
            self._select_sha_asset(generic_sha_candidates[0])
            return
        elif generic_sha_candidates:
            logging.info("Multiple generic SHA files found")
            print("SHA files compatible with your architecture:")
            self._select_sha_from_list(generic_sha_candidates)
            return

        # 4. Fallback to any SHA file if no architecture-specific or generic files found
        all_sha = [a for a in assets if self._is_sha_file(a["name"])]
        if len(all_sha) == 1:
            self._select_sha_asset(all_sha[0])
            return
        elif all_sha:
            logging.info("Found multiple SHA files")
            print("Found multiple SHA files:")
            self._select_sha_from_list(all_sha)
            return

        # 5. Final fallback to manual input
        self._handle_sha_fallback(assets)

    def _extract_arch_from_filename(self, filename: str) -> str:
        """
        Extract architecture information from a filename.

        This helper method identifies the architecture pattern in filenames
        to allow better matching between AppImages and SHA files.

        Args:
            filename: The filename to analyze

        Returns:
            str: Architecture identifier or empty string if not found
        """
        if not filename:
            return ""

        filename_lower = filename.lower()

        # Check for common architecture patterns in the filename
        arch_patterns = {
            "x86_64": ["x86_64", "x86-64", "amd64", "x64"],
            "arm64": ["arm64", "aarch64"],
            "armv7": ["armv7", "armhf", "arm32"],
            "arm": ["arm"],
            "i386": ["i386", "i686", "x86"],
            "mac": ["mac", "darwin"],
            "win": ["win", "windows"],
        }

        # Find which architecture pattern matches the filename
        for arch, patterns in arch_patterns.items():
            if any(pattern in filename_lower for pattern in patterns):
                return arch

        return ""

    def _is_sha_file(self, filename: str) -> bool:
        """Check if file is a valid SHA file using simple rules"""
        name = filename.lower()
        return (
            any(
                name.endswith(ext)
                for ext in (
                    ".sha256",
                    ".sha512",
                    ".yml",
                    ".yaml",
                    ".txt",
                    ".sum",
                    ".sha",
                )
            )
            or "checksum" in name
            or "sha256" in name
            or "sha512" in name
        )

    def _select_sha_asset(self, asset):
        """Your original hash type detection with improvements"""
        self.sha_name = asset["name"]
        self.sha_url = asset["browser_download_url"]

        # Original auto-detection logic
        name_lower = self.sha_name.lower()
        if "sha256" in name_lower:
            self.hash_type = "sha256"
        elif "sha512" in name_lower:
            self.hash_type = "sha512"
        elif name_lower.endswith((".yml", ".yaml")):
            # Default for YAML files as in original code
            self.hash_type = "sha512"
        else:
            # Fallback to user input
            logging.info(f"Could not detect hash type from {self.sha_name}")
            print(f"Could not detect hash type from {self.sha_name}")
            default = "sha256"
            user_input = input(f"Enter hash type (default: {default}): ").strip()
            self.hash_type = user_input if user_input else default

        logging.info(f"Selected SHA file: {self.sha_name} (hash type: {self.hash_type})")

    def _select_sha_from_list(self, sha_assets):
        """Simple user selection prompt"""
        for idx, asset in enumerate(sha_assets, 1):
            print(f"{idx}. {asset['name']}")

        while True:
            choice = input(f"Select SHA file (1-{len(sha_assets)}): ")
            if choice.isdigit() and 1 <= int(choice) <= len(sha_assets):
                self._select_sha_asset(sha_assets[int(choice) - 1])
                return
            logging.warning("Invalid input, try again")
            print("Invalid input, try again")

    def _handle_sha_fallback(self, assets):
        """Original fallback logic with improved prompts"""
        logging.warning("Could not find SHA file automatically")
        print(f"Could not find SHA file automatically for {self.appimage_name}")
        print("1. Enter filename manually")
        print("2. Skip verification")
        choice = input("Your choice (1-2): ")

        if choice == "1":
            self.sha_name = input("Enter exact SHA filename: ")
            for asset in assets:
                if asset["name"] == self.sha_name:
                    self.sha_url = asset["browser_download_url"]
                    self._select_sha_asset(asset)  # Trigger hash type detection
                    return
            raise ValueError(f"SHA file {self.sha_name} not found")
        else:
            self.sha_name = "no_sha_file"
            self.hash_type = "no_hash"
            logging.info("User chose to skip SHA verification")
