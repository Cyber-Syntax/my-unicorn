#!/usr/bin/env python3
"""Cleanup utilities for AppImage files and related SHA files."""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def get_user_cleanup_confirmation(app_name: str, file_count: int) -> bool:
    """Ask the user for confirmation before removing files that failed verification.

    Args:
        app_name: Name of the app for which files failed
        file_count: Number of files that would be removed

    Returns:
        bool: True if user confirms removal, False otherwise

    """
    print("\n" + "=" * 70)
    print(f"WARNING: Files for '{app_name}' failed verification or update.")
    print("This could indicate tampering, download corruption, or update failure.")
    print("You have two options:")
    print("  1. Remove the files (recommended for security and disk space)")
    print("  2. Keep the files (if you want to manually verify or report an issue)")
    print(f"Files to be removed: {file_count}")
    print("=" * 70)

    while True:
        try:
            response = input("\nRemove the files? [y/N]: ").strip().lower()
            if response in ("y", "yes"):
                return True
            if response in ("", "n", "no"):
                return False
            print("Please enter 'y' for yes or 'n' for no.")
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            return False


def get_user_single_file_confirmation(filepath: str) -> bool:
    """Ask user for confirmation before removing a single file that failed verification.

    Args:
        filepath: Path to the file that failed verification

    Returns:
        bool: True if user confirms removal, False otherwise

    """
    filename = os.path.basename(filepath)

    print("\n" + "=" * 70)
    print(f"WARNING: The file '{filename}' failed verification.")
    print("This could indicate tampering or download corruption.")
    print("You have two options:")
    print("  1. Remove the file (recommended for security)")
    print("  2. Keep the file (if you want to manually verify or report an issue)")
    print("=" * 70)

    while True:
        try:
            response = input("\nRemove the file? [y/N]: ").strip().lower()
            if response in ("y", "yes"):
                return True
            if response in ("", "n", "no"):
                return False
            print("Please answer 'y' for yes or 'n' for no.")
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled by user.")
            return False


def remove_single_file(filepath: str, verbose: bool = True) -> bool:
    """Remove a single file without user confirmation.

    Args:
        filepath: Path to the file to remove
        verbose: Whether to print removal messages

    Returns:
        bool: True if removal succeeded, False otherwise

    """
    try:
        if not os.path.exists(filepath):
            logger.info("File not found, nothing to clean up: %s", filepath)
            return True

        os.remove(filepath)
        logger.info("Removed file: %s", filepath)
        if verbose:
            print(f"Removed failed file: {filepath}")
        return True

    except OSError as e:
        logger.error("Failed to remove file: %s", e)
        if verbose:
            print(f"Warning: Could not remove failed file: {filepath}")
        return False


def cleanup_app_files(
    app_name: str,
    downloads_dir: str,
    verbose: bool = True,
    appimage_name: str | None = None,
    sha_name: str | None = None,
    ask_confirmation: bool = True,
) -> list[str]:
    """Clean up AppImage and SHA files using exact filenames.

    Args:
        app_name: Name of the app to clean up files for (used for logging only)
        downloads_dir: Directory where downloads are stored
        verbose: Whether to print cleanup messages
        appimage_name: Exact AppImage filename to remove
        sha_name: Exact SHA filename to remove
        ask_confirmation: Whether to ask user for confirmation before removal

    Returns:
        List of file paths that were successfully removed

    """
    if ask_confirmation:
        # Count files that would be removed to show user
        file_count = 0
        if appimage_name and os.path.exists(os.path.join(downloads_dir, appimage_name)):
            file_count += 1
        if sha_name and os.path.exists(os.path.join(downloads_dir, os.path.basename(sha_name))):
            file_count += 1

        if file_count == 0:
            logger.info("No files found to clean up for %s", app_name)
            return []

        if not get_user_cleanup_confirmation(app_name, file_count):
            logger.info("User declined to remove files for %s", app_name)
            return []

    # Remove files without additional confirmation using exact filenames
    return remove_files_by_exact_names(downloads_dir, appimage_name, sha_name, verbose=verbose)


def remove_files_by_exact_names(
    downloads_dir: str,
    appimage_name: str | None = None,
    sha_name: str | None = None,
    verbose: bool = True,
) -> list[str]:
    """Remove AppImage and SHA files using exact filenames without user confirmation.

    This function provides a simplified interface when exact filenames are known,
    avoiding the need for complex pattern matching.

    Args:
        downloads_dir: Directory where downloads are stored
        appimage_name: Exact AppImage filename to remove
        sha_name: Exact SHA filename to remove
        verbose: Whether to print cleanup messages

    Returns:
        List of file paths that were successfully removed

    """
    removed_files = []

    # Remove AppImage file if provided
    if appimage_name:
        appimage_file = os.path.join(downloads_dir, appimage_name)
        if _remove_file_if_exists(appimage_file, verbose, "AppImage"):
            removed_files.append(appimage_file)

    # Remove SHA file if provided
    if sha_name:
        # Extract just the filename from the path if it's a full path
        sha_filename = os.path.basename(sha_name)
        sha_file = os.path.join(downloads_dir, sha_filename)
        if _remove_file_if_exists(sha_file, verbose, "SHA"):
            removed_files.append(sha_file)

    return removed_files


