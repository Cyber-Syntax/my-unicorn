"""Update workflow orchestration.

This module contains workflow functions for single and multiple app updates,
including progress tracking and error handling.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.constants import VERSION_UNKNOWN
from my_unicorn.core.download import DownloadService
from my_unicorn.core.post_download import OperationType, PostDownloadContext
from my_unicorn.core.protocols.progress import ProgressReporter
from my_unicorn.core.update.info import UpdateInfo
from my_unicorn.exceptions import UpdateError, VerificationError
from my_unicorn.logger import get_logger
from my_unicorn.utils.download_utils import extract_filename_from_url

logger = get_logger(__name__)


async def update_cached_progress(
    app_name: str,
    shared_api_task_id: str | None,
    progress_reporter: ProgressReporter,
) -> None:
    """Update progress for cached update info.

    Args:
        app_name: Name of the app being processed
        shared_api_task_id: Shared API task ID for progress tracking
        progress_reporter: Progress reporter instance

    """
    if not shared_api_task_id:
        return

    # Null object pattern: no need for None check on progress_reporter
    if not progress_reporter.is_active():
        return

    try:
        task_info = progress_reporter.get_task_info(shared_api_task_id)
        if not task_info:
            return

        completed = task_info.get("completed", 0)
        total_value = task_info.get("total")
        new_completed = int(completed) + 1
        total = (
            int(total_value)
            if total_value and total_value > 0
            else new_completed
        )
        await progress_reporter.update_task(
            shared_api_task_id,
            completed=float(new_completed),
            description=(
                f"🌐 Retrieved {app_name} (cached) ({new_completed}/{total})"
            ),
        )
    except Exception as e:
        logger.debug(
            "Progress update failed for %s: %s",
            app_name,
            e,
            exc_info=True,
        )


async def update_single_app(
    app_name: str,
    session: aiohttp.ClientSession,
    force: bool,
    update_info: UpdateInfo | None,
    global_config: dict[str, Any],
    prepare_context_func: callable,
    backup_service: object,
    post_download_processor: object,
) -> tuple[bool, str | None]:
    """Update a single app using direct parameter passing.

    Args:
        app_name: Name of the app to update
        session: aiohttp session
        force: Force update even if no new version available
        update_info: Optional pre-fetched update info with cached release data
        global_config: Global configuration dictionary
        prepare_context_func: Function to prepare update context
        backup_service: Backup service instance
        post_download_processor: Post-download processor instance

    Returns:
        Tuple of (success status, error reason or None)

    Raises:
        UpdateError: If update fails (download, verification, processing)
        VerificationError: If hash verification fails

    """
    try:
        # Prepare update context
        context, error = await prepare_context_func(
            app_name, session, force, update_info
        )
        if error or context is None:
            return False, error
        if context.get("skip"):
            return True, None

        # Extract from context with runtime type checking
        app_config = context["app_config"]
        update_info_raw = context.get("update_info")
        if not isinstance(update_info_raw, UpdateInfo):
            msg = "Invalid update context: missing or invalid UpdateInfo"
            return False, msg
        update_info = update_info_raw
        appimage_asset = context["appimage_asset"]

        # Setup paths
        storage_dir = Path(global_config["directory"]["storage"])
        download_dir = Path(global_config["directory"]["download"])

        # Get download path
        filename = extract_filename_from_url(
            appimage_asset.browser_download_url
        )
        download_path = download_dir / filename

        # Backup current version
        installed_path_str = app_config.get("state", {}).get(
            "installed_path", ""
        )
        current_appimage_path = (
            Path(installed_path_str)
            if installed_path_str
            else storage_dir / f"{app_name}.AppImage"
        )
        if current_appimage_path.exists():
            backup_path = backup_service.create_backup(
                current_appimage_path,
                app_name,
                update_info.current_version,
            )
            if backup_path:
                logger.debug("Backup created: %s", backup_path)

        # Download AppImage
        download_service = DownloadService(
            session, post_download_processor.progress_reporter
        )
        downloaded_path = await download_service.download_appimage(
            appimage_asset, download_path
        )
        if not downloaded_path:
            raise UpdateError(
                message="Download failed",
                context={
                    "app_name": app_name,
                    "download_url": appimage_asset.browser_download_url,
                },
            )

        # release_data is guaranteed to exist at this point
        if update_info.release_data is None:
            raise UpdateError(
                message="release_data must be available",
                context={"app_name": app_name},
            )

        # Create processing context
        post_context = PostDownloadContext(
            app_name=app_name,
            downloaded_path=downloaded_path,
            asset=appimage_asset,
            release=update_info.release_data,
            app_config=app_config,
            catalog_entry=context["catalog_entry"],
            operation_type=OperationType.UPDATE,
            owner=context["owner"],
            repo=context["repo"],
            verify_downloads=True,  # Always verify updates
            source="catalog" if context.get("catalog_entry") else "url",
        )

        # Process download
        result = await post_download_processor.process(post_context)

        if result.success:
            logger.debug(
                "✅ Successfully updated %s to %s",
                app_name,
                update_info.latest_version,
            )
            return True, None
        return False, result.error or "Post-download processing failed"

    except (UpdateError, VerificationError) as e:
        # Re-raise domain exceptions as they already have context
        logger.exception("Failed to update %s", app_name)
        return False, str(e)
    except Exception as e:
        # Wrap unexpected exceptions in UpdateError with context
        logger.exception("Failed to update %s", app_name)
        raise UpdateError(
            message=f"Update failed: {e}",
            context={
                "app_name": app_name,
                "force": force,
            },
            cause=e,
        ) from e


async def update_multiple_apps(
    app_names: list[str],
    force: bool,
    update_infos: list[UpdateInfo] | None,
    api_task_id: str | None,
    global_config: dict[str, Any],
    update_single_app_func: callable,
    update_cached_progress_func: callable,
    progress_reporter: ProgressReporter,
) -> tuple[dict[str, bool], dict[str, str]]:
    """Update multiple apps.

    Args:
        app_names: List of app names to update
        force: Force update even if no new version available
        update_infos: Optional pre-fetched update info objects with cached
            release data
        api_task_id: Optional API progress task ID for tracking
        global_config: Global configuration dictionary
        update_single_app_func: Function to update single app
        update_cached_progress_func: Function to update cached progress
        progress_reporter: Progress reporter instance

    Returns:
        Tuple of (success status dict, error reasons dict)
        - success status dict: maps app names to True/False
        - error reasons dict: maps failed app names to error messages

    Note:
        This method catches all exceptions per-app to ensure partial
        success. Individual app failures are captured in the error_reasons
        dict rather than propagating exceptions.

    """
    semaphore = asyncio.Semaphore(global_config["max_concurrent_downloads"])
    results: dict[str, bool] = {}
    error_reasons: dict[str, str] = {}

    # Create lookup map for update infos
    update_info_map: dict[str, UpdateInfo] = {}
    if update_infos:
        update_info_map = {info.app_name: info for info in update_infos}
        logger.debug(
            "Using cached update info for %d apps (eliminates cache re-reads)",
            len(update_info_map),
        )

    async with aiohttp.ClientSession() as session:

        async def update_with_semaphore(
            app_name: str,
        ) -> tuple[str, bool, str | None]:
            cached_info = update_info_map.get(app_name)

            # Update progress for cached data outside semaphore
            if cached_info:
                await update_cached_progress_func(
                    app_name, api_task_id, progress_reporter
                )

            async with semaphore:
                success, error_reason = await update_single_app_func(
                    app_name, session, force, cached_info
                )
                return app_name, success, error_reason

        tasks = [update_with_semaphore(app) for app in app_names]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in task_results:
            if isinstance(result, tuple):
                app_name, success, error_reason = result
                results[app_name] = success
                if not success and error_reason:
                    error_reasons[app_name] = error_reason
            elif isinstance(result, Exception):
                logger.error("Update task failed: %s", result)
                error_reasons[VERSION_UNKNOWN] = f"Task failed: {result}"

    return results, error_reasons
