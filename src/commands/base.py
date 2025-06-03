#!/usr/bin/env python3
"""Command interface for the application.

This module defines the base Command interface that all command implementations must follow.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self


class CommandError(Exception):
    """Base exception for command errors."""


class Command(ABC):
    """Abstract base class for commands with modern Python features."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def name(self) -> str:
        """Return command name."""
        return self.__class__.__name__.removesuffix("Command")

    @abstractmethod
    def execute(self) -> None:
        """Execute the command logic."""

    def can_execute(self) -> bool:
        """Check if command can be executed."""
        return True

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} command"