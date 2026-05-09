"""Simplified verification service for AppImage integrity checking.

This module provides the main VerificationService that handles file
verification using digest and checksum file methods.

Logging Strategy:
- logger.debug(): Developer debugging (method details, hashes, etc.)
- logger.info(): User-facing verification milestones (for log files)
- logger.warning(): Issues users should know about
- Progress display uses finish_task() only - intermediate percentage updates
  are not shown in the simplified KISS-compliant progress display.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from my_unicorn.constants import (
    CHECKSUM_FILE_SUFFIXES,
    DEFAULT_HASH_TYPE,
    DIGEST_FILE_SUFFIXES,
    SUPPORTED_HASH_ALGORITHMS,
    UNSTABLE_VERSION_KEYWORDS,
    YAML_CHECKSUM_EXTENSIONS,
    YAML_DEFAULT_HASH,
    HashType,
    VerificationMethod,
)
from my_unicorn.core.api import Asset, AssetSelector
from my_unicorn.core.checksum_parser import (
    ChecksumFileResult,
    convert_base64_to_hex,
    detect_hash_type_from_checksum_filename,
    parse_all_checksums,
    parse_checksum_file,
)
from my_unicorn.core.progress.progress_types import (
    ProgressType,
    SubProgressType,
)
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
)
from my_unicorn.exceptions import VerificationError
from my_unicorn.logger import get_logger
from my_unicorn.types import ChecksumFileInfo

if TYPE_CHECKING:
    from pathlib import Path

    from my_unicorn.core.cache import ReleaseCacheManager
    from my_unicorn.core.download import DownloadService


# enable_file_logging so logger.info() calls reach the log file in addition
# to the console, matching the original per-module logging behaviour.
logger = get_logger(__name__, enable_file_logging=True)

BYTES_PER_UNIT = 1024.0

# Files larger than this threshold are hashed in a ThreadPoolExecutor to
# avoid blocking the event loop during CPU-intensive hash computation.
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100 MB


@dataclass(slots=True, frozen=True)
class MethodResult:
    """Result of a single verification method attempt."""

    passed: bool
    hash: str
    details: str
    computed_hash: str | None = None
    url: str | None = None
    hash_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility.

        Returns:
            Dictionary representation of the result.

        """
        result: dict[str, Any] = {
            "passed": self.passed,
            "hash": self.hash,
            "details": self.details,
        }
        if self.computed_hash:
            result["computed_hash"] = self.computed_hash
        if self.url:
            result["url"] = self.url
        if self.hash_type:
            result["hash_type"] = self.hash_type
        return result


@dataclass(slots=True, frozen=True)
class VerificationResult:
    """Result of a verification attempt.

    Attributes:
        passed: Overall verification success status.
        methods: Dictionary of all verification method results.
        updated_config: Configuration updated with verification results.
        warning: Optional warning message for partial verification success.

    """

    passed: bool
    methods: dict[str, Any]
    updated_config: dict[str, Any]
    warning: str | None = None


