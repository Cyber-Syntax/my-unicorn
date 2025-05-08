#!/usr/bin/env python3
"""GitHub Release Checksums Extractor.

This module provides functionality to extract SHA256 checksums from GitHub release
descriptions for applications that store their checksums in the release description
rather than as separate SHA files (e.g., Zen Browser).

Functions:
    extract_checksums: Extract checksums from GitHub release description
    save_checksums_file: Create a checksums file from extracted checksums
    verify_with_release_checksums: Verify an AppImage using extracted checksums
"""

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import List, Optional

from requests.exceptions import RequestException

from src.auth_manager import GitHubAuthManager

# Configure module logger
logger = logging.getLogger(__name__)


def extract_checksums(owner: str, repo: str, appimage_name: Optional[str] = None) -> List[str]:
    """Extract checksums from GitHub release description.

    Args:
        owner: Repository owner/organization
        repo: Repository name
        appimage_name: Optional AppImage filename to filter checksums for

    Returns:
        List of checksum lines in "hash filename" format

    Raises:
        ValueError: If no checksums found

    """
    logger.info(f"Extracting checksums for {owner}/{repo}")

    # Prepare authenticated request
    headers = GitHubAuthManager.get_auth_headers()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    try:
        # Fetch release description
        logger.debug(f"Fetching release description from {api_url}")
        response = GitHubAuthManager.make_authenticated_request(
            "GET", api_url, headers=headers, timeout=30, audit_action="fetch_release_description"
        )
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch release: {response.status_code} {response.text}")

        # Extract release description
        release_data = response.json()
        release_description = release_data.get("body", "")
        if not release_description:
            raise ValueError("Empty release description")

        # Extract SHA256 checksums from the release description
        checksums = _parse_checksums_from_description(release_description)
        if not checksums:
            raise ValueError("No checksums found in release description")

        logger.debug(f"Found {len(checksums)} checksums in release description")

        # Filter by appimage_name if provided
        if appimage_name:
            appimage_basename = os.path.basename(appimage_name).lower()
            filtered_checksums = [line for line in checksums if appimage_basename in line.lower()]
            if filtered_checksums:
                logger.debug(f"Filtered to {len(filtered_checksums)} checksums for {appimage_name}")
                return filtered_checksums
            else:
                logger.warning(f"No checksums found for {appimage_name}, returning all checksums")

        return checksums

    except RequestException as e:
        logger.error(f"Network error fetching release: {e}")
        raise ValueError(f"Network error: {e}")
    except Exception as e:
        logger.exception(f"Error extracting checksums: {e}")
        raise ValueError(f"Error extracting checksums: {e}")


def save_checksums_file(checksums: List[str], output_path: Optional[str] = None) -> str:
    """Save checksums to a SHA256SUMS.txt file.

    Args:
        checksums: List of checksum lines
        output_path: Optional path where to save the file (default: temp file)

    Returns:
        Path to the created checksums file

    Raises:
        IOError: If file cannot be created

    """
    if not checksums:
        raise ValueError("No checksums provided")

    # Create file path if not provided
    if not output_path:
        downloads_dir = Path.home() / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(downloads_dir / "SHA256SUMS.txt")

    try:
        # Write checksums with atomic pattern
        with open(f"{output_path}.tmp", "w", encoding="utf-8") as f:
            for line in checksums:
                f.write(f"{line}\n")

        # Atomic rename to avoid partial writes
        if os.path.exists(output_path):
            os.remove(output_path)
        os.rename(f"{output_path}.tmp", output_path)

        logger.info(f"Created checksums file with {len(checksums)} entries: {output_path}")
        return output_path

    except OSError as e:
        logger.error(f"Failed to write checksums file: {e}")
        raise OSError(f"Failed to write checksums file: {e}")


