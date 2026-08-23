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
    from my_unicorn.core.protocols import ProgressReporter

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# TODO: are we need these here?
from my_unicorn.core.progress.progress_types import (
    TaskConfig,
    TaskInfo,
    TaskState,
)

from .progress import (
    NullProgressReporter,
    ProgressReporter,
    github_api_progress_task,
    operation_progress_session,
)

__all__ = [
    "IDGenerator",
    "LoggerSuppression",
    "NullProgressReporter",
    "ProgressDisplay",
    "ProgressReporter",
    "SessionManager",
    "TaskConfig",
    "TaskInfo",
    "TaskRegistry",
    "TaskState",
    "create_api_fetching_task",
    "create_installation_workflow",
    "github_api_progress_task",
    "operation_progress_session",
]

if TYPE_CHECKING:
    from my_unicorn.core.progress.progress import (
        IDGenerator,
        LoggerSuppression,
        ProgressDisplay,
        SessionManager,
        TaskRegistry,
        create_api_fetching_task,
        create_installation_workflow,
    )


def __getattr__(name: str) -> Any:
    if name in {
        "IDGenerator",
        "LoggerSuppression",
        "ProgressDisplay",
        "SessionManager",
        "TaskRegistry",
        "create_api_fetching_task",
        "create_installation_workflow",
        "create_verification_task",
    }:
        from my_unicorn.core.progress import progress as progress_module

        return getattr(progress_module, name)
    raise AttributeError(f"module {__name__} has no attribute {name!r}")
