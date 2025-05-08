#!/usr/bin/env python3
"""GitHub release checksums extractor.

This module provides functionality to extract checksums from GitHub release descriptions
and create SHA256SUMS.txt files compatible with the verification system.

Example usage:
    # Extract checksums for a specific AppImage and save to a file
    from src.utils.release_desc import extract_checksums_to_file

    sha_file = extract_checksums_to_file(
        owner="zen-browser",
        repo="desktop",
        appimage_name="zen-x86_64.AppImage"
    )

    # Then use the sha_file with VerificationManager for verification
"""

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from src.auth_manager import GitHubAuthManager

# Configure module logger
logger = logging.getLogger(__name__)


class GitHubReleaseParser:
    """Extracts checksums from GitHub release descriptions."""

    def __init__(self, owner: str, repo: str) -> None:
        """Initialize with GitHub repository information.

        Args:
            owner: Repository owner/organization
            repo: Repository name

        """
        self.owner = owner
        self.repo = repo
        self.release_description = None
        self._headers = GitHubAuthManager.get_auth_headers()
        self.output_path = None

    def fetch_release_description(self) -> Optional[str]:
        """Fetch the release description directly from GitHub API.

        Returns:
            str: The release description text or None if unavailable

        """
        try:
            api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
            logger.debug(f"Fetching release description from {api_url}")

            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
                audit_action="fetch_release_description",
            )

            if response.status_code == 200:
                data = response.json()
                self.release_description = data.get("body", "")
                logger.info(
                    f"Successfully fetched release description ({len(self.release_description)} characters)"
                )
                return self.release_description
            else:
                logger.error(
                    f"Failed to fetch release description: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Error fetching release description: {e}")
            return None

    def extract_checksums(self, target_filename: Optional[str] = None) -> List[str]:
        """Extract checksum lines from the release description.

        Args:
            target_filename: Optional specific filename to filter checksums for

        Returns:
            List of lines containing checksums in "hash filename" format

        Raises:
            ValueError: If no checksums found or no release description available

        """
        if not self.release_description:
            self.release_description = self.fetch_release_description()

        if not self.release_description:
            raise ValueError("No release description available")

        checksums = self._parse_checksums_from_description()
        if not checksums:
            raise ValueError("No checksums found in release description")

        # Filter checksums for specific target file if provided
        if target_filename:
            target_name = os.path.basename(target_filename).lower()
            filtered_checksums = []

            for line in checksums:
                if target_name in line.lower():
                    filtered_checksums.append(line)
                    logger.debug(f"Found matching checksum: {line}")

            # Return filtered list if matches found, otherwise return all
            return filtered_checksums if filtered_checksums else checksums

        return checksums

    def write_checksums_file(
        self, target_filename: Optional[str] = None, output_path: Optional[str] = None
    ) -> str:
        """Write extracted checksums to a SHA256SUMS.txt file.

        Args:
            target_filename: Optional specific filename to filter checksums for
            output_path: Path to write the checksums file (if None, creates a temp file)

        Returns:
            str: Path to the created checksums file

        Raises:
            ValueError: If checksums extraction fails
            OSError: If file writing fails

        """
        checksums = self.extract_checksums(target_filename)

        if not output_path:
            # Create a SHA256SUMS.txt file in a reasonable location
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, "SHA256SUMS.txt")

        try:
            # Use Path for better path handling
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write checksums with atomic write pattern
            with open(f"{output_path}.tmp", "w", encoding="utf-8") as f:
                for line in checksums:
                    f.write(f"{line}\n")

            # Atomic rename to avoid partial writes
            if os.path.exists(output_path):
                os.remove(output_path)
            os.replace(f"{output_path}.tmp", output_path)

            self.output_path = output_path
            logger.info(f"Created checksums file with {len(checksums)} entries: {output_path}")
            return output_path

        except OSError as e:
            logger.error(f"Failed to write checksums file: {e}")
            raise OSError(f"Failed to write checksums file: {e}")

    def _parse_checksums_from_description(self) -> List[str]:
        """Extract SHA256 checksum lines from the release description.

        Returns:
            List of lines containing SHA256 checksums

        """
        checksums = []

        # Strategy 1: Look in <details> sections with checksums/SHA keywords
        checksums_section = re.search(
            r"<details>.*?<summary>.*?(checksum|sha|hash).*?</summary>(.*?)</details>",
            self.release_description,
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
            code_blocks = re.findall(r"```[^\n]*\n(.*?)```", self.release_description, re.DOTALL)
            for block in code_blocks:
                lines = block.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if re.match(r"^[0-9a-f]{64}\s+\S+", line, re.IGNORECASE):
                        checksums.append(line)

        # Strategy 3: Last resort - scan the entire description line by line
        if not checksums:
            logger.debug("Scanning entire description for checksums")
            lines = self.release_description.split("\n")
            for line in lines:
                line = line.strip()
                if re.match(r"^[0-9a-f]{64}\s+\S+", line, re.IGNORECASE):
                    checksums.append(line)

        logger.debug(f"Found {len(checksums)} SHA256 checksum entries")
        return checksums


def extract_checksums_to_file(
    owner: str, repo: str, appimage_name: str, output_path: Optional[str] = None
) -> Optional[str]:
    """Extract checksums for a specific AppImage from GitHub release.

    Args:
        owner: Repository owner/organization
        repo: Repository name
        appimage_name: Name of the AppImage file to match
        output_path: Optional path for the output file (default: temp file)

    Returns:
        str: Path to the created checksums file, or None on failure

    """
    try:
        logger.info(f"Extracting checksums for {appimage_name} from {owner}/{repo}")
        parser = GitHubReleaseParser(owner=owner, repo=repo)

        # Fetch release description
        if not parser.fetch_release_description():
            logger.error("Failed to fetch release description")
            return None

        # Create a SHA256SUMS.txt file in the downloads directory if no output path provided
        if not output_path:
            # Get downloads directory from GlobalConfigManager
            from src.global_config import GlobalConfigManager

            config_manager = GlobalConfigManager()
            downloads_dir = Path(config_manager.expanded_app_download_path)
            output_path = str(downloads_dir / "SHA256SUMS.txt")
            logger.info(f"Using downloads directory for checksums file: {output_path}")

        # Extract and write checksums
        sha_file = parser.write_checksums_file(appimage_name, output_path)
        logger.info(f"Created checksums file: {sha_file}")
        return sha_file

    except Exception as e:
        logger.exception(f"Error extracting checksums: {e}")
        return None


def get_repo_info_for_appimage(appimage_path: str) -> Dict[str, str]:
    """Get owner/repo information for an AppImage based on filename.

    This function tries to determine the GitHub owner/repo information
    based on the AppImage filename by matching it with app catalog entries.

    Args:
        appimage_path: Path to the AppImage file

    Returns:
        Dict containing 'owner' and 'repo' keys, or empty dict if not found

    """
    try:
        from src.app_catalog import APP_CATALOG

        # Extract the base name without extension
        appimage_name = os.path.basename(appimage_path)
        app_id = appimage_name.split("-")[0].lower()

        logger.info(f"Trying to find repository info for app_id: {app_id}")

        # Check if this app_id matches any catalog entries
        for catalog_app_id, app_info in APP_CATALOG.items():
            if app_id == catalog_app_id.lower():
                logger.info(f"Found matching app in catalog: {catalog_app_id}")
                return {"owner": app_info.owner, "repo": app_info.repo}

            # Also try to match by repo name
            if app_id == app_info.repo.lower():
                logger.info(f"Found matching repo in catalog: {app_info.repo}")
                return {"owner": app_info.owner, "repo": app_info.repo}

        # If we reach here, no match was found in the catalog
        logger.warning(f"No matching repository found for {app_id}")
        return {}

    except Exception as e:
        logger.exception(f"Error finding repository info: {e}")
        return {}


def handle_release_description_verification(
    appimage_path: str,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    cleanup_on_failure: bool = False,
) -> bool:
    """Handle verification for apps that use release description for checksums.

    Args:
        appimage_path: Full path to the AppImage file to verify
        owner: Repository owner/organization (optional)
        repo: Repository name (optional)
        cleanup_on_failure: Whether to remove the AppImage if verification fails

    Returns:
        bool: True if verification passed, False otherwise

    """
    try:
        # Get the AppImage filename only
        appimage_name = os.path.basename(appimage_path)

        # First, determine owner and repo if not provided
        if not owner or not repo:
            repo_info = get_repo_info_for_appimage(appimage_path)
            owner = repo_info.get("owner")
            repo = repo_info.get("repo")

            if not owner or not repo:
                logger.error(f"Could not determine owner/repo for {appimage_name}")
                return False

        logger.info(f"Using GitHub release description for verification of {appimage_name}")
        logger.info(f"Owner: {owner}, Repo: {repo}")

        # Extract checksums to a file in the downloads directory
        sha_file = extract_checksums_to_file(owner=owner, repo=repo, appimage_name=appimage_name)

        if not sha_file:
            logger.error(f"Failed to extract checksums for {appimage_name}")
            return False

        # Verify the AppImage using the extracted checksums
        from src.verify import VerificationManager

        verifier = VerificationManager(
            sha_name=sha_file,
            appimage_name=appimage_name,
            appimage_path=appimage_path,
            hash_type="sha256",
        )

        # Perform verification using the standard verification system
        success = verifier.verify_appimage(cleanup_on_failure=cleanup_on_failure)

        if success:
            logger.info(
                f"Successfully verified {appimage_name} using release description checksums"
            )
        else:
            logger.error(
                f"Verification failed for {appimage_name} using release description checksums"
            )

        return success

    except Exception as e:
        logger.exception(f"Release description verification error: {e}")
        return False


if __name__ == "__main__":
    # Configure logging when run as script
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Example usage
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Extract checksums from GitHub release descriptions for verification"
    )
    parser.add_argument("owner", help="Repository owner/organization")
    parser.add_argument("repo", help="Repository name")
    parser.add_argument(
        "--appimage", "-a", help="Optional AppImage filename to filter checksums for"
    )
    parser.add_argument(
        "--output", "-o", help="Output file path (default: SHA256SUMS.txt in current directory)"
    )
    parser.add_argument(
        "--verify",
        "-v",
        metavar="PATH",
        help="Verify the specified AppImage file after extracting checksums",
    )
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    parser.add_argument("--quiet", "-q", action="store_true", help="Print only essential output")
    parser.add_argument(
        "--force", "-f", action="store_true", help="Overwrite output file if it exists"
    )

    args = parser.parse_args()

    # Set logging level based on arguments
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # Default output file path
    output_file = args.output or "SHA256SUMS.txt"

    # Check if output file exists and handle according to force flag
    if Path(output_file).exists() and not args.force and not args.verify:
        print(f"Error: Output file {output_file} already exists. Use --force to overwrite.")
        sys.exit(1)

    if args.verify:
        # Verify mode
        try:
            if not Path(args.verify).exists():
                print(f"Error: AppImage file not found: {args.verify}")
                sys.exit(1)

            if not args.quiet:
                print(f"Verifying {args.verify} using GitHub release checksums...")

            success = handle_release_description_verification(
                appimage_path=args.verify,
                owner=args.owner,
                repo=args.repo,
                cleanup_on_failure=False,
            )

            if success:
                print(f"\n✓ Verification succeeded for {Path(args.verify).name}")
                sys.exit(0)
            else:
                print(f"\n✗ Verification failed for {Path(args.verify).name}")
                sys.exit(1)
        except Exception as e:
            print(f"Error during verification: {e}")
            sys.exit(1)
    else:
        # Extract mode
        try:
            parser = GitHubReleaseParser(owner=args.owner, repo=args.repo)
            if not args.quiet:
                print(f"Fetching release description for {args.owner}/{args.repo}...")

            if not parser.fetch_release_description():
                print("Error: Failed to fetch release description")
                sys.exit(1)

            sha_file = parser.write_checksums_file(args.appimage, output_file)

            if not args.quiet:
                print(f"Created checksums file: {sha_file}")

                # Print preview of checksums
                checksums = parser.extract_checksums(args.appimage)
                if checksums:
                    print("\nChecksum preview:")
                    for i, checksum in enumerate(checksums[:3]):
                        print(f"  {i + 1}. {checksum}")
                    if len(checksums) > 3:
                        print(f"  ...and {len(checksums) - 3} more")
                    print("\nUse this file for AppImage verification with:")
                    print(
                        f"  python -m src.utils.release_desc {args.owner} {args.repo} --verify /path/to/appimage"
                    )
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
