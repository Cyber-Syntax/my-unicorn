"""Core protocols for dependency injection and interface abstraction.

This package defines abstract interfaces (protocols) that allow domain
services to depend on abstractions rather than concrete UI implementations.
This follows the Dependency Inversion Principle (DIP) from SOLID.

Available protocols:
    ProgressReporter: Abstract interface for progress reporting

Available context managers:
    github_api_progress_task: Manage GitHub API progress task lifecycle
    operation_progress_session: Manage progress session for operations

Usage:
    from my_unicorn.core.protocols import ProgressReporter, ProgressType

"""

from .progress import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
    github_api_progress_task,
    operation_progress_session,
)

__all__ = [
    "NullProgressReporter",
    "ProgressReporter",
    "ProgressType",
    "github_api_progress_task",
    "operation_progress_session",
]