@dataclass(slots=True, frozen=True)
class VerificationConfig:
    """Verification configuration data."""

    skip: bool = False
    checksum_file: str | None = None
    checksum_hash_type: str = "sha256"
    digest_enabled: bool = False

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> VerificationConfig:
        """Create VerificationConfig from a dictionary.

        Args:
            config: Dictionary with configuration values.

        Returns:
            VerificationConfig instance.

        """
        return cls(
            skip=config.get("skip", False),
            checksum_file=config.get("checksum_file"),
            checksum_hash_type=config.get("checksum_hash_type", "sha256"),
            # VerificationMethod is imported at module level — no local import
            digest_enabled=config.get(VerificationMethod.DIGEST, False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility.

        Returns:
            Dictionary with configuration values.

        """
        return {
            "skip": self.skip,
            "checksum_file": self.checksum_file,
            "checksum_hash_type": self.checksum_hash_type,
            VerificationMethod.DIGEST: self.digest_enabled,
        }


@dataclass(slots=True)
class VerificationContext:
    """Internal context for verification state management.

    Holds mutable state during the verification process to reduce
    parameter passing between the phases of VerificationService.
    """

    file_path: Path
    asset: Asset
    config: dict[str, Any]
    owner: str
    repo: str
    tag_name: str
    app_name: str
    assets: list[Asset] | None
    progress_task_id: Any | None
    # Populated during _prepare_verification
    has_digest: bool = False
    checksum_files: list[ChecksumFileInfo] | None = None
    verifier: Verifier | None = None
    updated_config: dict[str, Any] | None = None
    # Populated during _finalize_verification
    verification_passed: bool = False
    verification_methods: dict[str, Any] = field(default_factory=dict)
    verification_warning: str | None = None

    def __post_init__(self) -> None:
        """Seed updated_config from config so it is never None."""
        # VerificationContext is slots=True but NOT frozen, so normal
        # attribute assignment works here — object.__setattr__ is only
        # required for frozen dataclasses.
        if self.updated_config is None:
            self.updated_config = self.config.copy()


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def build_checksum_url(
    owner: str,
    repo: str,
    tag_name: str,
    checksum_file: str,
) -> str:
    """Build a GitHub release download URL for a checksum file.

    Args:
        owner: Repository owner.
        repo: Repository name.
        tag_name: Release tag name.
        checksum_file: Checksum filename.

    Returns:
        Complete checksum file download URL.

    """
    return (
        f"https://github.com/{owner}/{repo}/releases/download/"
        f"{tag_name}/{checksum_file}"
    )


def resolve_manual_checksum_file(
    manual_checksum_file: str,
    asset: Asset,
    owner: str | None,
    repo: str | None,
    tag_name: str | None,
) -> list[ChecksumFileInfo]:
    """Resolve a manually configured checksum file, expanding any templates.

    Supported template placeholders: ``{version}``, ``{tag}``,
    ``{asset_name}``.

    Args:
        manual_checksum_file: Configured checksum filename (may contain
            template placeholders).
        asset: GitHub asset information.
        owner: Repository owner.
        repo: Repository name.
        tag_name: Release tag name.

    Returns:
        List with a single ChecksumFileInfo, or an empty list when the
        required context (owner/repo/tag_name) is missing.

    """
    resolved_name = manual_checksum_file
    try:
        if "{" in manual_checksum_file and tag_name:
            resolved_name = manual_checksum_file.replace(
                "{version}", tag_name
            ).replace("{tag}", tag_name)
        if (
            "{asset_name}" in resolved_name
            and asset
            and hasattr(asset, "name")
        ):
            resolved_name = resolved_name.replace("{asset_name}", asset.name)
    except Exception:
        resolved_name = manual_checksum_file

    if not (owner and repo and tag_name):
        return []

    url = build_checksum_url(owner, repo, tag_name, resolved_name)
    format_type = (
        "yaml"
        if resolved_name.lower().endswith(YAML_CHECKSUM_EXTENSIONS)
        else "traditional"
    )
    return [
        ChecksumFileInfo(
            filename=resolved_name,
            url=url,
            format_type=format_type,
        )
    ]


class VerificationService:
    """Service for file verification using digest and checksum file methods."""

    def __init__(
        self,
        download_service: DownloadService,
        progress_reporter: ProgressReporter | None = None,
        cache_manager: ReleaseCacheManager | None = None,
    ) -> None:
        """Initialize verification service.

        Args:
            download_service: Service for downloading checksum files.
            progress_reporter: Optional progress reporter for tracking.
            cache_manager: Optional cache manager for storing checksum files.

        """
        self.download_service = download_service
        self.progress_reporter = progress_reporter or NullProgressReporter()
        self.cache_manager = cache_manager

    async def verify_file(
        self,
        file_path: Path,
        asset: Asset,
        config: dict[str, Any],
        owner: str,
        repo: str,
        tag_name: str,
        app_name: str,
        assets: list[Asset] | None = None,
        progress_task_id: Any | None = None,
    ) -> VerificationResult:
        """Perform comprehensive file verification.

        Args:
            file_path: Path to file to verify.
            asset: GitHub asset information.
            config: Verification configuration.
            owner: Repository owner.
            repo: Repository name.
            tag_name: Release tag name.
            app_name: Application name for logging.
            assets: All GitHub release assets (enables auto-detection).
            progress_task_id: Optional progress task ID for tracking.

        Returns:
            VerificationResult with success status and methods used.

        Raises:
            VerificationError: If all available verification methods fail.

        """
        context = VerificationContext(
            file_path=file_path,
            asset=asset,
            config=config,
            owner=owner,
            repo=repo,
            tag_name=tag_name,
            app_name=app_name,
            assets=assets,
            progress_task_id=progress_task_id,
        )

        # Phase 1: Prepare — detect methods, check skip conditions.
        skip_result = await self._prepare_verification(context)
        if skip_result:
            return skip_result

        # Phase 2: Execute all available verification methods concurrently.
        await execute_all_verification_methods(
            context, self.download_service, self.cache_manager
        )

        # Phase 3: Evaluate results and return.
        return await self._finalize_verification(context)

    async def _prepare_verification(
        self, context: VerificationContext
    ) -> VerificationResult | None:
        """Prepare verification: detect methods and check skip conditions.

        Args:
            context: Verification context (mutated in place).

        Returns:
            A VerificationResult signalling "skip" when no methods are
            available and the config says to skip, otherwise None.

        """
        logger.debug(
            "Starting verification: app=%s, skip=%s, checksum_file=%s,"
            " digest=%s",
            context.app_name,
            context.config.get("skip", False),
            context.config.get("checksum_file", ""),
            context.config.get(VerificationMethod.DIGEST, False),
        )
        logger.debug("Asset digest: %s", context.asset.digest or "None")
        logger.debug(
            "Assets provided: %s (%d items)",
            bool(context.assets),
            len(context.assets) if context.assets else 0,
        )

        header_verification = SubProgressType.VERIFICATION
        # Create a progress task when the reporter is active and no task was
        # injected by the caller.
        if (
            context.progress_task_id is None
            and self.progress_reporter.is_active()
        ):
            context.progress_task_id = await self.progress_reporter.add_task(
                f"{header_verification} {context.app_name}",
                progress_type=ProgressType.PROCESSING,
                sub_type=header_verification,
            )

        context.has_digest, context.checksum_files = detect_available_methods(
            context.asset,
            context.config,
            context.assets,
            context.owner,
            context.repo,
            context.tag_name,
        )
        has_checksum_files = bool(context.checksum_files)

        logger.debug(
            "   Available methods: digest=%s, checksum_files=%d",
            context.has_digest,
            len(context.checksum_files) if context.checksum_files else 0,
        )
        logger.info(
            "Verifying %s: digest=%s, checksum_files=%d",
            context.app_name,
            context.has_digest,
            len(context.checksum_files) if context.checksum_files else 0,
        )

        should_skip, context.updated_config = should_skip_verification(
            context.config, context.has_digest, has_checksum_files
        )
        if should_skip:
            await self._finish_progress(
                context.progress_task_id, True, "verification skipped"
            )
            return VerificationResult(
                passed=False,
                methods={"skip": {"passed": False, "status": "skipped"}},
                updated_config=context.updated_config,
                warning="Not verified - developer did not provide checksums",
            )

        context.verifier = Verifier(context.file_path)
        return None

    async def _finalize_verification(
        self, context: VerificationContext
    ) -> VerificationResult:
        """Evaluate all method results and determine the overall status.

        Partial success (≥1 passing method alongside failures) is allowed
        with a warning. Complete failure raises VerificationError so the
        caller can abort installation.

        Args:
            context: Verification context populated by the execution phase.

        Returns:
            VerificationResult with final status and optional warning.

        Raises:
            VerificationError: When strong methods are available but every
                one of them fails.

        """
        has_checksum_files = bool(context.checksum_files)
        strong_methods_available = context.has_digest or has_checksum_files

        passed_methods: list[str] = []
        failed_methods: list[str] = []

        for method_key, method_result in (
            context.verification_methods or {}
        ).items():
            if method_result.get("passed"):
                passed_methods.append(method_key)
            else:
                failed_methods.append(method_key)

        has_passing_method = bool(passed_methods)

        logger.debug(
            "Verification methods summary: passed=%d, failed=%d",
            len(passed_methods),
            len(failed_methods),
        )
        if passed_methods:
            logger.debug("Passed methods: %s", ", ".join(passed_methods))
        if failed_methods:
            logger.debug("Failed methods: %s", ", ".join(failed_methods))

        warning_message: str | None = None
        overall_passed = strong_methods_available and has_passing_method

        if not strong_methods_available:
            context.verification_methods["skip"] = {
                "passed": False,
                "status": "skipped",
            }
            warning_message = (
                "Not verified - developer did not provide checksums"
            )
            logger.debug(
                "No verification methods available for %s - "
                "developer did not provide checksums or digest. "
                "Installation will proceed without verification. "
                "Security risk: File integrity cannot be verified.",
                context.app_name,
            )
        elif has_passing_method and failed_methods:
            warning_message = (
                f"Partial verification: {len(passed_methods)} passed, "
                f"{len(failed_methods)} failed"
            )
            logger.warning(
                "Partial verification success for %s: %s passed, %s failed",
                context.app_name,
                ", ".join(passed_methods),
                ", ".join(failed_methods),
            )
        elif not has_passing_method and strong_methods_available:
            warning_message = "All verification methods failed"
            logger.error(
                "All verification methods failed for %s", context.app_name
            )
            await self._finish_progress(
                context.progress_task_id,
                success=False,
                description="verification failed",
            )
            msg = f"All verification methods failed for {context.app_name}"
            raise VerificationError(
                msg,
                context={
                    "app_name": context.app_name,
                    "file_path": str(context.file_path),
                    "available_methods": (
                        list(context.verification_methods.keys())
                        if context.verification_methods
                        else []
                    ),
                    "failed_methods": failed_methods,
                },
            )

        context.verification_passed = has_passing_method
        context.verification_warning = warning_message

        self._log_verification_summary(
            context, strong_methods_available, overall_passed
        )

        # Update progress with a message that reflects the final outcome.
        if not strong_methods_available:
            await self._finish_progress(
                context.progress_task_id,
                True,
                "not verified (dev did not provide checksums)",
            )
            logger.info(
                "Verification completed for %s: skipped (no checksums provided)",
                context.app_name,
            )
        elif overall_passed and not warning_message:
            await self._finish_progress(
                context.progress_task_id, True, "verification passed"
            )
            logger.debug(
                "Verification completed: app=%s, status=passed",
                context.app_name,
            )
            logger.info(
                "Verification completed for %s: passed", context.app_name
            )
        elif (
            overall_passed and warning_message and "Partial" in warning_message
        ):
            await self._finish_progress(
                context.progress_task_id,
                True,
                "verification passed (with warnings)",
            )
            logger.info(
                "Verification completed for %s: passed with warnings",
                context.app_name,
            )
        else:
            await self._finish_progress(
                context.progress_task_id,
                False,
                "verification failed",
            )
            logger.warning(
                "Verification completed with failures: app=%s",
                context.app_name,
            )
            logger.info(
                "Verification completed for %s: failed", context.app_name
            )

        return VerificationResult(
            passed=overall_passed,
            methods=context.verification_methods or {},
            updated_config=context.updated_config or context.config,
            warning=warning_message,
        )

    def _log_verification_summary(
        self,
        context: VerificationContext,
        strong_methods_available: bool,
        overall_passed: bool,
    ) -> None:
        """Log a debug summary of all method results.

        Args:
            context: Verification context.
            strong_methods_available: Whether any strong method was available.
            overall_passed: Overall verification result.

        """
        logger.debug("Verification summary: app=%s", context.app_name)
        logger.debug(
            "   🔐 Strong methods available: %s", strong_methods_available
        )
        logger.debug("   ✓ Verification passed: %s", overall_passed)
        methods = context.verification_methods or {}
        logger.debug("   📋 Methods used: %s", list(methods.keys()))
        for method, result in methods.items():
            logger.debug(
                "      %s: %s",
                method,
                "✓ PASS" if result.get("passed") else "× FAIL",
            )

    async def _finish_progress(
        self,
        task_id: Any | None,
        success: bool,
        description: str,
    ) -> None:
        """Finish a progress task if one is active.

        Args:
            task_id: Progress task ID (may be None).
            success: Whether the task succeeded.
            description: Final status description.

        """
        if not task_id:
            return
        finish_coro = self.progress_reporter.finish_task(
            task_id,
            success=success,
            description=description,
        )
        # finish_task may be sync (NullProgressReporter) or async (real UI).
        if asyncio.iscoroutine(finish_coro):
            await finish_coro


# ---------------------------------------------------------------------------
# Verifier: hash computation and low-level verification
# ---------------------------------------------------------------------------


def format_bytes(num_bytes: float) -> str:
    """Convert a byte count to a human-readable string.

    Uses decimal multiples (KB, MB, …) with one decimal place.

    Args:
        num_bytes: Size in bytes (must be ≥ 0).

    Returns:
        Human-readable size string, e.g. ``"123.4 MB"``.

    Raises:
        ValueError: If ``num_bytes`` is negative.

    """
    if num_bytes < 0:
        msg = "Byte size cannot be negative"
        raise ValueError(msg)

    units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(num_bytes)
    unit_index = 0

    while size >= BYTES_PER_UNIT and unit_index < len(units) - 1:
        size /= BYTES_PER_UNIT
        unit_index += 1

    return f"{size:.1f} {units[unit_index]}"


class Verifier:
    """Handles hash computation and low-level file verification.

    Supports sha256 and sha512 only (sha1/md5 are intentionally excluded).
    Large files (> LARGE_FILE_THRESHOLD) are hashed in a ThreadPoolExecutor
    via ``compute_hash_async`` to keep the event loop responsive.
    """

    def __init__(self, file_path: Path) -> None:
        """Create a verifier for a downloaded file.

        Args:
            file_path: Path to the file to verify.

        """
        self.file_path: Path = file_path
        self._last_computed_hash: str | None = None
        self._log_file_info()

    def _log_file_info(self) -> None:
        """Log basic file metadata at debug level."""
        if self.file_path.exists():
            file_size = self.file_path.stat().st_size
            logger.debug("📁 File info: %s", self.file_path.name)
            logger.debug("   Path: %s", self.file_path)
            logger.debug(
                "   Size: %s (%s bytes)",
                format_bytes(file_size),
                f"{file_size:,}",
            )
        else:
            logger.warning("! File does not exist: %s", self.file_path)

    def verify_digest(self, expected_digest: str) -> None:
        """Verify the file against a GitHub API digest string.

        The digest must be in ``algorithm:hexhash`` format, e.g.
        ``sha256:abcdef…``.  Only algorithms listed in
        ``SUPPORTED_HASH_ALGORITHMS`` (sha256, sha512) are accepted.

        Args:
            expected_digest: Digest string from the GitHub API asset field.

        Raises:
            ValueError: If the digest is empty, malformed, uses an
                unsupported algorithm, or does not match the file.

        """
        logger.debug(
            "🔍 Starting digest verification for %s", self.file_path.name
        )
        logger.debug("   Expected digest: %s", expected_digest)

        if not expected_digest:
            msg = "Digest cannot be empty"
            logger.error("× %s", msg)
            raise ValueError(msg)

        algo, _, hash_value = expected_digest.partition(":")
        if not hash_value:
            msg = f"Invalid digest format: {expected_digest}"
            logger.error("× %s", msg)
            raise ValueError(msg)

        if algo not in SUPPORTED_HASH_ALGORITHMS:
            msg = f"Unsupported digest algorithm: {algo}"
            logger.error("× %s", msg)
            raise ValueError(msg)

        logger.debug("   Algorithm: %s", algo.upper())
        logger.debug("   Expected hash: %s", hash_value)
        logger.debug("🧮 Computing %s hash…", algo.upper())

        actual_hash = self.compute_hash(algo)  # type: ignore[arg-type]
        logger.debug("   Computed hash: %s", actual_hash)

        if actual_hash.lower() != hash_value.lower():
            msg = (
                "Digest mismatch!\n"
                f"Expected: {hash_value}\n"
                f"Actual:   {actual_hash}"
            )
            logger.error("× Digest verification FAILED!")
            logger.error("   Expected:  %s", hash_value)
            logger.error("   Actual:    %s", actual_hash)
            logger.error("   Algorithm: %s", algo.upper())
            logger.error("   File:      %s", self.file_path)
            raise ValueError(msg)

        logger.debug("✓ Digest verification PASSED!")
        logger.debug("   Algorithm: %s", algo.upper())
        logger.debug("   Hash: %s", actual_hash)

    def verify_hash(self, expected_hash: str, hash_type: HashType) -> None:
        """Verify the file against a known hex hash value.

        Args:
            expected_hash: Expected hexadecimal hash string.
            hash_type: Algorithm to use (sha256 or sha512).

        Raises:
            ValueError: If the computed hash does not match.

        """
        logger.debug(
            "🔍 Starting %s hash verification for %s",
            hash_type.upper(),
            self.file_path.name,
        )
        logger.debug("   Expected hash: %s", expected_hash)
        logger.debug("🧮 Computing %s hash…", hash_type.upper())

        actual_hash = self.compute_hash(hash_type)
        logger.debug("   Computed hash: %s", actual_hash)

        if actual_hash.lower() != expected_hash.lower():
            msg = (
                f"{hash_type.upper()} mismatch!\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}"
            )
            logger.error("× %s verification FAILED!", hash_type.upper())
            logger.error("   Expected: %s", expected_hash)
            logger.error("   Actual:   %s", actual_hash)
            logger.error("   File: %s", self.file_path)
            raise ValueError(msg)

        logger.debug("✓ %s verification PASSED!", hash_type.upper())
        logger.debug("   Hash: %s", actual_hash)

    def compute_hash(self, hash_type: HashType) -> str:
        """Compute the file hash synchronously.

        For async callers that need to avoid blocking the event loop on
        large files, use ``compute_hash_async`` instead.

        Args:
            hash_type: Hash algorithm — sha256 or sha512.

        Returns:
            Lowercase hexadecimal digest string.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If ``hash_type`` is unsupported.

        """
        return self._compute_hash_sync(hash_type)

    async def compute_hash_async(self, hash_type: HashType) -> str:
        """Compute the file hash, offloading large files to a thread pool.

        Files smaller than ``LARGE_FILE_THRESHOLD`` are hashed synchronously.
        Larger files run in a ``ThreadPoolExecutor`` so the event loop
        remains responsive.

        Args:
            hash_type: Hash algorithm — sha256 or sha512.

        Returns:
            Lowercase hexadecimal digest string.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If ``hash_type`` is unsupported.

        """
        if not self.file_path.exists():
            msg = f"File not found: {self.file_path}"
            logger.error("× %s", msg)
            raise FileNotFoundError(msg)

        file_size = self.file_path.stat().st_size

        if file_size < LARGE_FILE_THRESHOLD:
            logger.debug(
                "📁 File size %s < threshold, using sync hash computation",
                format_bytes(file_size),
            )
            return self._compute_hash_sync(hash_type)

        logger.debug(
            "📁 File size %s >= threshold, offloading to ThreadPoolExecutor",
            format_bytes(file_size),
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._compute_hash_sync,
            hash_type,
        )

    def _compute_hash_sync(self, hash_type: HashType) -> str:
        """Synchronous hash computation implementation.

        Args:
            hash_type: Hash algorithm — sha256 or sha512.

        Returns:
            Lowercase hexadecimal digest string.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If ``hash_type`` is unsupported.

        """
        if not self.file_path.exists():
            msg = f"File not found: {self.file_path}"
            logger.error("× %s", msg)
            raise FileNotFoundError(msg)

        hash_algorithms = {
            "sha256": hashlib.sha256,
            "sha512": hashlib.sha512,
        }

        if hash_type not in hash_algorithms:
            msg = f"Unsupported hash type: {hash_type}"
            logger.error("× %s", msg)
            raise ValueError(msg)

        logger.debug(
            "🧮 Computing %s hash for %s",
            hash_type.upper(),
            self.file_path.name,
        )

        hasher = hash_algorithms[hash_type]()
        bytes_processed = 0
        chunk_size = 8192

        with self.file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hasher.update(chunk)
                bytes_processed += len(chunk)

        computed_hash = hasher.hexdigest()
        self._last_computed_hash = computed_hash

        logger.debug(
            "   Processed: %s (%d bytes)",
            format_bytes(bytes_processed),
            bytes_processed,
        )
        logger.debug("   Hash: %s", computed_hash)
        return computed_hash

    async def verify_from_checksum_file(
        self,
        checksum_url: str,
        hash_type: HashType,
        download_service: DownloadService,
        filename: str | None = None,
    ) -> None:
        """Verify the file by downloading and parsing a remote checksum file.

        Args:
            checksum_url: URL of the checksum file to download.
            hash_type: Expected hash algorithm (sha256 or sha512).
            download_service: Service used to fetch the checksum file.
            filename: Target filename to look up; defaults to the file's
                own name when not provided.

        Raises:
            ValueError: If the target filename is not found in the checksum
                file or the hash does not match.

        """
        target_filename = filename or self.file_path.name

        logger.debug(
            "🔍 Starting checksum file verification for %s",
            self.file_path.name,
        )
        logger.debug("   Checksum URL: %s", checksum_url)
        logger.debug("   Target filename: %s", target_filename)
        logger.debug("   Hash type: %s", hash_type.upper())

        checksum_content = await download_service.download_checksum_file(
            checksum_url
        )
        logger.debug("   Downloaded %d characters", len(checksum_content))

        expected_hash = parse_checksum_file(
            checksum_content, target_filename, hash_type
        )

        if not expected_hash:
            msg = f"Hash for {target_filename} not found in checksum file"
            logger.error("× %s", msg)
            logger.debug("   Checksum file content:\n%s", checksum_content)
            raise ValueError(msg)

        logger.debug("✓ Found expected hash in checksum file")
        logger.debug("   Expected hash: %s", expected_hash)

        self.verify_hash(expected_hash, hash_type)

    def parse_checksum_file(
        self, content: str, filename: str, hash_type: HashType
    ) -> str | None:
        """Expose checksum parsing for callers that already have the content.

        Args:
            content: Raw checksum file content.
            filename: Filename to look up in the checksum file.
            hash_type: Expected hash algorithm.

        Returns:
            Hex hash string, or None if the filename was not found.

        """
        return parse_checksum_file(content, filename, hash_type)

    def detect_hash_type_from_filename(self, filename: str) -> HashType:
        """Infer hash type from a checksum filename, falling back to default.

        Args:
            filename: Checksum filename (e.g. ``SHA256SUMS.txt``).

        Returns:
            Detected HashType, or ``DEFAULT_HASH_TYPE`` when undetectable.

        """
        detected = detect_hash_type_from_checksum_filename(filename)
        return detected or DEFAULT_HASH_TYPE

    def _convert_base64_to_hex(self, base64_hash: str) -> str:
        """Convert a base64-encoded digest to hexadecimal.

        Args:
            base64_hash: Base64-encoded hash string.

        Returns:
            Hexadecimal representation of the decoded bytes.

        """
        return convert_base64_to_hex(base64_hash)


# ---------------------------------------------------------------------------
# Standalone verification functions
# ---------------------------------------------------------------------------


async def verify_digest(
    verifier: Verifier,
    digest: str,
    app_name: str,
    skip_configured: bool,
) -> MethodResult | None:
    """Verify a file using the GitHub API asset digest field.

    Calls ``verifier.verify_digest`` once — no double file read.
    If verification passes, the expected hash is extracted from the
    digest string (which we know equals the computed hash at that point).

    Args:
        verifier: Verifier instance for the target file.
        digest: ``algorithm:hexhash`` digest from the GitHub API.
        app_name: Application name used in log messages.
        skip_configured: Whether ``skip=true`` was set in config (logged
            only; verification still runs when a digest is available).

    Returns:
        MethodResult with ``passed=True`` on success, or ``passed=False``
        when an exception is raised.

    """
    try:
        logger.debug("Attempting digest verification from GitHub API")
        logger.debug("AppImage file: %s", verifier.file_path.name)
        logger.debug("Expected digest: %s", digest)
        if skip_configured:
            logger.debug("Note: Using digest despite skip=true setting")

        # verify_digest reads the file once and raises on mismatch.
        # We do NOT call compute_hash separately to avoid a second read.
        verifier.verify_digest(digest)

        # Verification passed — the hash portion of the digest equals the
        # computed hash, so we can safely expose it without re-reading.
        _, _, verified_hash = digest.partition(":")

        logger.debug("✓ Digest verification passed")
        return MethodResult(
            passed=True,
            hash=digest,
            computed_hash=verified_hash,
            details="GitHub API digest verification",
        )
    except Exception as e:
        # Preserve computed hash on failures without forcing a second file read.
        actual_digest: str | None = None

        last = getattr(verifier, "_last_computed_hash", None)
        if isinstance(last, str) and last:
            actual_digest = last

        if not actual_digest and isinstance(e, VerificationError):
            ctx_actual = e.context.get("actual_hash")
            if isinstance(ctx_actual, str) and ctx_actual:
                actual_digest = ctx_actual

        message = str(e)
        if not actual_digest:
            # Handles our ValueError message:
            # "Digest mismatch!\nExpected: ...\nActual:   <hash>"
            for line in message.splitlines():
                stripped = line.strip()
                if stripped.lower().startswith("actual:"):
                    actual_digest = stripped.split(":", 1)[1].strip()
                    break

        if not actual_digest and " got " in message:
            # Handles test/mocked error messages:
            # "... but got <hash>"
            actual_digest = message.rsplit(" got ", 1)[-1].strip().split()[0]

        logger.error("Digest verification failed: %s", e)
        logger.error("Expected: %s", digest)
        logger.error("AppImage: %s", verifier.file_path.name)
        return MethodResult(
            passed=False,
            hash=digest,
            computed_hash=actual_digest,
            details=str(e),
        )


async def verify_checksum_file(
    verifier: Verifier,
    checksum_file: ChecksumFileInfo,
    target_filename: str,
    app_name: str,
    download_service: DownloadService,
    cache_manager: ReleaseCacheManager | None = None,
    context: VerificationContext | None = None,
) -> MethodResult | None:
    """Verify a file against a remote checksum file.

    Args:
        verifier: Verifier instance for the target file.
        checksum_file: Metadata for the checksum file to download.
        target_filename: Filename to look up inside the checksum file.
        app_name: Application name used in log messages.
        download_service: Service for downloading the checksum file.
        cache_manager: Optional cache manager for storing parsed hashes.
        context: Verification context used for cache storage keys.

    Returns:
        MethodResult with ``passed=True`` on a hash match, or
        ``passed=False`` on mismatch / missing entry / exception.

    """
    try:
        logger.debug(
            "Verifying using checksum file: %s (%s format)",
            checksum_file.filename,
            checksum_file.format_type,
        )

        content = await download_service.download_checksum_file(
            checksum_file.url
        )

        # Resolve hash type: YAML files always use YAML_DEFAULT_HASH (sha512);
        # traditional files are inferred from the filename.
        hash_type: HashType
        if checksum_file.format_type == "yaml":
            hash_type = YAML_DEFAULT_HASH
        else:
            detected_hash = verifier.detect_hash_type_from_filename(
                checksum_file.filename
            )
            hash_type = (
                detected_hash
                if detected_hash in SUPPORTED_HASH_ALGORITHMS
                else DEFAULT_HASH_TYPE
            )

        expected_hash = verifier.parse_checksum_file(
            content, target_filename, hash_type
        )
        if not expected_hash:
            logger.error("Checksum file verification FAILED - hash not found!")
            logger.error(
                "   📄 Checksum file: %s (%s format)",
                checksum_file.filename,
                checksum_file.format_type,
            )
            logger.error("   Looking for: %s", target_filename)
            return MethodResult(
                passed=False,
                hash="",
                details=(
                    f"Hash not found for {target_filename} in checksum file"
                ),
            )

        logger.debug(
            "   📄 Checksum file: %s (%s format)",
            checksum_file.filename,
            checksum_file.format_type,
        )
        logger.debug("   🔍 Target file: %s", target_filename)
        logger.debug(
            "   📋 Expected hash (%s): %s",
            hash_type.upper(),
            expected_hash,
        )

        computed_hash = verifier.compute_hash(hash_type)
        logger.debug(
            "   🧮 Computed hash (%s): %s",
            hash_type.upper(),
            computed_hash,
        )

        hashes_match = computed_hash.lower() == expected_hash.lower()
        logger.debug(
            "Hash comparison: %s… == %s… → %s",
            computed_hash.lower()[:32],
            expected_hash.lower()[:32],
            "MATCH" if hashes_match else "MISMATCH",
        )

        if hashes_match:
            logger.debug(
                "✓ Checksum file verification PASSED! (%s)",
                hash_type.upper(),
            )
            await cache_checksum_file_data(
                content,
                checksum_file,
                hash_type,
                cache_manager,
                context,
            )
            return MethodResult(
                passed=True,
                hash=expected_hash,
                computed_hash=computed_hash,
                details=(
                    f"Verified against {checksum_file.format_type} checksum file"
                ),
                url=checksum_file.url,
                hash_type=hash_type,
            )

        logger.error("Checksum file verification FAILED")
        logger.error(
            "   Checksum file: %s (%s format)",
            checksum_file.filename,
            checksum_file.format_type,
        )
        logger.error("   Expected hash: %s", expected_hash)
        logger.error("   Computed hash: %s", computed_hash)
        return MethodResult(
            passed=False,
            hash=expected_hash,
            computed_hash=computed_hash,
            details=f"Hash mismatch (expected: {expected_hash})",
            url=checksum_file.url,
            hash_type=hash_type,
        )

    except Exception as e:
        logger.error("Checksum file verification failed: %s", e)
        return MethodResult(
            passed=False,
            hash="",
            details=str(e),
        )


async def cache_checksum_file_data(
    content: str,
    checksum_file: ChecksumFileInfo,
    hash_type: HashType,
    cache_manager: ReleaseCacheManager | None,
    context: VerificationContext | None,
) -> None:
    """Cache all hashes from a checksum file after successful verification.

    Parses every hash in the file and stores the result so future
    verification runs can skip the download.

    Args:
        content: Raw downloaded checksum file content.
        checksum_file: Metadata for the checksum file.
        hash_type: Algorithm that was used for verification.
        cache_manager: Cache manager; silently skipped when None.
        context: Verification context providing owner/repo/tag keys.

    """
    if not cache_manager or not context:
        return

    try:
        all_hashes = parse_all_checksums(content)
        if not all_hashes:
            logger.debug(
                "No hashes parsed from checksum file: %s",
                checksum_file.filename,
            )
            return

        algorithm = hash_type.upper()
        if algorithm not in ("SHA256", "SHA512"):
            algorithm = "SHA256"

        checksum_result = ChecksumFileResult(
            source=checksum_file.url,
            filename=checksum_file.filename,
            algorithm=algorithm,
            hashes=all_hashes,
        )

        stored = await cache_manager.store_checksum_file(
            context.owner,
            context.repo,
            context.tag_name,
            checksum_result.to_cache_dict(),
        )

        if stored:
            logger.debug(
                "Cached checksum file: %s with %d hashes",
                checksum_file.filename,
                len(all_hashes),
            )
        else:
            logger.debug(
                "Failed to cache checksum file: %s (cache may be missing)",
                checksum_file.filename,
            )

    except Exception as e:
        logger.debug(
            "Error caching checksum file %s: %s",
            checksum_file.filename,
            e,
        )


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def detect_available_methods(
    asset: Asset,
    config: dict[str, Any],
    assets: list[Asset] | None = None,
    owner: str | None = None,
    repo: str | None = None,
    tag_name: str | None = None,
) -> tuple[bool, list[ChecksumFileInfo]]:
    """Detect which verification methods are available for an asset.

    Args:
        asset: GitHub asset to verify.
        config: Verification configuration dict.
        assets: Full list of release assets (enables auto-detection).
        owner: Repository owner.
        repo: Repository name.
        tag_name: Release tag name.

    Returns:
        Tuple of (has_digest, checksum_files).

    """
    has_digest = check_digest_availability(asset, config)
    checksum_files = resolve_checksum_files(
        asset, config, assets, owner, repo, tag_name
    )
    return has_digest, checksum_files


def check_digest_availability(asset: Asset, config: dict[str, Any]) -> bool:
    """Check whether the asset carries a usable digest field.

    Args:
        asset: GitHub asset information.
        config: Verification configuration dict.

    Returns:
        True if the asset digest is non-empty.

    """
    digest_value = asset.digest or ""
    has_digest = bool(digest_value and digest_value.strip())
    digest_requested = config.get(VerificationMethod.DIGEST, False)

    if digest_requested and not has_digest:
        logger.warning(
            "! Digest verification requested but no digest available "
            "from GitHub API"
        )
        logger.debug("   Asset digest field: '%s'", digest_value or "None")
    elif has_digest:
        logger.debug(
            "✓ Digest available for verification: %s…",
            digest_value[:16],
        )

    return has_digest


def resolve_checksum_files(
    asset: Asset,
    config: dict[str, Any],
    assets: list[Asset] | None,
    owner: str | None,
    repo: str | None,
    tag_name: str | None,
) -> list[ChecksumFileInfo]:
    """Resolve checksum files from manual config or auto-detection.

    Manual config takes precedence over auto-detection.  Auto-detection
    is skipped when digest verification is explicitly enabled (to avoid
    redundant downloads).

    Args:
        asset: GitHub asset information.
        config: Verification configuration dict.
        assets: Full list of release assets.
        owner: Repository owner.
        repo: Repository name.
        tag_name: Release tag name.

    Returns:
        List of ChecksumFileInfo to try (may be empty).

    """
    manual_checksum_file = config.get("checksum_file")

    if manual_checksum_file:
        if isinstance(manual_checksum_file, dict):
            # v2 format: {"filename": "...", "algorithm": "..."}
            filename = manual_checksum_file.get("filename", "")
            if filename and filename.strip():
                return resolve_manual_checksum_file(
                    filename, asset, owner, repo, tag_name
                )
        elif (
            isinstance(manual_checksum_file, str)
            and manual_checksum_file.strip()
        ):
            # v1 format: plain string
            return resolve_manual_checksum_file(
                manual_checksum_file, asset, owner, repo, tag_name
            )

    if (
        assets
        and owner
        and repo
        and tag_name
        and not config.get(VerificationMethod.DIGEST, False)
    ):
        return auto_detect_checksum_files(assets, tag_name)

    if assets and config.get(VerificationMethod.DIGEST, False):
        logger.debug(
            "   Skipping auto-detection: digest verification explicitly enabled"
        )

    return []


def auto_detect_checksum_files(
    assets: list[Asset], tag_name: str
) -> list[ChecksumFileInfo]:
    """Auto-detect checksum files from GitHub release assets.

    Args:
        assets: Full list of GitHub release assets.
        tag_name: Release tag name.

    Returns:
        List of detected ChecksumFileInfo (x86_64 Linux only).

    """
    logger.debug(
        "🔍 Auto-detecting checksum files (digest not explicitly enabled)"
    )
    try:
        checksum_files = AssetSelector.detect_checksum_files(assets, tag_name)
        logger.debug(
            "🔍 Auto-detected %d checksum files from assets",
            len(checksum_files),
        )
        return checksum_files
    except Exception as e:
        logger.warning("Failed to auto-detect checksum files: %s", e)
        return []


def should_skip_verification(
    config: dict[str, Any],
    has_digest: bool,
    has_checksum_files: bool,
) -> tuple[bool, dict[str, Any]]:
    """Determine whether verification should be skipped.

    Skips only when ``skip=true`` is configured AND no strong verification
    methods are available.  If strong methods exist, the skip flag is
    overridden so integrity is always checked when data is available.

    Args:
        config: Verification configuration dict.
        has_digest: Whether an asset digest is available.
        has_checksum_files: Whether checksum files are available.

    Returns:
        Tuple of (should_skip, updated_config).

    """
    catalog_skip = config.get("skip", False) or config.get("method") == "skip"
    updated_config = config.copy()

    if catalog_skip and not has_digest and not has_checksum_files:
        logger.debug(
            "⏭️ Verification skipped "
            "(configured skip, no strong methods available)"
        )
        return True, updated_config

    if catalog_skip and (has_digest or has_checksum_files):
        logger.debug(
            "🔄 Overriding skip setting — strong verification methods available"
        )
        updated_config["skip"] = False

    return False, updated_config


def prioritize_checksum_files(
    checksum_files: list[ChecksumFileInfo],
    target_filename: str,
) -> list[ChecksumFileInfo]:
    """Sort checksum files so the most relevant one comes first.

    Priority order (lower number = higher priority):

    1. Exact ``.DIGEST`` / ``.digest`` match for ``target_filename``
    2. Per-file hash suffix (``target_filename.sha256``, etc.)
    3. YAML files (usually most comprehensive)
    4. Other ``.digest`` files (belong to a different file, may still
       contain the target hash)
    5. Generic checksum files (``SHA256SUMS.txt``, etc.);
       files matching ``UNSTABLE_VERSION_KEYWORDS`` receive +10 penalty.

    Args:
        checksum_files: Detected checksum files (any order).
        target_filename: Name of the AppImage being verified.

    Returns:
        Re-ordered list with the best candidate first.

    """
    if not checksum_files:
        return checksum_files

    logger.debug(
        "🔍 Prioritizing %d checksum files for target: %s",
        len(checksum_files),
        target_filename,
    )

    def get_priority(checksum_file: ChecksumFileInfo) -> tuple[int, str]:
        """Return a (score, filename) sort key; lower score = higher priority."""
        filename = checksum_file.filename

        # Priority 1: exact .DIGEST/.digest for this specific target file.
        if filename in {
            f"{target_filename}{ext}" for ext in DIGEST_FILE_SUFFIXES
        }:
            logger.debug("   📌 Priority 1 (exact .DIGEST): %s", filename)
            return (1, filename)

        # Priority 2: per-file hash suffix for this specific target file.
        for ext in CHECKSUM_FILE_SUFFIXES:
            if filename == f"{target_filename}{ext}":
                logger.debug("   📌 Priority 2 (per-file hash): %s", filename)
                return (2, filename)

        # Priority 3: YAML files (electron-builder style, most comprehensive).
        if checksum_file.format_type == "yaml":
            logger.debug("   📌 Priority 3 (YAML): %s", filename)
            return (3, filename)

        # Priority 4: other .digest files that are NOT an exact match for the
        # target (e.g. belong to a different AppImage in the same release).
        # They're still worth trying as they may contain the target's hash.
        if filename.lower().endswith(DIGEST_FILE_SUFFIXES):
            logger.debug(
                "   📌 Priority 4 (other .digest, not exact match): %s",
                filename,
            )
            return (4, filename)

        # Priority 5: generic checksum files (SHA256SUMS.txt, etc.).
        # Unstable / experimental variants are penalised via the shared
        # UNSTABLE_VERSION_KEYWORDS constant so this stays in sync with the
        # rest of the asset-filtering logic.
        penalty = (
            10
            if any(kw in filename.lower() for kw in UNSTABLE_VERSION_KEYWORDS)
            else 0
        )
        logger.debug("   📌 Priority %d (generic): %s", 5 + penalty, filename)
        return (5 + penalty, filename)

    prioritized = sorted(checksum_files, key=get_priority)

    logger.debug("   📋 Final priority order:")
    for i, cf in enumerate(prioritized, 1):
        logger.debug("      %d. %s", i, cf.filename)

    return prioritized


# ---------------------------------------------------------------------------
# Execution orchestration
# ---------------------------------------------------------------------------


async def execute_digest_verification(
    context: VerificationContext,
) -> MethodResult | None:
    """Run digest verification for the asset in *context*.

    Args:
        context: Verification context.

    Returns:
        MethodResult, or None when digest is unavailable or verifier is
        not yet initialised.

    """
    if not context.has_digest or not context.asset.digest:
        return None

    if context.verifier is None:
        logger.error("Verifier not initialised for digest verification")
        return None

    skip_configured = context.config.get("skip", False)
    logger.debug("Attempting digest verification: app=%s", context.app_name)

    result = await verify_digest(
        context.verifier,
        context.asset.digest,
        context.app_name,
        skip_configured,
    )

    if result:
        if result.passed:
            logger.debug(
                "Digest verification passed: app=%s", context.app_name
            )
            logger.info("Digest verification passed for %s", context.app_name)
        else:
            logger.warning(
                "Digest verification failed: app=%s", context.app_name
            )
            logger.info("Digest verification failed for %s", context.app_name)

    return result


async def execute_checksum_file_verification(
    context: VerificationContext,
    checksum_file: ChecksumFileInfo,
    download_service: DownloadService,
    cache_manager: ReleaseCacheManager | None,
) -> MethodResult | None:
    """Run checksum file verification for a single checksum file.

    Args:
        context: Verification context.
        checksum_file: The checksum file to download and parse.
        download_service: Service for downloading the checksum file.
        cache_manager: Optional cache manager.

    Returns:
        MethodResult, or None when the verifier is not yet initialised.

    """
    if context.verifier is None:
        logger.error("Verifier not initialised for checksum verification")
        return None

    # Use the original asset name (pre-download) for checksum lookups.
    original_asset_name = context.asset.name or context.file_path.name
    logger.debug(
        "Attempting checksum verification with: %s",
        checksum_file.filename,
    )

    result = await verify_checksum_file(
        context.verifier,
        checksum_file,
        original_asset_name,
        context.app_name,
        download_service,
        cache_manager,
        context,
    )

    if result:
        if result.passed:
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

    return result


async def execute_all_verification_methods(
    context: VerificationContext,
    download_service: DownloadService,
    cache_manager: ReleaseCacheManager | None,
) -> None:
    """Execute all available verification methods concurrently.

    Builds coroutines for digest and (the best) checksum file, runs them
    with ``asyncio.gather``, and stores every result in
    ``context.verification_methods``.

    Using ``None`` (rather than ``-1``) as the sentinel for "no digest task"
    makes the index bookkeeping explicit and avoids relying on the implicit
    property that ``enumerate`` never produces ``-1``.

    Args:
        context: Verification context (mutated in place).
        download_service: Service for downloading checksum files.
        cache_manager: Optional cache manager.

    """
    # Each entry is (coroutine, checksum_file_or_None).
    tasks: list[tuple[Any, ChecksumFileInfo | None]] = []

    if context.has_digest:
        logger.debug("Adding digest verification to concurrent execution")
        tasks.append((execute_digest_verification(context), None))

    if context.checksum_files:
        logger.debug(
            "Checksum file verification available — found %d file(s)",
            len(context.checksum_files),
        )
        for cf in context.checksum_files:
            logger.debug(
                "   Available: %s (%s format)", cf.filename, cf.format_type
            )

        original_asset_name = context.asset.name or context.file_path.name
        prioritized = prioritize_checksum_files(
            context.checksum_files, original_asset_name
        )
        best = prioritized[0]
        logger.debug("Selected best checksum file: %s", best.filename)
        tasks.append(
            (
                execute_checksum_file_verification(
                    context, best, download_service, cache_manager
                ),
                best,
            )
        )

    if not tasks:
        return

    logger.debug(
        "Executing %d verification method(s) concurrently", len(tasks)
    )

    task_coroutines = [coro for coro, _ in tasks]
    # Map task index → ChecksumFileInfo for the checksum task (if present).
    checksum_file_map: dict[int, ChecksumFileInfo] = {
        idx: cf for idx, (_, cf) in enumerate(tasks) if cf is not None
    }

    # Use None as the sentinel: digest is always tasks[0] when present, but
    # only when context.has_digest is True.
    digest_index: int | None = 0 if context.has_digest else None

    results = await asyncio.gather(*task_coroutines, return_exceptions=True)

    for i, result in enumerate(results):
        is_digest_task = i == digest_index

        if isinstance(result, BaseException):
            logger.error("Verification method raised exception: %s", result)
            method_key = (
                VerificationMethod.DIGEST
                if is_digest_task
                else "checksum_file"
            )
            context.verification_methods[method_key] = MethodResult(
                passed=False,
                hash="",
                details=f"Exception: {result}",
            ).to_dict()
            continue

        if result is None or not isinstance(result, MethodResult):
            continue

        if is_digest_task:
            context.verification_methods[VerificationMethod.DIGEST] = (
                result.to_dict()
            )
            if result.passed and context.updated_config is not None:
                context.updated_config[VerificationMethod.DIGEST] = True
        else:
            context.verification_methods["checksum_file"] = result.to_dict()
            if result.passed:
                cf = checksum_file_map.get(i)
                if cf and context.updated_config is not None:
                    context.updated_config["checksum_file"] = cf.filename

    logger.debug(
        "Concurrent verification completed: %d method(s) recorded",
        len(context.verification_methods),
    )
