"""GitHub configuration service for unified config extraction and validation.

This module provides a validated GitHub configuration dataclass and
helper function to consolidate config extraction and validation logic
used across install and update workflows.
"""

from dataclasses import dataclass
from typing import Any

from my_unicorn.config.validation import ConfigurationValidator
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GitHubConfig:
    """Validated GitHub repository configuration.

    This dataclass represents a validated GitHub configuration
    extracted from application configuration.

    Attributes:
        owner: GitHub repository owner/organization
        repo: GitHub repository name
        prerelease: Whether to use prerelease versions

    """

    owner: str
    repo: str
    prerelease: bool = False


def get_github_config(app_config: dict[str, Any]) -> GitHubConfig:
    """Extract and validate GitHub configuration from app config.

    This function consolidates the pattern of extracting GitHub config
    and validating it for security, eliminating duplicate code across
    install and update workflows.

    Args:
        app_config: Application configuration dictionary

    Returns:
        GitHubConfig: Validated configuration object

    Raises:
        ValueError: If GitHub identifiers are invalid or missing

    Examples:
        >>> config = {
        ...     "source": {
        ...         "owner": "AppFlowy-IO",
        ...         "repo": "AppFlowy",
        ...         "prerelease": False
        ...     }
        ... }
        >>> github_config = get_github_config(config)
        >>> github_config.owner
        'AppFlowy-IO'

    """
    owner, repo, prerelease = extract_github_config(app_config)
    # Validate the config structure (includes GitHub identifier validation)
    ConfigurationValidator.validate_app_config(app_config)
    return GitHubConfig(owner=owner, repo=repo, prerelease=prerelease)


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
