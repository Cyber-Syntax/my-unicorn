"""Asset digest verification for GitHub API assets.

This module handles verification of AppImages using GitHub API asset digests,
which provide cryptographic verification of downloaded assets.
"""

import hashlib
import logging
import os
from typing import Tuple

from src.verification.hash_calculator import HashCalculator


class AssetDigestVerifier:
    """Handles GitHub API asset digest verification."""
    
    def __init__(self) -> None:
        """Initialize the asset digest verifier."""
        pass
    
    def verify_asset_digest(
        self, 
        appimage_path: str, 
        asset_digest: str, 
        appimage_name: str | None = None
    ) -> bool:
        """Verify AppImage using GitHub API asset digest.
        
        Args:
            appimage_path: Path to the AppImage file
            asset_digest: Asset digest in format "algorithm:hash"
            appimage_name: Name of the AppImage for logging (optional)
            
        Returns:
            True if verification passes, False otherwise
            
        Raises:
            ValueError: If digest format is invalid
            OSError: If file operations fail
        """
        if not asset_digest:
            raise ValueError("Asset digest not provided for verification")
        
        if not os.path.exists(appimage_path):
            raise OSError(f"AppImage file not found: {appimage_path}")
        
        # Parse digest format
        digest_type, digest_hash = self._parse_digest(asset_digest)
        
        # Verify digest type is supported
        if digest_type not in hashlib.algorithms_available:
            raise ValueError(f"Digest type {digest_type} not available in this system")
        
        # Calculate and compare hashes
        calculator = HashCalculator(digest_type)
        
        try:
            actual_hash = calculator.calculate_file_hash(appimage_path)
            expected_hash = digest_hash.lower()
            
            is_valid = calculator.compare_hashes(actual_hash, expected_hash)
            
            self._log_verification_result(
                is_valid, 
                appimage_name or os.path.basename(appimage_path),
                digest_type,
                actual_hash,
                expected_hash
            )
            
            return is_valid
            
        except Exception as e:
            logging.error(f"Error during digest verification: {e}")
            raise
    
    def _parse_digest(self, asset_digest: str) -> Tuple[str, str]:
        """Parse asset digest into algorithm and hash components.
        
        Args:
            asset_digest: Digest string in format "algorithm:hash"
            
        Returns:
            Tuple of (algorithm, hash)
            
        Raises:
            ValueError: If digest format is invalid
        """
        try:
            digest_type, digest_hash = asset_digest.split(":", 1)
            return digest_type.strip(), digest_hash.strip()
        except ValueError:
            raise ValueError(f"Invalid digest format: {asset_digest}. Expected 'algorithm:hash'")
    
    def _log_verification_result(
        self,
        is_valid: bool,
        appimage_name: str,
        digest_type: str,
        actual_hash: str,
        expected_hash: str
    ) -> None:
        """Log the verification result with appropriate status.
        
        Args:
            is_valid: Whether verification passed
            appimage_name: Name of the AppImage
            digest_type: Hash algorithm used
            actual_hash: Calculated hash
            expected_hash: Expected hash from digest
        """
        status_symbol = "✓" if is_valid else "✗"
        status_text = "passed" if is_valid else "failed"
        
        log_message = (
            f"{status_symbol} Asset digest verification {status_text} for {appimage_name}\n"
            f"Algorithm: {digest_type.upper()}\n"
            f"Expected: {expected_hash}\n"
            f"Actual:   {actual_hash}"
        )
        
        if is_valid:
            logging.info(log_message)
            print(f"{status_symbol} Digest verification passed for {appimage_name}")
        else:
            logging.error(log_message)
            print(f"{status_symbol} Digest verification failed for {appimage_name}")