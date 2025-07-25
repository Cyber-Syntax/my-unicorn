#!/usr/bin/env python3
"""UI utilities.

This module provides functions for user interface interactions.
"""

import asyncio
import concurrent.futures
import logging
import threading

# Configure module logger
logger = logging.getLogger(__name__)

# Global variable to store the main event loop
_main_event_loop: asyncio.AbstractEventLoop | None = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Set the main asyncio event loop for ui_utils to use."""
    global _main_event_loop
    _main_event_loop = loop
    logger.debug("Main event loop set in ui_utils: %s", _main_event_loop)


def _actual_input_logic(prompt_str: str, default_val: str | None) -> str:
    """The core input logic run in the main thread."""
    # This internal function encapsulates the original logic of get_user_input
    # It also needs to handle KeyboardInterrupt if it's the one directly calling input()
    try:
        if default_val:
            user_input = input(f"{prompt_str} (default: {default_val}): ").strip()
            return user_input if user_input else default_val
        return input(f"{prompt_str}: ").strip()
    except KeyboardInterrupt:
        # This will be caught by the main get_user_input if called directly,
        # or by the future.set_exception if called via call_soon_threadsafe.
        logger.info("User cancelled input (Ctrl+C) during actual input operation")
        print("\nInput cancelled.")  # Provide immediate feedback
        raise


def get_user_input(prompt: str, default: str | None = None) -> str:
    """Get user input with an optional default value.

    Handles being called from a worker thread by delegating to the main asyncio loop.
    """
    # Note: The prompt string itself is passed to _actual_input_logic,
    # which will then format it with the default value.
    # This is a slight change from the original where full_prompt was constructed here.
    # For simplicity, we'll let _actual_input_logic handle the full prompt string construction.
    # Or, we can construct full_prompt here and pass it. Let's do that for clarity.

    if threading.current_thread() is not threading.main_thread():
        target_loop = None
        if _main_event_loop and _main_event_loop.is_running():
            target_loop = _main_event_loop
            logger.debug("Using globally set main event loop for input.")
        else:
            try:
                target_loop = asyncio.get_running_loop()
                logger.debug("Using current thread's running event loop for input.")
            except RuntimeError as e:
                logger.warning(
                    f"Could not get running asyncio loop from worker thread: {e}. "
                    f"Globally set loop was: {_main_event_loop}. Falling back to direct input."
                )

                # Fallback to direct input if asyncio context is not available
                return _actual_input_logic(prompt, default)  # Pass original prompt and default

        if target_loop and target_loop.is_running():
            try:
                future = concurrent.futures.Future()

                def do_input_in_main_thread():
                    try:
                        # Pass the already formatted prompt string
                        result = _actual_input_logic(
                            prompt, default
                        )  # Pass original prompt and default
                        future.set_result(result)
                    except KeyboardInterrupt as e:
                        future.set_exception(e)
                    except Exception as e:
                        future.set_exception(e)

                target_loop.call_soon_threadsafe(do_input_in_main_thread)

                try:
                    return future.result()  # This will block the worker thread
                except KeyboardInterrupt:
                    # This KI is from future.result() if main thread raised it and set it on future
                    # The _actual_input_logic already prints "Input cancelled."
                    # We just need to re-raise it so the caller (e.g. SHAManager) can also stop.
                    raise
                except Exception as e:
                    logger.error("Error getting input via main thread: %s", e)
                    raise  # Re-raise to make it visible
            except Exception as e_outer:  # Catch other errors during loop interaction
                logger.error(
                    "Outer error interacting with event loop for input: %s. Falling back.",
                    e_outer,
                )
                # Fallback to direct input
                return _actual_input_logic(prompt, default)
        else:
            logger.warning(
                "No valid running event loop found for input delegation. Falling back to direct input."
            )
            # Fallback to direct input
            return _actual_input_logic(prompt, default)

    # Direct input if in main thread (initial check passed)
    return _actual_input_logic(prompt, default)  # Pass original prompt and default
