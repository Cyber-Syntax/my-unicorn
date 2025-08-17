"""Factory for creating appropriate update strategies.

This module provides a factory for selecting and creating the appropriate
update strategy based on the given context and parameters.
"""

from ..logger import get_logger
from .check_only_update_strategy import CheckOnlyUpdateStrategy
from .update_all_apps_strategy import UpdateAllAppsStrategy
from .update_specific_apps_strategy import UpdateSpecificAppsStrategy
from .update_strategy import UpdateContext, UpdateStrategy

logger = get_logger(__name__)


class UpdateStrategyFactory:
    """Factory class for creating update strategies.

    This factory follows the Factory pattern to encapsulate the logic
    for selecting the appropriate update strategy based on the context.
    """

    @staticmethod
    def create_strategy(context: UpdateContext) -> UpdateStrategy:
        """Create the appropriate update strategy based on context.

        Args:
            context: Update context containing configuration and parameters

        Returns:
            The appropriate UpdateStrategy instance

        Raises:
            ValueError: If the context parameters don't match any known strategy

        """
        if context.check_only:
            logger.debug("Creating CheckOnlyUpdateStrategy")
            return CheckOnlyUpdateStrategy()

        if context.app_names:
            logger.debug(f"Creating UpdateSpecificAppsStrategy for apps: {context.app_names}")
            return UpdateSpecificAppsStrategy()

        logger.debug("Creating UpdateAllAppsStrategy")
        return UpdateAllAppsStrategy()

    @staticmethod
    def get_strategy_name(context: UpdateContext) -> str:
        """Get the name of the strategy that would be created for the given context.

        Args:
            context: Update context to analyze

        Returns:
            Human-readable name of the strategy

        """
        if context.check_only:
            return "Check Only"

        if context.app_names:
            return f"Update Specific Apps ({len(context.app_names)} app(s))"

        return "Update All Apps"
