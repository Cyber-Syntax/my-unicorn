"""Installation state checking for workflow planning.

This module provides functionality to determine which applications
actually need installation work based on their current state.
"""

from pathlib import Path

from my_unicorn.config.config import ConfigManager
from my_unicorn.types import InstallPlan


class InstallStateChecker:
    """Checks which apps need installation work."""

    async def get_apps_needing_installation(
        self,
        config_manager: ConfigManager,
        url_targets: list[str],
        catalog_targets: list[str],
        force: bool,
    ) -> InstallPlan:
        """Check which apps actually need installation work.

        Args:
            config_manager: Configuration manager instance
            url_targets: List of URL targets
            catalog_targets: List of catalog targets
            force: Force installation even if already installed

        Returns:
            InstallPlan with categorized targets

        """
        # All URLs need work by default
        urls_needing_work: list[str] = list(url_targets)
        catalog_needing_work: list[str] = []
        already_installed: list[str] = []

        for app_name in catalog_targets:
            try:
                # Check if app exists in catalog
                try:
                    config_manager.load_catalog(app_name)
                except (FileNotFoundError, ValueError):
                    catalog_needing_work.append(app_name)
                    continue

                if not force:
                    # Check if app is already installed
                    try:
                        installed_config = config_manager.load_app_config(
                            app_name
                        )
                        if installed_config:
                            installed_path = Path(
                                installed_config.get("installed_path", "")
                            )
                            if installed_path.exists():
                                already_installed.append(app_name)
                                continue
                    except (FileNotFoundError, KeyError):
                        # Not installed, needs work
                        pass

                catalog_needing_work.append(app_name)
            except Exception:
                # If we can't determine the status, assume it needs work
                catalog_needing_work.append(app_name)

        return InstallPlan(
            urls_needing_work=urls_needing_work,
            catalog_needing_work=catalog_needing_work,
            already_installed=already_installed,
        )
