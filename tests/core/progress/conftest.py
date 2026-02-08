"""Fixtures for progress-related tests.

Provide shared pytest fixtures used across tests in ``tests/core/progress/``.
"""

import pytest

from my_unicorn.core.progress.progress import ProgressDisplay


@pytest.fixture
def progress_service() -> ProgressDisplay:
    """Provide a ProgressDisplay instance for tests in this package.

    The fixture intentionally does not start the session so tests can verify
    both active and inactive behaviors.
    """
    return ProgressDisplay()
