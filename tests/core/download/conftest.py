"""Pytest configuration and fixtures for download module tests.

Download-specific fixtures for testing the download service.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
def mock_session() -> MagicMock:
    """Provide a mock aiohttp.ClientSession for download tests.

    Returns:
        MagicMock configured for async context manager protocol.

    """
    return MagicMock()


@pytest.fixture
def patch_logger() -> Generator:
    """Patch get_logger to avoid real logging output.

    Yields:
        Mock logger instance for testing without actual logging.

    """
    with patch("my_unicorn.core.download.get_logger") as mock_logger:
        yield mock_logger