def cleanup_failed_verification_files(
    app_name: str,
    appimage_name: str | None = None,
    sha_name: str | None = None,
    ask_confirmation: bool = True,
    verbose: bool = True
) -> list[str]:
    """Unified cleanup function for files that failed verification.

    This function consolidates all cleanup logic for failed verification scenarios,
    eliminating duplication across verify module, cleanup utils, and update commands.

    Args:
        app_name: Name of the app for which files failed verification
        appimage_name: Exact AppImage filename to remove (if known)
        sha_name: Exact SHA filename to remove (if known)
        ask_confirmation: Whether to ask user for confirmation before removal
        verbose: Whether to print cleanup messages

    Returns:
        List of file paths that were successfully removed
    """
    from src.global_config import GlobalConfigManager

    downloads_dir = GlobalConfigManager().expanded_app_download_path

    # Debug logging for troubleshooting
    logger.debug("cleanup_failed_verification_files called for app: %s", app_name)
    logger.debug("appimage_name: %s, sha_name: %s", appimage_name, sha_name)

    # Count files that would be removed
    file_count = 0
    if appimage_name and os.path.exists(os.path.join(downloads_dir, appimage_name)):
        file_count += 1
    if sha_name and os.path.exists(os.path.join(downloads_dir, os.path.basename(sha_name))):
        file_count += 1

    if file_count == 0:
        logger.info("No files found to clean up for %s", app_name)
        if verbose:
            print(f"No files found to clean up for {app_name}")
        return []

    # Get user confirmation if requested
    if ask_confirmation:
        if not get_user_cleanup_confirmation(app_name, file_count):
            logger.info("User declined to remove files for %s", app_name)
            return []

    # Remove files using exact filenames
    return remove_files_by_exact_names(downloads_dir, appimage_name, sha_name, verbose=verbose)


def cleanup_single_failed_file(
    filepath: str,
    ask_confirmation: bool = True,
    verbose: bool = True
) -> bool:
    """Unified cleanup function for a single file that failed verification.

    Args:
        filepath: Path to the file that failed verification
        ask_confirmation: Whether to ask user for confirmation before removal
        verbose: Whether to print cleanup messages

    Returns:
        bool: True if cleanup succeeded or was declined, False on error
    """
    try:
        if not os.path.exists(filepath):
            logger.info("File not found, nothing to clean up: %s", filepath)
            if verbose:
                print(f"File not found: {filepath}")
            return True

        # Ask user for confirmation if requested
        if ask_confirmation:
            if not get_user_single_file_confirmation(filepath):
                logger.info("User chose to keep the file despite verification failure: %s", filepath)
                if verbose:
                    print(f"File kept: {filepath}")
                    print("Note: You may want to investigate this verification failure or report it as an issue.")
                return True

        # Remove the file
        success = remove_single_file(filepath, verbose=verbose)

        if success and verbose:
            print(f"Removed failed file: {filepath}")

        return success

    except Exception as e:
        logger.error("Failed to remove file after verification failure: %s", e)
        if verbose:
            print(f"Warning: Could not remove failed file: {filepath}")
        return False


def cleanup_batch_failed_updates(
    failed_apps: list[str],
    results: dict[str, dict[str, Any]],
    ask_confirmation: bool = True,
    verbose: bool = True
) -> int:
    """Unified cleanup function for batch operations with failed updates.

    This function consolidates the cleanup logic used by both async and auto
    update commands when multiple apps fail and need cleanup.

    Args:
        failed_apps: List of app names that failed update
        results: Dictionary mapping app names to their result data
        ask_confirmation: Whether to ask user for confirmation before removal
        verbose: Whether to print cleanup messages

    Returns:
        int: Number of apps that had files successfully cleaned up
    """
    if not failed_apps:
        return 0

    # If asking for confirmation, do it once for the whole batch
    if ask_confirmation:
        total_files = 0
        for app_name in failed_apps:
            app_result = results.get(app_name, {})
            appimage_name = app_result.get("appimage_name")
            sha_name = app_result.get("sha_name")

            from src.global_config import GlobalConfigManager
            downloads_dir = GlobalConfigManager().expanded_app_download_path

            if appimage_name and os.path.exists(os.path.join(downloads_dir, appimage_name)):
                total_files += 1
            if sha_name and os.path.exists(os.path.join(downloads_dir, os.path.basename(sha_name))):
                total_files += 1

        if total_files == 0:
            if verbose:
                print("No files found to clean up for failed updates.")
            return 0

        print(f"\nFound {total_files} files from {len(failed_apps)} failed updates.")
        try:
            resp = input("Remove downloaded files for failed updates? [y/N]: ").strip().lower()
            if resp not in ("y", "yes"):
                logger.info("User declined batch cleanup of failed updates")
                return 0
        except KeyboardInterrupt:
            print("\nCleanup cancelled.")
            return 0

    # Clean up files for each failed app
    cleaned_count = 0
    for app_name in failed_apps:
        app_result = results.get(app_name, {})
        appimage_name = app_result.get("appimage_name")
        sha_name = app_result.get("sha_name")

        # Use our unified cleanup function without asking confirmation again
        removed_files = cleanup_failed_verification_files(
            app_name=app_name,
            appimage_name=appimage_name,
            sha_name=sha_name,
            ask_confirmation=False,  # Already confirmed for the batch
            verbose=verbose
        )

        if removed_files:
            cleaned_count += 1

    if verbose and cleaned_count > 0:
        print(f"Cleaned up files for {cleaned_count} failed updates.")

    return cleaned_count


def _remove_file_if_exists(file_path: str, verbose: bool, file_type: str) -> bool:
    """Remove a file if it exists.

    Args:
        file_path: Path to the file to remove
        verbose: Whether to print removal messages
        file_type: Type of file for logging (e.g., "AppImage", "SHA")

    Returns:
        bool: True if file was removed successfully, False otherwise

    """
    if not os.path.exists(file_path):
        return False

    try:
        os.remove(file_path)
        if verbose:
            print(f"Removed failed {file_type} file: {file_path}")
        logger.info("Removed %s file: %s", file_type, file_path)
        return True
    except OSError as e:
        logger.warning("Failed to remove %s file %s: %s", file_type, file_path, e)
        return False
