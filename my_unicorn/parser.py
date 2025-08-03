"""Simple GitHub URL parser for my-unicorn CLI.

This module provides a clean interface for parsing GitHub URLs to extract
owner and repository information. It keeps things simple and focused.
"""

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ParsedURL:
    """Represents a parsed GitHub URL with owner and repo."""

    url: str
    owner: str
    repo: str

    @classmethod
    def from_url(cls, url: str) -> "ParsedURL":
        """Create ParsedURL from a GitHub URL.

        Args:
            url: GitHub URL to parse

        Returns:
            ParsedURL instance

        Raises:
            ValueError: If URL format is invalid

        """
        if not url:
            raise ValueError("URL cannot be empty")

        # Normalize URL
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        if not url.startswith("https://github.com/"):
            raise ValueError("Must be a GitHub URL (https://github.com/owner/repo)")

        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip("/").split("/")

            if len(path_parts) < 2:
                raise ValueError(
                    "Invalid GitHub URL format. Expected: https://github.com/owner/repo"
                )

            owner = path_parts[0]
            repo = path_parts[1]

            if not owner or not repo:
                raise ValueError("Owner and repository name cannot be empty")

            return cls(url=url, owner=owner, repo=repo)

        except Exception as e:
            raise ValueError(f"Failed to parse GitHub URL: {e}") from e

    def to_repo_string(self) -> str:
        """Get owner/repo format string."""
        return f"{self.owner}/{self.repo}"


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse GitHub URL and return owner, repo tuple.

    Args:
        url: GitHub URL to parse

    Returns:
        Tuple of (owner, repo)

    Raises:
        ValueError: If URL format is invalid

    """
    parsed = ParsedURL.from_url(url)
    return parsed.owner, parsed.repo


def is_github_url(text: str) -> bool:
    """Check if text looks like a GitHub URL.

    Args:
        text: Text to check

    Returns:
        True if text appears to be a GitHub URL

    """
    text = text.strip()
    return (
        text.startswith("https://github.com/")
        or text.startswith("http://github.com/")
        or text.startswith("github.com/")
    )


def validate_github_url(url: str) -> tuple[bool, str]:
    """Validate GitHub URL format.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, error_message)

    """
    try:
        parse_github_url(url)
        return True, ""
    except ValueError as e:
        return False, str(e)
