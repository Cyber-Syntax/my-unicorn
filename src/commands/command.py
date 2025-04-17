#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Command interface for the application.

This module defines the base Command interface that all command implementations must follow.
"""

from abc import ABC, abstractmethod


class Command(ABC):
    """Abstract base class for all commands in the application."""

    @abstractmethod
    def execute(self) -> None:
        """Execute the command's logic."""
        pass
