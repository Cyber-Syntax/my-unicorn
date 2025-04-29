#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI utilities.

This module provides functions for user interface interactions.
"""

import logging
from typing import List, Dict, Any, Optional, Callable

# Configure module logger
logger = logging.getLogger(__name__)


def select_from_list(
    items: List[Dict[str, Any]],
    prompt: str,
    display_key: str = "name",
    callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Prompt user to select an item from a list.

    Args:
        items: List of items to choose from
        prompt: Prompt message for the user
        display_key: Key to use for displaying items
        callback: Optional callback function to call with selected item

    Returns:
        dict: Selected item

    Raises:
        ValueError: If items list is empty
    """
    if not items:
        raise ValueError("No items to select from")

    for idx, item in enumerate(items, 1):
        print(f"{idx}. {item[display_key]}")

    while True:
        choice = input(f"{prompt} (1-{len(items)}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            selected = items[int(choice) - 1]
            if callback:
                callback(selected)
            return selected

        logger.warning("Invalid input, try again")
        print("Invalid input, try again")


def get_user_input(prompt: str, default: Optional[str] = None) -> str:
    """
    Get user input with optional default value.

    Args:
        prompt: Prompt message for the user
        default: Default value if user enters nothing

    Returns:
        str: User input or default value
    """
    if default:
        user_input = input(f"{prompt} (default: {default}): ").strip()
        return user_input if user_input else default

    return input(f"{prompt}: ").strip()


def confirm_action(prompt: str, default: bool = False) -> bool:
    """
    Ask user to confirm an action.

    Args:
        prompt: Prompt message for the user
        default: Default response if user enters nothing

    Returns:
        bool: True if user confirmed, False otherwise
    """
    default_prompt = "[Y/n]" if default else "[y/N]"
    response = input(f"{prompt} {default_prompt}: ").strip().lower()

    if not response:
        return default

    return response in ("y", "yes")
