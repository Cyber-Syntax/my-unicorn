"""Install template base class using Template Method pattern.

This module provides the template method implementation for install operations,
defining the common algorithm skeleton while allowing strategy-specific variations.
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from ...logger import get_logger
from ...models import InstallationError, ProgressTracker

logger = get_logger(__name__)


class InstallTemplate(ABC):
    """Template method for install operations with common algorithm skeleton."""

    def __init__(
        self,
        download_service: Any,
        storage_service: Any,
        session: Any,
        config_manager: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize install template with shared services.

        Args:
            download_service: Service for downloading files
            storage_service: Service for file storage operations
            session: aiohttp session for HTTP requests
            config_manager: Configuration manager for app configs
            **kwargs: Additional keyword arguments

        """
        self.download_service = download_service
        self.storage_service = storage_service
        self.session = session
        self.config_manager = config_manager

        # Initialize progress tracker
        progress_service = getattr(download_service, "progress_service", None)
        self.progress_tracker = ProgressTracker(progress_service)

        # Global configuration access
        from ...config import ConfigManager

        global_config_manager = ConfigManager()
        self.global_config = global_config_manager.load_global_config()

    def validate_inputs(self, targets: list[str], **kwargs: Any) -> None:
        """Validate input parameters (common validation)."""
        if not targets:
            raise InstallationError("No installation targets provided")

    @asynccontextmanager
    async def _setup_progress_session(self, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        """Set up progress session for the installation operation."""
        show_progress = kwargs.get("show_progress", True)

        if (
            show_progress
            and hasattr(self.download_service, "progress_service")
            and self.download_service.progress_service
            and self.download_service.progress_service.is_active()
        ):
            # Calculate total operations (each app: download, verify, icon, config)
            targets_count = kwargs.get("targets_count", 0)
            total_operations = targets_count * 4
            async with self.download_service.progress_service.session(total_operations):
                yield {"session_active": True}
        else:
            yield {"session_active": False}

    async def install(self, targets: list[str], **kwargs: Any) -> list[dict[str, Any]]:
        """Execute the main template method defining the installation algorithm.

        Args:
            targets: List of installation targets
            **kwargs: Installation options

        Returns:
            List of installation results

        """
        self.validate_inputs(targets, **kwargs)

        # Calculate targets count for progress calculation
        kwargs["targets_count"] = len(targets)

        async with self._setup_progress_session(**kwargs):
            # Template method pattern - define the algorithm skeleton
            contexts = await self._prepare_installation_contexts(targets, **kwargs)
            results = await self._process_installations(contexts, **kwargs)
            return await self._finalize_results(results, **kwargs)

    async def _process_installations(
        self, contexts: list[Any], **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Process all installations with common concurrency pattern."""
        concurrent_limit = kwargs.get(
            "concurrent", self.global_config["max_concurrent_downloads"]
        )
        logger.info("📦 Install template using %d concurrent installations", concurrent_limit)

        semaphore = asyncio.Semaphore(concurrent_limit)
        tasks = [self._install_single_app(semaphore, ctx, **kwargs) for ctx in contexts]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results: list[dict[str, Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "target": getattr(contexts[i], "target", f"target_{i}"),
                        "success": False,
                        "error": str(result),
                        "path": None,
                    }
                )
            elif isinstance(result, dict):
                processed_results.append(result)

        return processed_results

    async def _install_single_app(
        self, semaphore: asyncio.Semaphore, context: Any, **kwargs: Any
    ) -> dict[str, Any]:
        """Install single app with common workflow (template method)."""
        async with semaphore:
            try:
                # Common installation workflow steps
                downloaded_path = await self._download_appimage(context, **kwargs)
                verified_result = await self._verify_appimage(
                    downloaded_path, context, **kwargs
                )
                final_path = await self._move_to_install_directory(
                    downloaded_path, context, **kwargs
                )
                icon_result = await self._extract_icon(final_path, context, **kwargs)
                config_result = await self._create_app_configuration(
                    final_path, context, icon_result, verification_result=verified_result, **kwargs
                )
                desktop_result = await self._create_desktop_entry(
                    final_path, context, config_result, **kwargs
                )

                return await self._build_success_result(
                    context,
                    final_path,
                    verified_result,
                    icon_result,
                    config_result,
                    desktop_result,
                    **kwargs,
                )
            except Exception as error:
                logger.error(
                    "Installation failed for %s: %s",
                    getattr(context, "target", "unknown"),
                    error,
                )
                return await self._build_error_result(context, error, **kwargs)

    # Abstract methods (strategy-specific variations)
    @abstractmethod
    async def _prepare_installation_contexts(
        self, targets: list[str], **kwargs: Any
    ) -> list[Any]:
        """Prepare installation contexts (strategy-specific).

        Args:
            targets: List of installation targets
            **kwargs: Installation options

        Returns:
            List of installation contexts

        """

    @abstractmethod
    async def _create_app_configuration(
        self, app_path: Path, context: Any, icon_result: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        """Create app configuration (strategy-specific).

        Args:
            app_path: Path to installed app
            context: Installation context
            icon_result: Result from icon extraction
            **kwargs: Installation options

        Returns:
            Configuration creation result

        """

    # Common implementation methods (shared across strategies)
    async def _download_appimage(self, context: Any, **kwargs: Any) -> Path:
        """Download AppImage (common implementation)."""
        appimage_asset = getattr(context, "appimage_asset", None)
        download_path = getattr(context, "download_path", None)

        if not appimage_asset or not download_path:
            raise InstallationError("Missing download information in context")

        return await self.download_service.download_appimage(
            appimage_asset,
            download_path,
            show_progress=kwargs.get("show_progress", True),
        )

    async def _verify_appimage(
        self, app_path: Path, context: Any, **kwargs: Any
    ) -> dict[str, Any] | None:
        """Verify AppImage (common implementation)."""
        if not kwargs.get("verify_downloads", True):
            return None

        # Get verification service from context or create it
        verification_service = getattr(self, "_verification_service", None)
        if not verification_service:
            from ...verification.verification_service import VerificationService

            progress_service = getattr(self.download_service, "progress_service", None)
            verification_service = VerificationService(self.download_service, progress_service)
            self._verification_service = verification_service

        # Update progress
        post_processing_task_id = getattr(context, "post_processing_task_id", None)
        await self.progress_tracker.update_progress(
            post_processing_task_id,
            20.0,
            f"🔍 Verifying {getattr(context, 'app_name', 'app')}...",
        )

        # Get required parameters for verification
        app_name = getattr(context, "app_name", app_path.stem)
        appimage_asset = getattr(context, "appimage_asset", {})
        verification_config = getattr(context, "verification_config", {})

        # Get owner/repo info
        if hasattr(context, "owner") and hasattr(context, "repo_name"):
            # URL context
            owner = context.owner
            repo = context.repo_name
            tag_name = getattr(context, "release_data", {}).get("tag_name", "unknown")
        elif hasattr(context, "app_config"):
            # Catalog context
            owner = context.app_config.get("owner", "unknown")
            repo = context.app_config.get("repo", "unknown")
            tag_name = getattr(context, "release_data", {}).get("tag_name", "unknown")
        else:
            # Fallback - skip verification if we don't have enough info
            logger.warning("Skipping verification for %s: insufficient context", app_name)
            return None

        try:
            # Get assets list - needed for verify_file
            assets = getattr(context, "release_data", {}).get("assets", [])

            # Perform verification using the correct method name
            result = await verification_service.verify_file(
                file_path=app_path,
                asset=appimage_asset,
                config=verification_config,
                owner=owner,
                repo=repo,
                tag_name=tag_name,
                app_name=app_name,
                assets=assets,
                progress_task_id=post_processing_task_id,
            )

            await self.progress_tracker.update_progress(
                post_processing_task_id, 40.0, "✅ Verification complete"
            )

            # Convert VerificationResult to dict for consistency
            return {
                "passed": result.passed,
                "methods": result.methods,
                "updated_config": result.updated_config,
            }

        except Exception as error:
            logger.error("Verification failed for %s: %s", app_name, error)
            await self.progress_tracker.update_progress(
                post_processing_task_id, 40.0, "⚠️ Verification skipped due to error"
            )
            return {
                "passed": False,
                "error": str(error),
                "methods": {},
                "updated_config": {},
            }

    async def _move_to_install_directory(
        self, app_path: Path, context: Any, **kwargs: Any
    ) -> Path:
        """Move app to install directory (common implementation)."""
        app_name = getattr(context, "app_name", app_path.stem)

        # Update progress
        post_processing_task_id = getattr(context, "post_processing_task_id", None)
        await self.progress_tracker.update_progress(
            post_processing_task_id, 50.0, f"📁 Moving {app_name} to install directory..."
        )

        final_path = self.storage_service.move_to_install_dir(app_path, app_name)

        await self.progress_tracker.update_progress(
            post_processing_task_id, 60.0, f"📦 {app_name} installed"
        )

        return final_path

    async def _extract_icon(
        self, app_path: Path, context: Any, **kwargs: Any
    ) -> dict[str, Any]:
        """Extract icon (common implementation)."""
        app_name = getattr(context, "app_name", app_path.stem)

        # Update progress
        post_processing_task_id = getattr(context, "post_processing_task_id", None)
        await self.progress_tracker.update_progress(
            post_processing_task_id, 70.0, f"🎨 Extracting icon for {app_name}..."
        )

        # Get icon service
        icon_service = getattr(self, "_icon_service", None)
        if not icon_service:
            from ...services.icon_service import IconService

            progress_service = getattr(self.download_service, "progress_service", None)
            icon_service = IconService(self.download_service, progress_service)
            self._icon_service = icon_service

        # Get icon configuration from context
        icon_extraction_enabled = kwargs.get("extract_icon", True)
        icon_url = getattr(context, "icon_url", None)

        # Create icon config
        from ...services.icon_service import IconConfig

        icon_config = IconConfig(
            extraction_enabled=icon_extraction_enabled,
            icon_url=icon_url,
            icon_filename=f"{app_name}.png",
        )

        # Get icon directory (where to save icons)
        icon_dir = getattr(
            self.storage_service, "icon_dir", Path.home() / ".local/share/icons"
        )

        # Get catalog entry if available
        catalog_entry = getattr(context, "app_config", None)

        # Extract icon
        icon_result = await icon_service.acquire_icon(
            icon_config=icon_config,
            app_name=app_name,
            icon_dir=icon_dir,
            appimage_path=app_path,
            catalog_entry=catalog_entry,
            progress_task_id=post_processing_task_id,
        )

        await self.progress_tracker.update_progress(
            post_processing_task_id, 80.0, f"🎨 Icon extracted for {app_name}"
        )

        # Convert IconResult to dict for consistency
        return {
            "icon_path": str(icon_result.icon_path) if icon_result.icon_path else None,
            "source": icon_result.source,
            "config": icon_result.config,
        }

    async def _create_desktop_entry(
        self, app_path: Path, context: Any, config_result: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        """Create desktop entry (common implementation)."""
        app_name = getattr(context, "app_name", app_path.stem)

        # Update progress
        post_processing_task_id = getattr(context, "post_processing_task_id", None)
        await self.progress_tracker.update_progress(
            post_processing_task_id, 90.0, f"🖥️ Creating desktop entry for {app_name}..."
        )

        # Create desktop entry using desktop module function
        try:
            from ...desktop import create_desktop_entry_for_app

            # Get icon path from config_result if available
            icon_path_str = config_result.get("config", {}).get("icon")
            icon_path = Path(icon_path_str) if icon_path_str else None

            # Get app description and categories
            app_config = getattr(context, "app_config", {})
            comment = app_config.get("description", "")
            categories = app_config.get("categories", [])

            desktop_path = create_desktop_entry_for_app(
                app_name=app_name,
                appimage_path=app_path,
                icon_path=icon_path,
                comment=comment,
                categories=categories,
                config_manager=self.config_manager,
            )
            result = {"success": True, "desktop_path": str(desktop_path)}
        except Exception as error:
            logger.warning("Failed to create desktop entry for %s: %s", app_name, error)
            result = {"success": False, "error": str(error)}

        await self.progress_tracker.update_progress(
            post_processing_task_id, 95.0, f"🖥️ Desktop entry for {app_name}"
        )

        return result

    async def _build_success_result(
        self,
        context: Any,
        final_path: Path,
        verified_result: dict[str, Any] | None,
        icon_result: dict[str, Any],
        config_result: dict[str, Any],
        desktop_result: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build success result (common structure)."""
        app_name = getattr(context, "app_name", final_path.stem)
        target = getattr(context, "target", app_name)

        # Finish progress
        post_processing_task_id = getattr(context, "post_processing_task_id", None)
        await self.progress_tracker.update_progress(
            post_processing_task_id, 100.0, f"✅ {app_name} installation complete"
        )

        return {
            "target": target,
            "success": True,
            "path": str(final_path),
            "name": app_name,
            "verification": verified_result,
            "icon": icon_result,
            "config": config_result,
            "desktop": desktop_result,
        }

    async def _build_error_result(
        self, context: Any, error: Exception, **kwargs: Any
    ) -> dict[str, Any]:
        """Build error result (common structure)."""
        target = getattr(context, "target", "unknown")
        app_name = getattr(context, "app_name", target)

        # Finish progress with error
        post_processing_task_id = getattr(context, "post_processing_task_id", None)
        if post_processing_task_id and hasattr(self.download_service, "progress_service"):
            progress_service = self.download_service.progress_service
            if progress_service and progress_service.is_active():
                await progress_service.finish_task(post_processing_task_id, success=False)

        return {
            "target": target,
            "success": False,
            "error": str(error),
            "path": None,
            "name": app_name,
        }

    async def _finalize_results(
        self, results: list[dict[str, Any]], **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Finalize results (common processing)."""
        # Log summary
        successful = sum(1 for r in results if r.get("success", False))
        total = len(results)
        logger.info("📊 Installation complete: %d/%d successful", successful, total)

        return results
