"""Concrete install template implementations.

This module provides concrete Template Method implementations for different install types.
"""

from typing import Any

from .install_template import InstallTemplate
from .operations import CatalogInstallOperation, URLInstallOperation
from .selectors import (
    CatalogAppSelector,
    CatalogInstallContext,
    URLAppSelector,
    URLInstallContext,
)


class CatalogInstallTemplate(InstallTemplate):
    """Template method implementation for catalog-based installations."""

    def __init__(
        self,
        selector: CatalogAppSelector,
        operation: CatalogInstallOperation,
        **kwargs: Any,
    ) -> None:
        """Initialize catalog install template.

        Args:
            selector: Catalog app selector
            operation: Catalog install operation
            **kwargs: Arguments passed to parent class

        """
        super().__init__(**kwargs)
        self.selector = selector
        self.operation = operation

    def validate_inputs(self, targets: list[str], **kwargs: Any) -> None:
        """Validate inputs using catalog-specific validation."""
        super().validate_inputs(targets, **kwargs)
        self.selector.validate_targets(targets)

    async def _prepare_installation_contexts(
        self, targets: list[str], **kwargs: Any
    ) -> list[CatalogInstallContext]:
        """Prepare catalog installation contexts."""
        contexts = []
        for target in targets:
            context = await self.selector.resolve_app_context(target, **kwargs)
            contexts.append(context)
        return contexts

    async def _create_app_configuration(
        self,
        app_path: Any,
        context: CatalogInstallContext,
        icon_result: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create catalog-specific app configuration."""
        return await self.operation.create_app_config(app_path, context, icon_result, **kwargs)


class URLInstallTemplate(InstallTemplate):
    """Template method implementation for URL-based installations."""

    def __init__(
        self,
        selector: URLAppSelector,
        operation: URLInstallOperation,
        **kwargs: Any,
    ) -> None:
        """Initialize URL install template.

        Args:
            selector: URL app selector
            operation: URL install operation
            **kwargs: Arguments passed to parent class

        """
        super().__init__(**kwargs)
        self.selector = selector
        self.operation = operation

    def validate_inputs(self, targets: list[str], **kwargs: Any) -> None:
        """Validate inputs using URL-specific validation."""
        super().validate_inputs(targets, **kwargs)
        self.selector.validate_targets(targets)

    async def _prepare_installation_contexts(
        self, targets: list[str], **kwargs: Any
    ) -> list[URLInstallContext]:
        """Prepare URL installation contexts."""
        contexts = []
        for target in targets:
            context = await self.selector.resolve_app_context(target, **kwargs)
            contexts.append(context)
        return contexts

    async def _create_app_configuration(
        self,
        app_path: Any,
        context: URLInstallContext,
        icon_result: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create URL-specific app configuration."""
        return await self.operation.create_app_config(app_path, context, icon_result, **kwargs)
