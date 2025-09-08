"""Factory for creating install templates based on target type.

This module provides factory implementation for creating appropriate install templates.
"""

from typing import Any

from ...logger import get_logger
from .operations import CatalogInstallOperation, URLInstallOperation
from .selectors import CatalogAppSelector, URLAppSelector
from .templates import CatalogInstallTemplate, URLInstallTemplate

logger = get_logger(__name__)


class InstallTemplateFactory:
    """Factory for creating install templates based on target type."""

    @staticmethod
    def create_template(install_type: str, **dependencies: Any) -> Any:
        """Create appropriate install template.

        Args:
            install_type: Type of installation ('catalog', 'url')
            **dependencies: Required dependencies for template creation

        Returns:
            Configured install template

        Raises:
            ValueError: If install_type is not supported

        """
        if install_type == "catalog":
            return InstallTemplateFactory._create_catalog_template(**dependencies)
        elif install_type == "url":
            return InstallTemplateFactory._create_url_template(**dependencies)
        else:
            raise ValueError(f"Unsupported install type: {install_type}")

    @staticmethod
    def _create_catalog_template(**dependencies: Any) -> CatalogInstallTemplate:
        """Create catalog install template."""
        # Extract required dependencies
        catalog_manager = dependencies["catalog_manager"]
        github_client = dependencies["github_client"]
        config_manager = dependencies["config_manager"]

        # Create selector and operation
        selector = CatalogAppSelector(catalog_manager, github_client)
        operation = CatalogInstallOperation(config_manager)

        return CatalogInstallTemplate(
            selector=selector,
            operation=operation,
            download_service=dependencies["download_service"],
            storage_service=dependencies["storage_service"],
            session=dependencies["session"],
            config_manager=config_manager,
        )

    @staticmethod
    def _create_url_template(**dependencies: Any) -> URLInstallTemplate:
        """Create URL install template."""
        # Extract required dependencies
        github_client = dependencies["github_client"]
        config_manager = dependencies["config_manager"]

        # Create selector and operation
        selector = URLAppSelector(github_client)
        operation = URLInstallOperation(config_manager)

        return URLInstallTemplate(
            selector=selector,
            operation=operation,
            download_service=dependencies["download_service"],
            storage_service=dependencies["storage_service"],
            session=dependencies["session"],
            config_manager=config_manager,
        )
