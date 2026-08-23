"""Progress module for my-unicorn.

This module contains all progress bar, spinner,
and progress display logic for my-unicorn.
"""

from my_unicorn.core.progress.progress import (
    IDGenerator,
    LoggerSuppression,
    Phase,
    ProgressConfig,
    ProgressDisplay,
    SessionManager,
    TaskInfo,
    TaskRegistry,
    TaskState,
    create_api_fetching_task,
    create_installation_workflow,
)
from my_unicorn.core.progress.progress_types import ProcessingPhase, TaskConfig

__all__ = [
    "IDGenerator",
    "LoggerSuppression",
    "Phase",
    "ProcessingPhase",
    "ProgressConfig",
    "ProgressDisplay",
    "SessionManager",
    "TaskConfig",
    "TaskInfo",
    "TaskRegistry",
    "TaskState",
    "create_api_fetching_task",
    "create_installation_workflow",
]
