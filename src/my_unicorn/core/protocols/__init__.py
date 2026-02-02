"""Core protocols for dependency injection and interface abstraction.

This package defines abstract interfaces (protocols) that allow domain
services to depend on abstractions rather than concrete UI implementations.
This follows the Dependency Inversion Principle (DIP) from SOLID.

Available protocols:
    ProgressReporter: Abstract interface for progress reporting

Usage:
    from my_unicorn.core.protocols import ProgressReporter, ProgressType

"""

from .progress import NullProgressReporter, ProgressReporter, ProgressType

__all__ = [
    "NullProgressReporter",
    "ProgressReporter",
    "ProgressType",
]
