"""Deprecated catalog lookup utilities.

This module is deprecated. All verification functionality has been moved to
the verification module for proper separation of concerns.

Use src.verification.release_desc_verifier.ReleaseDescVerifier instead.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_repo_info_for_appimage(appimage_path: str | Path) -> dict[str, str]:
    """Get owner/repo information for an AppImage from app catalog.

    DEPRECATED: Use ReleaseDescVerifier.get_repo_info_for_appimage() instead.
    """
    logger.warning(
        "get_repo_info_for_appimage() is deprecated. "
        "Use ReleaseDescVerifier.get_repo_info_for_appimage() from src.verification.release_desc_verifier instead."
    )
    
    try:
        from src.verification.release_desc_verifier import ReleaseDescVerifier
        return ReleaseDescVerifier.get_repo_info_for_appimage(appimage_path)
    except ImportError as e:
        logger.error(f"Failed to import ReleaseDescVerifier: {e}")
        return {}


def extract_app_id_from_filename(filename: str | Path) -> str:
    """Extract app ID from AppImage filename.

    DEPRECATED: This is a simple utility function, use Path(filename).stem.split("-")[0].lower() directly.
    """
    logger.warning(
        "extract_app_id_from_filename() is deprecated. "
        "Use Path(filename).stem.split('-')[0].lower() directly."
    )
    return Path(filename).stem.split("-")[0].lower()


def validate_repo_info(repo_info: dict[str, str]) -> bool:
    """Validate that repository information contains required fields.

    DEPRECATED: Use ReleaseDescVerifier.validate_repo_info() instead.
    """
    logger.warning(
        "validate_repo_info() is deprecated. "
        "Use ReleaseDescVerifier.validate_repo_info() from src.verification.release_desc_verifier instead."
    )
    return bool(
        repo_info 
        and repo_info.get("owner") 
        and repo_info.get("repo")
    )


def format_repo_identifier(owner: str, repo: str) -> str:
    """Format owner and repo into a standard identifier.

    DEPRECATED: Use f"{owner}/{repo}" directly.
    """
    logger.warning(
        "format_repo_identifier() is deprecated. "
        "Use f'{owner}/{repo}' directly."
    )
    return f"{owner}/{repo}"


def verify_with_release_checksums(
    owner: str, repo: str, appimage_path: str | Path, cleanup_on_failure: bool = False
) -> bool:
    """Verify an AppImage using checksums from GitHub release description.

    DEPRECATED: Use ReleaseDescVerifier instead.
    """
    logger.warning(
        "verify_with_release_checksums() is deprecated. "
        "Use ReleaseDescVerifier from src.verification.release_desc_verifier instead."
    )
    
    try:
        from src.verification.release_desc_verifier import ReleaseDescVerifier
        verifier = ReleaseDescVerifier(owner=owner, repo=repo)
        return verifier.verify_appimage(appimage_path=appimage_path, cleanup_on_failure=cleanup_on_failure)
    except ImportError as e:
        logger.error(f"Failed to import ReleaseDescVerifier: {e}")
        return False


def handle_release_description_verification(
    appimage_path: str | Path,
    owner: str | None = None,
    repo: str | None = None,
    cleanup_on_failure: bool = False,
) -> bool:
    """Handle verification for apps that use release description for checksums.

    DEPRECATED: Use ReleaseDescVerifier.verify_appimage_standalone() instead.
    """
    logger.warning(
        "handle_release_description_verification() is deprecated. "
        "Use ReleaseDescVerifier.verify_appimage_standalone() from src.verification.release_desc_verifier instead."
    )
    
    try:
        from src.verification.release_desc_verifier import ReleaseDescVerifier
        return ReleaseDescVerifier.verify_appimage_standalone(
            appimage_path=appimage_path,
            owner=owner,
            repo=repo,
            cleanup_on_failure=cleanup_on_failure,
        )
    except ImportError as e:
        logger.error(f"Failed to import ReleaseDescVerifier: {e}")
        return False