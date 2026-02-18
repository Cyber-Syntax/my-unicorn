"""Verification execution logic.

This module provides functions for executing verification methods
concurrently and processing results.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from my_unicorn.constants import VerificationMethod
from my_unicorn.core.verification.detection import prioritize_checksum_files
from my_unicorn.core.verification.results import MethodResult
from my_unicorn.core.verification.verification_methods import (
    verify_checksum_file,
    verify_digest,
)
from my_unicorn.logger import get_logger

if TYPE_CHECKING:
    from my_unicorn.core.cache import ReleaseCacheManager
    from my_unicorn.core.download import DownloadService
    from my_unicorn.core.github import ChecksumFileInfo
    from my_unicorn.core.verification.context import VerificationContext

logger = get_logger(__name__, enable_file_logging=True)


async def execute_digest_verification(
    context: VerificationContext,
) -> MethodResult | None:
    """Execute digest verification asynchronously.

    Args:
        context: Verification context

    Returns:
        MethodResult or None if digest not available

    """
    if not context.has_digest or not context.asset.digest:
        return None

    if context.verifier is None:
        logger.error("Verifier not initialized for digest verification")
        return None

    skip_configured = context.config.get("skip", False)
    logger.debug("Attempting digest verification: app=%s", context.app_name)

    digest_result = await verify_digest(
        context.verifier,
        context.asset.digest,
        context.app_name,
        skip_configured,
    )

    if digest_result:
        if digest_result.passed:
            logger.debug(
                "Digest verification passed: app=%s", context.app_name
            )
            logger.info("Digest verification passed for %s", context.app_name)
        else:
            logger.warning(
                "Digest verification failed: app=%s", context.app_name
            )
            logger.info("Digest verification failed for %s", context.app_name)

    return digest_result


async def execute_checksum_file_verification(
    context: VerificationContext,
    checksum_file: ChecksumFileInfo,
    download_service: DownloadService,
    cache_manager: ReleaseCacheManager | None,
) -> MethodResult | None:
    """Execute checksum file verification asynchronously.

    Args:
        context: Verification context
        checksum_file: Checksum file information
        download_service: Service for downloading checksum files
        cache_manager: Optional cache manager

    Returns:
        MethodResult or None if failed

    """
    # Use original asset name for checksum lookups
    original_asset_name = (
        context.asset.name if context.asset.name else context.file_path.name
    )

    logger.debug(
        "Attempting checksum verification with: %s",
        checksum_file.filename,
    )

    if context.verifier is None:
        logger.error("Verifier not initialized for checksum verification")
        return None

    checksum_result = await verify_checksum_file(
        context.verifier,
        checksum_file,
        original_asset_name,
        context.app_name,
        download_service,
        cache_manager,
        context,
    )

    if checksum_result:
        if checksum_result.passed:
            logger.debug(
                "Checksum verification succeeded with: %s",
                checksum_file.filename,
            )
            logger.info(
                "Checksum verification passed for %s using %s",
                context.app_name,
                checksum_file.filename,
            )
        else:
            logger.warning(
                "Checksum verification failed with: %s",
                checksum_file.filename,
            )

    return checksum_result


async def execute_all_verification_methods(
    context: VerificationContext,
    download_service: DownloadService,
    cache_manager: ReleaseCacheManager | None,
) -> None:
    """Execute all available verification methods concurrently.

    This function builds tasks for all available verification methods
    (digest and checksum files) and executes them concurrently using
    asyncio.gather(). All results are stored in context.verification_methods.

    Args:
        context: Verification context (modified in place)
        download_service: Service for downloading checksum files
        cache_manager: Optional cache manager

    """
    tasks: list[tuple[Any, ChecksumFileInfo | None]] = []

    # Add digest verification task if available
    if context.has_digest:
        logger.debug("Adding digest verification to concurrent execution")
        tasks.append((execute_digest_verification(context), None))

    # Add checksum file verification tasks
    if context.checksum_files:
        logger.debug(
            "Checksum file verification available - found %d files",
            len(context.checksum_files),
        )
        for cf in context.checksum_files:
            logger.debug(
                "Available: %s (%s format)",
                cf.filename,
                cf.format_type,
            )

        # Prioritize checksum files and select only the best match (YAGNI)
        original_asset_name = (
            context.asset.name
            if context.asset.name
            else context.file_path.name
        )
        prioritized_files = prioritize_checksum_files(
            context.checksum_files, original_asset_name
        )

        # Use only the highest-priority checksum file (first in list)
        best_checksum_file = prioritized_files[0]
        logger.debug(
            "Selected best checksum file: %s",
            best_checksum_file.filename,
        )
        tasks.append(
            (
                execute_checksum_file_verification(
                    context,
                    best_checksum_file,
                    download_service,
                    cache_manager,
                ),
                best_checksum_file,
            )
        )

    # Execute all tasks concurrently
    if tasks:
        logger.debug(
            "Executing %d verification methods concurrently", len(tasks)
        )

        # Extract just the coroutines for gather
        task_coroutines = []
        checksum_file_map = {}  # Map index to checksum_file

        for idx, (coro, checksum_file) in enumerate(tasks):
            task_coroutines.append(coro)
            if checksum_file is not None:
                checksum_file_map[idx] = checksum_file

        results = await asyncio.gather(
            *task_coroutines, return_exceptions=True
        )

        # Process results
        digest_index = 0 if context.has_digest else -1

        for i, result in enumerate(results):
            # Handle exceptions
            if isinstance(result, BaseException):
                logger.error(
                    "Verification method raised exception: %s", result
                )
                # Record as failed method
                if i == digest_index:
                    method_key = VerificationMethod.DIGEST
                    error_result = MethodResult(
                        passed=False,
                        hash="",
                        details=f"Exception: {result}",
                    )
                else:
                    # Single checksum file - always use "checksum_file" key
                    method_key = "checksum_file"
                    error_result = MethodResult(
                        passed=False,
                        hash="",
                        details=f"Exception: {result}",
                    )
                context.verification_methods[method_key] = (
                    error_result.to_dict()
                )
                continue

            # Skip None results
            if result is None:
                continue

            # Type guard - ensure result is MethodResult
            if not isinstance(result, MethodResult):
                continue

            # Store successful method results
            if i == digest_index:
                # Digest result
                context.verification_methods[VerificationMethod.DIGEST] = (
                    result.to_dict()
                )
                if result.passed and context.updated_config is not None:
                    context.updated_config[VerificationMethod.DIGEST] = True
            else:
                # Single checksum file result - always use "checksum_file" key
                method_key = "checksum_file"
                context.verification_methods[method_key] = result.to_dict()
                if result.passed:
                    # Store the checksum file in config
                    checksum_file = checksum_file_map.get(i)
                    if checksum_file and context.updated_config is not None:
                        context.updated_config["checksum_file"] = (
                            checksum_file.filename
                        )

        logger.debug(
            "Concurrent verification completed: %d methods executed",
            len(context.verification_methods),
        )
