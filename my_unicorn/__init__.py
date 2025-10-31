"""Top-level package for my-unicorn.

Author: 2023 - 2025 Cyber-Syntax
License: GPL-3.0
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("my-unicorn")
    # Handle None return in Python 3.13+ for uninstalled packages
    if __version__ is None:
        __version__ = "dev"
except PackageNotFoundError:
    # Fallback for development environments where package isn't installed
    __version__ = "dev"
