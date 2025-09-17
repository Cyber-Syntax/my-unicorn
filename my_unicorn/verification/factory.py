"""Factory and facade for verification strategies."""

from __future__ import annotations

from typing import Any

from my_unicorn.download import DownloadService
from my_unicorn.logger import get_logger
from my_unicorn.services.progress import ProgressService
from my_unicorn.verification.detection import (
    ChecksumFilePrioritizationService,
    VerificationDetectionService,
)
from my_unicorn.verification.strategies import (
    ChecksumFileVerificationStrategy,
    DigestVerificationStrategy,
    VerificationStrategy,
)

logger = get_logger(__name__, enable_file_logging=True)


class VerificationStrategyFactory:
    """Factory for creating verification strategies."""

    def __init__(self, download_service: DownloadService) -> None:
        """Initialize the factory.

        Args:
            download_service: Service for downloading checksum files

        """
        self.download_service = download_service

    def create_digest_strategy(self) -> DigestVerificationStrategy:
        """Create a digest verification strategy.

        Returns:
            DigestVerificationStrategy instance

        """
        return DigestVerificationStrategy()

    def create_checksum_file_strategy(self) -> ChecksumFileVerificationStrategy:
        """Create a checksum file verification strategy.

        Returns:
            ChecksumFileVerificationStrategy instance

        """
        return ChecksumFileVerificationStrategy(self.download_service)

    def get_available_strategies(self) -> dict[str, VerificationStrategy]:
        """Get all available verification strategies.

        Returns:
            Dictionary mapping strategy names to strategy instances

        """
        return {
            "digest": self.create_digest_strategy(),
            "checksum_file": self.create_checksum_file_strategy(),
        }


class VerificationServiceFacade:
    """Facade that simplifies the verification service interface."""

    def __init__(
        self,
        download_service: DownloadService,
        progress_service: ProgressService | None = None,
    ) -> None:
        """Initialize the facade.

        Args:
            download_service: Service for downloading checksum files
            progress_service: Optional progress service for tracking

        """
        self.factory = VerificationStrategyFactory(download_service)
        self.detection_service = VerificationDetectionService()
        self.prioritization_service = ChecksumFilePrioritizationService()
        self.progress_service = progress_service

    def should_skip_verification(
        self,
        config: dict[str, Any],
        has_digest: bool,
        has_checksum_files: bool,
    ) -> tuple[bool, dict[str, Any]]:
        """Determine if verification should be skipped.

        Args:
            config: Verification configuration
            has_digest: Whether digest verification is available
            has_checksum_files: Whether checksum file verification is available

        Returns:
            Tuple of (should_skip, updated_config)

        """
        catalog_skip = config.get("skip", False)
        updated_config = config.copy()

        # Only skip if configured AND no strong verification methods available
        if catalog_skip and not has_digest and not has_checksum_files:
            logger.debug(
                "⏭️ Verification skipped (configured skip, no strong methods available)"
            )
            return True, updated_config
        elif catalog_skip and (has_digest or has_checksum_files):
            logger.debug("🔄 Overriding skip setting - strong verification methods available")
            # Update config to reflect that we're now using verification
            updated_config["skip"] = False

        return False, updated_config
