"""Template Method pattern implementation for update operations.

This module defines the base UpdateTemplate class that provides the algorithm skeleton
for all update operations, eliminating code duplication across different update scenarios.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from ...logger import get_logger
from ...models import UpdateContext, UpdateResult
from ...update import UpdateInfo

logger = get_logger(__name__)


class AppSelector(Protocol):
    """Strategy interface for app selection."""

    def select_apps(self, context: UpdateContext) -> list[str]:
        """Select which apps to work with.

        Args:
            context: Update context with configuration and dependencies

        Returns:
            List of app names to process

        """
        ...


class UpdateOperation(Protocol):
    """Command interface for update operations."""

    async def execute(
        self,
        apps: list[str],
        update_infos: list[UpdateInfo],
        context: UpdateContext,
        session_context: "SessionContext",
    ) -> dict[str, bool]:
        """Execute the operation on the specified apps.

        Args:
            apps: List of app names to process
            update_infos: Update information for the apps
            context: Update context with configuration and dependencies
            session_context: Progress session context

        Returns:
            Dictionary mapping app names to success status

        """
        ...


@dataclass
class SessionContext:
    """Encapsulates progress session state."""

    progress_service: Any
    api_task_id: str


class UpdateTemplate:
    """Template method for update operations.

    This class implements the Template Method pattern, defining the algorithm skeleton
    that all update operations follow while allowing specific steps to be customized
    through composition with AppSelector strategies and UpdateOperation commands.
    """

    def __init__(self, app_selector: AppSelector, operation: UpdateOperation):
        """Initialize the template with selector and operation.

        Args:
            app_selector: Strategy for selecting which apps to process
            operation: Command for executing the operation on selected apps

        """
        self.app_selector = app_selector
        self.operation = operation

    def validate_inputs(self, context: UpdateContext) -> bool:
        """Validate inputs for the update template.

        This method delegates validation to the app selector, which knows
        how to validate the specific type of app selection being performed.

        Args:
            context: Update context to validate

        Returns:
            True if inputs are valid, False otherwise

        """
        try:
            # Delegate validation to the app selector
            target_apps = self.app_selector.select_apps(context)
            return len(target_apps) > 0
        except (ValueError, Exception) as e:
            logger.error("Input validation failed: %s", e)
            return False

    async def execute(self, context: UpdateContext) -> UpdateResult:
        """Template method defining the algorithm skeleton.

        This method defines the common algorithm that all update operations follow:
        1. Setup infrastructure (progress session, API tasks)
        2. Select target apps (delegated to strategy)
        3. Check for updates (common logic)
        4. Execute operation (delegated to command)
        5. Process results (common logic)
        6. Cleanup

        Args:
            context: Update context with configuration and dependencies

        Returns:
            UpdateResult with operation results

        """
        logger.debug("Executing update template")

        # 1. Setup infrastructure
        async with self._setup_progress_session(context) as session_context:
            try:
                # 2. Select target apps (delegated to strategy)
                target_apps = self._select_target_apps(context)
                if not target_apps:
                    return self._create_empty_result("No apps to process")

                # 3. Check for updates (common logic)
                update_infos = await self._check_for_updates(
                    target_apps, context, session_context
                )
                if not update_infos:
                    return self._create_empty_result("Failed to check for updates")

                # 4. Execute operation (delegated to command)
                operation_results = await self._execute_operation(
                    target_apps, update_infos, context, session_context
                )

                # 5. Process results (common logic)
                return self._create_final_result(operation_results, update_infos, target_apps)

            except Exception as e:
                await self._handle_error(session_context, e)
                raise

    def _select_target_apps(self, context: UpdateContext) -> list[str]:
        """Delegate app selection to strategy.

        Args:
            context: Update context with configuration

        Returns:
            List of selected app names

        """
        return self.app_selector.select_apps(context)

    async def _execute_operation(
        self,
        apps: list[str],
        update_infos: list[UpdateInfo],
        context: UpdateContext,
        session_context: SessionContext,
    ) -> dict[str, bool]:
        """Delegate operation execution to command.

        Args:
            apps: List of app names to process
            update_infos: Update information for the apps
            context: Update context with configuration
            session_context: Progress session context

        Returns:
            Dictionary mapping app names to success status

        """
        return await self.operation.execute(apps, update_infos, context, session_context)

    @asynccontextmanager
    async def _setup_progress_session(self, context: UpdateContext):
        """Set up progress session and API tasks.

        Centralized progress session management that was previously duplicated
        across all strategy implementations.

        Args:
            context: Update context with configuration

        Yields:
            SessionContext with progress service and API task

        """
        from ...services.progress import get_progress_service, progress_session

        async with progress_session():
            progress_service = get_progress_service()

            # Create shared API progress task
            api_task_id = await progress_service.create_api_fetching_task(
                endpoint="API assets", total_requests=1
            )

            # Set shared task for update manager
            context.update_manager._shared_api_task_id = api_task_id

            session_context = SessionContext(
                progress_service=progress_service, api_task_id=api_task_id
            )

            try:
                yield session_context
                await progress_service.finish_task(api_task_id, success=True)
            except Exception:
                await progress_service.finish_task(api_task_id, success=False)
                raise
            finally:
                # Clean up shared task
                context.update_manager._shared_api_task_id = None

    async def _check_for_updates(
        self, apps: list[str], context: UpdateContext, session_context: SessionContext
    ) -> list[UpdateInfo]:
        """Common update checking logic.

        Centralized update checking that was previously duplicated across strategies.

        Args:
            apps: List of app names to check
            context: Update context with configuration
            session_context: Progress session context

        Returns:
            List of UpdateInfo objects

        """
        logger.debug("Checking for updates for %d apps", len(apps))

        update_infos = await context.update_manager.check_all_updates_with_progress(
            apps, refresh_cache=context.refresh_cache
        )

        return update_infos

    def _create_final_result(
        self,
        operation_results: dict[str, bool],
        update_infos: list[UpdateInfo],
        target_apps: list[str],
    ) -> UpdateResult:
        """Common result processing logic.

        Centralized result processing that was previously duplicated across strategies.

        Args:
            operation_results: Results from operation execution
            update_infos: Update information for all apps
            target_apps: List of target app names

        Returns:
            Final UpdateResult object

        """
        # Categorize results
        updated_apps = [app for app, success in operation_results.items() if success]
        failed_apps = [app for app, success in operation_results.items() if not success]

        # Find apps that were up to date
        apps_with_updates = {info.app_name for info in update_infos if info.has_update}
        up_to_date_apps = [
            info.app_name
            for info in update_infos
            if not info.has_update and info.app_name in target_apps
        ]

        # Generate appropriate message
        updated_count = len(updated_apps)
        failed_count = len(failed_apps)
        total_checked = len(update_infos)

        if updated_count > 0 and failed_count == 0:
            message = f"Successfully processed {updated_count} out of {total_checked} app(s)"
        elif updated_count > 0 and failed_count > 0:
            message = f"Processed {updated_count} app(s), {failed_count} failed out of {total_checked} checked"
        elif failed_count > 0:
            message = f"Failed to process {failed_count} out of {total_checked} app(s)"
        else:
            message = f"All {total_checked} app(s) processed successfully"

        success = len(failed_apps) == 0

        return UpdateResult(
            success=success,
            updated_apps=updated_apps,
            failed_apps=failed_apps,
            up_to_date_apps=up_to_date_apps,
            update_infos=update_infos,
            message=message,
        )

    def _create_empty_result(self, message: str) -> UpdateResult:
        """Create an empty result for edge cases.

        Args:
            message: Descriptive message for the result

        Returns:
            Empty UpdateResult object

        """
        return UpdateResult(
            success=True,
            updated_apps=[],
            failed_apps=[],
            up_to_date_apps=[],
            update_infos=[],
            message=message,
        )

    async def _handle_error(self, session_context: SessionContext, error: Exception) -> None:
        """Handle errors during template execution.

        Args:
            session_context: Progress session context
            error: The exception that occurred

        """
        logger.error("Error during update template execution: %s", error)
        # Error handling is centralized here instead of duplicated across strategies
