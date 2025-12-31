"""Pytest configuration and fixtures for my-unicorn tests."""

import logging

import pytest


@pytest.fixture(autouse=True)
def enable_log_propagation():
    """Enable log propagation for all loggers during tests.

    This allows pytest's caplog fixture to capture logs from all loggers,
    even those created with propagate=False in production code.
    """
    # Get all existing loggers and enable propagation
    original_propagation = {}
    for name in list(logging.Logger.manager.loggerDict.keys()):
        if name.startswith("my_unicorn"):
            logger = logging.getLogger(name)
            original_propagation[name] = logger.propagate
            logger.propagate = True

    yield

    # Restore original propagation settings
    for name, propagate_value in original_propagation.items():
        logger = logging.getLogger(name)
        logger.propagate = propagate_value
