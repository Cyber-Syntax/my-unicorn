"""Shared services package for eliminating code duplication."""


# Use lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "ChecksumFileInfo":
        from my_unicorn.github_client import ChecksumFileInfo

        return ChecksumFileInfo
    elif name == "IconConfig":
        from .icon_service import IconConfig

        return IconConfig
    elif name == "IconResult":
        from .icon_service import IconResult

        return IconResult
    elif name == "IconService":
        from .icon_service import IconService

        return IconService
    elif name == "VerificationConfig":
        from .verification_service import VerificationConfig

        return VerificationConfig
    elif name == "VerificationResult":
        from .verification_service import VerificationResult

        return VerificationResult
    elif name == "VerificationService":
        from .verification_service import VerificationService

        return VerificationService
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "ChecksumFileInfo",
    "IconConfig",
    "IconResult",
    "IconService",
    "VerificationConfig",
    "VerificationResult",
    "VerificationService",
]
