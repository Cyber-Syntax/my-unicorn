"""Target resolution for installation workflows.

This module provides functionality to separate mixed installation targets
(URLs and catalog names) into their respective categories.
"""

from my_unicorn.config.config import ConfigManager
from my_unicorn.constants import ERROR_UNKNOWN_APPS_OR_URLS
from my_unicorn.exceptions import InstallationError


class TargetResolver:
    """Resolves installation targets into URLs and catalog names."""

    @staticmethod
    def separate_targets(
        config_manager: ConfigManager, targets: list[str]
    ) -> tuple[list[str], list[str]]:
        """Separate targets into URL and catalog targets.

        This is a helper for CLI code and tests to reuse the same logic
        for categorizing installation targets.

        Args:
            config_manager: Configuration manager instance
            targets: List of mixed targets (URLs or catalog names)

        Returns:
            Tuple of (url_targets, catalog_targets)

        Raises:
            InstallationError: If unknown targets are present

        """
        url_targets: list[str] = []
        catalog_targets: list[str] = []
        unknown_targets: list[str] = []

        available_apps = set(config_manager.list_catalog_apps())

        for target in targets:
            if target.startswith("https://github.com/"):
                url_targets.append(target)
            elif target in available_apps:
                catalog_targets.append(target)
            else:
                unknown_targets.append(target)

        if unknown_targets:
            unknown_list = ", ".join(unknown_targets)
            msg = ERROR_UNKNOWN_APPS_OR_URLS.format(targets=unknown_list)
            raise InstallationError(msg)

        return url_targets, catalog_targets
