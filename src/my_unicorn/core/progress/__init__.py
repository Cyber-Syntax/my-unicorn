"""Progress module for my-unicorn.

This module contains all progress bar, spinner,
and progress display logic for my-unicorn.
"""

from my_unicorn.core.progress.progress import (
    IDGenerator,
    LoggerSuppression,
    ProgressDisplay,
    SessionManager,
    TaskInfo,
    TaskRegistry,
    TaskState,
    create_api_fetching_task,
    create_installation_workflow,
    create_verification_task,
)
from my_unicorn.core.progress.progress_types import TaskConfig

__all__ = [
    "IDGenerator",
    "LoggerSuppression",
    "ProgressDisplay",
    "SessionManager",
    "TaskConfig",
    "TaskInfo",
    "TaskRegistry",
    "TaskState",
    "create_api_fetching_task",
    "create_installation_workflow",
    "create_verification_task",
]
