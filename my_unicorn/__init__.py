"""Top-level package for my-unicorn.

Author: 2023 - 2025 Cyber-Syntax
License: GPL-3.0
"""

from importlib.metadata import PackageNotFoundError, metadata

try:
    __version__ = metadata("my-unicorn")["Version"]
except PackageNotFoundError:
    # Fallback for development environments where package isn't installed
    __version__ = "dev"