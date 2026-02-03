"""Update application service for orchestrating update workflows.

This service extracts business logic from UpdateHandler to follow
Clean Architecture. It orchestrates the complete update workflow including:
- Target app resolution
- Update checking
- Filtering apps needing updates
- Progress management
- Update execution
"""

from my_unicorn.config import ConfigManager
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
    github_api_progress_task,
)
from my_unicorn.core.workflows.update import UpdateInfo, UpdateManager
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


class UpdateApplicationService:
    """Application service for updating AppImages.

    This service follows Clean Architecture principles:
    - Owns business workflow orchestration
    - Manages progress lifecycle
    - Returns structured data without side effects
    - Testable in isolation
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        update_manager: UpdateManager,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        """Initialize update application service.

        Args:
            config_manager: Configuration manager
            update_manager: Update manager (domain service)
            progress_reporter: Optional progress reporter for tracking

        """
        self.config_manager = config_manager
        self.update_manager = update_manager
        self.progress_reporter = progress_reporter or NullProgressReporter()

    def _validate_app_names(
        self, app_names: list[str] | None
    ) -> tuple[list[str], list[str]]:
        """Validate and resolve app names.

        Args:
            app_names: Specific apps to check, or None for all

        Returns:
            Tuple of (valid_apps, invalid_apps)

        """
        installed_apps = self.config_manager.list_installed_apps()

        if not app_names:
            return installed_apps, []

        valid = []
        invalid = []
        for name in app_names:
            matches = [app for app in installed_apps if name in app]
            if matches:
                valid.extend(matches)
            else:
                invalid.append(name)

        return list(set(valid)), invalid

    async def check_updates(
        self,
        app_names: list[str] | None = None,
        *,
        refresh_cache: bool = False,
    ) -> list[UpdateInfo]:
        """Check for updates without installing.

        Args:
            app_names: Specific apps to check, or None for all
            refresh_cache: Whether to bypass cache

        Returns:
            List of UpdateInfo objects

        """
        # Delegate to update manager
        return await self.update_manager.check_updates(
            app_names=app_names,
            refresh_cache=refresh_cache,
        )

    async def update(
        self,
        app_names: list[str] | None = None,
        *,
        refresh_cache: bool = False,
        force: bool = False,
    ) -> tuple[list[str], list[str], list[str], list[UpdateInfo]]:
        """Execute update workflow.

        Args:
            app_names: Specific apps to update, or None for all
            refresh_cache: Whether to bypass cache
            force: Force update even if no new version available

        Returns:
            Tuple of (updated_apps, failed_apps, up_to_date_apps, update_infos)

        """
        # Check for updates first
        update_infos = await self.update_manager.check_updates(
            app_names=app_names,
            refresh_cache=refresh_cache,
        )

        if not update_infos:
            return [], [], [], []

        # Filter apps needing updates
        apps_to_update = [
            info.app_name for info in update_infos if info.has_update or force
        ]

        if not apps_to_update:
            # All up to date
            up_to_date = [info.app_name for info in update_infos]
            return [], [], up_to_date, update_infos

        # Execute updates with progress management
        async with github_api_progress_task(
            self.progress_reporter,
            task_name="GitHub Releases",
            total=len(apps_to_update),
        ) as api_task_id:
            # Execute updates with proper dependency injection
            (
                update_results,
                error_reasons,
            ) = await self.update_manager.update_multiple_apps(
                apps_to_update,
                force=force,
                update_infos=update_infos,
                api_task_id=api_task_id,
            )

        # Process results
        updated_apps = [
            app for app, success in update_results.items() if success
        ]
        failed_apps = [
            app for app, success in update_results.items() if not success
        ]
        up_to_date_apps = [
            info.app_name
            for info in update_infos
            if not info.has_update and not force
        ]

        # Attach error reasons to UpdateInfo objects
        for info in update_infos:
            if info.app_name in error_reasons:
                info.error_reason = error_reasons[info.app_name]

        return updated_apps, failed_apps, up_to_date_apps, update_infos

    async def check_for_updates(
        self,
        app_names: list[str] | None = None,
        *,
        refresh_cache: bool = False,
    ) -> dict:
        """Check for available updates with validation.

        Args:
            app_names: Specific apps to check, or None for all
            refresh_cache: Whether to bypass cache

        Returns:
            Dictionary with:
                available_updates: List of dicts with update info
                up_to_date: List of app names that are current
                invalid_apps: List of app names not found

        """
        valid_apps, invalid_apps = self._validate_app_names(app_names)

        if not valid_apps:
            return {
                "available_updates": [],
                "up_to_date": [],
                "invalid_apps": invalid_apps,
            }

        update_infos = await self.update_manager.check_updates(
            app_names=valid_apps,
            refresh_cache=refresh_cache,
        )

        available = [info for info in update_infos if info.has_update]
        up_to_date = [
            info.app_name for info in update_infos if not info.has_update
        ]

        return {
            "available_updates": [
                {
                    "app_name": info.app_name,
                    "current_version": info.current_version,
                    "latest_version": info.latest_version,
                }
                for info in available
            ],
            "up_to_date": up_to_date,
            "invalid_apps": invalid_apps,
        }

    async def perform_updates(
        self,
        app_names: list[str] | None = None,
        *,
        refresh_cache: bool = False,
        force: bool = False,
    ) -> dict:
        """Perform updates on apps with validation.

        Args:
            app_names: Specific apps to update, or None for all
            refresh_cache: Whether to bypass cache
            force: Force update even if no new version

        Returns:
            Dictionary with:
                updated: List of successfully updated app names
                failed: List of failed app names
                up_to_date: List of apps that didn't need updates
                invalid_apps: List of app names not found
                update_infos: List of UpdateInfo objects

        """
        valid_apps, invalid_apps = self._validate_app_names(app_names)

        if not valid_apps:
            return {
                "updated": [],
                "failed": [],
                "up_to_date": [],
                "invalid_apps": invalid_apps,
                "update_infos": [],
            }

        # Use existing update method
        (
            updated_apps,
            failed_apps,
            up_to_date_apps,
            update_infos,
        ) = await self.update(
            app_names=valid_apps,
            refresh_cache=refresh_cache,
            force=force,
        )

        return {
            "updated": updated_apps,
            "failed": failed_apps,
            "up_to_date": up_to_date_apps,
            "invalid_apps": invalid_apps,
            "update_infos": update_infos,
        }
