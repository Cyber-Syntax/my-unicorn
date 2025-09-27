"""Factory for creating appropriate update templates.

This module provides a factory for selecting and creating the appropriate
update template based on the given context and parameters.
"""

from ...logger import get_logger
from ...models import UpdateContext
from .operations import CheckOnlyOperation, UpdateActionOperation
from .selectors import AllAppsSelector, SpecificAppsSelector
from .update_template import UpdateTemplate

logger = get_logger(__name__)


class UpdateTemplateFactory:
    """Factory class for creating update templates.

    This factory follows the Factory pattern to encapsulate the logic
    for selecting the appropriate combination of app selector and operation
    based on the context.
    """

    @staticmethod
    def create_template(context: UpdateContext) -> UpdateTemplate:
        """Create the appropriate template based on context.

        Args:
            context: Update context containing configuration and parameters

        Returns:
            The appropriate UpdateTemplate instance with correct selector and operation

        """
        # Select app selector strategy
        if context.app_names:
            logger.debug("Creating SpecificAppsSelector for apps: %s", context.app_names)
            app_selector = SpecificAppsSelector()
        else:
            logger.debug("Creating AllAppsSelector")
            app_selector = AllAppsSelector()

        # Select operation command
        if context.check_only:
            logger.debug("Creating CheckOnlyOperation")
            operation = CheckOnlyOperation()
        else:
            logger.debug("Creating UpdateActionOperation")
            operation = UpdateActionOperation()

        # Create and return the template
        template = UpdateTemplate(app_selector, operation)
        logger.debug(
            "Created UpdateTemplate with %s and %s",
            type(app_selector).__name__,
            type(operation).__name__,
        )

        return template

    @staticmethod
    def get_template_name(context: UpdateContext) -> str:
        """Get the name of the template that would be created for the given context.

        Args:
            context: Update context to analyze

        Returns:
            Human-readable name of the template

        """
        if context.check_only:
            return "Check Only"

        if context.app_names:
            return f"Update Specific Apps ({len(context.app_names)} app(s))"

        return "Update All Apps"
