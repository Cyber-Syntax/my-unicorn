"""Update command handler for my-unicorn CLI.

This module handles the updating of installed AppImages using the Strategy pattern
to provide clean separation of different update scenarios.
"""

from argparse import Namespace

from ..logger import get_logger
from ..models import UpdateContext, UpdateResultDisplay
from .base import BaseCommandHandler

logger = get_logger(__name__)


class UpdateHandler(BaseCommandHandler):
    """Handler for update command operations.

    This class follows the Command pattern and uses the Strategy pattern
    to delegate different update scenarios to appropriate strategy classes.
    """

    async def execute(self, args: Namespace) -> None:
        """Execute the update command using appropriate strategy.

        Args:
            args: Parsed command-line arguments containing update parameters

        """
        try:
            # Create context object with all required dependencies and data
            context = self._build_context(args)

            # Select and create the appropriate strategy
            # strategy = UpdateStrategyFactory.create_strategy(context)
            from ..template import UpdateTemplateFactory
            strategy = UpdateTemplateFactory.create_template(context)

            # Log the selected strategy for debugging
            strategy_name = UpdateTemplateFactory.get_template_name(context)
            logger.debug("Selected strategy: %s", strategy_name)

            # Validate inputs using the strategy's validation logic
            # if not strategy.validate_inputs(context):
            #     return

            # Execute the strategy - only use progress session for actual updates, not check-only
            if context.check_only:
                result = await strategy.execute(context)
            else:
                # For update operations, the strategy will determine if progress UI is needed
                result = await strategy.execute(context)

            # Display results using consistent formatting
            UpdateResultDisplay.display_summary(result)

            # Log final result for debugging
            logger.debug("Update operation completed: %s", result.message)

        except Exception as e:
            logger.error("Update command failed: %s", e)
            UpdateResultDisplay.display_error(f"Update operation failed: {e}")

    def _build_context(self, args: Namespace) -> UpdateContext:
        """Build the context object from command arguments.

        Args:
            args: Parsed command-line arguments

        Returns:
            UpdateContext object with all required dependencies and data

        """
        # Parse and expand app names if provided
        app_names = None
        if args.apps:
            app_names = self._parse_app_names(args.apps)

        return UpdateContext(
            app_names=app_names,
            check_only=getattr(args, "check_only", False),
            refresh_cache=getattr(args, "refresh_cache", False),
            config_manager=self.config_manager,
            update_manager=self.update_manager,
        )

    def _parse_app_names(self, app_args: list[str]) -> list[str]:
        """Parse app names from command arguments, handling comma-separated values.

        Args:
            app_args: Raw app arguments from command line

        Returns:
            List of parsed and cleaned app names

        """
        return self._expand_comma_separated_targets(app_args)
