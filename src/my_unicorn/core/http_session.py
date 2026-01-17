"""HTTP session utilities for my-unicorn.

This module provides utilities for creating configured HTTP sessions
with proper timeout and connection settings.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiohttp

from my_unicorn.types import GlobalConfig


@asynccontextmanager
async def create_http_session(
    global_config: GlobalConfig,
) -> AsyncIterator[aiohttp.ClientSession]:
    """Create configured HTTP session.

    Args:
        global_config: Global configuration dictionary

    Yields:
        Configured aiohttp.ClientSession

    """
    network_cfg = global_config.get("network", {})
    timeout_seconds = int(network_cfg.get("timeout_seconds", 10))
    max_concurrent = global_config.get("max_concurrent_downloads", 3)

    timeout = aiohttp.ClientTimeout(
        total=timeout_seconds * 60,
        sock_read=timeout_seconds * 3,
        sock_connect=timeout_seconds,
    )
    connector = aiohttp.TCPConnector(
        limit=10,
        limit_per_host=max_concurrent,
    )

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
    ) as session:
        yield session
