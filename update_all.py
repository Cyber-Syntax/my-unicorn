#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update all module.

This module provides functionality to check for and apply updates to all configured applications.
"""

import logging
import os
import sys
from typing import Dict, List, Any

from src.api import GitHubAPI

# Configure module logger
logger = logging.getLogger(__name__)


def get_app_info(owner: str, repo: str) -> Dict[str, Any]:
    """
    Get information about the latest release of an application.

    Args:
        owner: GitHub repository owner
        repo: GitHub repository name

    Returns:
        dict: Information about the latest release or empty dict if unavailable
    """
    try:
        api = GitHubAPI(owner=owner, repo=repo)
        api.get_latest_release_info()

        if api.version and api.appimage_name and api.appimage_url:
            return {
                "version": api.version,
                "appimage_name": api.appimage_name,
                "appimage_url": api.appimage_url,
            }
        return {}
    except Exception as e:
        logger.error(f"Failed to get release info for {owner}/{repo}: {str(e)}")
        return {}


def find_updatable_apps(config_dir, logger) -> list:
    """
    Find applications that can be updated based on their configuration files.

    Args:
        config_dir: Directory containing application configuration files
        logger: Logger instance for recording operations

    Returns:
        list: List of updatable applications with their information
    """
    from src.app_config import AppConfigManager

    updatable_apps = []

    # Create the application config manager
    app_config = AppConfigManager(config_dir=config_dir)

    try:
        # Iterate through each configuration file
        for config_file in app_config.select_files():
            try:
                # Load the configuration
                app_config.load_config(config_file)

                # Get release information for the application
                app_name = app_config.app_name
                owner = app_config.owner
                repo = app_config.repo

                logger.info(f"Checking for updates: {app_name} ({owner}/{repo})")
                print(f"Checking for updates: {app_name}")

                # Get information for latest release
                app_info = get_app_info(owner, repo)

                if app_info:
                    # Check if the application needs an update
                    local_version = app_config.version
                    remote_version = app_info.get("version")

                    if local_version != remote_version:
                        logger.info(
                            f"{app_name} can be updated: {local_version} → {remote_version}"
                        )
                        print(f"✓ {app_name} can be updated: {local_version} → {remote_version}")

                        # Add this application to the list of updatable apps
                        updatable_apps.append(
                            {
                                "name": app_name,
                                "owner": owner,
                                "repo": repo,
                                "current_version": local_version,
                                "new_version": remote_version,
                                "config_file": config_file,
                            }
                        )
                    else:
                        logger.info(f"{app_name} is already up to date ({local_version})")
                        print(f"- {app_name} is already up to date ({local_version})")
            except KeyboardInterrupt:
                # Allow clean exit with Ctrl+C during app processing
                logger.info("Update check interrupted by user (Ctrl+C)")
                print("\nUpdate check interrupted. Exiting gracefully...")
                raise  # Re-raise to be caught by the outer try-except
            except Exception as e:
                # Handle errors for individual applications without breaking the loop
                logger.error(f"Error processing {config_file}: {str(e)}")
                print(f"× Error checking {os.path.basename(config_file)}: {str(e)}")
    except KeyboardInterrupt:
        # Handle Ctrl+C for the entire function
        logger.info("Update check interrupted by user (Ctrl+C)")
        print("\nUpdate check canceled. Exiting gracefully...")
        return []  # Return empty list when interrupted

    return updatable_apps
