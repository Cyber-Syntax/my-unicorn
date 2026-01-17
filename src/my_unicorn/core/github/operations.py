"""GitHub operations utilities for install and update workflows.

This module provides unified GitHub operations extracted from install.py
and update.py to eliminate code duplication.

Functions:
    parse_github_url: Parse GitHub URL to extract owner/repo
    extract_github_config: Extract GitHub info from effective config

"""

from typing import Any

from my_unicorn.exceptions import InstallationError
from my_unicorn.logger import get_logger

logger = get_logger(__name__)

# Minimum number of path parts expected for GitHub owner/repo
MIN_GITHUB_PARTS = 2


def parse_github_url(url: str) -> dict[str, str]:
    """Parse GitHub URL to extract owner and repo.

    Args:
        url: GitHub repository URL (e.g., https://github.com/owner/repo)

    Returns:
        Dictionary containing:
            - owner: Repository owner
            - repo: Repository name
            - app_name: Lowercase repository name

    Raises:
        InstallationError: If URL format is invalid

    Examples:
        >>> parse_github_url("https://github.com/AppFlowy-IO/AppFlowy")
        {'owner': 'AppFlowy-IO', 'repo': 'AppFlowy', 'app_name': 'appflowy'}

    """
    try:
        # Parse owner/repo from URL
        parts = url.replace("https://github.com/", "").split("/")
        if len(parts) < MIN_GITHUB_PARTS:
            msg = f"Invalid GitHub URL format: {url}"
            raise InstallationError(msg)

        owner, repo = parts[0], parts[1]
        app_name = repo.lower()

    except InstallationError:
        raise
    except Exception as error:
        logger.exception("Failed to parse GitHub URL %s", url)
        msg = f"Invalid GitHub URL: {url}"
        raise InstallationError(msg) from error
    else:
        return {
            "owner": owner,
            "repo": repo,
            "app_name": app_name,
        }


def extract_github_config(
    effective_config: dict[str, Any],
) -> tuple[str, str, bool]:
    """Extract GitHub repository configuration from effective config.

    Args:
        effective_config: Effective app configuration dictionary

    Returns:
        Tuple containing:
            - owner: Repository owner
            - repo: Repository name
            - prerelease: Whether to use prereleases

    Examples:
        >>> config = {
        ...     "source": {
        ...         "owner": "AppFlowy-IO",
        ...         "repo": "AppFlowy",
        ...         "prerelease": False
        ...     }
        ... }
        >>> extract_github_config(config)
        ('AppFlowy-IO', 'AppFlowy', False)

    """
    source_config = effective_config.get("source", {})
    owner = source_config.get("owner", "unknown")
    repo = source_config.get("repo", "unknown")
    prerelease = source_config.get("prerelease", False)

    return owner, repo, prerelease