def verify_with_release_checksums(
    owner: str, repo: str, appimage_path: str, cleanup_on_failure: bool = False
) -> bool:
    """Verify an AppImage using checksums from GitHub release description.

    Args:
        owner: Repository owner/organization
        repo: Repository name
        appimage_path: Path to the AppImage to verify
        cleanup_on_failure: Whether to remove the AppImage if verification fails

    Returns:
        bool: True if verification succeeds, False otherwise

    """
    from src.verify import VerificationManager

    try:
        # Get AppImage filename
        appimage_name = os.path.basename(appimage_path)
        logger.info(f"Verifying {appimage_name} using checksums from {owner}/{repo}")

        # Extract checksums for the AppImage
        checksums = extract_checksums(owner, repo, appimage_name)
        if not checksums:
            logger.error("No checksums found in release description")
            return False

        # Create a temporary file for the checksums
        temp_dir = tempfile.gettempdir()
        sha_file = os.path.join(temp_dir, "SHA256SUMS.txt")
        save_checksums_file(checksums, sha_file)

        # Create verification manager
        verifier = VerificationManager(
            sha_name=sha_file,
            appimage_name=appimage_name,
            appimage_path=appimage_path,
            hash_type="sha256",
        )

        # Verify the AppImage
        return verifier.verify_appimage(cleanup_on_failure=cleanup_on_failure)

    except Exception as e:
        logger.exception(f"Error verifying with release checksums: {e}")
        return False


def _parse_checksums_from_description(description: str) -> List[str]:
    """Extract SHA256 checksum lines from the release description.

    Args:
        description: Release description text

    Returns:
        List of lines containing SHA256 checksums in "hash filename" format

    """
    checksums = []

    # Strategy 1: Look in <details> sections with checksums/SHA keywords
    checksums_section = re.search(
        r"<details>.*?<summary>.*?(checksum|sha|hash).*?</summary>(.*?)</details>",
        description,
        re.IGNORECASE | re.DOTALL,
    )

    if checksums_section:
        logger.debug("Found checksums in <details> section")
        section_content = checksums_section.group(2)

        # Look for code blocks within the section
        code_blocks = re.findall(r"```[^\n]*\n(.*?)```", section_content, re.DOTALL)

        # Process each code block
        for block in code_blocks:
            lines = block.strip().split("\n")
            for line in lines:
                line = line.strip()
                # Match SHA256 hash pattern (64 hex chars) followed by filename
                if re.match(r"^[0-9a-f]{64}\s+\S+", line, re.IGNORECASE):
                    checksums.append(line)

    # Strategy 2: Check code blocks directly if nothing found in details
    if not checksums:
        logger.debug("Looking for checksums in code blocks")
        code_blocks = re.findall(r"```[^\n]*\n(.*?)```", description, re.DOTALL)

        for block in code_blocks:
            lines = block.strip().split("\n")
            for line in lines:
                line = line.strip()
                if re.match(r"^[0-9a-f]{64}\s+\S+", line, re.IGNORECASE):
                    checksums.append(line)

    # Strategy 3: Last resort - scan the entire description line by line
    if not checksums:
        logger.debug("Scanning entire description for checksums")
        lines = description.split("\n")
        for line in lines:
            line = line.strip()
            if re.match(r"^[0-9a-f]{64}\s+\S+", line, re.IGNORECASE):
                checksums.append(line)

    logger.debug(f"Found {len(checksums)} SHA256 checksum entries")
    return checksums


if __name__ == "__main__":
    # Example usage when run as a script
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Extract checksums from GitHub release descriptions"
    )
    parser.add_argument("owner", help="Repository owner/organization")
    parser.add_argument("repo", help="Repository name")
    parser.add_argument(
        "--appimage", "-a", help="Optional AppImage filename to filter checksums for"
    )
    parser.add_argument(
        "--output", "-o", help="Output file path (default: SHA256SUMS.txt in current directory)"
    )
    parser.add_argument("--verify", "-v", metavar="PATH", help="Verify the specified AppImage file")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        if args.verify:
            if verify_with_release_checksums(args.owner, args.repo, args.verify):
                print(f"✓ Verification succeeded for {os.path.basename(args.verify)}")
                sys.exit(0)
            else:
                print(f"✗ Verification failed for {os.path.basename(args.verify)}")
                sys.exit(1)
        else:
            checksums = extract_checksums(args.owner, args.repo, args.appimage)
            output_path = args.output or "SHA256SUMS.txt"
            save_checksums_file(checksums, output_path)
            print(f"Created checksums file: {output_path}")
            if checksums:
                print("\nChecksum preview:")
                for i, checksum in enumerate(checksums[:3]):
                    print(f"  {i + 1}. {checksum}")
                if len(checksums) > 3:
                    print(f"  ...and {len(checksums) - 3} more")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
