"""Configuration validation utilities.

This module centralizes validation logic for application configurations,
particularly GitHub identifiers and other security-critical fields.
"""

from typing import Any

from my_unicorn.utils.validation import validate_github_identifier


class ConfigurationValidator:
    """Validates application configuration data."""

    @staticmethod
    def validate_app_config(config: dict[str, Any]) -> None:
        """Validate app configuration structure and values.

        Currently validates GitHub identifiers for security.
        Additional validation can be added as needed.

        Args:
            config: Application configuration dictionary

        Raises:
            ValueError: If configuration contains invalid values

        """
        # Extract source info from v2 config structure
        source_config = config.get("source", {})
        owner = source_config.get("owner", "")
        repo = source_config.get("repo", "")

        # Validate GitHub identifiers for security
        validate_github_identifier(owner, "GitHub owner")
        validate_github_identifier(repo, "GitHub repo")
